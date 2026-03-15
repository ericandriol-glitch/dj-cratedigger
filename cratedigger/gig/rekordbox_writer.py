"""Write Rekordbox 7 compatible XML files for import."""

import logging
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

_KIND_MAP = {
    ".mp3": "MP3 File", ".wav": "WAV File", ".flac": "FLAC File",
    ".aiff": "AIFF File", ".aif": "AIFF File", ".m4a": "M4A File",
    ".aac": "AAC File", ".ogg": "OGG File", ".alac": "ALAC File",
}


@dataclass
class ExportCuePoint:
    """A cue point to write into Rekordbox XML."""
    name: str
    position_seconds: float
    num: int  # hot cue slot 0-7
    red: int = 40
    green: int = 226
    blue: int = 160


@dataclass
class ExportTrack:
    """A track to include in the Rekordbox XML export."""
    location: str
    name: str = ""
    artist: str = ""
    bpm: float | None = None
    key: str | None = None
    cue_points: list[ExportCuePoint] = field(default_factory=list)


def _filepath_to_location(filepath: Path) -> str:
    """Convert a filesystem path to Rekordbox file://localhost/ URL format."""
    posix = str(filepath.resolve()).replace("\\", "/")
    if not posix.startswith("/"):
        posix = "/" + posix
    return "file://localhost" + urllib.parse.quote(posix, safe="/:")


def _normalize_bitrate(bitrate: int) -> int:
    """Normalize bitrate to kbps. Mutagen returns bps (320000), Rekordbox expects kbps (320)."""
    if bitrate > 9999:
        return bitrate // 1000
    return bitrate


def _safe(value: object) -> str:
    """Convert value to string, treating None as empty string."""
    return "" if value is None else str(value)


def _track_to_xml_element(track: dict, track_id: int) -> ET.Element:
    """Convert a track dict to a Rekordbox TRACK XML element."""
    fp = Path(track.get("filepath", ""))
    size = track.get("size", 0)
    if not size and fp.exists():
        size = fp.stat().st_size
    bpm = track.get("bpm")
    bpm_str = f"{float(bpm):.2f}" if bpm else "0.00"

    elem = ET.Element("TRACK", **{
        "TrackID": str(track_id),
        "Name": _safe(track.get("title", "")),
        "Artist": _safe(track.get("artist", "")),
        "Album": _safe(track.get("album", "")),
        "Genre": _safe(track.get("genre", "")),
        "Kind": _KIND_MAP.get(fp.suffix.lower(), "Audio File"),
        "Size": str(size),
        "TotalTime": str(int(track.get("duration_seconds", 0) or 0)),
        "DiscNumber": _safe(track.get("disc_number", "0")),
        "TrackNumber": _safe(track.get("track_number", "0")),
        "Year": _safe(track.get("year", "")),
        "AverageBpm": bpm_str,
        "DateAdded": str(track.get("date_added", date.today().isoformat())),
        "BitRate": str(_normalize_bitrate(track.get("bitrate", 0) or 0)),
        "SampleRate": str(track.get("sample_rate", 0) or 0),
        "Comments": _safe(track.get("comment", "")),
        "Rating": _safe(track.get("rating", "0")),
        "Location": _filepath_to_location(fp),
        "Tonality": _safe(track.get("key_camelot", "")),
        "Label": _safe(track.get("label", "")),
        "Mix": _safe(track.get("mix", "")),
    })
    if bpm and float(bpm) > 0:
        ET.SubElement(elem, "TEMPO", Inizio="0.000", Bpm=bpm_str, Metro="4/4", Battito="1")
    for cue in track.get("cue_points", []):
        if isinstance(cue, ExportCuePoint):
            ET.SubElement(elem, "POSITION_MARK", Name=cue.name, Type="0",
                          Start=f"{cue.position_seconds:.3f}", Num=str(cue.num),
                          Red=str(cue.red), Green=str(cue.green), Blue=str(cue.blue))
        elif isinstance(cue, dict):
            ET.SubElement(elem, "POSITION_MARK", Name=str(cue.get("name", "")),
                          Type=str(cue.get("type", "0")),
                          Start=f"{float(cue.get('start', 0)):.3f}",
                          Num=str(cue.get("num", 0)), Red=str(cue.get("red", 40)),
                          Green=str(cue.get("green", 226)), Blue=str(cue.get("blue", 160)))
    return elem


