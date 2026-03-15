"""Tests for USB/folder pre-flight validation (cratedigger preflight)."""

import struct
import wave
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from cratedigger.cli import cli
from cratedigger.preflight.checks import (
    PreflightResult,
    _check_duplicate_filenames,
    _check_missing_metadata,
    _compute_stats,
    run_preflight,
)
from cratedigger.preflight.report import (
    _format_duration,
    _format_size,
    _top_genres,
    print_preflight_report,
)
from cratedigger.models import TrackMetadata


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav(path: Path, duration_seconds: float = 1.0) -> Path:
    """Create a minimal valid WAV file.

    Args:
        path: Output file path.
        duration_seconds: Duration of silence to generate.

    Returns:
        The path written.
    """
    sample_rate = 8000
    n_samples = int(sample_rate * duration_seconds)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_samples}h", *([0] * n_samples)))
    return path


def _make_zero_byte(path: Path) -> Path:
    """Create an empty (zero-byte) file."""
    path.write_bytes(b"")
    return path


def _make_corrupt(path: Path) -> Path:
    """Create a file with garbage bytes that is not readable audio."""
    path.write_bytes(b"NOT_AUDIO_DATA_AT_ALL_GARBAGE_BYTES_1234567890")
    return path


def _build_fixture_folder(tmp_path: Path) -> Path:
    """Build a test folder with a mix of good, corrupt, and zero-byte files.

    Layout:
        root/
            good1.wav          (valid, duration ~1s)
            good2.wav          (valid, duration ~1s)
            subfolder/
                good1.wav      (duplicate filename)
                corrupt.wav    (garbage bytes)
                empty.wav      (zero-byte)
    """
    root = tmp_path / "usb"
    root.mkdir()
    sub = root / "subfolder"
    sub.mkdir()

    _make_wav(root / "good1.wav")
    _make_wav(root / "good2.wav")
    _make_wav(sub / "good1.wav")  # duplicate filename
    _make_corrupt(sub / "corrupt.wav")
    _make_zero_byte(sub / "empty.wav")

    return root


# ---------------------------------------------------------------------------
# TestPreflightChecks
# ---------------------------------------------------------------------------

