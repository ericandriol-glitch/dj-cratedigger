"""Enrich write-back: fill missing BPM/key tags from Essentia analysis."""

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from cratedigger.metadata import read_metadata
from cratedigger.utils.db import get_connection

logger = logging.getLogger(__name__)
console = Console()

CONFIDENCE_THRESHOLD = 0.85


@dataclass
class EnrichAction:
    """A proposed tag write for a single track."""

    file_path: Path
    field: str
    old_value: str | None
    new_value: str
    confidence: float


def plan_enrichment(
    audio_files: list[Path],
    db_path: Path | None = None,
    force: bool = False,
) -> list[EnrichAction]:
    """Plan tag enrichment from Essentia analysis results.

    Args:
        audio_files: Files to consider for enrichment.
        db_path: SQLite database path.
        force: If True, overwrite existing tags.

    Returns:
        List of proposed tag writes.
    """
    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT filepath, bpm, bpm_confidence, key_camelot, key_confidence "
        "FROM audio_analysis"
    )
    analysis_map = {}
    for row in cursor.fetchall():
        analysis_map[row[0]] = {
            "bpm": row[1],
            "bpm_confidence": row[2],
            "key": row[3],
            "key_confidence": row[4],
        }
    conn.close()

    actions: list[EnrichAction] = []

    for filepath in audio_files:
        fp_str = str(filepath)
        if fp_str not in analysis_map:
            continue

        analysis = analysis_map[fp_str]
        meta = read_metadata(filepath)

        # BPM: fill gap or overwrite if forced
        if analysis["bpm"] is not None:
            has_tag = meta.bpm is not None
            if not has_tag or force:
                actions.append(EnrichAction(
                    file_path=filepath,
                    field="bpm",
                    old_value=str(meta.bpm) if meta.bpm else None,
                    new_value=str(round(analysis["bpm"])),
                    confidence=analysis["bpm_confidence"],
                ))

        # Key: fill gap or overwrite if forced
        if analysis["key"] is not None:
            from cratedigger.core.analyzer import musical_key_to_camelot
            has_tag = meta.key is not None and meta.key.strip() != ""
            # Check if tag key is same as detected (just different notation)
            tag_matches = False
            if has_tag and meta.key:
                tag_camelot = musical_key_to_camelot(meta.key.strip())
                tag_matches = tag_camelot == analysis["key"]
            if (not has_tag or force) and not tag_matches:
                actions.append(EnrichAction(
                    file_path=filepath,
                    field="key",
                    old_value=meta.key if meta.key else None,
                    new_value=analysis["key"],
                    confidence=analysis["key_confidence"],
                ))

    return actions


def print_enrichment_plan(actions: list[EnrichAction]) -> None:
    """Display proposed enrichment changes."""
    if not actions:
        console.print("  [green]No enrichment needed — all tags already filled.[/green]\n")
        return

    # Group by file
    by_file: dict[Path, list[EnrichAction]] = {}
    for action in actions:
        by_file.setdefault(action.file_path, []).append(action)

    table = Table(title=f"Proposed Enrichment ({len(actions)} changes across {len(by_file)} files)")
    table.add_column("Track", style="cyan", max_width=45)
    table.add_column("Field", style="yellow")
    table.add_column("Before", style="red")
    table.add_column("After", style="green")
    table.add_column("Confidence", justify="right")

    for filepath, file_actions in sorted(by_file.items()):
        for i, action in enumerate(file_actions):
            name = filepath.name[:45] if i == 0 else ""
            conf_style = "green" if action.confidence >= CONFIDENCE_THRESHOLD else "yellow"
            table.add_row(
                name,
                action.field.upper(),
                action.old_value or "—",
                action.new_value,
                f"[{conf_style}]{action.confidence:.2f}[/{conf_style}]",
            )

    console.print(table)


def apply_enrichment(
    actions: list[EnrichAction],
    backup_dir: Path | None = None,
) -> tuple[int, list[str]]:
    """Apply enrichment by writing tags to files.

    Args:
        actions: Enrichment actions to apply.
        backup_dir: Directory for file backups. Created if needed.

    Returns:
        (success_count, list of error messages)
    """
    from cratedigger.fixers.tags import TagFix, apply_tag_fixes

    # Create backups
    if backup_dir:
        backup_dir.mkdir(parents=True, exist_ok=True)

    backed_up: set[Path] = set()
    for action in actions:
        if action.file_path not in backed_up:
            if backup_dir:
                dest = backup_dir / action.file_path.name
                # Avoid overwriting existing backups
                if dest.exists():
                    stem = dest.stem
                    suffix = dest.suffix
                    counter = 1
                    while dest.exists():
                        dest = backup_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                shutil.copy2(action.file_path, dest)
            backed_up.add(action.file_path)

    # Convert to TagFix format
    fixes = [
        TagFix(
            file_path=action.file_path,
            field=action.field,
            old_value=action.old_value,
            new_value=action.new_value,
        )
        for action in actions
    ]

    return apply_tag_fixes(fixes)
