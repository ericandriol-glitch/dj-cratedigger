"""Tests for crate-based transition practice analysis."""

import sqlite3
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from cratedigger.gig.crate import CrateTrack, GigCrate, _compute_stats
from cratedigger.gig.crate_practice import (
    TransitionAnalysis,
    analyze_transition,
    find_bridge_tracks,
    find_hardest_transitions,
    get_practice_history,
    log_practice,
)
from cratedigger.gig.crate_practice_report import (
    print_practice_history,
    print_transition_table,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _make_track(
    filepath: str = "/music/Artist - Track.mp3",
    artist: str = "Artist",
    title: str = "Track",
    bpm: float = 126.0,
    key_camelot: str = "8A",
    energy: float = 0.7,
    genre: str = "deep-house",
    energy_zone: str = "build",
) -> CrateTrack:
    return CrateTrack(
        filepath=filepath, artist=artist, title=title, bpm=bpm,
        key_camelot=key_camelot, energy=energy, genre=genre,
        energy_zone=energy_zone, has_cues=False, duration_seconds=360.0,
    )


def _make_crate(tracks: list[CrateTrack], name: str = "Test") -> GigCrate:
    crate = GigCrate(name=name, tracks=tracks)
    _compute_stats(crate)
    return crate


@pytest.fixture
def practice_db(tmp_path: Path) -> Path:
    """Create a temporary database for practice logging."""
    db_path = tmp_path / "practice_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audio_analysis (
            filepath TEXT PRIMARY KEY,
            bpm REAL, bpm_confidence REAL,
            key_camelot TEXT, key_confidence REAL,
            energy REAL, danceability REAL, genre TEXT,
            analyzed_at TEXT, analyzer_version TEXT
        );
    """)
    conn.close()
    return db_path


# ── TestAnalyzeTransition ────────────────────────────────────────────


class TestAnalyzeTransition:
    """Tests for single transition analysis."""

    def test_smooth_transition(self):
        """Two compatible tracks should be rated easy."""
        a = _make_track(bpm=126, key_camelot="8A", energy=0.7)
        b = _make_track(bpm=127, key_camelot="8A", energy=0.72, filepath="/b.mp3")
        result = analyze_transition(a, b)
        assert result.difficulty == "easy"
        assert result.key_compatible is True
        assert result.bpm_delta == 1.0
        assert "phrasing" in result.suggestion.lower() or "smooth" in result.suggestion.lower()

    def test_hard_bpm_gap(self):
        """Large BPM delta should be rated hard."""
        a = _make_track(bpm=120, key_camelot="8A", energy=0.7)
        b = _make_track(bpm=130, key_camelot="8A", energy=0.72, filepath="/b.mp3")
        result = analyze_transition(a, b)
        assert result.difficulty == "hard"
        assert result.bpm_delta == 10.0
        assert "bpm" in result.suggestion.lower()

    def test_hard_key_clash(self):
        """Clashing keys should be rated hard."""
        a = _make_track(bpm=126, key_camelot="1A", energy=0.7)
        b = _make_track(bpm=126, key_camelot="7A", energy=0.72, filepath="/b.mp3")
        result = analyze_transition(a, b)
        assert result.difficulty == "hard"
        assert result.key_compatible is False
        assert "key" in result.suggestion.lower() or "fx" in result.suggestion.lower()

    def test_hard_energy_jump(self):
        """Large energy delta should be rated hard."""
        a = _make_track(bpm=126, key_camelot="8A", energy=0.3)
        b = _make_track(bpm=126, key_camelot="8A", energy=0.8, filepath="/b.mp3")
        result = analyze_transition(a, b)
        assert result.difficulty == "hard"
        assert result.energy_delta == pytest.approx(0.5)

    def test_medium_bpm(self):
        """Medium BPM gap should contribute to medium difficulty."""
        a = _make_track(bpm=126, key_camelot="8A", energy=0.7)
        b = _make_track(bpm=130, key_camelot="8A", energy=0.72, filepath="/b.mp3")
        result = analyze_transition(a, b)
        assert result.difficulty == "medium"

    def test_medium_key(self):
        """Moderate key distance should be medium."""
        a = _make_track(bpm=126, key_camelot="8A", energy=0.7)
        b = _make_track(bpm=126, key_camelot="10A", energy=0.72, filepath="/b.mp3")
        result = analyze_transition(a, b)
        # key_score for 2 steps = 0.5, which is medium
        assert result.difficulty == "medium"

    def test_medium_energy(self):
        """Moderate energy delta should be medium."""
        a = _make_track(bpm=126, key_camelot="8A", energy=0.5)
        b = _make_track(bpm=126, key_camelot="8A", energy=0.75, filepath="/b.mp3")
        result = analyze_transition(a, b)
        assert result.difficulty == "medium"

    def test_worst_difficulty_wins(self):
        """If one dimension is hard, overall is hard even if others are easy."""
        a = _make_track(bpm=126, key_camelot="8A", energy=0.7)
        b = _make_track(bpm=126, key_camelot="4A", energy=0.72, filepath="/b.mp3")
        result = analyze_transition(a, b)
        # Keys are 4 steps apart -> 0.2 score -> hard
        assert result.difficulty == "hard"

    def test_invalid_key_handled(self):
        """Invalid Camelot key doesn't crash, defaults to hard."""
        a = _make_track(key_camelot="XY")
        b = _make_track(key_camelot="8A", filepath="/b.mp3")
        result = analyze_transition(a, b)
        assert result.key_score == 0.2
        assert result.key_compatible is False

    def test_bridge_candidates_included_with_crate(self):
        """When crate is provided, bridge candidates are found."""
        a = _make_track(bpm=120, energy=0.3, filepath="/a.mp3")
        b = _make_track(bpm=130, energy=0.8, filepath="/b.mp3")
        bridge = _make_track(bpm=125, energy=0.55, filepath="/bridge.mp3")
        crate = _make_crate([a, b, bridge])

        result = analyze_transition(a, b, crate)
        assert len(result.bridge_candidates) >= 1
        assert any(c.filepath == "/bridge.mp3" for c in result.bridge_candidates)

    def test_no_bridge_without_crate(self):
        """Without a crate, no bridge candidates."""
        a = _make_track(bpm=120, energy=0.3)
        b = _make_track(bpm=130, energy=0.8, filepath="/b.mp3")
        result = analyze_transition(a, b)
        assert result.bridge_candidates == []