class TestPreflightChecks:
    """Test individual check functions."""

    def test_zero_byte_detected(self, tmp_path: Path) -> None:
        root = tmp_path / "usb"
        root.mkdir()
        _make_zero_byte(root / "empty.wav")

        result = run_preflight(root)
        assert len(result.zero_byte_files) == 1
        assert result.zero_byte_files[0].name == "empty.wav"

    def test_corrupt_detected(self, tmp_path: Path) -> None:
        root = tmp_path / "usb"
        root.mkdir()
        _make_corrupt(root / "bad.wav")

        result = run_preflight(root)
        assert len(result.corrupt_files) == 1
        assert result.corrupt_files[0].name == "bad.wav"

    def test_valid_file_not_flagged(self, tmp_path: Path) -> None:
        root = tmp_path / "usb"
        root.mkdir()
        _make_wav(root / "good.wav")

        result = run_preflight(root)
        assert len(result.corrupt_files) == 0
        assert len(result.zero_byte_files) == 0
        assert result.total_tracks == 1

    def test_missing_bpm_key_genre(self, tmp_path: Path) -> None:
        """WAV files have no ID3 tags, so BPM/key/genre should be missing."""
        root = tmp_path / "usb"
        root.mkdir()
        _make_wav(root / "notags.wav")

        result = run_preflight(root)
        # WAV files typically have no BPM/key/genre tags
        assert len(result.missing_bpm) >= 1
        assert len(result.missing_key) >= 1
        assert len(result.missing_genre) >= 1

    def test_duplicate_filenames_found(self, tmp_path: Path) -> None:
        root = tmp_path / "usb"
        root.mkdir()
        sub = root / "sub"
        sub.mkdir()
        _make_wav(root / "track.wav")
        _make_wav(sub / "track.wav")

        result = run_preflight(root)
        assert len(result.duplicate_filenames) == 1
        assert len(result.duplicate_filenames[0]) == 2

    def test_no_duplicates_when_unique(self, tmp_path: Path) -> None:
        root = tmp_path / "usb"
        root.mkdir()
        _make_wav(root / "track_a.wav")
        _make_wav(root / "track_b.wav")

        result = run_preflight(root)
        assert len(result.duplicate_filenames) == 0

    def test_empty_folder(self, tmp_path: Path) -> None:
        root = tmp_path / "empty"
        root.mkdir()

        result = run_preflight(root)
        assert result.total_tracks == 0
        assert result.is_clean

    def test_stats_computed(self, tmp_path: Path) -> None:
        root = tmp_path / "usb"
        root.mkdir()
        _make_wav(root / "a.wav", duration_seconds=2.0)
        _make_wav(root / "b.wav", duration_seconds=3.0)

        result = run_preflight(root)
        # Should have total size > 0 and duration > 0
        assert result.total_size_bytes > 0
        assert result.total_duration_seconds > 0

    def test_issue_count(self, tmp_path: Path) -> None:
        root = _build_fixture_folder(tmp_path)
        result = run_preflight(root)
        # Should count corrupt + zero-byte + missing metadata + duplicates
        assert result.issue_count > 0
        assert not result.is_clean

    def test_check_duplicate_filenames_helper(self) -> None:
        paths = [
            Path("/a/track.wav"),
            Path("/b/track.wav"),
            Path("/c/other.wav"),
        ]
        dupes = _check_duplicate_filenames(paths)
        assert len(dupes) == 1
        assert len(dupes[0]) == 2

    def test_check_missing_metadata_helper(self) -> None:
        meta_map = {
            Path("/a.wav"): TrackMetadata(bpm=128.0, key="Am", genre="Techno"),
            Path("/b.wav"): TrackMetadata(bpm=None, key=None, genre=None),
        }
        missing_bpm, missing_key, missing_genre = _check_missing_metadata(meta_map)
        assert Path("/b.wav") in missing_bpm
        assert Path("/b.wav") in missing_key
        assert Path("/b.wav") in missing_genre
        assert Path("/a.wav") not in missing_bpm

    def test_compute_stats_helper(self) -> None:
        meta_map = {
            Path("/a.wav"): TrackMetadata(
                bpm=120.0, key="Am", genre="Techno", duration_seconds=300.0
            ),
            Path("/b.wav"): TrackMetadata(
                bpm=130.0, key="Cm", genre="Techno", duration_seconds=240.0
            ),
            Path("/c.wav"): TrackMetadata(
                bpm=125.0, key="Am", genre="House", duration_seconds=360.0
            ),
        }
        bpm_range, bpm_median, key_dist, genre_dist, total_dur = _compute_stats(
            meta_map
        )
        assert bpm_range == (120.0, 130.0)
        assert bpm_median == 125.0
        assert key_dist["Am"] == 2
        assert key_dist["Cm"] == 1
        assert genre_dist["Techno"] == 2
        assert genre_dist["House"] == 1
        assert total_dur == 900.0


# ---------------------------------------------------------------------------
# TestPreflightReport
# ---------------------------------------------------------------------------

