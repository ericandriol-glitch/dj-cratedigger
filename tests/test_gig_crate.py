"""Tests for gig crate builder."""

import json
import sqlite3
import tempfile
from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from cratedigger.gig.crate import (
    DEFAULT_ENERGY,
    CrateTrack,
    GigCrate,
    _classify_zone,
    _compute_stats,
    _smart_select,
    build_crate,
    export_crate,
    list_crates,
    load_crate,
    save_crate,
)
from cratedigger.gig.crate_report import (
    _format_duration,
    _genre_summary,
    print_crate_report,
)


# ── Fixtures ──────────────────────────────────────────────────────────


def _seed_db(db_path: Path, tracks: list[dict] | None = None) -> None:
    """Create a test database with audio_analysis data."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audio_analysis (
            filepath TEXT PRIMARY KEY,
            bpm REAL,
            bpm_confidence REAL,
            key_camelot TEXT,
            key_confidence REAL,
            energy REAL,
            danceability REAL,
            genre TEXT,
            analyzed_at TEXT,
            analyzer_version TEXT
        );
        CREATE TABLE IF NOT EXISTS gig_crates (
            name TEXT PRIMARY KEY,
            crate_json TEXT,
            created_at TEXT,
            updated_at TEXT
        );
    """)

    if tracks is None:
        tracks = _default_test_tracks()

    for t in tracks:
        conn.execute(
            """INSERT OR REPLACE INTO audio_analysis
               (filepath, bpm, key_camelot, energy, genre, analyzed_at, analyzer_version)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                t["filepath"],
                t["bpm"],
                t["key_camelot"],
                t.get("energy"),
                t.get("genre"),
                t.get("analyzed_at", "2026-03-15T00:00:00"),
                "test",
            ),
        )
    conn.commit()
    conn.close()


def _default_test_tracks() -> list[dict]:
    """Generate 30 test tracks spanning different BPMs, keys, energies, genres."""
    keys = [
        "1A", "2A", "3A", "4A", "5A", "6A", "7A", "8A", "9A", "10A", "11A", "12A",
        "1B", "2B", "3B", "4B", "5B", "6B", "7B", "8B", "9B", "10B", "11B", "12B",
    ]
    genres = ["deep-house", "tech-house", "melodic-techno", "afro-house"]
    tracks = []
    for i in range(30):
        energy = 0.2 + (i / 30) * 0.8  # 0.2 to ~1.0
        tracks.append({
            "filepath": f"/music/Artist {i % 5} - Track {i:03d}.mp3",
            "bpm": 118 + i * 0.5,
            "key_camelot": keys[i % len(keys)],
            "energy": round(energy, 2),
            "genre": genres[i % len(genres)],
            "analyzed_at": f"2026-03-{15 - (i % 3):02d}T00:00:00",
        })
    return tracks


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary test database."""
    db_path = tmp_path / "test.db"
    _seed_db(db_path)
    return db_path


@pytest.fixture
def empty_db(tmp_path: Path) -> Path:
    """Create an empty test database."""
    db_path = tmp_path / "empty.db"
    _seed_db(db_path, tracks=[])
    return db_path


def _make_crate_track(
    filepath: str = "/music/Artist - Track.mp3",
    artist: str = "Artist",
    title: str = "Track",
    bpm: float = 126.0,
    key_camelot: str = "8A",
    energy: float = 0.7,
    genre: str = "deep-house",
    energy_zone: str = "build",
    has_cues: bool = False,
    duration_seconds: float = 360.0,
) -> CrateTrack:
    return CrateTrack(
        filepath=filepath, artist=artist, title=title, bpm=bpm,
        key_camelot=key_camelot, energy=energy, genre=genre,
        energy_zone=energy_zone, has_cues=has_cues,
        duration_seconds=duration_seconds,
    )


# ── TestCrateBuild ────────────────────────────────────────────────────


class TestCrateBuild:
    """Tests for crate building with filters."""

    def test_build_basic(self, test_db: Path):
        """Build a crate with no filters."""
        crate = build_crate("Test Gig", db_path=test_db)
        assert crate.name == "Test Gig"
        assert len(crate.tracks) == 30  # All tracks, since 30 < default 80

    def test_build_with_size(self, test_db: Path):
        """Target size limits the crate."""
        crate = build_crate("Small Gig", size=10, db_path=test_db)
        assert len(crate.tracks) == 10

    def test_build_genre_filter(self, test_db: Path):
        """Vibe filter limits to matching genres."""
        crate = build_crate("Deep Set", vibe=["deep-house"], db_path=test_db)
        for t in crate.tracks:
            assert "deep-house" in (t.genre or "").lower()

    def test_build_genre_filter_case_insensitive(self, test_db: Path):
        """Genre filter is case-insensitive."""
        crate = build_crate("Deep Set", vibe=["DEEP-HOUSE"], db_path=test_db)
        assert len(crate.tracks) > 0
        for t in crate.tracks:
            assert "deep-house" in (t.genre or "").lower()

    def test_build_bpm_range(self, test_db: Path):
        """BPM range limits tracks."""
        crate = build_crate("Tight BPM", bpm_range=(122, 128), db_path=test_db)
        for t in crate.tracks:
            assert 122 <= t.bpm <= 128

    def test_build_energy_range(self, test_db: Path):
        """Energy range limits tracks."""
        crate = build_crate("High Energy", energy_range=(0.7, 1.0), db_path=test_db)
        for t in crate.tracks:
            assert t.energy >= 0.7

    def test_build_empty_result(self, test_db: Path):
        """No tracks match impossible filters."""
        crate = build_crate("Empty", vibe=["nonexistent-genre"], db_path=test_db)
        assert len(crate.tracks) == 0

    def test_build_empty_db(self, empty_db: Path):
        """Empty database returns empty crate."""
        crate = build_crate("Empty", db_path=empty_db)
        assert len(crate.tracks) == 0

    def test_energy_zone_coverage(self, test_db: Path):
        """Smart selection ensures energy zone coverage."""
        crate = build_crate("Diverse", size=20, db_path=test_db)
        # With 30 tracks spanning 0.2-1.0, a 20-track crate should
        # have at least some tracks in most zones
        zones_with_tracks = [z for z, tracks in crate.energy_zones.items() if tracks]
        assert len(zones_with_tracks) >= 3

    def test_created_at_set(self, test_db: Path):
        """Crate has a created_at timestamp."""
        crate = build_crate("Timestamped", db_path=test_db)
        assert crate.created_at != ""

    def test_artist_title_from_filename(self, test_db: Path):
        """Artist and title are parsed from 'Artist - Title' filename."""
        crate = build_crate("Parse Test", db_path=test_db)
        # Our test tracks are named "Artist N - Track NNN.mp3"
        has_artist = any(t.artist != "" for t in crate.tracks)
        assert has_artist


# ── TestCrateStats ────────────────────────────────────────────────────


class TestCrateStats:
    """Tests for crate statistics computation."""

    def test_bpm_median(self):
        """BPM median is computed correctly."""
        tracks = [
            _make_crate_track(bpm=120),
            _make_crate_track(bpm=126),
            _make_crate_track(bpm=130),
        ]
        crate = GigCrate(name="Test", tracks=tracks)
        _compute_stats(crate)
        assert crate.bpm_median == 126.0

    def test_bpm_range(self):
        """BPM range captures min and max."""
        tracks = [
            _make_crate_track(bpm=118),
            _make_crate_track(bpm=132),
        ]
        crate = GigCrate(name="Test", tracks=tracks)
        _compute_stats(crate)
        assert crate.bpm_range == (118.0, 132.0)

    def test_genre_distribution(self):
        """Genre counts are accurate."""
        tracks = [
            _make_crate_track(genre="deep-house"),
            _make_crate_track(genre="deep-house"),
            _make_crate_track(genre="techno"),
        ]
        crate = GigCrate(name="Test", tracks=tracks)
        _compute_stats(crate)
        assert crate.genre_distribution["deep-house"] == 2
        assert crate.genre_distribution["techno"] == 1

    def test_key_coverage(self):
        """Key coverage counts distinct Camelot keys."""
        tracks = [
            _make_crate_track(key_camelot="8A"),
            _make_crate_track(key_camelot="8A"),
            _make_crate_track(key_camelot="9B"),
            _make_crate_track(key_camelot="3A"),
        ]
        crate = GigCrate(name="Test", tracks=tracks)
        _compute_stats(crate)
        assert crate.key_coverage == 3

    def test_duration_total(self):
        """Total duration sums all tracks."""
        tracks = [
            _make_crate_track(duration_seconds=300),
            _make_crate_track(duration_seconds=420),
        ]
        crate = GigCrate(name="Test", tracks=tracks)
        _compute_stats(crate)
        assert crate.total_duration_seconds == 720.0

    def test_cue_stats(self):
        """Cue presence is counted correctly."""
        tracks = [
            _make_crate_track(has_cues=True),
            _make_crate_track(has_cues=True),
            _make_crate_track(has_cues=False),
        ]
        crate = GigCrate(name="Test", tracks=tracks)
        _compute_stats(crate)
        assert crate.tracks_with_cues == 2
        assert crate.tracks_without_cues == 1

    def test_empty_crate_stats(self):
        """Empty crate stats don't crash."""
        crate = GigCrate(name="Empty")
        _compute_stats(crate)
        assert crate.bpm_median == 0.0
        assert crate.key_coverage == 0

    def test_energy_zones_populated(self):
        """Tracks are sorted into correct energy zones."""
        tracks = [
            _make_crate_track(energy=0.9, energy_zone="peak"),
            _make_crate_track(energy=0.7, energy_zone="build"),
            _make_crate_track(energy=0.5, energy_zone="groove"),
            _make_crate_track(energy=0.3, energy_zone="warmup"),
        ]
        crate = GigCrate(name="Test", tracks=tracks)
        _compute_stats(crate)
        assert len(crate.energy_zones["peak"]) == 1
        assert len(crate.energy_zones["build"]) == 1
        assert len(crate.energy_zones["groove"]) == 1
        assert len(crate.energy_zones["warmup"]) == 1


# ── TestClassifyZone ──────────────────────────────────────────────────


class TestClassifyZone:
    """Tests for energy zone classification."""

    def test_peak(self):
        assert _classify_zone(0.9) == "peak"
        assert _classify_zone(0.8) == "peak"
        assert _classify_zone(1.0) == "peak"

    def test_build(self):
        assert _classify_zone(0.7) == "build"
        assert _classify_zone(0.6) == "build"

    def test_groove(self):
        assert _classify_zone(0.5) == "groove"
        assert _classify_zone(0.4) == "groove"

    def test_warmup(self):
        assert _classify_zone(0.3) == "warmup"
        assert _classify_zone(0.2) == "warmup"
        assert _classify_zone(0.1) == "warmup"


# ── TestSmartSelect ───────────────────────────────────────────────────


class TestSmartSelect:
    """Tests for smart selection algorithm."""

    def test_returns_all_if_under_target(self):
        candidates = [{"filepath": f"/t{i}", "bpm": 126, "key_camelot": "8A",
                        "energy": 0.5, "genre": "house", "analyzed_at": ""} for i in range(5)]
        result = _smart_select(candidates, 10)
        assert len(result) == 5

    def test_limits_to_target_size(self):
        candidates = [{"filepath": f"/t{i}", "bpm": 120 + i, "key_camelot": f"{(i % 12) + 1}A",
                        "energy": 0.2 + (i / 50), "genre": "house",
                        "analyzed_at": ""} for i in range(50)]
        result = _smart_select(candidates, 20)
        assert len(result) == 20

    def test_ensures_zone_diversity(self):
        """Selection should include tracks from multiple energy zones."""
        candidates = []
        for i in range(40):
            energy = 0.2 + (i / 40) * 0.8
            candidates.append({
                "filepath": f"/t{i}", "bpm": 126, "key_camelot": "8A",
                "energy": round(energy, 2), "genre": "house", "analyzed_at": "",
            })
        result = _smart_select(candidates, 16)
        zones = {_classify_zone(t["energy"]) for t in result}
        assert len(zones) >= 3


# ── TestCrateSaveLoad ─────────────────────────────────────────────────


class TestCrateSaveLoad:
    """Tests for saving and loading crates."""

    def test_save_and_load(self, test_db: Path):
        """Save a crate and load it back."""
        crate = build_crate("Roundtrip", db_path=test_db)
        save_crate(crate, db_path=test_db)

        loaded = load_crate("Roundtrip", db_path=test_db)
        assert loaded is not None
        assert loaded.name == "Roundtrip"
        assert len(loaded.tracks) == len(crate.tracks)

    def test_load_nonexistent(self, test_db: Path):
        """Loading a missing crate returns None."""
        result = load_crate("Does Not Exist", db_path=test_db)
        assert result is None

    def test_save_overwrites(self, test_db: Path):
        """Saving again with same name overwrites."""
        crate1 = build_crate("Overwrite", size=5, db_path=test_db)
        save_crate(crate1, db_path=test_db)

        crate2 = build_crate("Overwrite", size=10, db_path=test_db)
        save_crate(crate2, db_path=test_db)

        loaded = load_crate("Overwrite", db_path=test_db)
        assert loaded is not None
        assert len(loaded.tracks) == len(crate2.tracks)

    def test_list_crates(self, test_db: Path):
        """List returns saved crates."""
        crate = build_crate("Listed", db_path=test_db)
        save_crate(crate, db_path=test_db)

        crates = list_crates(db_path=test_db)
        assert any(c["name"] == "Listed" for c in crates)

    def test_list_empty(self, empty_db: Path):
        """List returns empty when no crates saved."""
        crates = list_crates(db_path=empty_db)
        assert crates == []

    def test_loaded_stats_recomputed(self, test_db: Path):
        """Loaded crate has stats recomputed."""
        crate = build_crate("Stats", db_path=test_db)
        save_crate(crate, db_path=test_db)

        loaded = load_crate("Stats", db_path=test_db)
        assert loaded is not None
        assert loaded.bpm_median > 0
        assert loaded.key_coverage > 0


# ── TestCrateExport ───────────────────────────────────────────────────


class TestCrateExport:
    """Tests for Rekordbox XML export."""

    def test_export_creates_file(self, test_db: Path, tmp_path: Path):
        """Export produces an XML file."""
        crate = build_crate("Export Test", db_path=test_db)
        output = tmp_path / "export.xml"
        result = export_crate(crate, output)
        assert result.exists()
        assert result.suffix == ".xml"

    def test_export_contains_tracks(self, test_db: Path, tmp_path: Path):
        """Exported XML contains track entries."""
        crate = build_crate("Export Tracks", db_path=test_db)
        output = tmp_path / "export.xml"
        export_crate(crate, output)

        content = output.read_text(encoding="utf-8")
        assert "TRACK" in content
        assert "DJ_PLAYLISTS" in content

    def test_export_has_zone_playlists(self, test_db: Path, tmp_path: Path):
        """Exported XML has sub-playlists for energy zones."""
        crate = build_crate("Zone Playlists", db_path=test_db)
        output = tmp_path / "zone_export.xml"
        export_crate(crate, output)

        content = output.read_text(encoding="utf-8")
        # Should have at least some zone names
        has_zones = any(z in content for z in ["PEAK", "BUILD", "GROOVE", "WARM-UP"])
        assert has_zones

    def test_export_empty_crate(self, tmp_path: Path):
        """Exporting an empty crate still produces valid XML."""
        crate = GigCrate(name="Empty Export")
        output = tmp_path / "empty.xml"
        result = export_crate(crate, output)
        assert result.exists()


# ── TestCrateReport ───────────────────────────────────────────────────


class TestCrateReport:
    """Tests for crate report formatting."""

    def test_format_duration_hours(self):
        assert _format_duration(3600 + 1020) == "1h 17m"

    def test_format_duration_minutes_only(self):
        assert _format_duration(300) == "5m"

    def test_format_duration_zero(self):
        assert _format_duration(0) == "0m"

    def test_genre_summary(self):
        dist = {"deep-house": 10, "techno": 5, "afro-house": 3}
        result = _genre_summary(dist, 18)
        assert "deep-house" in result
        assert "%" in result

    def test_genre_summary_empty(self):
        assert _genre_summary({}, 0) == "none"

    def test_print_report_runs(self, test_db: Path):
        """Report prints without crashing."""
        crate = build_crate("Report Test", db_path=test_db)
        console = Console(file=StringIO())
        print_crate_report(crate, console)

    def test_print_report_empty_crate(self):
        """Report handles empty crate without crashing."""
        crate = GigCrate(name="Empty")
        _compute_stats(crate)
        console = Console(file=StringIO())
        print_crate_report(crate, console)

    def test_print_report_single_track(self):
        """Report works with a single track."""
        tracks = [_make_crate_track()]
        crate = GigCrate(name="Solo", tracks=tracks)
        _compute_stats(crate)
        console = Console(file=StringIO())
        print_crate_report(crate, console)
