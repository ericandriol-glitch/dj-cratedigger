"""Tests for Rekordbox 7 XML writer."""

import xml.etree.ElementTree as ET
from pathlib import Path

from cratedigger.gig.rekordbox_parser import parse_rekordbox_xml
from cratedigger.gig.rekordbox_writer import (
    ExportCuePoint,
    ExportTrack,
    _filepath_to_location,
    _track_to_xml_element,
    _build_playlist_nodes,
    write_rekordbox_xml,
)


def _sample_tracks() -> list[dict]:
    return [
        {
            "filepath": Path("/Music/Solomun - Midnight Express.mp3"),
            "artist": "Solomun",
            "title": "Midnight Express",
            "album": "",
            "genre": "Melodic Techno",
            "bpm": 122.0,
            "key_camelot": "Am",
            "year": 2024,
            "duration_seconds": 342,
            "bitrate": 320,
            "sample_rate": 44100,
            "size": 8234567,
            "cue_points": [
                ExportCuePoint(name="Intro", position_seconds=0.123, num=0,
                               red=40, green=226, blue=160),
                ExportCuePoint(name="Drop", position_seconds=64.5, num=1,
                               red=255, green=90, blue=126),
            ],
        },
        {
            "filepath": Path("/Music/Fisher - Losing It.mp3"),
            "artist": "Fisher",
            "title": "Losing It",
            "album": "",
            "genre": "Tech House",
            "bpm": 126.0,
            "key_camelot": "Bbm",
            "year": 2018,
            "duration_seconds": 210,
            "bitrate": 320,
            "sample_rate": 44100,
            "size": 5000000,
        },
    ]


class TestFilepathToLocation:
    def test_encodes_spaces(self):
        loc = _filepath_to_location(Path("/Music/My Track.mp3"))
        assert "%20" in loc or "My" in loc

    def test_starts_with_file_localhost(self):
        loc = _filepath_to_location(Path("/Music/track.mp3"))
        assert loc.startswith("file://localhost/")

    def test_forward_slashes_only(self):
        loc = _filepath_to_location(Path("/Music/sub dir/track.mp3"))
        assert "\\" not in loc


class TestTrackToXmlElement:
    def test_basic_attributes(self):
        track = _sample_tracks()[0]
        elem = _track_to_xml_element(track, 1)
        assert elem.get("TrackID") == "1"
        assert elem.get("Name") == "Midnight Express"
        assert elem.get("Artist") == "Solomun"
        assert elem.get("AverageBpm") == "122.00"
        assert elem.get("Tonality") == "Am"

    def test_file_kind(self):
        track = _sample_tracks()[0]
        elem = _track_to_xml_element(track, 1)
        assert elem.get("Kind") == "MP3 File"

    def test_tempo_element(self):
        track = _sample_tracks()[0]
        elem = _track_to_xml_element(track, 1)
        tempos = elem.findall("TEMPO")
        assert len(tempos) == 1
        assert tempos[0].get("Bpm") == "122.00"
        assert tempos[0].get("Metro") == "4/4"
        assert tempos[0].get("Battito") == "1"

    def test_cue_points(self):
        track = _sample_tracks()[0]
        elem = _track_to_xml_element(track, 1)
        cues = elem.findall("POSITION_MARK")
        assert len(cues) == 2
        assert cues[0].get("Name") == "Intro"
        assert cues[0].get("Start") == "0.123"
        assert cues[1].get("Name") == "Drop"

    def test_no_bpm_no_tempo(self):
        track = {"filepath": Path("/test.mp3"), "title": "Raw", "artist": "DJ"}
        elem = _track_to_xml_element(track, 1)
        assert elem.get("AverageBpm") == "0.00"
        assert len(elem.findall("TEMPO")) == 0

    def test_none_values_become_empty(self):
        track = {"filepath": Path("/test.mp3"), "artist": None, "title": None}
        elem = _track_to_xml_element(track, 1)
        assert elem.get("Artist") == ""
        assert elem.get("Name") == ""

    def test_flac_kind(self):
        track = {"filepath": Path("/music/track.flac")}
        elem = _track_to_xml_element(track, 1)
        assert elem.get("Kind") == "FLAC File"

    def test_dict_cue_points(self):
        track = {
            "filepath": Path("/test.mp3"),
            "cue_points": [{"name": "Start", "start": 1.5, "num": 0}],
        }
        elem = _track_to_xml_element(track, 1)
        cues = elem.findall("POSITION_MARK")
        assert len(cues) == 1
        assert cues[0].get("Name") == "Start"


class TestBuildPlaylistNodes:
    def test_flat_playlist(self):
        elem = _build_playlist_nodes("My Set", [1, 2, 3], None)
        playlist = elem.find(".//NODE[@Type='1']")
        assert playlist is not None
        assert playlist.get("Name") == "My Set"
        assert playlist.get("Entries") == "3"
        assert len(playlist.findall("TRACK")) == 3

    def test_sub_playlists(self):
        subs = {"Warm-up": [0], "Peak": [1, 2]}
        elem = _build_playlist_nodes("Energy", [1, 2, 3], subs)
        folder = elem.find(".//NODE[@Name='Energy']")
        assert folder is not None
        assert folder.get("Type") == "0"
        warmup = folder.find("NODE[@Name='Warm-up']")
        assert warmup is not None
        assert warmup.get("Entries") == "1"
        peak = folder.find("NODE[@Name='Peak']")
        assert peak is not None
        assert peak.get("Entries") == "2"


