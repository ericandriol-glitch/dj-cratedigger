"""Tests for the Essentia-based audio analyzer."""

import wave
from pathlib import Path

import numpy as np

from cratedigger.core.analyzer import (
    AudioFeatures,
    _to_camelot,
    analyze_track,
)

# --- Camelot conversion tests ---


class TestCamelotConversion:
    """Test key-to-Camelot notation conversion."""

    def test_c_major(self):
        assert _to_camelot("C", "major") == "8B"

    def test_a_minor(self):
        assert _to_camelot("A", "minor") == "8A"

    def test_f_sharp_minor(self):
        assert _to_camelot("F#", "minor") == "11A"

    def test_db_normalized_to_c_sharp(self):
        """Essentia may return Db instead of C#."""
        assert _to_camelot("Db", "major") == "3B"

    def test_gb_normalized_to_f_sharp(self):
        """Essentia may return Gb instead of F#."""
        assert _to_camelot("Gb", "minor") == "11A"

    def test_all_major_keys_covered(self):
        """Every major key maps to a *B Camelot code."""
        major_keys = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
        for key in major_keys:
            result = _to_camelot(key, "major")
            assert result is not None, f"Missing Camelot mapping for {key} major"
            assert result.endswith("B"), f"{key} major should map to *B, got {result}"

    def test_all_minor_keys_covered(self):
        """Every minor key maps to a *A Camelot code."""
        minor_keys = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
        for key in minor_keys:
            result = _to_camelot(key, "minor")
            assert result is not None, f"Missing Camelot mapping for {key} minor"
            assert result.endswith("A"), f"{key} minor should map to *A, got {result}"

    def test_unknown_key_returns_none(self):
        assert _to_camelot("X", "major") is None


# --- Helper to create test audio files ---


def _make_wav(path: Path, freq: float = 440.0, duration: float = 5.0, sr: int = 44100) -> Path:
    """Generate a WAV file with a sine wave."""
    n_samples = int(sr * duration)
    t = np.linspace(0, duration, n_samples, dtype=np.float64)
    samples = (0.5 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())

    return path


# --- Analyzer integration tests ---


class TestAnalyzeTrack:
    """Test the full analyze_track pipeline."""

    def test_returns_audio_features(self, tmp_path: Path):
        """analyze_track returns an AudioFeatures dataclass."""
        wav = _make_wav(tmp_path / "test.wav")
        result = analyze_track(wav)
        assert isinstance(result, AudioFeatures)

    def test_bpm_is_float_or_none(self, tmp_path: Path):
        """BPM should be a float or None."""
        wav = _make_wav(tmp_path / "test.wav")
        result = analyze_track(wav)
        assert result.bpm is None or isinstance(result.bpm, float)

    def test_key_is_camelot_format(self, tmp_path: Path):
        """Key should be in Camelot notation (e.g., '8A', '11B') or None."""
        wav = _make_wav(tmp_path / "test.wav", duration=10.0)
        result = analyze_track(wav)
        if result.key is not None:
            # Camelot format: 1-12 followed by A or B
            num = result.key[:-1]
            letter = result.key[-1]
            assert letter in ("A", "B"), f"Key {result.key} should end with A or B"
            assert 1 <= int(num) <= 12, f"Key {result.key} number should be 1-12"

    def test_bpm_confidence_range(self, tmp_path: Path):
        """BPM confidence should be 0.0-1.0."""
        wav = _make_wav(tmp_path / "test.wav")
        result = analyze_track(wav)
        assert 0.0 <= result.bpm_confidence <= 1.0

    def test_key_confidence_range(self, tmp_path: Path):
        """Key confidence should be 0.0-1.0."""
        wav = _make_wav(tmp_path / "test.wav")
        result = analyze_track(wav)
        assert 0.0 <= result.key_confidence <= 1.0

    def test_energy_range(self, tmp_path: Path):
        """Energy should be 0.0-1.0 or None."""
        wav = _make_wav(tmp_path / "test.wav")
        result = analyze_track(wav)
        if result.energy is not None:
            assert 0.0 <= result.energy <= 1.0

    def test_danceability_range(self, tmp_path: Path):
        """Danceability should be 0.0-1.0 or None."""
        wav = _make_wav(tmp_path / "test.wav")
        result = analyze_track(wav)
        if result.danceability is not None:
            assert 0.0 <= result.danceability <= 1.0

    def test_nonexistent_file_returns_empty_features(self):
        """Missing file should return AudioFeatures with all None fields."""
        result = analyze_track(Path("/nonexistent/track.mp3"))
        assert result.bpm is None
        assert result.key is None
        assert result.energy is None
        assert result.danceability is None

    def test_short_audio_returns_empty_features(self, tmp_path: Path):
        """Audio shorter than 2 seconds should return empty features."""
        wav = _make_wav(tmp_path / "short.wav", duration=1.0)
        result = analyze_track(wav)
        assert result.bpm is None
        assert result.key is None

    def test_corrupt_file_returns_empty_features(self, tmp_path: Path):
        """Corrupt file should not crash, returns empty features."""
        bad_file = tmp_path / "corrupt.mp3"
        bad_file.write_bytes(b"this is not audio data at all")
        result = analyze_track(bad_file)
        assert result.bpm is None
        assert result.key is None
