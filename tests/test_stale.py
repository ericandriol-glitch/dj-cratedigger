"""Tests for stale track detection."""

import os
import time
import wave
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner

from cratedigger.audit.stale import (
    StaleResult,
    StaleTrack,
    _compute_bpm_iqr,
    _compute_energy_iqr,
    _parse_rekordbox_play_counts,
    find_stale_tracks,
)
from cratedigger.audit.stale_report import _format_size, display_stale_report
from cratedigger.cli import cli
from cratedigger.core.analyzer import AudioFeatures
from cratedigger.utils.db import get_connection, store_results


def _make_wav(path: Path, freq: float = 440.0, duration: float = 1.0) -> Path:
    """Generate a minimal WAV file."""
    sr = 44100
    n_samples = int(sr * duration)
    t = np.linspace(0, duration, n_samples, dtype=np.float64)
    samples = (0.5 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return path


def _make_old_wav(path: Path, age_days: int = 400) -> Path:
    """Create a WAV and set its mtime to the past."""
    _make_wav(path)
    old_time = time.time() - (age_days * 24 * 3600)
    os.utime(str(path), (old_time, old_time))
    return path


def _make_rekordbox_xml(xml_path: Path, tracks: list[dict]) -> Path:
    """Create a minimal Rekordbox XML with play counts."""
    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
    product = ET.SubElement(root, "PRODUCT", Name="rekordbox", Version="6.0")
    collection = ET.SubElement(root, "COLLECTION", Entries=str(len(tracks)))
    for i, t in enumerate(tracks):
        ET.SubElement(collection, "TRACK", **{
            "TrackID": str(i + 1),
            "Name": t.get("name", f"Track {i}"),
            "Artist": t.get("artist", "Artist"),
            "Location": t.get("location", ""),
            "PlayCount": str(t.get("play_count", 0)),
        })
    tree = ET.ElementTree(root)
    tree.write(str(xml_path), xml_declaration=True, encoding="utf-8")
    return xml_path


class TestComputeIQR:
    """Test IQR computation helpers."""

    def test_bpm_iqr_normal(self):
        bpms = [120, 122, 124, 126, 128, 130, 132, 134]
        lo, hi = _compute_bpm_iqr(bpms)
        assert lo < 120
        assert hi > 134

    def test_bpm_iqr_small_list(self):
        bpms = [120, 130]
        lo, hi = _compute_bpm_iqr(bpms)
        assert lo == 120
        assert hi == 130

    def test_energy_iqr_normal(self):
        energies = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        lo, hi = _compute_energy_iqr(energies)
        assert lo <= 0.3
        assert hi >= 1.0

    def test_energy_iqr_small_list(self):
        energies = [0.5, 0.6]
        lo, hi = _compute_energy_iqr(energies)
        assert lo == 0.5
        assert hi == 0.6


class TestFindStaleTracks:
    """Test the main stale detection logic."""

    def test_empty_directory(self, tmp_path):
        result = find_stale_tracks(tmp_path)
        assert result.total_library == 0
        assert len(result.stale_tracks) == 0

    def test_dormant_tracks(self, tmp_path):
        """Old files should be flagged as dormant."""
        _make_old_wav(tmp_path / "old_track.wav", age_days=400)
        _make_wav(tmp_path / "new_track.wav")

        result = find_stale_tracks(tmp_path, since_months=12)
        assert result.total_library == 2
        dormant = [t for t in result.stale_tracks if t.reason == "dormant"]
        assert len(dormant) >= 1
        assert dormant[0].filepath.name == "old_track.wav"

    def test_all_fresh_tracks(self, tmp_path):
        """Recent files should not be flagged as dormant."""
        _make_wav(tmp_path / "track1.wav")
        _make_wav(tmp_path / "track2.wav")

        result = find_stale_tracks(tmp_path, since_months=12)
        dormant = [t for t in result.stale_tracks if t.reason == "dormant"]
        assert len(dormant) == 0

    def test_never_played_with_rekordbox(self, tmp_path):
        """Tracks with 0 play count in Rekordbox should be flagged."""
        wav1 = _make_wav(tmp_path / "played.wav")
        wav2 = _make_wav(tmp_path / "unplayed.wav")

        xml_path = tmp_path / "library.xml"
        _make_rekordbox_xml(xml_path, [
            {"name": "Played", "location": f"file://localhost{wav1}", "play_count": 5},
            {"name": "Unplayed", "location": f"file://localhost{wav2}", "play_count": 0},
        ])

        result = find_stale_tracks(tmp_path, rekordbox_xml=xml_path)
        never_played = [t for t in result.stale_tracks if t.reason == "never_played"]
        assert len(never_played) >= 1

    def test_outlier_bpm(self, tmp_path):
        """Tracks with extreme BPM should be flagged as outliers."""
        db_path = tmp_path / "test.db"
        # Create tracks
        wavs = []
        for i in range(10):
            wavs.append(_make_wav(tmp_path / f"track{i}.wav"))

        # Seed DB with normal BPMs except one outlier
        conn = get_connection(db_path)
        results = []
        for i, w in enumerate(wavs):
            bpm = 126.0 if i < 9 else 200.0  # last track is outlier
            features = AudioFeatures(bpm=bpm, energy=0.7)
            results.append((str(w), features))
        store_results(conn, results)
        conn.close()

        result = find_stale_tracks(tmp_path, db_path=db_path)
        outliers = [t for t in result.stale_tracks if t.reason == "outlier"]
        assert len(outliers) >= 1

    def test_total_size_bytes(self, tmp_path):
        """Stale result should track reclaimable size."""
        _make_old_wav(tmp_path / "old.wav", age_days=400)
        result = find_stale_tracks(tmp_path, since_months=12)
        assert result.total_size_bytes > 0

    def test_grouped_by_genre(self, tmp_path):
        """Stale tracks should be grouped by genre."""
        _make_old_wav(tmp_path / "old1.wav", age_days=400)
        _make_old_wav(tmp_path / "old2.wav", age_days=400)
        result = find_stale_tracks(tmp_path, since_months=12)
        # WAV files have no genre tag, so they group under "Unknown"
        assert "Unknown" in result.by_genre
        assert len(result.by_genre["Unknown"]) >= 2

    def test_since_months_threshold(self, tmp_path):
        """Custom threshold should affect dormant detection."""
        _make_old_wav(tmp_path / "old.wav", age_days=100)
        # 100 days > 3 months but < 12 months
        result_strict = find_stale_tracks(tmp_path, since_months=3)
        result_lenient = find_stale_tracks(tmp_path, since_months=12)
        strict_dormant = [t for t in result_strict.stale_tracks if t.reason == "dormant"]
        lenient_dormant = [t for t in result_lenient.stale_tracks if t.reason == "dormant"]
        assert len(strict_dormant) >= len(lenient_dormant)


class TestParseRekordboxPlayCounts:
    """Test Rekordbox XML play count parsing."""

    def test_parse_play_counts(self, tmp_path):
        xml_path = tmp_path / "test.xml"
        _make_rekordbox_xml(xml_path, [
            {"name": "Track A", "location": "file://localhost/music/a.mp3", "play_count": 10},
            {"name": "Track B", "location": "file://localhost/music/b.mp3", "play_count": 0},
        ])
        counts = _parse_rekordbox_play_counts(xml_path)
        assert "/music/a.mp3" in counts
        assert counts["/music/a.mp3"] == 10
        assert counts["/music/b.mp3"] == 0

    def test_missing_xml(self, tmp_path):
        counts = _parse_rekordbox_play_counts(tmp_path / "nope.xml")
        assert counts == {}


class TestStaleReport:
    """Test report formatting."""

    def test_format_size_bytes(self):
        assert _format_size(500) == "500 B"

    def test_format_size_mb(self):
        assert "MB" in _format_size(5 * 1024 * 1024)

    def test_format_size_gb(self):
        assert "GB" in _format_size(2 * 1024 ** 3)

    def test_display_empty_result(self, capsys):
        result = StaleResult(total_library=10)
        display_stale_report(result)
        # Should not crash

    def test_display_with_tracks(self, capsys):
        result = StaleResult(
            total_library=100,
            stale_tracks=[
                StaleTrack(Path("/a.mp3"), "Artist", "Title", "Tech House", "2024-01-01", "dormant"),
            ],
            by_genre={"Tech House": [
                StaleTrack(Path("/a.mp3"), "Artist", "Title", "Tech House", "2024-01-01", "dormant"),
            ]},
            total_size_bytes=1024 * 1024,
        )
        display_stale_report(result)
        # Should not crash


class TestStaleCLI:
    """Test the stale CLI command."""

    def test_stale_command_runs(self, tmp_path):
        _make_wav(tmp_path / "track.wav")

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = tmp_path / "test.db"
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["stale", str(tmp_path)])
            assert result.exit_code == 0, result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_stale_with_since_option(self, tmp_path):
        _make_old_wav(tmp_path / "old.wav", age_days=200)

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = tmp_path / "test.db"
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["stale", str(tmp_path), "--since", "3"])
            assert result.exit_code == 0, result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original
