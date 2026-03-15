"""Deep library audit scanner — categorize issues by severity."""

from dataclasses import dataclass, field
from pathlib import Path

from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from ..fixers.parse_filename import parse_filename
from ..metadata import read_metadata
from ..models import TrackAnalysis, TrackMetadata
from ..scanner import find_audio_files


@dataclass
class AuditResult:
    """Results of a library health audit."""

    path: Path
    total_tracks: int = 0
    health_score: int = 0  # 0-100
    critical: list[dict] = field(default_factory=list)  # corrupt, zero-byte
    high: list[dict] = field(default_factory=list)      # missing BPM, key, artist/title
    medium: list[dict] = field(default_factory=list)     # filename mismatch, dupes
    low: list[dict] = field(default_factory=list)        # missing year, album


def _is_zero_byte(path: Path) -> bool:
    """Check if a file is zero bytes."""
    try:
        return path.stat().st_size == 0
    except OSError:
        return True


def _is_corrupt(path: Path) -> bool:
    """Check if metadata read fails completely (likely corrupt)."""
    try:
        meta = read_metadata(path)
        # If every field is None, the file is likely unreadable
        return (
            meta.artist is None
            and meta.title is None
            and meta.duration_seconds is None
            and meta.bitrate is None
        )
    except Exception:
        return True


def _check_filename_tag_mismatch(path: Path, meta: TrackMetadata) -> str | None:
    """Compare parsed filename against metadata tags.

    Returns a description of the mismatch, or None if consistent.
    """
    parsed = parse_filename(path)

    if not parsed.artist and not parsed.title:
        return None  # Can't compare if filename has no structure

    mismatches: list[str] = []

    if parsed.artist and meta.artist:
        if parsed.artist.lower().strip() != meta.artist.lower().strip():
            mismatches.append(
                f"artist: filename='{parsed.artist}' vs tag='{meta.artist}'"
            )

    if parsed.title and meta.title:
        if parsed.title.lower().strip() != meta.title.lower().strip():
            mismatches.append(
                f"title: filename='{parsed.title}' vs tag='{meta.title}'"
            )

    return "; ".join(mismatches) if mismatches else None


def _find_true_duplicates(
    tracks: list[tuple[Path, TrackMetadata]],
) -> list[list[Path]]:
    """Find tracks that are likely duplicates based on artist+title.

    Returns groups of 2+ paths that share the same normalized artist+title.
    """
    from collections import defaultdict

    key_map: dict[tuple[str, str], list[Path]] = defaultdict(list)
    for path, meta in tracks:
        artist = (meta.artist or "").strip().lower()
        title = (meta.title or "").strip().lower()
        if artist and title:
            key_map[(artist, title)].append(path)

    return [paths for paths in key_map.values() if len(paths) >= 2]


def run_audit(path: Path, db_path: Path | None = None) -> AuditResult:
    """Deep scan a library folder and categorize all issues by severity.

    Issue detection:
        - Critical: corrupt files (read_metadata fails), zero-byte files
        - High: missing BPM, missing key, no artist or title
        - Medium: filename doesn't match tags, true duplicates
        - Low: missing year, missing album

    Args:
        path: Root directory to scan.
        db_path: Optional database path (reserved for future use).

    Returns:
        AuditResult with issues categorized by severity and a health score.
    """
    path = Path(path).resolve()
    if not path.is_dir():
        raise ValueError(f"Not a directory: {path}")

    audio_files = find_audio_files(path)
    result = AuditResult(path=path, total_tracks=len(audio_files))

    if not audio_files:
        result.health_score = 100
        return result

    # Scan all tracks
    tracks_with_meta: list[tuple[Path, TrackMetadata]] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Auditing library...", total=len(audio_files))

        for fp in audio_files:
            progress.advance(task)

            # Critical: zero-byte
            if _is_zero_byte(fp):
                result.critical.append({
                    "path": str(fp),
                    "issue": "zero-byte file",
                })
                continue

            # Read metadata
            meta = read_metadata(fp)

            # Critical: corrupt (all fields None)
            if (
                meta.artist is None
                and meta.title is None
                and meta.duration_seconds is None
                and meta.bitrate is None
                and meta.sample_rate is None
            ):
                result.critical.append({
                    "path": str(fp),
                    "issue": "corrupt or unreadable metadata",
                })
                continue

            tracks_with_meta.append((fp, meta))

            # High: missing BPM
            if not meta.bpm:
                result.high.append({
                    "path": str(fp),
                    "issue": "missing BPM",
                })

            # High: missing key
            if not meta.key:
                result.high.append({
                    "path": str(fp),
                    "issue": "missing key",
                })

            # High: no artist or title
            if not meta.artist and not meta.title:
                result.high.append({
                    "path": str(fp),
                    "issue": "missing artist and title",
                })
            elif not meta.artist:
                result.high.append({
                    "path": str(fp),
                    "issue": "missing artist",
                })
            elif not meta.title:
                result.high.append({
                    "path": str(fp),
                    "issue": "missing title",
                })

            # Medium: filename vs tag mismatch
            mismatch = _check_filename_tag_mismatch(fp, meta)
            if mismatch:
                result.medium.append({
                    "path": str(fp),
                    "issue": f"filename/tag mismatch: {mismatch}",
                })

            # Low: missing year
            if not meta.year:
                result.low.append({
                    "path": str(fp),
                    "issue": "missing year",
                })

            # Low: missing album
            if not meta.album:
                result.low.append({
                    "path": str(fp),
                    "issue": "missing album",
                })

    # Medium: duplicates (separate pass after collecting all metadata)
    dupe_groups = _find_true_duplicates(tracks_with_meta)
    for group in dupe_groups:
        for dupe_path in group:
            result.medium.append({
                "path": str(dupe_path),
                "issue": f"duplicate ({len(group)} copies)",
                "group": [str(p) for p in group],
            })

    # Calculate health score: 100 - (critical*10 + high*2 + medium*1 + low*0.2)
    penalty = (
        len(result.critical) * 10
        + len(result.high) * 2
        + len(result.medium) * 1
        + len(result.low) * 0.2
    )
    result.health_score = max(0, int(100 - penalty))

    return result
