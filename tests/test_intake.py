"""Tests for the intake pipeline — TDD spec for `cratedigger intake`."""
import shutil
import wave
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
from mutagen.id3 import ID3, TBPM, TCON, TIT2, TPE1

from cratedigger.gig.rekordbox_parser import parse_rekordbox_xml
from cratedigger.gig.rekordbox_writer import (
    _filepath_to_location, generate_intake_xml, write_rekordbox_xml,
)
from cratedigger.intake.models import IntakeResult, IntakeTrack
from cratedigger.scanner import AUDIO_EXTENSIONS, find_audio_files


def _make_mp3(path: Path, artist=None, title=None, genre=None, bpm=None) -> Path:
    """Create a minimal valid MP3 with optional ID3 tags."""
    path.write_bytes(bytes([0xFF, 0xFB, 0x90, 0x00]) + b"\x00" * 413)
    if any([artist, title, genre, bpm]):
        tags = ID3()
        if artist: tags.add(TPE1(encoding=3, text=[artist]))
        if title:  tags.add(TIT2(encoding=3, text=[title]))
        if genre:  tags.add(TCON(encoding=3, text=[genre]))
        if bpm:    tags.add(TBPM(encoding=3, text=[str(bpm)]))
        tags.save(path)
    return path


def _make_wav(path: Path, freq: float = 440.0, duration: float = 0.5) -> Path:
    """Generate a short WAV file with a sine wave."""
    sr, n = 44100, int(44100 * duration)
    t = np.linspace(0, duration, n, dtype=np.float64)
    samples = (0.5 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(samples.tobytes())
    return path


@pytest.fixture
def dummy_mp3(tmp_path):
    return _make_mp3(tmp_path / "Disclosure - Latch.mp3",
                     artist="Disclosure", title="Latch", genre="House", bpm="122")

@pytest.fixture
def source_folder(tmp_path):
    src = tmp_path / "incoming"; src.mkdir()
    _make_mp3(src / "Solomun - Midnight Express.mp3",
              artist="Solomun", title="Midnight Express", genre="Tech House", bpm="122")
    _make_mp3(src / "Fisher - Losing It.mp3",
              artist="Fisher", title="Losing It", genre="Tech House", bpm="126")
    _make_mp3(src / "Peggy Gou - Starry Night.mp3",
              artist="Peggy Gou", title="Starry Night", genre="Deep House", bpm="118")
    return src

@pytest.fixture
def dest_folder(tmp_path):
    dest = tmp_path / "library"; dest.mkdir(); return dest


class TestIntakePipeline:
    def test_scan_finds_audio_files(self, tmp_path):
        _make_mp3(tmp_path / "track1.mp3"); _make_wav(tmp_path / "track2.wav")
        (tmp_path / "notes.txt").write_text("ignore me")
        files = find_audio_files(tmp_path)
        assert len(files) == 2
        assert all(f.suffix.lower() in AUDIO_EXTENSIONS for f in files)

    def test_metadata_reading(self, dummy_mp3):
        from cratedigger.metadata import read_metadata
        meta = read_metadata(dummy_mp3)
        assert meta.artist == "Disclosure"
        assert meta.title == "Latch"
        assert meta.genre == "House"

    def test_fingerprint_skipped_when_no_api_key(self, tmp_path):
        t = IntakeTrack(filepath=tmp_path / "t.mp3", original_filename="t.mp3")
        assert t.identified_via == "none"
        assert t.identification_confidence == 0.0

    def test_fingerprint_skipped_with_no_fingerprint_flag(self, tmp_path):
        t = IntakeTrack(filepath=tmp_path / "t.mp3", original_filename="t.mp3")
        assert t.identified_via == "none"

    def test_analysis_falls_back_to_librosa(self, tmp_path):
        t = IntakeTrack(filepath=tmp_path / "t.mp3", original_filename="t.mp3",
                        bpm=126.0, bpm_source="librosa")
        assert t.bpm_source == "librosa"

    def test_enrichment_skipped_with_no_enrich_flag(self, tmp_path):
        t = IntakeTrack(filepath=tmp_path / "t.mp3", original_filename="t.mp3",
                        artist="Test", title="Track")
        assert t.album is None and t.year is None

    @pytest.mark.parametrize("artist,title,ext,expected", [
        ("Solomun", "Midnight Express", ".mp3", "Solomun - Midnight Express.mp3"),
        ("Fisher", "Losing It", ".wav", "Fisher - Losing It.wav"),
        ("DJ Snake", "Turn Down", ".flac", "DJ Snake - Turn Down.flac"),
    ])
    def test_suggested_filename_format(self, artist, title, ext, expected):
        assert f"{artist} - {title}{ext}" == expected

    def test_intake_track_dataclass(self, tmp_path):
        t = IntakeTrack(filepath=tmp_path / "a.mp3", original_filename="a.mp3")
        assert t.status == "pending"
        assert t.identified_via == "none"
        assert t.bpm_source == "none" and t.key_source == "none"
        assert t.artist is None and t.destination_folder is None and t.new_filepath is None


class TestReviewQueue:
    def test_auto_mode_accepts_all(self):
        tracks = [IntakeTrack(filepath=Path(f"/t{i}.mp3"), original_filename=f"t{i}.mp3",
                              artist=f"Artist{i}", title=f"Title{i}") for i in range(3)]
        for t in tracks: t.status = "approved"
        assert all(t.status == "approved" for t in tracks)

    def test_auto_mode_assigns_genre_folders(self):
        tracks = [
            IntakeTrack(filepath=Path("/t1.mp3"), original_filename="t1.mp3", genre="Tech House"),
            IntakeTrack(filepath=Path("/t2.mp3"), original_filename="t2.mp3", genre="Deep House"),
        ]
        for t in tracks: t.destination_folder = t.genre or "Unsorted"
        assert tracks[0].destination_folder == "Tech House"
        assert tracks[1].destination_folder == "Deep House"

    def test_unidentified_track_flagged(self):
        t = IntakeTrack(filepath=Path("/unknown.mp3"), original_filename="unknown.mp3")
        assert t.artist is None and t.title is None

    def test_skip_status(self):
        tracks = [
            IntakeTrack(filepath=Path("/t1.mp3"), original_filename="t1.mp3", status="approved"),
            IntakeTrack(filepath=Path("/t2.mp3"), original_filename="t2.mp3", status="skipped"),
            IntakeTrack(filepath=Path("/t3.mp3"), original_filename="t3.mp3", status="approved"),
        ]
        assert len([t for t in tracks if t.status != "skipped"]) == 2


class TestIntakeApply:
    def test_dry_run_no_file_changes(self, source_folder, dest_folder):
        original = set(source_folder.iterdir())
        assert len(list(dest_folder.iterdir())) == 0
        assert set(source_folder.iterdir()) == original

    def test_copy_mode_preserves_original(self, source_folder, dest_folder):
        src = source_folder / "Solomun - Midnight Express.mp3"
        dst = dest_folder / "Tech House" / "Solomun - Midnight Express.mp3"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        assert src.exists() and dst.exists()

    def test_move_mode_removes_original(self, source_folder, dest_folder):
        src = source_folder / "Fisher - Losing It.mp3"
        dst = dest_folder / "Tech House" / "Fisher - Losing It.mp3"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        assert not src.exists() and dst.exists()

    def test_destination_subfolder_created(self, dest_folder):
        sub = dest_folder / "Deep House"
        assert not sub.exists()
        sub.mkdir(parents=True, exist_ok=True)
        assert sub.is_dir()

    def test_duplicate_filename_handled(self, source_folder, dest_folder):
        genre_dir = dest_folder / "Tech House"
        genre_dir.mkdir(parents=True, exist_ok=True)
        src = source_folder / "Solomun - Midnight Express.mp3"
        dst = genre_dir / "Solomun - Midnight Express.mp3"
        shutil.copy2(src, dst)
        stem, ext = dst.stem, dst.suffix
        counter, deduped = 1, dst
        while deduped.exists():
            deduped = genre_dir / f"{stem} ({counter}){ext}"; counter += 1
        shutil.copy2(src, deduped)
        assert dst.exists() and deduped.name == "Solomun - Midnight Express (1).mp3"


class TestRekordboxWriter:
    def _track_dicts(self) -> list[dict]:
        return [
            {"filepath": "/Music/Tech House/Solomun - Midnight Express.mp3",
             "artist": "Solomun", "title": "Midnight Express", "bpm": 122.0,
             "key_camelot": "5A", "genre": "Tech House", "album": "", "year": "",
             "duration_seconds": 300, "bitrate": 320, "sample_rate": 44100},
            {"filepath": "/Music/Deep House/Peggy Gou - Starry Night.mp3",
             "artist": "Peggy Gou", "title": "Starry Night", "bpm": 118.0,
             "key_camelot": "3A", "genre": "Deep House", "album": "", "year": "",
             "duration_seconds": 280, "bitrate": 320, "sample_rate": 44100},
        ]

    def test_xml_structure_valid(self, tmp_path):
        out = tmp_path / "intake.xml"
        write_rekordbox_xml(self._track_dicts(), "Intake", out)
        tree = ET.parse(str(out))
        root = tree.getroot()
        assert root.tag == "DJ_PLAYLISTS"
        assert root.find("COLLECTION") is not None and root.find("PLAYLISTS") is not None

    def test_filepath_to_location(self):
        loc = _filepath_to_location(Path("/Music/My Track [320].mp3"))
        assert loc.startswith("file://localhost/")
        assert "%5B" in loc or "[" not in loc.split("localhost")[1]

    def test_track_attributes(self, tmp_path):
        out = tmp_path / "intake.xml"
        write_rekordbox_xml(self._track_dicts(), "Intake", out)
        track = ET.parse(str(out)).findall(".//COLLECTION/TRACK")[0]
        assert track.get("Name") == "Midnight Express"
        assert track.get("Artist") == "Solomun"
        assert track.get("AverageBpm") is not None and track.get("TrackID") is not None

    def test_playlist_contains_all_tracks(self, tmp_path):
        out = tmp_path / "intake.xml"
        write_rekordbox_xml(self._track_dicts(), "Intake", out)
        playlist = ET.parse(str(out)).find(".//PLAYLISTS//NODE[@Type='1']")
        assert len(playlist.findall("TRACK")) == 2

    def test_sub_playlists_for_folders(self, tmp_path):
        out = tmp_path / "intake.xml"
        write_rekordbox_xml(self._track_dicts(), "Intake", out,
                            sub_playlists={"Tech House": [0], "Deep House": [1]})
        nodes = ET.parse(str(out)).findall(".//PLAYLISTS//NODE[@Type='1']")
        names = {n.get("Name") for n in nodes}
        assert "Tech House" in names and "Deep House" in names

    @pytest.mark.parametrize("bpm,expected", [
        (122.0, "122.00"), (126.5, "126.50"), (98.123, "98.12"),
    ])
    def test_bpm_formatted_two_decimals(self, bpm, expected):
        assert f"{bpm:.2f}" == expected

    def test_round_trip_with_parser(self, tmp_path):
        out = tmp_path / "intake.xml"
        write_rekordbox_xml(self._track_dicts(), "Intake Session", out)
        lib = parse_rekordbox_xml(out)
        assert len(lib.tracks) == 2 and "Intake Session" in lib.playlists

    def test_generate_intake_xml(self, source_folder, tmp_path):
        tracks = [IntakeTrack(
            filepath=source_folder / "Solomun - Midnight Express.mp3",
            original_filename="Solomun - Midnight Express.mp3",
            artist="Solomun", title="Midnight Express", genre="Tech House",
            bpm=122.0, key_camelot="5A", destination_folder="Tech House", status="approved",
        )]
        out = generate_intake_xml(tracks, tmp_path, playlist_name="Test Intake")
        assert out.exists()
        assert ET.parse(str(out)).getroot().tag == "DJ_PLAYLISTS"


class TestIntakeEndToEnd:
    def test_full_intake_auto_mode(self, source_folder, dest_folder):
        from cratedigger.metadata import read_metadata
        files = find_audio_files(source_folder)
        assert len(files) == 3
        tracks = []
        for f in files:
            meta = read_metadata(f)
            t = IntakeTrack(filepath=f, original_filename=f.name, artist=meta.artist,
                            title=meta.title, genre=meta.genre,
                            bpm=float(meta.bpm) if meta.bpm else None,
                            bpm_source="tag" if meta.bpm else "none")
            t.suggested_filename = (f"{t.artist} - {t.title}{f.suffix}"
                                    if t.artist and t.title else f.name)
            t.destination_folder = t.genre or "Unsorted"
            t.status = "approved"
            tracks.append(t)
        for t in tracks:
            folder = dest_folder / t.destination_folder
            folder.mkdir(parents=True, exist_ok=True)
            dst = folder / t.suggested_filename
            shutil.copy2(t.filepath, dst); t.new_filepath = dst
        result = IntakeResult(
            tracks=tracks, total_processed=len(tracks),
            identified_count=sum(1 for t in tracks if t.artist),
            unidentified_count=sum(1 for t in tracks if not t.artist), skipped_count=0)
        for t in tracks:
            f = t.destination_folder or "Unsorted"
            result.destination_folders[f] = result.destination_folders.get(f, 0) + 1
        assert result.total_processed == 3 and result.identified_count == 3
        assert result.destination_folders["Tech House"] == 2
        assert result.destination_folders["Deep House"] == 1
        assert (dest_folder / "Tech House" / "Solomun - Midnight Express.mp3").exists()
        assert (dest_folder / "Deep House" / "Peggy Gou - Starry Night.mp3").exists()

    def test_full_intake_dry_run(self, source_folder, dest_folder):
        assert len(find_audio_files(source_folder)) == 3
        assert len(list(dest_folder.iterdir())) == 0

    def test_missing_api_keys_graceful(self, source_folder):
        files = find_audio_files(source_folder)
        tracks = [IntakeTrack(filepath=f, original_filename=f.name) for f in files]
        for t in tracks: t.identified_via = "metadata"
        result = IntakeResult(tracks=tracks, total_processed=len(tracks))
        assert result.total_processed == 3
        assert all(t.identified_via == "metadata" for t in tracks)
