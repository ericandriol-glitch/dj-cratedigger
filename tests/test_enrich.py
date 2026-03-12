"""Tests for Essentia enrichment write-back."""

import wave
from pathlib import Path

import numpy as np
from click.testing import CliRunner

from cratedigger.cli import cli
from cratedigger.core.analyzer import AudioFeatures
from cratedigger.core.enrich import EnrichAction, apply_enrichment, plan_enrichment
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


def _seed_db(db_path: Path, filepath: str, bpm: float = 126.0, key: str = "8A") -> None:
    """Insert a fake analysis result into the DB."""
    conn = get_connection(db_path)
    features = AudioFeatures(
        bpm=bpm,
        bpm_confidence=0.92,
        key=key,
        key_confidence=0.87,
        energy=0.7,
        danceability=0.6,
    )
    store_results(conn, [(filepath, features)])
    conn.close()


class TestPlanEnrichment:
    """Test enrichment planning."""

    def test_plans_bpm_and_key_for_untagged_file(self, tmp_path: Path):
        wav = _make_wav(tmp_path / "track.wav")
        db_path = tmp_path / "test.db"
        _seed_db(db_path, str(wav))

        actions = plan_enrichment([wav], db_path=db_path)
        fields = {a.field for a in actions}
        # WAV files may not support tags, but plan should still propose
        assert "bpm" in fields or "key" in fields

    def test_no_actions_without_analysis(self, tmp_path: Path):
        wav = _make_wav(tmp_path / "track.wav")
        db_path = tmp_path / "test.db"
        get_connection(db_path).close()  # create empty DB

        actions = plan_enrichment([wav], db_path=db_path)
        assert len(actions) == 0

    def test_force_overwrites_existing(self, tmp_path: Path):
        wav = _make_wav(tmp_path / "track.wav")
        db_path = tmp_path / "test.db"
        _seed_db(db_path, str(wav))

        # First plan without force — should get actions (WAV has no tags)
        actions_normal = plan_enrichment([wav], db_path=db_path)

        # With force — should also get actions
        actions_force = plan_enrichment([wav], db_path=db_path, force=True)
        assert len(actions_force) >= len(actions_normal)


class TestApplyEnrichment:
    """Test enrichment application with backups."""

    def test_creates_backup(self, tmp_path: Path):
        wav = _make_wav(tmp_path / "track.wav")
        backup_dir = tmp_path / "_backups"

        actions = [
            EnrichAction(
                file_path=wav,
                field="bpm",
                old_value=None,
                new_value="126",
                confidence=0.92,
            )
        ]

        # This may fail on WAV (no tag support) but backup should still be created
        apply_enrichment(actions, backup_dir=backup_dir)
        assert backup_dir.exists()
        assert len(list(backup_dir.iterdir())) == 1

    def test_backup_no_overwrite(self, tmp_path: Path):
        wav = _make_wav(tmp_path / "track.wav")
        backup_dir = tmp_path / "_backups"
        backup_dir.mkdir()
        # Pre-existing backup
        (backup_dir / "track.wav").write_bytes(b"old backup")

        actions = [
            EnrichAction(
                file_path=wav,
                field="bpm",
                old_value=None,
                new_value="126",
                confidence=0.92,
            )
        ]

        apply_enrichment(actions, backup_dir=backup_dir)
        # Should have original backup + new numbered backup
        backups = list(backup_dir.iterdir())
        assert len(backups) == 2


class TestEnrichCLI:
    """Test enrich-essentia CLI command."""

    def test_dry_run_default(self, tmp_path: Path):
        wav = _make_wav(tmp_path / "track.wav")
        db_path = tmp_path / "test.db"
        _seed_db(db_path, str(wav))

        import cratedigger.utils.db as db_mod
        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path

        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["enrich-essentia", str(tmp_path)])
            assert result.exit_code == 0, result.output
            assert "Dry run" in result.output or "No enrichment needed" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_no_audio_files(self, tmp_path: Path):
        (tmp_path / "readme.txt").write_text("not audio")
        runner = CliRunner()
        result = runner.invoke(cli, ["enrich-essentia", str(tmp_path)])
        assert result.exit_code == 0
        assert "No audio files found" in result.output
