"""Stale track detection — find never-played, dormant, and outlier tracks."""

import logging
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cratedigger.metadata import read_metadata
from cratedigger.scanner import find_audio_files

logger = logging.getLogger(__name__)


@dataclass
class StaleTrack:
    """A single stale track with reason for flagging."""

    filepath: Path
    artist: str
    title: str
    genre: str | None
    date_added: str | None  # from file creation/mtime
    reason: str  # "never_played", "dormant", "outlier"


@dataclass
class StaleResult:
    """Aggregated stale track analysis."""

    total_library: int
    stale_tracks: list[StaleTrack] = field(default_factory=list)
    by_genre: dict[str, list[StaleTrack]] = field(default_factory=dict)
    total_size_bytes: int = 0


def _get_file_date(filepath: Path) -> datetime:
    """Get the earliest meaningful date for a file (mtime as proxy)."""
    stat = filepath.stat()
    return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)


def _parse_rekordbox_play_counts(rekordbox_xml: Path) -> dict[str, int]:
    """Extract play counts from Rekordbox XML by file location.

    Returns:
        Mapping of decoded file path -> play count.
    """
    import urllib.parse
    import xml.etree.ElementTree as ET

    play_counts: dict[str, int] = {}
    try:
        tree = ET.parse(rekordbox_xml)
        root = tree.getroot()
        collection = root.find("COLLECTION")
        if collection is None:
            return play_counts
        for track_elem in collection.findall("TRACK"):
            location = track_elem.get("Location", "")
            # Decode file:// URL
            if location.startswith("file://localhost"):
                location = location[len("file://localhost"):]
            elif location.startswith("file://"):
                location = location[len("file://"):]
            location = urllib.parse.unquote(location)
            count = int(track_elem.get("PlayCount", "0"))
            play_counts[location] = count
    except Exception as exc:
        logger.warning("Failed to parse Rekordbox XML for play counts: %s", exc)
    return play_counts


def _compute_bpm_iqr(bpms: list[float]) -> tuple[float, float]:
    """Compute interquartile range for BPM values."""
    if len(bpms) < 4:
        return (min(bpms), max(bpms))
    sorted_bpms = sorted(bpms)
    n = len(sorted_bpms)
    q1 = sorted_bpms[n // 4]
    q3 = sorted_bpms[3 * n // 4]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return (lower, upper)


def _compute_energy_iqr(energies: list[float]) -> tuple[float, float]:
    """Compute interquartile range for energy values."""
    if len(energies) < 4:
        return (min(energies), max(energies))
    sorted_e = sorted(energies)
    n = len(sorted_e)
    q1 = sorted_e[n // 4]
    q3 = sorted_e[3 * n // 4]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return (lower, upper)


def _get_db_analysis(db_path: Path | None) -> dict[str, dict]:
    """Load BPM/energy analysis from the database.

    Returns:
        Mapping of filepath -> {"bpm": float|None, "energy": float|None}.
    """
    from cratedigger.utils.db import get_connection

    analysis: dict[str, dict] = {}
    try:
        conn = get_connection(db_path)
        rows = conn.execute(
            "SELECT filepath, bpm, energy FROM audio_analysis"
        ).fetchall()
        conn.close()
        for filepath, bpm, energy in rows:
            analysis[filepath] = {"bpm": bpm, "energy": energy}
    except Exception as exc:
        logger.warning("Could not read analysis DB: %s", exc)
    return analysis


def find_stale_tracks(
    library_path: Path,
    since_months: int = 12,
    rekordbox_xml: Path | None = None,
    db_path: Path | None = None,
) -> StaleResult:
    """Identify tracks that are never played, dormant, or outliers.

    Args:
        library_path: Root directory of music library.
        since_months: Months threshold for dormant detection.
        rekordbox_xml: Optional Rekordbox XML for play count analysis.
        db_path: Optional SQLite database path for BPM/energy data.

    Returns:
        StaleResult with all flagged tracks grouped by genre.
    """
    audio_files = find_audio_files(library_path)
    if not audio_files:
        return StaleResult(total_library=0)

    # Play counts from Rekordbox
    play_counts: dict[str, int] = {}
    if rekordbox_xml:
        play_counts = _parse_rekordbox_play_counts(rekordbox_xml)

    # DB analysis for outlier detection
    db_analysis = _get_db_analysis(db_path)

    # Collect BPMs and energies for IQR computation
    all_bpms = [
        v["bpm"] for v in db_analysis.values()
        if v.get("bpm") is not None
    ]
    all_energies = [
        v["energy"] for v in db_analysis.values()
        if v.get("energy") is not None
    ]

    bpm_bounds = _compute_bpm_iqr(all_bpms) if len(all_bpms) >= 4 else None
    energy_bounds = _compute_energy_iqr(all_energies) if len(all_energies) >= 4 else None

    now = datetime.now(timezone.utc)
    cutoff_seconds = since_months * 30 * 24 * 3600

    stale_tracks: list[StaleTrack] = []
    total_size = 0

    for fp in audio_files:
        meta = read_metadata(fp)
        artist = meta.artist or "Unknown"
        title = meta.title or fp.stem
        genre = meta.genre

        file_date = _get_file_date(fp)
        date_str = file_date.strftime("%Y-%m-%d")
        fp_str = str(fp)
        reason: str | None = None

        # Check 1: Never played (Rekordbox)
        if play_counts and fp_str in play_counts and play_counts[fp_str] == 0:
            reason = "never_played"
        elif play_counts:
            # Normalize path: check with forward slashes too
            fp_posix = fp.as_posix()
            for loc, count in play_counts.items():
                if (loc == fp_posix or loc.endswith(fp.name)) and count == 0:
                    reason = "never_played"
                    break

        # Check 2: Dormant (file not modified in N months)
        if reason is None:
            age_seconds = (now - file_date).total_seconds()
            if age_seconds > cutoff_seconds:
                reason = "dormant"

        # Check 3: Outlier BPM or energy
        if reason is None and fp_str in db_analysis:
            track_data = db_analysis[fp_str]
            bpm = track_data.get("bpm")
            energy = track_data.get("energy")
            if bpm is not None and bpm_bounds is not None:
                if bpm < bpm_bounds[0] or bpm > bpm_bounds[1]:
                    reason = "outlier"
            if reason is None and energy is not None and energy_bounds is not None:
                if energy < energy_bounds[0] or energy > energy_bounds[1]:
                    reason = "outlier"

        if reason:
            size = fp.stat().st_size
            total_size += size
            stale_tracks.append(StaleTrack(
                filepath=fp,
                artist=artist,
                title=title,
                genre=genre,
                date_added=date_str,
                reason=reason,
            ))

    # Group by genre
    by_genre: dict[str, list[StaleTrack]] = defaultdict(list)
    for track in stale_tracks:
        key = track.genre or "Unknown"
        by_genre[key].append(track)

    return StaleResult(
        total_library=len(audio_files),
        stale_tracks=stale_tracks,
        by_genre=dict(by_genre),
        total_size_bytes=total_size,
    )
