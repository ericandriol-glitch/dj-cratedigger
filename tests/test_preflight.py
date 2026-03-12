"""Tests for gig pre-flight check."""

from pathlib import Path

from click.testing import CliRunner

from cratedigger.cli import cli
from cratedigger.gig.preflight import (
    ReadinessLevel,
    check_track,
    run_preflight,
)
from cratedigger.gig.rekordbox_parser import CuePoint, RekordboxTrack, parse_rekordbox_xml

FIXTURE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="6.8.4" />
  <COLLECTION Entries="3">
    <TRACK TrackID="1" Name="Ready Track" Artist="DJ Ready"
           TotalTime="300" AverageBpm="126.00" Tonality="Am"
           Location="file://localhost/track1.mp3">
      <TEMPO Inizio="0.1" Bpm="126.00" Metro="4/4" />
      <POSITION_MARK Name="Intro" Type="0" Start="0.1" Num="0"
                     Red="40" Green="226" Blue="160" />
    </TRACK>
    <TRACK TrackID="2" Name="Needs Work" Artist="DJ Lazy"
           TotalTime="250" AverageBpm="124.00" Tonality="Gm"
           Location="file://localhost/track2.mp3">
      <TEMPO Inizio="0.05" Bpm="124.00" Metro="4/4" />
    </TRACK>
    <TRACK TrackID="3" Name="Not Ready" Artist="DJ Raw"
           TotalTime="200"
           Location="file://localhost/track3.mp3">
    </TRACK>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="root">
      <NODE Name="Friday Set" Type="1" Entries="3">
        <TRACK Key="1" />
        <TRACK Key="2" />
        <TRACK Key="3" />
      </NODE>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
"""


def _write_fixture(tmp_path: Path) -> Path:
    xml_path = tmp_path / "rekordbox.xml"
    xml_path.write_text(FIXTURE_XML, encoding="utf-8")
    return xml_path


class TestCheckTrack:
    """Test individual track readiness checks."""

    def test_ready_track(self):
        track = RekordboxTrack(
            track_id="1", name="Test", artist="DJ",
            location="/test.mp3", bpm=126.0, key="Am",
            has_beatgrid=True,
            cue_points=[CuePoint(name="Intro", cue_type=0, start=0.1, num=0)],
        )
        result = check_track(track)
        assert result.level == ReadinessLevel.READY
        assert result.has_bpm
        assert result.has_key
        assert result.has_beatgrid
        assert result.has_hot_cues

    def test_needs_work_no_cues(self):
        track = RekordboxTrack(
            track_id="2", name="Test", artist="DJ",
            location="/test.mp3", bpm=124.0, key="Gm",
            has_beatgrid=True,
        )
        result = check_track(track)
        assert result.level == ReadinessLevel.NEEDS_WORK
        assert "No cue points" in result.issues

    def test_not_ready_no_analysis(self):
        track = RekordboxTrack(
            track_id="3", name="Test", artist="DJ",
            location="/test.mp3",
        )
        result = check_track(track)
        assert result.level == ReadinessLevel.NOT_READY
        assert "Missing BPM" in result.issues
        assert "No beatgrid" in result.issues

    def test_needs_work_missing_key(self):
        track = RekordboxTrack(
            track_id="4", name="Test", artist="DJ",
            location="/test.mp3", bpm=128.0,
            has_beatgrid=True,
            cue_points=[CuePoint(name="Intro", cue_type=0, start=0.1, num=0)],
        )
        result = check_track(track)
        assert result.level == ReadinessLevel.NEEDS_WORK
        assert "Missing key" in result.issues


class TestRunPreflight:
    """Test full pre-flight on a playlist."""

    def test_preflight_report(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        report = run_preflight(lib, "Friday Set")
        assert report.total == 3
        assert report.ready_count == 1
        assert report.needs_work_count == 1
        assert report.not_ready_count == 1

    def test_ready_percent(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        report = run_preflight(lib, "Friday Set")
        assert report.ready_percent == 33.3

    def test_empty_playlist(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        report = run_preflight(lib, "Nonexistent")
        assert report.total == 0
        assert report.ready_percent == 0.0


class TestPreflightCLI:
    """Test pre-flight CLI command."""

    def test_preflight_runs(self, tmp_path: Path):
        xml_path = _write_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["gig", "preflight", "Friday Set", "--rekordbox", str(xml_path)])
        assert result.exit_code == 0, result.output
        assert "Pre-Flight Check" in result.output
        assert "33%" in result.output

    def test_playlist_not_found(self, tmp_path: Path):
        xml_path = _write_fixture(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["gig", "preflight", "Nope", "--rekordbox", str(xml_path)])
        assert result.exit_code == 0
        assert "not found" in result.output
        assert "Friday Set" in result.output  # should list available playlists
