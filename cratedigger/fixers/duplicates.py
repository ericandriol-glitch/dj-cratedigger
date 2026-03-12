"""Manage duplicate files — identify which to keep and which to remove."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..models import TrackAnalysis
from .parse_filename import parse_filename


@dataclass
class DuplicateAction:
    keep: TrackAnalysis
    remove: list[TrackAnalysis]
    reason: str


def plan_duplicate_cleanup(duplicate_groups: list[list[TrackAnalysis]]) -> list[DuplicateAction]:
    """
    For each duplicate group, decide which file to keep.

    Strategy:
    1. Prefer the file with the bitrate tag in filename (e.g., [320]) — it's the organized copy
    2. Among those, prefer higher bitrate
    3. Prefer more complete metadata
    4. Prefer the file with Artist - Title format in filename
    """
    actions: list[DuplicateAction] = []

    for group in duplicate_groups:
        if len(group) < 2:
            continue

        scored = []
        for track in group:
            score = 0
            parsed = parse_filename(track.file_path)

            # Prefer files with bitrate tag in filename (organized)
            if parsed.bitrate:
                score += 100

            # Prefer higher bitrate
            if track.metadata.bitrate:
                score += track.metadata.bitrate / 10000

            # Prefer more complete metadata
            meta = track.metadata
            for field in [meta.artist, meta.title, meta.album, meta.genre]:
                if field:
                    score += 5

            # Prefer Artist - Title format
            if parsed.artist and parsed.title:
                score += 20

            scored.append((score, track))

        scored.sort(key=lambda x: x[0], reverse=True)
        keep = scored[0][1]
        remove = [t for _, t in scored[1:]]

        # Build reason
        keep_parsed = parse_filename(keep.file_path)
        reasons = []
        if keep_parsed.bitrate:
            reasons.append(f"has [{keep_parsed.bitrate}] tag")
        if keep.metadata.bitrate:
            reasons.append(f"{keep.metadata.bitrate // 1000}kbps")
        reason = ", ".join(reasons) if reasons else "best metadata"

        actions.append(DuplicateAction(
            keep=keep,
            remove=remove,
            reason=reason,
        ))

    return actions


def apply_duplicate_cleanup(actions: list[DuplicateAction], trash_dir: Optional[Path] = None) -> tuple[int, list[str]]:
    """
    Remove duplicate files. Moves to trash_dir if provided, otherwise deletes.

    Returns:
        (files_removed, list of error messages)
    """
    removed = 0
    errors: list[str] = []

    if trash_dir:
        trash_dir.mkdir(parents=True, exist_ok=True)

    for action in actions:
        for track in action.remove:
            try:
                if trash_dir:
                    dest = trash_dir / track.file_path.name
                    # Handle name conflicts in trash
                    counter = 1
                    while dest.exists():
                        dest = trash_dir / f"{track.file_path.stem}_{counter}{track.file_path.suffix}"
                        counter += 1
                    track.file_path.rename(dest)
                else:
                    track.file_path.unlink()
                removed += 1
            except Exception as e:
                errors.append(f"{track.file_path.name}: {e}")

    return removed, errors
