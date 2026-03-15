"""Pre-flight validation checks for a USB stick or folder before a gig."""

import logging
import platform
import statistics
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ..metadata import read_metadata
from ..models import TrackMetadata
from ..scanner import find_audio_files

logger = logging.getLogger(__name__)


@dataclass
class PreflightResult:
    """Results from all pre-flight checks on a folder/USB."""

    path: Path
    total_tracks: int = 0
    # Check results
    corrupt_files: list[Path] = field(default_factory=list)
    zero_byte_files: list[Path] = field(default_factory=list)
    missing_bpm: list[Path] = field(default_factory=list)
    missing_key: list[Path] = field(default_factory=list)
    missing_genre: list[Path] = field(default_factory=list)
    duplicate_filenames: list[list[Path]] = field(default_factory=list)
    # Stats
    bpm_range: tuple[float, float] | None = None
    bpm_median: float | None = None
    key_distribution: dict[str, int] = field(default_factory=dict)
    genre_distribution: dict[str, int] = field(default_factory=dict)
    total_duration_seconds: float = 0.0
    total_size_bytes: int = 0
    # Rekordbox checks (optional)
    rekordbox_analyzed: int | None = None
    rekordbox_not_analyzed: list[str] | None = None
    tracks_with_cues: int | None = None
    tracks_without_cues: list[str] | None = None
    # Filesystem
    filesystem_type: str | None = None

    @property
    def issue_count(self) -> int:
        """Total number of issues found."""
        return (
            len(self.corrupt_files)
            + len(self.zero_byte_files)
            + len(self.missing_bpm)
            + len(self.missing_key)
            + len(self.missing_genre)
            + len(self.duplicate_filenames)
        )

    @property
    def is_clean(self) -> bool:
        """True if no issues were found."""
        return self.issue_count == 0


def _detect_filesystem(path: Path) -> str | None:
    """Detect filesystem type for a path (Windows only).

    Args:
        path: Any path on the target volume.

    Returns:
        Filesystem type string (e.g. 'FAT32', 'exFAT', 'NTFS') or None.
    """
    if platform.system() != "Windows":
        return None
    try:
        drive = str(path.resolve()).split(":")[0] + ":"
        result = subprocess.run(
            ["fsutil", "fsinfo", "volumeinfo", drive],
            capture_output=True,
            text=True,
            timeout=5,
        )
        for line in result.stdout.splitlines():
            if "File System Name" in line:
                return line.split(":")[-1].strip()
    except Exception:
        logger.debug("Could not detect filesystem for %s", path, exc_info=True)
    return None


def _check_corrupt_and_zero(
    audio_files: list[Path],
) -> tuple[list[Path], list[Path], dict[Path, TrackMetadata]]:
    """Check for corrupt and zero-byte files, returning metadata for good files.

    Args:
        audio_files: List of audio file paths.

    Returns:
        Tuple of (corrupt_files, zero_byte_files, metadata_map).
    """
    corrupt: list[Path] = []
    zero_byte: list[Path] = []
    metadata_map: dict[Path, TrackMetadata] = {}

    for fp in audio_files:
        try:
            size = fp.stat().st_size
        except OSError:
            corrupt.append(fp)
            continue

        if size == 0:
            zero_byte.append(fp)
            continue

        meta = read_metadata(fp)
        # If read_metadata returns a completely empty TrackMetadata with no
        # duration, the file is likely corrupt (unreadable audio data).
        if meta.duration_seconds is None and meta.bitrate is None:
            corrupt.append(fp)
        else:
            metadata_map[fp] = meta

    return corrupt, zero_byte, metadata_map


def _check_missing_metadata(
    metadata_map: dict[Path, TrackMetadata],
) -> tuple[list[Path], list[Path], list[Path]]:
    """Check for missing BPM, key, and genre tags.

    Args:
        metadata_map: Map of file path to its metadata.

    Returns:
        Tuple of (missing_bpm, missing_key, missing_genre).
    """
    missing_bpm: list[Path] = []
    missing_key: list[Path] = []
    missing_genre: list[Path] = []

    for fp, meta in metadata_map.items():
        if not meta.bpm:
            missing_bpm.append(fp)
        if not meta.key:
            missing_key.append(fp)
        if not meta.genre:
            missing_genre.append(fp)

    return missing_bpm, missing_key, missing_genre


