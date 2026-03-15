"""Tests for enhanced DJ profile builder."""

import json
import wave
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner

from cratedigger.cli import cli
from cratedigger.core.analyzer import AudioFeatures
from cratedigger.profile.enhanced import (
    DJProfile,
    _compute_iqr,
    build_profile,
    generate_sound_summary,
    load_enhanced_profile,
    save_enhanced_profile,
)
from cratedigger.profile.report import display_enhanced_profile
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


def _seed_db(db_path: Path, filepaths: list[str]) -> None:
    """Insert fake analysis results for profile testing."""
    conn = get_connection(db_path)
    bpms = [122.0, 124.0, 126.0, 128.0, 130.0]
    keys = ["8A", "5A", "7A", "8A", "11B"]
    energies = [0.5, 0.6, 0.7, 0.8, 0.9]

    results = []
    for i, fp in enumerate(filepaths):
        features = AudioFeatures(
            bpm=bpms[i % len(bpms)],
            bpm_confidence=0.9,
            key=keys[i % len(keys)],
            key_confidence=0.85,
            energy=energies[i % len(energies)],
            danceability=0.6,
        )
        results.append((fp, features))

    store_results(conn, results)
    conn.close()


class TestComputeIQR:
    """Test IQR computation."""

    def test_normal_list(self):
        values = [100, 110, 120, 125, 126, 128, 130, 135, 140, 150]
        q1, q3 = _compute_iqr(values)
        assert q1 < q3
        assert 110 <= q1 <= 125
        assert 130 <= q3 <= 145

    def test_small_list(self):
        values = [120, 130]
        q1, q3 = _compute_iqr(values)
        assert q1 == 120
        assert q3 == 130

    def test_four_elements(self):
        values = [100, 120, 130, 150]
        q1, q3 = _compute_iqr(values)
        assert q1 == 120.0
        assert q3 == 150.0


