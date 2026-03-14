"""Tests for DJ profile builder."""

import wave
from pathlib import Path

import numpy as np
from click.testing import CliRunner

from cratedigger.cli import cli
from cratedigger.core.analyzer import AudioFeatures
from cratedigger.digger.profile import (
    DJProfile,
    build_profile,
    load_profile,
    save_profile,
)
from cratedigger.utils.db import get_connection, store_results


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


def _seed_db(db_path: Path, filepaths: list[str]) -> None:
    """Insert fake analysis results for profile testing."""
    conn = get_connection(db_path)
    bpms = [122.0, 126.0, 128.0, 124.0, 130.0]
    keys = ["8A", "5B", "7A", "8A", "11B"]
    energies = [0.6, 0.7, 0.8, 0.65, 0.75]

    results = []
    for i, fp in enumerate(filepaths):
        features = AudioFeatures(
            bpm=bpms[i % len(bpms)],
            bpm_confidence=0.9,
            key=keys[i % len(keys)],
            key_confidence=0.85,
            energy=energies[i % len(energies)],
            danceability=0.6 + (i * 0.05),
        )
        results.append((fp, features))

    store_results(conn, results)
    conn.close()


class TestBuildProfile:
    """Test profile building from library data."""

    def test_empty_directory(self, tmp_path: Path):
        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = tmp_path / "test.db"
        try:
            prof = build_profile(tmp_path)
            assert prof.total_tracks == 0
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_builds_from_audio_files(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(5)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            prof = build_profile(tmp_path, db_path=db_path)
            assert prof.total_tracks == 5
            assert prof.analyzed_tracks == 5
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_bpm_range(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(5)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            prof = build_profile(tmp_path, db_path=db_path)
            assert prof.bpm_range["min"] == 122.0
            assert prof.bpm_range["max"] == 130.0
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_key_distribution(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(5)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            prof = build_profile(tmp_path, db_path=db_path)
            assert "8A" in prof.key_distribution
            assert prof.key_distribution["8A"] > 0
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_top_artists_empty_for_wavs(self, tmp_path: Path):
        """WAV files have no artist tags, so top_artists should be empty."""
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(3)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            prof = build_profile(tmp_path, db_path=db_path)
            assert len(prof.top_artists) == 0
        finally:
            db_mod.DEFAULT_DB_PATH = original


class TestSaveLoadProfile:
    """Test profile persistence."""

    def test_save_and_load(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        prof = DJProfile(
            total_tracks=100,
            analyzed_tracks=90,
            bpm_range={"min": 120, "max": 132, "median": 126},
            genres={"Tech House": 0.3, "Deep House": 0.2},
        )
        save_profile(prof, db_path=db_path)
        loaded = load_profile(db_path=db_path)

        assert loaded is not None
        assert loaded.total_tracks == 100
        assert loaded.bpm_range["median"] == 126
        assert "Tech House" in loaded.genres

    def test_load_empty_db(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        get_connection(db_path).close()
        loaded = load_profile(db_path=db_path)
        assert loaded is None


class TestProfileCLI:
    """Test profile CLI commands."""

    def test_profile_show_no_profile(self):
        import cratedigger.utils.db as db_mod
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            original = db_mod.DEFAULT_DB_PATH
            db_mod.DEFAULT_DB_PATH = Path(td) / "test.db"
            try:
                runner = CliRunner()
                result = runner.invoke(cli, ["profile", "show"])
                assert result.exit_code == 0
                assert "No profile found" in result.output
            finally:
                db_mod.DEFAULT_DB_PATH = original

    def test_profile_build(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(3)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["profile", "build", str(tmp_path)])
            assert result.exit_code == 0, result.output
            assert "Profile saved" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original