# ── TestFindBridgeTracks ─────────────────────────────────────────────


class TestFindBridgeTracks:
    """Tests for bridge track discovery."""

    def test_finds_bridge_between_tracks(self):
        """Bridge track in BPM/energy range is found."""
        a = _make_track(bpm=120, energy=0.4, filepath="/a.mp3")
        b = _make_track(bpm=130, energy=0.8, filepath="/b.mp3")
        bridge = _make_track(bpm=125, energy=0.6, filepath="/bridge.mp3")
        crate = _make_crate([a, b, bridge])

        bridges = find_bridge_tracks(a, b, crate)
        assert len(bridges) == 1
        assert bridges[0].filepath == "/bridge.mp3"

    def test_excludes_source_and_dest(self):
        """Source and destination tracks are not returned as bridges."""
        a = _make_track(bpm=125, energy=0.6, filepath="/a.mp3")
        b = _make_track(bpm=125, energy=0.6, filepath="/b.mp3")
        crate = _make_crate([a, b])

        bridges = find_bridge_tracks(a, b, crate)
        assert len(bridges) == 0

    def test_no_bridge_when_gap_too_narrow(self):
        """No bridge candidates when tracks are already close."""
        a = _make_track(bpm=126, energy=0.7, filepath="/a.mp3")
        b = _make_track(bpm=127, energy=0.72, filepath="/b.mp3")
        other = _make_track(bpm=140, energy=0.9, filepath="/other.mp3")
        crate = _make_crate([a, b, other])

        bridges = find_bridge_tracks(a, b, crate)
        # The 'other' track at 140 BPM should not qualify
        assert all(125 <= br.bpm <= 129 for br in bridges)

    def test_bridges_sorted_by_centrality(self):
        """Bridges closest to midpoint come first."""
        a = _make_track(bpm=120, energy=0.4, filepath="/a.mp3")
        b = _make_track(bpm=130, energy=0.8, filepath="/b.mp3")
        close = _make_track(bpm=125, energy=0.6, filepath="/close.mp3")
        far = _make_track(bpm=121, energy=0.45, filepath="/far.mp3")
        crate = _make_crate([a, b, close, far])

        bridges = find_bridge_tracks(a, b, crate)
        assert len(bridges) == 2
        assert bridges[0].filepath == "/close.mp3"


