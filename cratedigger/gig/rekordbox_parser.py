"""Parse Rekordbox XML library exports."""

import logging
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CuePoint:
    """A single cue point (hot cue or memory cue)."""

    name: str
    cue_type: int  # 0 = hot cue, 1 = memory cue
    start: float  # position in seconds
    num: int  # slot number (0-7 for hot cues)
    red: int = 0
    green: int = 0
    blue: int = 0


@dataclass
class RekordboxTrack:
    """A track from a Rekordbox XML collection."""

    track_id: str
    name: str
    artist: str
    location: str  # file path (URL-decoded)
    total_time: int = 0  # seconds
    bpm: float | None = None
    key: str | None = None  # Tonality field
    has_beatgrid: bool = False
    cue_points: list[CuePoint] = field(default_factory=list)

    @property
    def hot_cues(self) -> list[CuePoint]:
        """Return only hot cues (Type=0)."""
        return [c for c in self.cue_points if c.cue_type == 0]

    @property
    def memory_cues(self) -> list[CuePoint]:
        """Return only memory cues (Type=1)."""
        return [c for c in self.cue_points if c.cue_type == 1]


@dataclass
class RekordboxPlaylist:
    """A playlist from a Rekordbox XML export."""

    name: str
    track_keys: list[str] = field(default_factory=list)  # TrackID references


@dataclass
class RekordboxLibrary:
    """Full parsed Rekordbox XML library."""

    tracks: dict[str, RekordboxTrack] = field(default_factory=dict)  # keyed by TrackID
    playlists: dict[str, RekordboxPlaylist] = field(default_factory=dict)  # keyed by name
    product_name: str = ""
    product_version: str = ""

    def get_playlist_tracks(self, playlist_name: str) -> list[RekordboxTrack]:
        """Get resolved tracks for a playlist by name."""
        playlist = self.playlists.get(playlist_name)
        if not playlist:
            return []
        return [
            self.tracks[key]
            for key in playlist.track_keys
            if key in self.tracks
        ]


def _decode_location(location: str) -> str:
    """Decode Rekordbox file:// URL to a filesystem path."""
    # Remove file://localhost prefix
    if location.startswith("file://localhost"):
        location = location[len("file://localhost"):]
    elif location.startswith("file://"):
        location = location[len("file://"):]

    return urllib.parse.unquote(location)


def _parse_track(track_elem: ET.Element) -> RekordboxTrack:
    """Parse a single TRACK element."""
    track_id = track_elem.get("TrackID", "")
    name = track_elem.get("Name", "")
    artist = track_elem.get("Artist", "")
    location = _decode_location(track_elem.get("Location", ""))
    total_time = int(track_elem.get("TotalTime", "0"))

    # BPM
    bpm_str = track_elem.get("AverageBpm", "")
    bpm = None
    if bpm_str:
        try:
            bpm_val = float(bpm_str)
            if bpm_val > 0:
                bpm = bpm_val
        except ValueError:
            pass

    # Key (Tonality)
    key = track_elem.get("Tonality") or None

    # Beatgrid (TEMPO elements)
    tempo_elems = track_elem.findall("TEMPO")
    has_beatgrid = len(tempo_elems) > 0

    # Cue points (POSITION_MARK elements)
    cue_points = []
    for pm in track_elem.findall("POSITION_MARK"):
        try:
            cue = CuePoint(
                name=pm.get("Name", ""),
                cue_type=int(pm.get("Type", "0")),
                start=float(pm.get("Start", "0")),
                num=int(pm.get("Num", "0")),
                red=int(pm.get("Red", "0")),
                green=int(pm.get("Green", "0")),
                blue=int(pm.get("Blue", "0")),
            )
            cue_points.append(cue)
        except (ValueError, TypeError) as e:
            logger.warning("Skipping malformed cue point in track %s: %s", name, e)

    return RekordboxTrack(
        track_id=track_id,
        name=name,
        artist=artist,
        location=location,
        total_time=total_time,
        bpm=bpm,
        key=key,
        has_beatgrid=has_beatgrid,
        cue_points=cue_points,
    )


def _parse_playlists(node: ET.Element, playlists: dict[str, RekordboxPlaylist]) -> None:
    """Recursively parse playlist NODE elements."""
    for child in node.findall("NODE"):
        node_type = child.get("Type", "0")
        name = child.get("Name", "")

        if node_type == "1":
            # Playlist node — collect track references
            track_keys = [t.get("Key", "") for t in child.findall("TRACK")]
            playlists[name] = RekordboxPlaylist(
                name=name,
                track_keys=[k for k in track_keys if k],
            )
        elif node_type == "0":
            # Folder node — recurse
            _parse_playlists(child, playlists)


def parse_rekordbox_xml(xml_path: Path) -> RekordboxLibrary:
    """Parse a Rekordbox XML export file.

    Args:
        xml_path: Path to the Rekordbox XML file.

    Returns:
        RekordboxLibrary with all tracks and playlists.

    Raises:
        FileNotFoundError: If the XML file doesn't exist.
        ET.ParseError: If the XML is malformed.
    """
    if not xml_path.exists():
        raise FileNotFoundError(f"Rekordbox XML not found: {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    library = RekordboxLibrary()

    # Product info
    product = root.find("PRODUCT")
    if product is not None:
        library.product_name = product.get("Name", "")
        library.product_version = product.get("Version", "")

    # Parse collection
    collection = root.find("COLLECTION")
    if collection is not None:
        for track_elem in collection.findall("TRACK"):
            track = _parse_track(track_elem)
            library.tracks[track.track_id] = track

    # Parse playlists
    playlists_root = root.find("PLAYLISTS")
    if playlists_root is not None:
        _parse_playlists(playlists_root, library.playlists)

    logger.info(
        "Parsed Rekordbox XML: %d tracks, %d playlists",
        len(library.tracks),
        len(library.playlists),
    )

    return library