def _build_playlist_nodes(
    playlist_name: str, track_ids: list[int],
    sub_playlists: dict[str, list[int]] | None,
) -> ET.Element:
    """Build the PLAYLISTS XML structure with optional sub-playlists.

    Args:
        playlist_name: Name of the top-level playlist or folder.
        track_ids: All track IDs (1-based).
        sub_playlists: Optional folder_name -> list of track indices (0-based).
    """
    playlists = ET.Element("PLAYLISTS")
    root_node = ET.SubElement(playlists, "NODE", Type="0", Name="ROOT", Count="1")
    if sub_playlists:
        folder = ET.SubElement(root_node, "NODE", Type="0", Name=playlist_name,
                               Count=str(len(sub_playlists)))
        for sub_name, indices in sub_playlists.items():
            sub_ids = [track_ids[i] for i in indices if i < len(track_ids)]
            node = ET.SubElement(folder, "NODE", Name=sub_name, Type="1",
                                 KeyType="0", Entries=str(len(sub_ids)))
            for tid in sub_ids:
                ET.SubElement(node, "TRACK", Key=str(tid))
    else:
        node = ET.SubElement(root_node, "NODE", Name=playlist_name, Type="1",
                             KeyType="0", Entries=str(len(track_ids)))
        for tid in track_ids:
            ET.SubElement(node, "TRACK", Key=str(tid))
    return playlists


def write_rekordbox_xml(
    tracks: list[dict], playlist_name: str, output_path: Path,
    sub_playlists: dict[str, list[int]] | None = None,
) -> Path:
    """Generate a Rekordbox 7 compatible XML import file.

    Args:
        tracks: List of track dicts with keys: filepath, artist, title,
            album, genre, bpm, key_camelot, year, duration_seconds,
            bitrate, sample_rate. Optional: size, comment, label, mix.
        playlist_name: Name for the playlist in Rekordbox.
        output_path: Where to write the XML file.
        sub_playlists: Optional folder_name -> list of track indices (0-based).

    Returns:
        Path to the written XML file.
    """
    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
    ET.SubElement(root, "PRODUCT", Name="rekordbox", Version="7.0.1", Company="Pioneer DJ")
    collection = ET.SubElement(root, "COLLECTION", Entries=str(len(tracks)))
    track_ids: list[int] = []
    for i, track in enumerate(tracks, 1):
        collection.append(_track_to_xml_element(track, i))
        track_ids.append(i)
    root.append(_build_playlist_nodes(playlist_name, track_ids, sub_playlists))
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(output_path), encoding="UTF-8", xml_declaration=True)
    logger.info("Wrote Rekordbox 7 XML: %d tracks to %s", len(tracks), output_path)
    return output_path


def generate_intake_xml(
    tracks: list, output_dir: Path, playlist_name: str | None = None,
) -> Path:
    """Generate Rekordbox XML from intake results.

    Args:
        tracks: IntakeTrack objects from the intake pipeline.
        output_dir: Directory to write the XML file into.
        playlist_name: Custom playlist name. Defaults to "Intake YYYY-MM-DD".

    Returns:
        Path to the generated XML file.
    """
    today = date.today().isoformat()
    if not playlist_name:
        playlist_name = f"Intake {today}"
    track_dicts: list[dict] = []
    folder_groups: dict[str, list[int]] = {}
    for i, t in enumerate(tracks):
        fp = Path(t.new_filepath or t.filepath)
        size = fp.stat().st_size if fp.exists() else 0
        track_dicts.append({
            "filepath": fp, "artist": t.artist or "", "title": t.title or "",
            "album": t.album or "", "genre": t.genre or "", "bpm": t.bpm,
            "key_camelot": t.key_camelot or "", "year": t.year or "",
            "duration_seconds": 0, "bitrate": 0, "sample_rate": 0,
            "size": size, "date_added": today,
        })
        folder = t.destination_folder or "Unsorted"
        folder_groups.setdefault(folder, []).append(i)
    sub = folder_groups if len(folder_groups) > 1 else None
    output_path = output_dir / f"intake-{today}.xml"
    return write_rekordbox_xml(track_dicts, playlist_name, output_path, sub)