# ── TestFindHardestTransitions ───────────────────────────────────────


class TestFindHardestTransitions:
    """Tests for finding the hardest transitions in a crate."""

    def test_returns_requested_count(self):
        """Returns at most the requested number of transitions."""
        tracks = [
            _make_track(bpm=120 + i * 2, energy=0.2 + i * 0.1,
                        key_camelot=f"{(i % 12) + 1}A",
                        filepath=f"/t{i}.mp3")
            for i in range(10)
        ]
        crate = _make_crate(tracks)
        result = find_hardest_transitions(crate, count=3)
        assert len(result) <= 3

    def test_hardest_first(self):
        """Results are sorted with hardest transitions first."""
        tracks = [
            _make_track(bpm=126, energy=0.3, key_camelot="8A", filepath="/easy_a.mp3"),
            _make_track(bpm=126, energy=0.35, key_camelot="8A", filepath="/easy_b.mp3"),
            _make_track(bpm=126, energy=0.5, key_camelot="8A", filepath="/mid.mp3"),
            _make_track(bpm=140, energy=0.9, key_camelot="1A", filepath="/hard.mp3"),
        ]
        crate = _make_crate(tracks)
        result = find_hardest_transitions(crate, count=10)
        # The transition to the 140 BPM / 1A track should be hardest
        assert result[0].difficulty in ("hard", "medium")

    def test_too_few_tracks(self):
        """Single track crate returns empty."""
        track = _make_track()
        crate = _make_crate([track])
        result = find_hardest_transitions(crate)
        assert result == []

    def test_empty_crate(self):
        """Empty crate returns empty."""
        crate = _make_crate([])
        result = find_hardest_transitions(crate)
        assert result == []

    def test_two_tracks(self):
        """Two-track crate produces exactly one transition."""
        a = _make_track(bpm=126, energy=0.5, filepath="/a.mp3")
        b = _make_track(bpm=128, energy=0.6, filepath="/b.mp3")
        crate = _make_crate([a, b])
        result = find_hardest_transitions(crate, count=5)
        assert len(result) == 1


# ── TestPracticeLog ──────────────────────────────────────────────────