class TestPreflightReport:
    """Test the report formatting."""

    def test_format_duration_hours(self) -> None:
        assert _format_duration(3600 + 23 * 60) == "1h 23m"

    def test_format_duration_minutes_only(self) -> None:
        assert _format_duration(45 * 60) == "45m"

    def test_format_duration_zero(self) -> None:
        assert _format_duration(0) == "0m"

    def test_format_size_gb(self) -> None:
        assert "GB" in _format_size(5_000_000_000)

    def test_format_size_mb(self) -> None:
        assert "MB" in _format_size(50_000_000)

    def test_format_size_kb(self) -> None:
        assert "KB" in _format_size(500)

    def test_top_genres(self) -> None:
        dist = {"Techno": 10, "House": 5, "Trance": 2}
        formatted = _top_genres(dist)
        assert "Techno" in formatted
        assert "%" in formatted

    def test_top_genres_empty(self) -> None:
        assert _top_genres({}) == "None"

    def test_report_clean(self) -> None:
        result = PreflightResult(
            path=Path("/usb"),
            total_tracks=10,
            total_duration_seconds=3600,
            total_size_bytes=1_000_000,
            bpm_range=(120.0, 130.0),
            bpm_median=125.0,
            key_distribution={"Am": 5, "Cm": 5},
            genre_distribution={"Techno": 10},
        )
        console = Console(file=None, force_terminal=True, width=120)
        # Should not raise
        with console.capture() as capture:
            print_preflight_report(result, console)
        output = capture.get()
        assert "VERDICT" in output
        assert "gig-ready" in output

    def test_report_with_issues(self) -> None:
        result = PreflightResult(
            path=Path("/usb"),
            total_tracks=10,
            missing_key=[Path("/usb/a.wav"), Path("/usb/b.wav")],
            total_duration_seconds=3600,
            total_size_bytes=1_000_000,
        )
        console = Console(file=None, force_terminal=True, width=120)
        with console.capture() as capture:
            print_preflight_report(result, console)
        output = capture.get()
        assert "VERDICT" in output
        assert "2" in output  # 2 issues

    def test_report_empty_folder(self) -> None:
        result = PreflightResult(path=Path("/usb"), total_tracks=0)
        console = Console(file=None, force_terminal=True, width=120)
        with console.capture() as capture:
            print_preflight_report(result, console)
        output = capture.get()
        assert "No audio files found" in output

    def test_report_list_all(self) -> None:
        paths = [Path(f"/usb/track{i}.wav") for i in range(10)]
        result = PreflightResult(
            path=Path("/usb"),
            total_tracks=10,
            missing_key=paths,
            total_duration_seconds=600,
            total_size_bytes=500_000,
        )
        console = Console(file=None, force_terminal=True, width=120)
        with console.capture() as capture:
            print_preflight_report(result, console, list_all=True)
        output = capture.get()
        # With list_all, all 10 should appear (not truncated to 5)
        assert "track9.wav" in output

    def test_report_truncated_by_default(self) -> None:
        paths = [Path(f"/usb/track{i}.wav") for i in range(10)]
        result = PreflightResult(
            path=Path("/usb"),
            total_tracks=10,
            missing_key=paths,
            total_duration_seconds=600,
            total_size_bytes=500_000,
        )
        console = Console(file=None, force_terminal=True, width=120)
        with console.capture() as capture:
            print_preflight_report(result, console, list_all=False)
        output = capture.get()
        assert "more" in output  # truncation indicator

    def test_report_rekordbox_section(self) -> None:
        result = PreflightResult(
            path=Path("/usb"),
            total_tracks=5,
            total_duration_seconds=600,
            total_size_bytes=500_000,
            rekordbox_analyzed=4,
            rekordbox_not_analyzed=["DJ Raw - Not Ready"],
            tracks_with_cues=3,
            tracks_without_cues=["DJ Lazy - Needs Work", "DJ Raw - Not Ready"],
        )
        console = Console(file=None, force_terminal=True, width=120, no_color=True, highlight=False)
        with console.capture() as capture:
            print_preflight_report(result, console)
        output = capture.get()
        assert "REKORDBOX" in output
        assert "4/5" in output


# ---------------------------------------------------------------------------
# TestPreflightEndToEnd
# ---------------------------------------------------------------------------

class TestPreflightEndToEnd:
    """End-to-end tests with fixture folders."""

    def test_mixed_folder(self, tmp_path: Path) -> None:
        root = _build_fixture_folder(tmp_path)
        result = run_preflight(root)

        # 5 audio files total (good1, good2, good1-dup, corrupt, empty)
        assert result.total_tracks == 5
        assert len(result.zero_byte_files) == 1
        assert len(result.corrupt_files) >= 1
        assert len(result.duplicate_filenames) == 1
        assert not result.is_clean

    def test_clean_folder(self, tmp_path: Path) -> None:
        """A folder with only valid, uniquely named files."""
        root = tmp_path / "clean"
        root.mkdir()
        _make_wav(root / "track_a.wav", duration_seconds=2.0)
        _make_wav(root / "track_b.wav", duration_seconds=3.0)

        result = run_preflight(root)
        assert result.total_tracks == 2
        assert len(result.corrupt_files) == 0
        assert len(result.zero_byte_files) == 0
        assert len(result.duplicate_filenames) == 0
        # WAV files won't have BPM/key/genre so those will be missing
        assert result.total_duration_seconds > 0
        assert result.total_size_bytes > 0

    def test_rekordbox_integration(self, tmp_path: Path) -> None:
        """Test with a Rekordbox XML fixture."""
        root = tmp_path / "usb"
        root.mkdir()
        _make_wav(root / "track.wav")

        xml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="6.8.4" />
  <COLLECTION Entries="2">
    <TRACK TrackID="1" Name="Analyzed" Artist="DJ A"
           TotalTime="300" AverageBpm="126.00" Tonality="Am"
           Location="file://localhost/track1.mp3">
      <TEMPO Inizio="0.1" Bpm="126.00" Metro="4/4" />
      <POSITION_MARK Name="Intro" Type="0" Start="0.1" Num="0" />
    </TRACK>
    <TRACK TrackID="2" Name="Raw" Artist="DJ B"
           TotalTime="200"
           Location="file://localhost/track2.mp3">
    </TRACK>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="root" />
  </PLAYLISTS>
