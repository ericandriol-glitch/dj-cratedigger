"""Tests for Rekordbox XML parser."""

from pathlib import Path

from cratedigger.gig.rekordbox_parser import (
    _decode_location,
    parse_rekordbox_xml,
)

# Fixture XML with tracks in various states
FIXTURE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="6.8.4" />
  <COLLECTION Entries="4">
    <TRACK TrackID="1" Name="Midnight Express" Artist="Solomun"
           TotalTime="423" AverageBpm="122.00" Tonality="Am"
           Location="file://localhost/Volumes/USB/Solomun%20-%20Midnight%20Express.mp3">
      <TEMPO Inizio="0.123" Bpm="122.00" Metro="4/4" />
      <POSITION_MARK Name="Intro" Type="0" Start="0.123" Num="0"
                     Red="40" Green="226" Blue="160" />
      <POSITION_MARK Name="Drop" Type="0" Start="64.500" Num="1"
                     Red="255" Green="90" Blue="126" />
      <POSITION_MARK Name="Memory1" Type="1" Start="30.0" Num="0"
                     Red="200" Green="200" Blue="200" />
    </TRACK>
    <TRACK TrackID="2" Name="Cola" Artist="CamelPhat"
           TotalTime="312" AverageBpm="124.00" Tonality="Gm"
           Location="file://localhost/Volumes/USB/CamelPhat%20-%20Cola.mp3">
      <TEMPO Inizio="0.050" Bpm="124.00" Metro="4/4" />
    </TRACK>
    <TRACK TrackID="3" Name="Unknown Track" Artist="DJ Foo"
           TotalTime="240"
           Location="file://localhost/Volumes/USB/DJ%20Foo%20-%20Unknown.mp3">
    </TRACK>
    <TRACK TrackID="4" Name="Losing It" Artist="Fisher"
           TotalTime="198" AverageBpm="126.00" Tonality="Bbm"
           Location="file://localhost/C%3A/Users/eandrio/Music/Fisher%20-%20Losing%20It.mp3">
      <TEMPO Inizio="0.100" Bpm="126.00" Metro="4/4" />
      <POSITION_MARK Name="Intro" Type="0" Start="0.100" Num="0"
                     Red="40" Green="226" Blue="160" />
    </TRACK>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="root">
      <NODE Name="Saturday @ Phonox" Type="1" Entries="3">
        <TRACK Key="1" />
        <TRACK Key="2" />
        <TRACK Key="4" />
      </NODE>
      <NODE Type="0" Name="Sets">
        <NODE Name="Warm Up" Type="1" Entries="2">
          <TRACK Key="2" />
          <TRACK Key="3" />
        </NODE>
      </NODE>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
"""


def _write_fixture(tmp_path: Path) -> Path:
    """Write the fixture XML and return its path."""
    xml_path = tmp_path / "rekordbox.xml"
    xml_path.write_text(FIXTURE_XML, encoding="utf-8")
    return xml_path


class TestDecodeLocation:
    """Test URL decoding for file paths."""

    def test_localhost_prefix(self):
        result = _decode_location("file://localhost/Volumes/USB/Track%20Name.mp3")
        assert result == "/Volumes/USB/Track Name.mp3"

    def test_url_encoded_spaces(self):
        result = _decode_location("file://localhost/path/My%20Track%20%5B320%5D.mp3")
        assert result == "/path/My Track [320].mp3"

    def test_windows_path(self):
        result = _decode_location("file://localhost/C%3A/Users/Music/track.mp3")
        assert result == "/C:/Users/Music/track.mp3"

    def test_bare_file_prefix(self):
        result = _decode_location("file:///Volumes/USB/track.mp3")
        assert result == "/Volumes/USB/track.mp3"


class TestParseRekordboxXml:
    """Test full XML parsing."""

    def test_parses_product_info(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        assert lib.product_name == "rekordbox"
        assert lib.product_version == "6.8.4"

    def test_parses_all_tracks(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        assert len(lib.tracks) == 4

    def test_track_metadata(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        track = lib.tracks["1"]
        assert track.name == "Midnight Express"
        assert track.artist == "Solomun"
        assert track.bpm == 122.0
        assert track.key == "Am"
        assert track.total_time == 423

    def test_track_location_decoded(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        track = lib.tracks["1"]
        assert "Solomun - Midnight Express.mp3" in track.location
        assert "%20" not in track.location

    def test_fully_analyzed_track(self, tmp_path: Path):
        """Track 1: has BPM, key, beatgrid, and cue points."""
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        track = lib.tracks["1"]
        assert track.bpm is not None
        assert track.key is not None
        assert track.has_beatgrid is True
        assert len(track.cue_points) == 3
        assert len(track.hot_cues) == 2
        assert len(track.memory_cues) == 1

    def test_analyzed_no_cues(self, tmp_path: Path):
        """Track 2: has BPM, key, beatgrid, but no cue points."""
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        track = lib.tracks["2"]
        assert track.bpm == 124.0
        assert track.has_beatgrid is True
        assert len(track.cue_points) == 0

    def test_not_analyzed(self, tmp_path: Path):
        """Track 3: no BPM, no key, no beatgrid, no cues."""
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        track = lib.tracks["3"]
        assert track.bpm is None
        assert track.key is None
        assert track.has_beatgrid is False
        assert len(track.cue_points) == 0

    def test_cue_point_details(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        track = lib.tracks["1"]
        intro = track.hot_cues[0]
        assert intro.name == "Intro"
        assert intro.cue_type == 0
        assert intro.start == 0.123
        assert intro.num == 0
        assert intro.green == 226

    def test_cue_point_colors(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        drop = lib.tracks["1"].hot_cues[1]
        assert drop.red == 255
        assert drop.green == 90
        assert drop.blue == 126


class TestPlaylists:
    """Test playlist parsing."""

    def test_parses_playlists(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        assert "Saturday @ Phonox" in lib.playlists
        assert "Warm Up" in lib.playlists

    def test_playlist_track_count(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        phonox = lib.playlists["Saturday @ Phonox"]
        assert len(phonox.track_keys) == 3

    def test_nested_playlist(self, tmp_path: Path):
        """Warm Up is inside a Sets folder — should still be found."""
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        warmup = lib.playlists["Warm Up"]
        assert len(warmup.track_keys) == 2

    def test_get_playlist_tracks(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        tracks = lib.get_playlist_tracks("Saturday @ Phonox")
        assert len(tracks) == 3
        names = [t.name for t in tracks]
        assert "Midnight Express" in names
        assert "Cola" in names
        assert "Losing It" in names

    def test_get_nonexistent_playlist(self, tmp_path: Path):
        lib = parse_rekordbox_xml(_write_fixture(tmp_path))
        tracks = lib.get_playlist_tracks("Does Not Exist")
        assert tracks == []


class TestErrorHandling:
    """Test error cases."""

    def test_missing_file_raises(self, tmp_path: Path):
        import pytest
        with pytest.raises(FileNotFoundError):
            parse_rekordbox_xml(tmp_path / "nonexistent.xml")

    def test_malformed_xml_raises(self, tmp_path: Path):
        import xml.etree.ElementTree as ET
        import pytest
        bad_xml = tmp_path / "bad.xml"
        bad_xml.write_text("not xml at all", encoding="utf-8")
        with pytest.raises(ET.ParseError):
            parse_rekordbox_xml(bad_xml)