def _check_duplicate_filenames(audio_files: list[Path]) -> list[list[Path]]:
    """Find files with the same name in different folders (confuses CDJs).

    Args:
        audio_files: List of audio file paths.

    Returns:
        List of groups where each group has 2+ files sharing a filename.
    """
    name_map: dict[str, list[Path]] = defaultdict(list)
    for fp in audio_files:
        name_map[fp.name.lower()].append(fp)

    return [paths for paths in name_map.values() if len(paths) > 1]


def _compute_stats(
    metadata_map: dict[Path, TrackMetadata],
) -> tuple[
    tuple[float, float] | None,
    float | None,
    dict[str, int],
    dict[str, int],
    float,
]:
    """Compute BPM/key/genre/duration statistics.

    Args:
        metadata_map: Map of file path to its metadata.

    Returns:
        Tuple of (bpm_range, bpm_median, key_dist, genre_dist, total_duration).
    """
    bpms: list[float] = []
    keys: list[str] = []
    genres: list[str] = []
    total_duration = 0.0

    for meta in metadata_map.values():
        if meta.bpm:
            bpms.append(meta.bpm)
        if meta.key:
            keys.append(meta.key)
        if meta.genre:
            genres.append(meta.genre)
        if meta.duration_seconds:
            total_duration += meta.duration_seconds

    bpm_range = (min(bpms), max(bpms)) if bpms else None
    bpm_median = statistics.median(bpms) if bpms else None
    key_dist = dict(Counter(keys).most_common())
    genre_dist = dict(Counter(genres).most_common())

    return bpm_range, bpm_median, key_dist, genre_dist, total_duration


def _check_rekordbox(
    rekordbox_xml: Path,
) -> tuple[int, list[str], int, list[str]]:
    """Cross-reference tracks with a Rekordbox XML export.

    Args:
        rekordbox_xml: Path to Rekordbox XML file.

    Returns:
        Tuple of (analyzed_count, not_analyzed_names,
                  with_cues_count, without_cues_names).
    """
    from ..gig.rekordbox_parser import parse_rekordbox_xml

    library = parse_rekordbox_xml(rekordbox_xml)

    analyzed = 0
    not_analyzed: list[str] = []
    with_cues = 0
    without_cues: list[str] = []

    for track in library.tracks.values():
        label = f"{track.artist} - {track.name}"
        if track.has_beatgrid:
            analyzed += 1
        else:
            not_analyzed.append(label)
        if track.cue_points:
            with_cues += 1
        else:
            without_cues.append(label)

    return analyzed, not_analyzed, with_cues, without_cues


def run_preflight(
    path: Path,
    rekordbox_xml: Path | None = None,
    strict: bool = False,
) -> PreflightResult:
    """Run all pre-flight checks on a folder or USB stick.

    Args:
        path: Root folder to scan.
        rekordbox_xml: Optional Rekordbox XML for cross-referencing.
        strict: Enable strict checks (reserved for future use).

    Returns:
        PreflightResult with all check outcomes and statistics.
    """
    path = Path(path).resolve()
    result = PreflightResult(path=path)

    # 1. Scan for audio files
    audio_files = find_audio_files(path)
    result.total_tracks = len(audio_files)

    if not audio_files:
        return result

    # 2. Corrupt / zero-byte + collect metadata
    corrupt, zero_byte, metadata_map = _check_corrupt_and_zero(audio_files)
    result.corrupt_files = corrupt
    result.zero_byte_files = zero_byte

    # 3. Missing metadata
    missing_bpm, missing_key, missing_genre = _check_missing_metadata(metadata_map)
    result.missing_bpm = missing_bpm
    result.missing_key = missing_key
    result.missing_genre = missing_genre

    # 4. Duplicate filenames
    result.duplicate_filenames = _check_duplicate_filenames(audio_files)

    # 5. Stats
    bpm_range, bpm_median, key_dist, genre_dist, total_dur = _compute_stats(
        metadata_map
    )
    result.bpm_range = bpm_range
    result.bpm_median = bpm_median
    result.key_distribution = key_dist
    result.genre_distribution = genre_dist
    result.total_duration_seconds = total_dur

    # Total size on disk
    result.total_size_bytes = sum(
        fp.stat().st_size for fp in audio_files if fp.exists()
    )

    # 6. Rekordbox cross-reference
    if rekordbox_xml:
        analyzed, not_analyzed, with_cues, without_cues = _check_rekordbox(
            rekordbox_xml
        )
        result.rekordbox_analyzed = analyzed
        result.rekordbox_not_analyzed = not_analyzed
        result.tracks_with_cues = with_cues
        result.tracks_without_cues = without_cues

    # 7. Filesystem detection
    result.filesystem_type = _detect_filesystem(path)

    return result
