"""Write Rekordbox-compatible XML files with cue points."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


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

    location: str  # file path
    name: str = ""
    artist: str = ""
    bpm: float | None = None
    key: str | None = None
    cue_points: list[ExportCuePoint] = field(default_factory=list)


def _encode_location(filepath: str) -> str:
    """Encode a filesystem path to Rekordbox file:// URL format."""
    import urllib.parse
    # Rekordbox uses file://localhost prefix
    encoded = urllib.parse.quote(filepath, safe="/:")
    return f"file://localhost{encoded}"


def write_rekordbox_xml(
    tracks: list[ExportTrack],
    output_path: Path,
    playlist_name: str | None = None,
) -> Path:
    """Write a Rekordbox-importable XML file.

    Args:
        tracks: Tracks to include with optional cue points.
        output_path: Where to write the XML file.
        playlist_name: Optional playlist name to create.

    Returns:
        Path to the written XML file.
    """
    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")

    # Product info
    ET.SubElement(root, "PRODUCT", Name="CrateDigger", Version="1.0")

    # Collection
    collection = ET.SubElement(root, "COLLECTION", Entries=str(len(tracks)))

    for i, track in enumerate(tracks, 1):
        track_id = str(i)
        attrs: dict[str, str] = {
            "TrackID": track_id,
            "Name": track.name,
            "Artist": track.artist,
            "Location": _encode_location(track.location),
        }

        if track.bpm is not None:
            attrs["AverageBpm"] = f"{track.bpm:.2f}"
        if track.key is not None:
            attrs["Tonality"] = track.key

        track_elem = ET.SubElement(collection, "TRACK", **attrs)

        # Add beatgrid if BPM present
        if track.bpm is not None:
            ET.SubElement(track_elem, "TEMPO",
                          Inizio="0.100", Bpm=f"{track.bpm:.2f}", Metro="4/4")

        # Add cue points
        for cue in track.cue_points:
            ET.SubElement(track_elem, "POSITION_MARK",
                          Name=cue.name,
                          Type="0",  # hot cue
                          Start=f"{cue.position_seconds:.3f}",
                          Num=str(cue.num),
                          Red=str(cue.red),
                          Green=str(cue.green),
                          Blue=str(cue.blue))

    # Playlists
    playlists = ET.SubElement(root, "PLAYLISTS")
    root_node = ET.SubElement(playlists, "NODE", Type="0", Name="root")

    if playlist_name:
        playlist_node = ET.SubElement(root_node, "NODE",
                                       Name=playlist_name,
                                       Type="1",
                                       Entries=str(len(tracks)))
        for i in range(1, len(tracks) + 1):
            ET.SubElement(playlist_node, "TRACK", Key=str(i))

    # Write with XML declaration
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(output_path), encoding="UTF-8", xml_declaration=True)

    logger.info("Wrote Rekordbox XML: %d tracks to %s", len(tracks), output_path)
    return output_path