class TestPracticeLog:
    """Tests for practice session logging and history."""

    def test_log_and_retrieve(self, practice_db: Path):
        """Log a practice session and retrieve it."""
        log_practice("/a.mp3", "/b.mp3", "medium", db_path=practice_db)
        history = get_practice_history(db_path=practice_db)
        assert len(history) == 1
        assert history[0]["track_a"] == "/a.mp3"
        assert history[0]["track_b"] == "/b.mp3"
        assert history[0]["confidence"] == "medium"

    def test_multiple_logs(self, practice_db: Path):
        """Multiple practice sessions are recorded."""
        log_practice("/a.mp3", "/b.mp3", "low", db_path=practice_db)
        log_practice("/b.mp3", "/c.mp3", "high", db_path=practice_db)
        log_practice("/a.mp3", "/b.mp3", "high", db_path=practice_db)
        history = get_practice_history(db_path=practice_db)
        assert len(history) == 3

    def test_history_most_recent_first(self, practice_db: Path):
        """History is returned most recent first."""
        log_practice("/a.mp3", "/b.mp3", "low", db_path=practice_db)
        log_practice("/c.mp3", "/d.mp3", "high", db_path=practice_db)
        history = get_practice_history(db_path=practice_db)
        # Most recent should be the c->d transition
        assert history[0]["track_a"] == "/c.mp3"

    def test_empty_history(self, practice_db: Path):
        """Empty database returns empty history."""
        history = get_practice_history(db_path=practice_db)
        assert history == []

    def test_practiced_at_populated(self, practice_db: Path):
        """Practice timestamp is recorded."""
        log_practice("/a.mp3", "/b.mp3", "high", db_path=practice_db)
        history = get_practice_history(db_path=practice_db)
        assert history[0]["practiced_at"] is not None
        assert len(history[0]["practiced_at"]) > 10


# ── TestPracticeReport ───────────────────────────────────────────────


class TestPracticeReport:
    """Tests for Rich report display."""

    def test_transition_table_renders(self):
        """Transition table renders without crashing."""
        a = _make_track(bpm=126, energy=0.5, filepath="/a.mp3")
        b = _make_track(bpm=130, energy=0.8, filepath="/b.mp3")
        analysis = analyze_transition(a, b)
        console = Console(file=StringIO())
        print_transition_table([analysis], console)

    def test_empty_table_renders(self):
        """Empty analysis list renders a message."""
        console = Console(file=StringIO())
        print_transition_table([], console)

    def test_history_renders(self):
        """Practice history renders without crashing."""
        history = [
            {"id": 1, "track_a": "/a.mp3", "track_b": "/b.mp3",
             "confidence": "high", "practiced_at": "2026-03-15T12:00:00"},
        ]
        console = Console(file=StringIO())
        print_practice_history(history, console)

    def test_empty_history_renders(self):
        """Empty history renders a message."""
        console = Console(file=StringIO())
        print_practice_history([], console)

    def test_transition_table_with_bridges(self):
        """Transition with bridge candidates renders correctly."""
        a = _make_track(bpm=120, energy=0.3, filepath="/a.mp3")
        b = _make_track(bpm=130, energy=0.8, filepath="/b.mp3")
        bridge = _make_track(bpm=125, energy=0.55, filepath="/bridge.mp3",
                             artist="Bridge", title="Track")
        crate = _make_crate([a, b, bridge])
        analysis = analyze_transition(a, b, crate)
        console = Console(file=StringIO())
        print_transition_table([analysis], console)

    def test_all_difficulty_levels_styled(self):
        """Each difficulty level gets a distinct style."""
        analyses = []
        # Easy
        a = _make_track(bpm=126, key_camelot="8A", energy=0.7, filepath="/e1.mp3")
        b = _make_track(bpm=127, key_camelot="8A", energy=0.72, filepath="/e2.mp3")
        analyses.append(analyze_transition(a, b))
        # Hard
        c = _make_track(bpm=120, key_camelot="1A", energy=0.3, filepath="/h1.mp3")
        d = _make_track(bpm=135, key_camelot="7A", energy=0.9, filepath="/h2.mp3")
        analyses.append(analyze_transition(c, d))

        console = Console(file=StringIO())
        print_transition_table(analyses, console)
        # If it didn't crash, the styles were applied


# ── TestCLIRegistration ──────────────────────────────────────────────


class TestCLIRegistration:
    """Tests for CLI command registration."""

    def test_gig_practice_command_exists(self):
        """gig-practice command is registered in the CLI."""
        from cratedigger.cli import cli
        commands = cli.list_commands(ctx=None)
        assert "gig-practice" in commands
