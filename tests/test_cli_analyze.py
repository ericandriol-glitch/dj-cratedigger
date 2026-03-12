"""Tests for Essentia CLI integration."""

import wave
from pathlib import Path

import numpy as np
from click.testing import CliRunner

from cratedigger.cli import cli


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


class TestScanEssentiaCommand:
    """Test the scan-essentia CLI command."""

    def test_scan_essentia_runs(self, tmp_path: Path):
        _make_wav(tmp_path / "track.wav")
        db_path = tmp_path / "test.db"

        # Patch default DB path for test isolation
        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["scan-essentia", str(tmp_path)])
            assert result.exit_code == 0, result.output
            assert "Done!" in result.output or "already analyzed" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_scan_essentia_no_audio(self, tmp_path: Path):
        (tmp_path / "readme.txt").write_text("not audio")
        runner = CliRunner()
        result = runner.invoke(cli, ["scan-essentia", str(tmp_path)])
        assert result.exit_code == 0
        assert "No audio files found" in result.output

    def test_scan_with_analyze_flag(self, tmp_path: Path):
        _make_wav(tmp_path / "track.wav")
        db_path = tmp_path / "test.db"

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["scan", str(tmp_path), "--analyze"])
            assert result.exit_code == 0, result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original