</DJ_PLAYLISTS>
"""
        xml_path = tmp_path / "rekordbox.xml"
        xml_path.write_text(xml_content, encoding="utf-8")

        result = run_preflight(root, rekordbox_xml=xml_path)
        assert result.rekordbox_analyzed == 1
        assert result.rekordbox_not_analyzed is not None
        assert len(result.rekordbox_not_analyzed) == 1
        assert result.tracks_with_cues == 1
        assert result.tracks_without_cues is not None
        assert len(result.tracks_without_cues) == 1


# ---------------------------------------------------------------------------
# TestPreflightCLI
# ---------------------------------------------------------------------------

class TestPreflightCLI:
    """Test the top-level preflight CLI command."""

    def test_basic_run(self, tmp_path: Path) -> None:
        root = tmp_path / "usb"
        root.mkdir()
        _make_wav(root / "track.wav")

        runner = CliRunner()
        result = runner.invoke(cli, ["preflight", str(root)])
        assert result.exit_code == 0, result.output
        assert "PREFLIGHT" in result.output
        assert "VERDICT" in result.output

    def test_empty_folder(self, tmp_path: Path) -> None:
        root = tmp_path / "empty"
        root.mkdir()

        runner = CliRunner()
        result = runner.invoke(cli, ["preflight", str(root)])
        assert result.exit_code == 0, result.output
        assert "No audio files" in result.output

    def test_list_all_flag(self, tmp_path: Path) -> None:
        root = tmp_path / "usb"
        root.mkdir()
        _make_wav(root / "a.wav")
        _make_wav(root / "b.wav")

        runner = CliRunner()
        result = runner.invoke(cli, ["preflight", str(root), "--list-all"])
        assert result.exit_code == 0, result.output

    def test_strict_flag(self, tmp_path: Path) -> None:
        root = tmp_path / "usb"
        root.mkdir()
        _make_wav(root / "a.wav")

        runner = CliRunner()
        result = runner.invoke(cli, ["preflight", str(root), "--strict"])
        assert result.exit_code == 0, result.output

    def test_with_rekordbox(self, tmp_path: Path) -> None:
        root = tmp_path / "usb"
        root.mkdir()
        _make_wav(root / "track.wav")

        xml_content = """\
<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="6.8.4" />
  <COLLECTION Entries="1">
    <TRACK TrackID="1" Name="Test" Artist="DJ"
           TotalTime="300" AverageBpm="126.00"
           Location="file://localhost/test.mp3">
      <TEMPO Inizio="0.1" Bpm="126.00" Metro="4/4" />
    </TRACK>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="root" />
  </PLAYLISTS>
</DJ_PLAYLISTS>
"""
        xml_path = tmp_path / "rekordbox.xml"
        xml_path.write_text(xml_content, encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(
            cli, ["preflight", str(root), "--rekordbox", str(xml_path)]
        )
        assert result.exit_code == 0, result.output
        assert "REKORDBOX" in result.output

    def test_nonexistent_path(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["preflight", "/nonexistent/path"])
        assert result.exit_code != 0

    def test_mixed_folder_end_to_end(self, tmp_path: Path) -> None:
        root = _build_fixture_folder(tmp_path)

        runner = CliRunner()
        result = runner.invoke(cli, ["preflight", str(root)])
        assert result.exit_code == 0, result.output
        assert "VERDICT" in result.output
        # Should report issues
        assert "issue" in result.output.lower()
