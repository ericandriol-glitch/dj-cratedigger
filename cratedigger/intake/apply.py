"""Apply approved intake changes — copy/move files, write tags, store analysis."""

import logging
import shutil
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from .models import IntakeTrack

logger = logging.getLogger(__name__)
console = Console()


def _write_tags(filepath: Path, track: IntakeTrack) -> None:
    """Write approved metadata tags to the destination file.

    Uses the existing TagFix infrastructure from fixers/tags.py.
    """
    from cratedigger.fixers.tags import TagFix, apply_tag_fixes

    fixes: list[TagFix] = []

    if track.artist:
        fixes.append(TagFix(file_path=filepath, field="artist", old_value=None, new_value=track.artist))
    if track.title:
        fixes.append(TagFix(file_path=filepath, field="title", old_value=None, new_value=track.title))
    if track.genre:
        fixes.append(TagFix(file_path=filepath, field="genre", old_value=None, new_value=track.genre))
    if track.year:
        fixes.append(TagFix(file_path=filepath, field="year", old_value=None, new_value=track.year))
    if track.bpm:
        fixes.append(TagFix(file_path=filepath, field="bpm", old_value=None, new_value=str(round(track.bpm))))
    if track.key_camelot:
        fixes.append(TagFix(file_path=filepath, field="key", old_value=None, new_value=track.key_camelot))

    if fixes:
        success, errors = apply_tag_fixes(fixes)
        if errors:
            for err in errors:
                logger.warning("Tag write error: %s", err)


def _store_analysis(track: IntakeTrack, dest_path: Path) -> None:
    """Store analysis results in the SQLite database."""
    try:
        from cratedigger.utils.db import get_connection

        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO audio_analysis
               (filepath, bpm, bpm_confidence, key_camelot, key_confidence, energy, genre)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(dest_path),
                track.bpm,
                1.0 if track.bpm else 0.0,
                track.key_camelot,
                1.0 if track.key_camelot else 0.0,
                track.energy,
                track.genre,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("DB storage failed for %s: %s", dest_path.name, exc)


def apply_intake(
    tracks: list[IntakeTrack],
    dest: Path,
    move: bool = False,
    dry_run: bool = False,
) -> dict:
    """Apply approved intake changes to the filesystem.

    For each approved track:
    1. Create destination subfolder if needed.
    2. Copy (default) or move the file.
    3. Write enriched tags to the new file.
    4. Store analysis results in the database.

    Args:
        tracks: List of IntakeTrack objects (post-review).
        dest: Destination root folder.
        move: If True, move files instead of copying.
        dry_run: If True, log changes without applying them.

    Returns:
        Stats dict with counts of actions taken.
    """
    dest = Path(dest).resolve()
    approved = [t for t in tracks if t.status in ("approved", "edited")]
    skipped = [t for t in tracks if t.status == "skipped"]

    stats: dict = {
        "copied": 0,
        "moved": 0,
        "tags_written": 0,
        "errors": [],
        "skipped": len(skipped),
    }

    if not approved:
        console.print("\n[yellow]No approved tracks to process.[/yellow]")
        return stats

    action_word = "Moving" if move else "Copying"
    console.print(f"\n[bold cyan]{action_word}[/bold cyan] {len(approved)} approved tracks")

    if dry_run:
        console.print("[yellow]DRY RUN — no files will be modified[/yellow]\n")
        for track in approved:
            folder = track.destination_folder or "unsorted"
            dest_path = dest / folder / (track.suggested_filename or track.original_filename)
            console.print(f"  [dim]{track.original_filename}[/dim]")
            console.print(f"    -> {dest_path}")
        stats["copied"] = len(approved)
        return stats

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"),
        BarColumn(), MofNCompleteColumn(), transient=True,
    ) as progress:
        task = progress.add_task(f"{action_word}...", total=len(approved))

        for track in approved:
            try:
                folder = track.destination_folder or "unsorted"
                dest_dir = dest / folder
                dest_dir.mkdir(parents=True, exist_ok=True)

                filename = track.suggested_filename or track.original_filename
                dest_path = dest_dir / filename

                # Handle existing file
                if dest_path.exists():
                    stem = dest_path.stem
                    suffix = dest_path.suffix
                    counter = 1
                    while dest_path.exists():
                        dest_path = dest_dir / f"{stem} ({counter}){suffix}"
                        counter += 1

                if move:
                    shutil.move(str(track.filepath), str(dest_path))
                    stats["moved"] += 1
                else:
                    shutil.copy2(str(track.filepath), str(dest_path))
                    stats["copied"] += 1

                track.new_filepath = dest_path

                # Write tags to the new file
                try:
                    _write_tags(dest_path, track)
                    stats["tags_written"] += 1
                except Exception as exc:
                    logger.warning("Tag write failed for %s: %s", dest_path.name, exc)

                # Store analysis in DB
                _store_analysis(track, dest_path)

            except Exception as exc:
                error_msg = f"{track.original_filename}: {exc}"
                stats["errors"].append(error_msg)
                logger.warning("Apply failed: %s", error_msg)

            progress.advance(task)

    action_key = "moved" if move else "copied"
    console.print(f"  [green]{stats[action_key]}[/green] files {action_key}")
    if stats["errors"]:
        console.print(f"  [red]{len(stats['errors'])}[/red] errors")

    return stats