class TestWriteRekordboxXml:
    def test_creates_file(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), "Test", out)
        assert out.exists()

    def test_valid_xml(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), "Test", out)
        tree = ET.parse(str(out))
        assert tree.getroot().tag == "DJ_PLAYLISTS"

    def test_rekordbox7_product(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), "Test", out)
        tree = ET.parse(str(out))
        product = tree.find("PRODUCT")
        assert product is not None
        assert product.get("Name") == "rekordbox"
        assert product.get("Version") == "7.0.1"
        assert product.get("Company") == "Pioneer DJ"

    def test_collection_count(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), "Test", out)
        tree = ET.parse(str(out))
        collection = tree.find("COLLECTION")
        assert collection is not None
        assert collection.get("Entries") == "2"

    def test_track_attributes(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), "Test", out)
        tree = ET.parse(str(out))
        tracks = tree.findall(".//COLLECTION/TRACK")
        assert len(tracks) == 2
        assert tracks[0].get("Name") == "Midnight Express"
        assert tracks[0].get("Artist") == "Solomun"
        assert tracks[0].get("AverageBpm") == "122.00"
        assert tracks[0].get("Tonality") == "Am"
        assert tracks[0].get("TotalTime") == "342"
        assert tracks[0].get("Size") == "8234567"

    def test_cue_points_written(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), "Test", out)
        tree = ET.parse(str(out))
        track1 = tree.findall(".//COLLECTION/TRACK")[0]
        cues = track1.findall("POSITION_MARK")
        assert len(cues) == 2
        assert cues[0].get("Name") == "Intro"
        assert cues[0].get("Type") == "0"
        assert cues[1].get("Name") == "Drop"

    def test_cue_colors(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), "Test", out)
        tree = ET.parse(str(out))
        cue = tree.findall(".//POSITION_MARK")[0]
        assert cue.get("Red") == "40"
        assert cue.get("Green") == "226"
        assert cue.get("Blue") == "160"

    def test_beatgrid_tempo(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), "Test", out)
        tree = ET.parse(str(out))
        tempo = tree.findall(".//TEMPO")
        assert len(tempo) == 2  # both tracks have BPM

    def test_playlist_created(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), "Saturday Set", out)
        tree = ET.parse(str(out))
        playlist = tree.find(".//PLAYLISTS//NODE[@Type='1']")
        assert playlist is not None
        assert playlist.get("Name") == "Saturday Set"
        assert len(playlist.findall("TRACK")) == 2

    def test_sub_playlists(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        subs = {"Warm-up": [0], "Peak": [1]}
        write_rekordbox_xml(_sample_tracks(), "Energy Zones", out, sub_playlists=subs)
        tree = ET.parse(str(out))
        folder = tree.find(".//NODE[@Name='Energy Zones']")
        assert folder is not None
        assert folder.get("Type") == "0"
        warmup = folder.find("NODE[@Name='Warm-up']")
        assert warmup is not None
        assert len(warmup.findall("TRACK")) == 1

    def test_roundtrip_parseable(self, tmp_path: Path):
        """Written XML should be parseable by our Rekordbox parser."""
        out = tmp_path / "export.xml"
        write_rekordbox_xml(_sample_tracks(), "Test", out)
        lib = parse_rekordbox_xml(out)
        assert len(lib.tracks) == 2
        assert "Test" in lib.playlists
        t1 = lib.tracks["1"]
        assert t1.name == "Midnight Express"
        assert t1.artist == "Solomun"
        assert t1.bpm == 122.0
        assert t1.key == "Am"
        assert t1.total_time == 342
        assert t1.has_beatgrid

    def test_roundtrip_sub_playlists(self, tmp_path: Path):
        out = tmp_path / "export.xml"
        subs = {"Warm-up": [0], "Peak": [1]}
        write_rekordbox_xml(_sample_tracks(), "Zones", out, sub_playlists=subs)
        lib = parse_rekordbox_xml(out)
        assert "Warm-up" in lib.playlists
        assert "Peak" in lib.playlists
        assert len(lib.playlists["Warm-up"].track_keys) == 1
        assert len(lib.playlists["Peak"].track_keys) == 1

    def test_creates_parent_directories(self, tmp_path: Path):
        out = tmp_path / "sub" / "dir" / "export.xml"
        write_rekordbox_xml(_sample_tracks(), "Test", out)
        assert out.exists()

    def test_location_encoded(self, tmp_path: Path):
        tracks = [{
            "filepath": Path("/Music/My Track [320].mp3"),
            "title": "My Track", "artist": "DJ",
        }]
        out = tmp_path / "export.xml"
        write_rekordbox_xml(tracks, "Test", out)
        tree = ET.parse(str(out))
        loc = tree.find(".//TRACK").get("Location")
        assert "file://localhost" in loc

    def test_track_without_bpm(self, tmp_path: Path):
        tracks = [{"filepath": Path("/test.mp3"), "title": "Raw", "artist": "DJ"}]
        out = tmp_path / "export.xml"
        write_rekordbox_xml(tracks, "Test", out)
        tree = ET.parse(str(out))
        track = tree.find(".//TRACK")
        assert track.get("AverageBpm") == "0.00"
        assert len(track.findall("TEMPO")) == 0


class TestExportTrackBackcompat:
    """Verify legacy ExportTrack/ExportCuePoint dataclasses still importable."""

    def test_export_track_creation(self):
        t = ExportTrack(location="/test.mp3", name="Test", artist="DJ", bpm=128.0)
        assert t.name == "Test"
        assert t.bpm == 128.0

    def test_export_cue_creation(self):
        c = ExportCuePoint(name="Drop", position_seconds=32.0, num=0)
        assert c.name == "Drop"
        assert c.red == 40  # default