class TestBuildProfile:
    """Test enhanced profile building."""

    def test_empty_directory(self, tmp_path):
        db_path = tmp_path / "test.db"
        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            profile = build_profile(db_path=db_path, library_path=tmp_path)
            assert profile.total_tracks == 0
            assert profile.genre_distribution == {}
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_builds_from_audio_files(self, tmp_path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(5)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            profile = build_profile(db_path=db_path, library_path=tmp_path)
            assert profile.total_tracks == 5
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_bpm_range_and_sweet_spot(self, tmp_path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(8)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            profile = build_profile(db_path=db_path, library_path=tmp_path)
            assert profile.bpm_range[0] <= profile.bpm_range[1]
            assert profile.bpm_sweet_spot[0] <= profile.bpm_sweet_spot[1]
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_key_preferences(self, tmp_path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(5)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            profile = build_profile(db_path=db_path, library_path=tmp_path)
            assert len(profile.key_preferences) > 0
            assert "8A" in profile.key_preferences  # most common key
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_energy_range(self, tmp_path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(5)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            profile = build_profile(db_path=db_path, library_path=tmp_path)
            assert profile.energy_range[0] <= profile.energy_range[1]
            assert profile.energy_range[0] >= 0.0
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_tracks_added_recently(self, tmp_path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(3)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            profile = build_profile(db_path=db_path, library_path=tmp_path)
            # All tracks are just created, so all are recent
            assert profile.tracks_added_last_3_months == 3
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_oldest_track_date(self, tmp_path):
        db_path = tmp_path / "test.db"
        _make_wav(tmp_path / "track.wav")
        _seed_db(db_path, [str(tmp_path / "track.wav")])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            profile = build_profile(db_path=db_path, library_path=tmp_path)
            assert profile.oldest_track_date is not None
        finally:
            db_mod.DEFAULT_DB_PATH = original


class TestGenerateSoundSummary:
    """Test template-based sound summary generation."""

    def test_minimal_profile(self):
        profile = DJProfile()
        summary = generate_sound_summary(profile)
        assert "Eclectic DJ" in summary

    def test_with_genres(self):
        profile = DJProfile(
            genre_distribution={"Tech House": 40.0, "Deep House": 30.0},
        )
        summary = generate_sound_summary(profile)
        assert "Tech House" in summary
        assert "Deep House" in summary

    def test_with_bpm_sweet_spot(self):
        profile = DJProfile(
            genre_distribution={"Techno": 50.0},
            bpm_sweet_spot=(126.0, 132.0),
        )
        summary = generate_sound_summary(profile)
        assert "126" in summary
        assert "132" in summary

    def test_with_key_preferences(self):
        profile = DJProfile(
            genre_distribution={"House": 50.0},
            key_preferences=["8A", "5A", "7A"],
        )
        summary = generate_sound_summary(profile)
        assert "minor key bias" in summary

    def test_with_major_key_bias(self):
        profile = DJProfile(
            genre_distribution={"House": 50.0},
            key_preferences=["8B", "5B", "7B"],
        )
        summary = generate_sound_summary(profile)
        assert "major key bias" in summary

    def test_with_top_artists(self):
        profile = DJProfile(
            genre_distribution={"Techno": 50.0},
            top_artists=[("Adam Beyer", 10), ("Charlotte de Witte", 8)],
        )
        summary = generate_sound_summary(profile)
        assert "Adam Beyer" in summary

    def test_with_spotify_divergence(self):
        profile = DJProfile(
            genre_distribution={"House": 50.0},
            spotify_divergence=[{"genre": "Drum and Bass"}, {"genre": "Jungle"}],
        )
        summary = generate_sound_summary(profile)
        assert "Drum and Bass" in summary


class TestSaveLoadEnhancedProfile:
    """Test profile persistence."""

    def test_save_and_load(self, tmp_path):
        db_path = tmp_path / "test.db"
        profile = DJProfile(
            total_tracks=200,
            genre_distribution={"Tech House": 45.0, "Deep House": 30.0},
            bpm_range=(120.0, 135.0),
            bpm_sweet_spot=(124.0, 130.0),
            key_preferences=["8A", "5B", "7A"],
            energy_range=(0.4, 0.9),
            top_artists=[("Fisher", 15), ("CamelPhat", 10)],
            top_labels=[("Toolroom", 8)],
            sound_summary="Tech House DJ with a BPM sweet spot of 124-130.",
        )
        save_enhanced_profile(profile, db_path=db_path)
        loaded = load_enhanced_profile(db_path=db_path)

        assert loaded is not None
        assert loaded.total_tracks == 200
        assert loaded.bpm_range == (120.0, 135.0)
        assert loaded.bpm_sweet_spot == (124.0, 130.0)
        assert loaded.key_preferences == ["8A", "5B", "7A"]
        assert loaded.top_artists[0] == ("Fisher", 15)
        assert "Tech House" in loaded.genre_distribution

    def test_load_empty_db(self, tmp_path):
        db_path = tmp_path / "test.db"
        get_connection(db_path).close()
        loaded = load_enhanced_profile(db_path=db_path)
        assert loaded is None


class TestEnhancedProfileReport:
    """Test rich report rendering."""

    def test_display_empty_profile(self, capsys):
        profile = DJProfile()
        display_enhanced_profile(profile)
        # Should not crash

    def test_display_full_profile(self, capsys):
        profile = DJProfile(
            total_tracks=200,
            genre_distribution={"Tech House": 45.0, "Deep House": 30.0, "Techno": 15.0},
            bpm_range=(120.0, 135.0),
            bpm_sweet_spot=(124.0, 130.0),
            key_preferences=["8A", "5B", "7A", "11B", "3A"],
            energy_range=(0.4, 0.9),
            top_artists=[("Fisher", 15), ("CamelPhat", 10)],
            top_labels=[("Toolroom", 8)],
            spotify_divergence=[{"genre": "Drum and Bass"}],
            tracks_added_last_3_months=25,
            oldest_track_date="2020-06-15",
            sound_summary="Tech House and Deep House DJ.",
        )
        display_enhanced_profile(profile)
        # Should not crash


class TestEnhancedProfileCLI:
    """Test CLI commands for enhanced profile."""

    def test_profile_show_no_profile(self, tmp_path):
        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = tmp_path / "test.db"
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["profile-show"])
            assert result.exit_code == 0
            assert "No enhanced profile found" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_profile_build_command(self, tmp_path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(3)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["profile-build", str(tmp_path)])
            assert result.exit_code == 0, result.output
            assert "Enhanced profile saved" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_profile_build_refresh(self, tmp_path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(3)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            runner = CliRunner()
            # Build first
            runner.invoke(cli, ["profile-build", str(tmp_path)])
            # Build again without refresh — should show existing
            result = runner.invoke(cli, ["profile-build", str(tmp_path)])
            assert result.exit_code == 0
            assert "Profile exists" in result.output
            # Build with refresh
            result = runner.invoke(cli, ["profile-build", str(tmp_path), "--refresh"])
            assert result.exit_code == 0
            assert "Enhanced profile saved" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_profile_show_after_build(self, tmp_path):
        db_path = tmp_path / "test.db"
        wavs = [_make_wav(tmp_path / f"track{i}.wav") for i in range(3)]
        _seed_db(db_path, [str(w) for w in wavs])

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            runner = CliRunner()
            runner.invoke(cli, ["profile-build", str(tmp_path)])
            result = runner.invoke(cli, ["profile-show"])
            assert result.exit_code == 0
            assert "Enhanced DJ Profile" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original
