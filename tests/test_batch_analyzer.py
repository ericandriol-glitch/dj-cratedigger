"""Tests for batch analyzer and SQLite storage."""

import wave
from pathlib import Path

import numpy as np

from cratedigger.core.analyzer import AudioFeatures
from cratedigger.core.batch_analyzer import BatchResult, batch_analyze
from cratedigger.utils.db import get_analyzed_paths, get_connection, store_results


def _make_wav(path: Path, freq: float = 440.0, duration: float = 5.0) -> Path:
    """Generate a WAV file with a sine wave."""
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


# --- DB tests ---


class TestDatabase:
    """Test SQLite operations."""

    def test_get_connection_creates_db(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        assert db_path.exists()
        conn.close()

    def test_schema_created(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='audio_analysis'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_store_and_retrieve(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)

        features = AudioFeatures(
            bpm=126.0,
            bpm_confidence=0.92,
            key="8A",
            key_confidence=0.85,
            energy=0.7,
            danceability=0.6,
        )
        store_results(conn, [("/path/to/track.mp3", features)])

        cursor = conn.execute("SELECT * FROM audio_analysis WHERE filepath = ?", ("/path/to/track.mp3",))
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == 126.0  # bpm
        assert row[3] == "8A"  # key_camelot
        conn.close()

    def test_get_analyzed_paths(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)

        features = AudioFeatures(bpm=120.0)
        store_results(conn, [
            ("/path/a.mp3", features),
            ("/path/b.mp3", features),
        ])

        paths = get_analyzed_paths(conn)
        assert paths == {"/path/a.mp3", "/path/b.mp3"}
        conn.close()

    def test_store_replaces_on_conflict(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)

        features_v1 = AudioFeatures(bpm=120.0)
        features_v2 = AudioFeatures(bpm=126.0)
        store_results(conn, [("/path/track.mp3", features_v1)])
        store_results(conn, [("/path/track.mp3", features_v2)])

        cursor = conn.execute("SELECT bpm FROM audio_analysis WHERE filepath = ?", ("/path/track.mp3",))
        assert cursor.fetchone()[0] == 126.0
        conn.close()


# --- Batch analyzer tests ---


class TestBatchAnalyze:
    """Test batch analysis pipeline."""

    def test_returns_batch_result(self, tmp_path: Path):
        wav = _make_wav(tmp_path / "track1.wav")
        db_path = tmp_path / "test.db"
        result = batch_analyze([wav], db_path=db_path)
        assert isinstance(result, BatchResult)

    def test_analyzes_files(self, tmp_path: Path):
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(3)]
        db_path = tmp_path / "test.db"
        result = batch_analyze(wavs, db_path=db_path)
        assert result.total == 3
        assert result.analyzed + result.failed == 3
        assert result.skipped == 0

    def test_skips_already_analyzed(self, tmp_path: Path):
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(3)]
        db_path = tmp_path / "test.db"

        # First run
        batch_analyze(wavs, db_path=db_path)

        # Second run should skip all
        result = batch_analyze(wavs, db_path=db_path)
        assert result.skipped == 3
        assert result.analyzed == 0

    def test_force_reanalyze(self, tmp_path: Path):
        wav = _make_wav(tmp_path / "track.wav")
        db_path = tmp_path / "test.db"

        batch_analyze([wav], db_path=db_path)
        result = batch_analyze([wav], db_path=db_path, force=True)
        assert result.skipped == 0
        assert result.analyzed + result.failed == 1

    def test_handles_corrupt_files(self, tmp_path: Path):
        good = _make_wav(tmp_path / "good.wav")
        bad = tmp_path / "bad.mp3"
        bad.write_bytes(b"not audio")
        db_path = tmp_path / "test.db"

        result = batch_analyze([good, bad], db_path=db_path)
        assert result.total == 2
        assert result.failed >= 1

    def test_results_stored_in_db(self, tmp_path: Path):
        wav = _make_wav(tmp_path / "track.wav")
        db_path = tmp_path / "test.db"
        batch_analyze([wav], db_path=db_path)

        conn = get_connection(db_path)
        paths = get_analyzed_paths(conn)
        assert str(wav) in paths
        conn.close()
