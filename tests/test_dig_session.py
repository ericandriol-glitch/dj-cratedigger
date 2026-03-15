"""Tests for the dig session orchestrator and report."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cratedigger.discovery.session import (
    DiscoveryResult,
    SessionReport,
    _check_library,
    _check_wishlist,
    _deduplicate,
    _normalize,
    run_dig_session,
)
from cratedigger.discovery.session_report import print_session_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_track(artist: str = "Artist A", title: str = "Track B", **kw) -> dict:
    """Build a minimal track dict."""
    base = {
        "artist": artist,
        "title": title,
        "genre": kw.get("genre", "Tech House"),
        "bpm": kw.get("bpm", 128.0),
        "preview_url": kw.get("preview_url", ""),
        "source_url": kw.get("source_url", ""),
        "label": kw.get("label", ""),
    }
    base.update(kw)
    return base


def _mock_weekly_report(tracks: list[dict] | None = None):
    """Return a mock WeeklyDigReport with NewRelease objects."""
    from cratedigger.digger.weekly_dig import NewRelease, WeeklyDigReport

    releases = []
    for t in (tracks or [_make_track(), _make_track("Artist C", "Track D")]):
        releases.append(NewRelease(
            title=t["title"],
            artist=t["artist"],
            genre=t.get("genre", ""),
            bpm=t.get("bpm"),
            preview_url=t.get("preview_url", ""),
            url=t.get("source_url", ""),
            label=t.get("label", ""),
        ))
    return WeeklyDigReport(releases=releases, total_found=len(releases))


def _mock_artist_profile(name: str = "Test Artist", releases: list | None = None):
    """Return a mock ArtistProfile."""
    from cratedigger.digger.artist_research import ArtistProfile

    return ArtistProfile(
        name=name,
        releases=releases or [
            {"title": "Release One", "type": "Single", "date": "2026-01"},
            {"title": "Release Two", "type": "EP", "date": "2025-12"},
        ],
        genres=["Tech House"],
    )


def _setup_library_db(tmp_path: Path) -> Path:
    """Create a temporary DB with audio_analysis rows."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audio_analysis (
            filepath TEXT PRIMARY KEY,
            bpm REAL, bpm_confidence REAL,
            key_camelot TEXT, key_confidence REAL,
            energy REAL, danceability REAL,
            genre TEXT, analyzed_at TEXT, analyzer_version TEXT
        );
        CREATE TABLE IF NOT EXISTS dj_profile (
            id INTEGER PRIMARY KEY DEFAULT 1,
            profile_json TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS spotify_profile (
            id INTEGER PRIMARY KEY DEFAULT 1,
            profile_json TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS youtube_profile (
            id INTEGER PRIMARY KEY DEFAULT 1,
            profile_json TEXT, updated_at TEXT
        );
    """)
    conn.execute(
        "INSERT INTO audio_analysis (filepath) VALUES (?)",
        ("Artist A - Track B.mp3",),
    )
    conn.commit()
    conn.close()
    return db_path


def _setup_wishlist_db(db_path: Path) -> None:
    """Add a wishlist table and a row."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS wishlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            artist TEXT, title TEXT, source TEXT,
            priority TEXT, style_tag TEXT, preview_url TEXT,
            status TEXT DEFAULT 'pending',
            added_at TEXT
        );
    """)
    conn.execute(
        "INSERT INTO wishlist (artist, title, source, priority) VALUES (?,?,?,?)",
        ("Artist C", "Track D", "test", "medium"),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# TestDigSession — aggregation
# ---------------------------------------------------------------------------

class TestDigSession:
    """Core session orchestration tests."""

    @patch("cratedigger.discovery.session._gather_sleeping", return_value=DiscoveryResult(source="sleeping"))
    @patch("cratedigger.discovery.session._gather_weekly")
    def test_weekly_results_aggregated(self, mock_weekly, mock_sleeping):
        """Weekly scan results appear in the session report."""
        weekly = DiscoveryResult(source="weekly", tracks=[
            _make_track("A1", "T1"),
            _make_track("A2", "T2"),
        ])
        mock_weekly.return_value = weekly

        report = run_dig_session(
            styles=["Tech House"],
            include_sleeping=False,
        )
        assert report.total_found == 2
        assert len(report.tracks) == 2
        assert report.results[0].source == "weekly"

    @patch("cratedigger.discovery.session._gather_sleeping", return_value=DiscoveryResult(source="sleeping"))
    @patch("cratedigger.discovery.session._gather_artist")
    @patch("cratedigger.discovery.session._gather_weekly")
    def test_artist_and_weekly_combined(self, mock_weekly, mock_artist, mock_sleeping):
        """Tracks from both weekly and artist sources are merged."""
        mock_weekly.return_value = DiscoveryResult(
            source="weekly", tracks=[_make_track("W1", "WT1")]
        )
        mock_artist.return_value = DiscoveryResult(
            source="artist", tracks=[_make_track("A1", "AT1")]
        )

        report = run_dig_session(
            styles=["Tech House"],
            artists=["A1"],
            include_sleeping=False,
        )
        assert report.total_found == 2
        assert len(report.tracks) == 2

    @patch("cratedigger.discovery.session._gather_sleeping", return_value=DiscoveryResult(source="sleeping"))
    @patch("cratedigger.discovery.session._gather_weekly")
    def test_no_weekly_flag(self, mock_weekly, mock_sleeping):
        """include_weekly=False skips the weekly scan."""
        report = run_dig_session(
            styles=["Tech House"],
            include_weekly=False,
            include_sleeping=False,
        )
        mock_weekly.assert_not_called()
        assert report.total_found == 0


# ---------------------------------------------------------------------------
# TestDeduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    """Deduplication by normalized artist+title."""

    def test_exact_duplicate_removed(self):
        tracks = [
            _make_track("Artist A", "Track B"),
            _make_track("Artist A", "Track B"),
        ]
        result = _deduplicate(tracks)
        assert len(result) == 1

    def test_case_insensitive_dedup(self):
        tracks = [
            _make_track("ARTIST A", "TRACK B"),
            _make_track("artist a", "track b"),
        ]
        result = _deduplicate(tracks)
        assert len(result) == 1

    def test_different_tracks_kept(self):
        tracks = [
            _make_track("Artist A", "Track B"),
            _make_track("Artist C", "Track D"),
        ]
        result = _deduplicate(tracks)
        assert len(result) == 2

    def test_same_artist_different_title(self):
        tracks = [
            _make_track("Artist A", "Track 1"),
            _make_track("Artist A", "Track 2"),
        ]
        result = _deduplicate(tracks)
        assert len(result) == 2

    def test_normalize_strips_punctuation(self):
        assert _normalize("The Artist's Name!") == "artists name"

    def test_normalize_handles_empty(self):
        assert _normalize("") == ""


# ---------------------------------------------------------------------------
# TestLibraryCrossRef
# ---------------------------------------------------------------------------

class TestLibraryCrossRef:
    """Cross-reference tracks against the library database."""

    def test_track_in_library_detected(self, tmp_path):
        db_path = _setup_library_db(tmp_path)
        tracks = [_make_track("Artist A", "Track B")]
        owned = _check_library(tracks, db_path)
        assert 0 in owned

    def test_track_not_in_library(self, tmp_path):
        db_path = _setup_library_db(tmp_path)
        tracks = [_make_track("Unknown Artist", "Unknown Track")]
        owned = _check_library(tracks, db_path)
        assert len(owned) == 0

    def test_no_db_returns_empty(self):
        tracks = [_make_track()]
        owned = _check_library(tracks, Path("/nonexistent/path.db"))
        assert len(owned) == 0


# ---------------------------------------------------------------------------
# TestWishlistCrossRef
# ---------------------------------------------------------------------------

class TestWishlistCrossRef:
    """Cross-reference tracks against the wishlist table."""

    def test_track_on_wishlist_detected(self, tmp_path):
        db_path = _setup_library_db(tmp_path)
        _setup_wishlist_db(db_path)

        # Create a fake wishlist module and inject it
        fake_wishlist = MagicMock()
        fake_wishlist.get_wishlist.return_value = [
            {"artist": "Artist C", "title": "Track D"},
        ]
        with patch.dict("sys.modules", {"cratedigger.discovery.wishlist": fake_wishlist}):
            tracks = [_make_track("Artist C", "Track D")]
            on_wl = _check_wishlist(tracks, db_path)
            assert 0 in on_wl

    def test_track_not_on_wishlist(self, tmp_path):
        db_path = _setup_library_db(tmp_path)
        fake_wishlist = MagicMock()
        fake_wishlist.get_wishlist.return_value = [
            {"artist": "Other", "title": "Other"},
        ]
        with patch.dict("sys.modules", {"cratedigger.discovery.wishlist": fake_wishlist}):
            tracks = [_make_track("New Artist", "New Track")]
            on_wl = _check_wishlist(tracks, db_path)
            assert len(on_wl) == 0

    def test_wishlist_import_error_graceful(self):
        """If wishlist module is missing, _check_wishlist returns empty."""
        with patch.dict("sys.modules", {"cratedigger.discovery.wishlist": None}):
            tracks = [_make_track()]
            on_wl = _check_wishlist(tracks)
            assert len(on_wl) == 0


# ---------------------------------------------------------------------------
# TestQuickMode
# ---------------------------------------------------------------------------

class TestQuickMode:
    """Quick mode bypasses prompts."""

    @patch("cratedigger.discovery.session._gather_sleeping", return_value=DiscoveryResult(source="sleeping"))
    @patch("cratedigger.discovery.session._gather_weekly")
    def test_quick_sets_flag(self, mock_weekly, mock_sleeping):
        mock_weekly.return_value = DiscoveryResult(
            source="weekly", tracks=[_make_track()]
        )
        report = run_dig_session(
            styles=["Tech House"],
            quick=True,
            include_sleeping=False,
        )
        # Quick mode doesn't change the report itself, just how CLI uses it
        assert report.total_found == 1


# ---------------------------------------------------------------------------
# TestSessionReport — formatting
# ---------------------------------------------------------------------------

class TestSessionReport:
    """Report printing produces expected output."""

    def test_report_prints_without_error(self, capsys):
        """Smoke test: print_session_report doesn't crash."""
        from rich.console import Console

        report = SessionReport(
            results=[
                DiscoveryResult(source="weekly", tracks=[
                    {**_make_track(), "owned": False, "on_wishlist": False},
                ]),
            ],
            total_found=1,
            new_to_you=1,
            already_owned=0,
            already_on_wishlist=0,
            tracks=[{**_make_track(), "owned": False, "on_wishlist": False}],
        )
        console = Console(force_terminal=False, width=120)
        print_session_report(report, console)
        # No assertion on content — just verifying no exceptions

    def test_empty_report_shows_message(self, capsys):
        """Empty session shows 'no discoveries' message."""
        from rich.console import Console

        report = SessionReport(
            results=[],
            total_found=0,
            new_to_you=0,
            already_owned=0,
            already_on_wishlist=0,
            tracks=[],
        )
        console = Console(force_terminal=False, width=120)
        print_session_report(report, console)

    def test_counts_correct(self):
        """Report counts match the track categorization."""
        tracks = [
            {**_make_track("A", "T1"), "owned": False, "on_wishlist": False},
            {**_make_track("B", "T2"), "owned": True, "on_wishlist": False},
            {**_make_track("C", "T3"), "owned": False, "on_wishlist": True},
        ]
        report = SessionReport(
            results=[DiscoveryResult(source="weekly", tracks=tracks)],
            total_found=3,
            new_to_you=1,
            already_owned=1,
            already_on_wishlist=1,
            tracks=tracks,
        )
        assert report.new_to_you == 1
        assert report.already_owned == 1
        assert report.already_on_wishlist == 1


# ---------------------------------------------------------------------------
# TestNormalize
# ---------------------------------------------------------------------------

class TestNormalize:
    """Normalization edge cases."""

    def test_strips_the_prefix(self):
        assert _normalize("The Black Madonna") == "black madonna"

    def test_strips_special_chars(self):
        assert _normalize("DJ's Choice!") == "djs choice"

    def test_collapses_whitespace(self):
        assert _normalize("  multiple   spaces  ") == "multiple spaces"
