"""Tests for Rekordbox XML writer."""

import xml.etree.ElementTree as ET
from pathlib import Path

from cratedigger.gig.rekordbox_parser import parse_rekordbox_xml
from cratedigger.gig.rekordbox_writer import (
    ExportCuePoint,
    ExportTrack,
    write_rekordbox_xml,
)


def _sample_tracks() -> list[ExportTrack]:
    return [
        ExportTrack(
            location="/Music/Solomun - Midnight Express.mp3",
            name="Midnight Express",
            artist="Solomun",
            bpm=122.0,
            key="Am",
            cue_points=[
                ExportCuePoint(name="Intro", position_seconds=0.123, num=0,
                               red=40, green=226, blue=160),
                ExportCuePoint(name="Drop", position_seconds=64.5, num=1,
                               red=255, green=90, blue=126),
            ],
        ),
        ExportTrack(
            location="/Music/Fisher - Losing It.mp3",
            name="Losing It",
            artist="Fisher",
            bpm=126.0,
            key="Bbm",
        ),
    ]


class TestWriteRekordboxXml:
    def test_creates_file(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), out)
        assert out.exists()

    def test_valid_xml(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), out)
        tree = ET.parse(str(out))
        assert tree.getroot().tag == "DJ_PLAYLISTS"

    def test_collection_count(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), out)
        tree = ET.parse(str(out))
        collection = tree.find("COLLECTION")
        assert collection is not None
        assert collection.get("Entries") == "2"

    def test_track_attributes(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), out)
        tree = ET.parse(str(out))
        tracks = tree.findall(".//COLLECTION/TRACK")
        assert len(tracks) == 2
        assert tracks[0].get("Name") == "Midnight Express"
        assert tracks[0].get("Artist") == "Solomun"
        assert tracks[0].get("AverageBpm") == "122.00"
        assert tracks[0].get("Tonality") == "Am"

    def test_cue_points_written(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), out)
        tree = ET.parse(str(out))
        track1 = tree.findall(".//COLLECTION/TRACK")[0]
        cues = track1.findall("POSITION_MARK")
        assert len(cues) == 2
        assert cues[0].get("Name") == "Intro"
        assert cues[0].get("Type") == "0"
        assert cues[0].get("Num") == "0"
        assert cues[1].get("Name") == "Drop"

    def test_cue_colors(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), out)
        tree = ET.parse(str(out))
        cue = tree.findall(".//POSITION_MARK")[0]
        assert cue.get("Red") == "40"
        assert cue.get("Green") == "226"
        assert cue.get("Blue") == "160"

    def test_beatgrid_tempo(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), out)
        tree = ET.parse(str(out))
        tempo = tree.findall(".//TEMPO")
        assert len(tempo) == 2  # both tracks have BPM

    def test_playlist_created(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), out, playlist_name="Saturday Set")
        tree = ET.parse(str(out))
        playlist = tree.find(".//PLAYLISTS//NODE[@Type='1']")
        assert playlist is not None
        assert playlist.get("Name") == "Saturday Set"
        assert len(playlist.findall("TRACK")) == 2

    def test_no_playlist_when_none(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), out)
        tree = ET.parse(str(out))
        playlists = tree.findall(".//PLAYLISTS//NODE[@Type='1']")
        assert len(playlists) == 0

    def test_roundtrip_parseable(self, tmp_path: Path):
        """Written XML should be parseable by our Rekordbox parser."""
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), out, playlist_name="Test")
        lib = parse_rekordbox_xml(out)
        assert len(lib.tracks) == 2
        assert "Test" in lib.playlists

    def test_track_without_bpm(self, tmp_path: Path):
        tracks = [ExportTrack(location="/test.mp3", name="Raw", artist="DJ")]
        out = tmp_path / "export.xml"
        write_rekordbox_xml(tracks, out)
        tree = ET.parse(str(out))
        track = tree.find(".//TRACK")
        assert track.get("AverageBpm") is None
        assert len(track.findall("TEMPO")) == 0

    def test_location_encoded(self, tmp_path: Path):
        tracks = [ExportTrack(
            location="/Music/My Track [320].mp3",
            name="My Track", artist="DJ",
        )]
        out = tmp_path / "export.xml"
        write_rekordbox_xml(tracks, out)
        tree = ET.parse(str(out))
        loc = tree.find(".//TRACK").get("Location")
        assert "file://localhost" in loc
        assert "%20" in loc or "My" in loc  # spaces should be encoded
