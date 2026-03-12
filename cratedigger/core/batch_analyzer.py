"""Batch audio analysis with progress bar and resume support."""

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)

from cratedigger.core.analyzer import AudioFeatures, analyze_track
from cratedigger.utils.db import get_analyzed_paths, get_connection, store_results

logger = logging.getLogger(__name__)
console = Console()

BATCH_COMMIT_SIZE = 10


@dataclass
class BatchResult:
    """Summary of a batch analysis run."""

    total: int
    analyzed: int
    skipped: int
    failed: int
    duration_seconds: float


def batch_analyze(
    file_paths: list[Path],
    db_path: Path | None = None,
    force: bool = False,
) -> BatchResult:
    """Analyze a list of audio files with progress tracking and resume.

    Args:
        file_paths: Audio files to analyze.
        db_path: SQLite database path. Uses default if None.
        force: If True, re-analyze files already in the database.

    Returns:
        BatchResult with counts of analyzed, skipped, and failed files.
    """
    conn = get_connection(db_path)

    # Check which files are already analyzed (for resume)
    if force:
        to_skip: set[str] = set()
    else:
        to_skip = get_analyzed_paths(conn)

    pending = []
    skipped = 0
    for fp in file_paths:
        if str(fp) in to_skip:
            skipped += 1
        else:
            pending.append(fp)

    if not pending:
        console.print(f"  All {len(file_paths)} tracks already analyzed. Use --force to re-analyze.")
        return BatchResult(
            total=len(file_paths),
            analyzed=0,
            skipped=skipped,
            failed=0,
            duration_seconds=0.0,
        )

    console.print(f"  Analyzing {len(pending)} tracks ({skipped} already done)...\n")

    analyzed = 0
    failed = 0
    buffer: list[tuple[str, AudioFeatures]] = []
    start = time.perf_counter()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("Analyzing", total=len(pending))

        for filepath in pending:
            progress.update(task, description=f"[cyan]{filepath.name[:40]}[/cyan]")

            features = analyze_track(filepath)

            if features.bpm is not None or features.key is not None:
                analyzed += 1
            else:
                failed += 1

            buffer.append((str(filepath), features))

            # Commit every BATCH_COMMIT_SIZE tracks
            if len(buffer) >= BATCH_COMMIT_SIZE:
                store_results(conn, buffer)
                buffer.clear()

            progress.advance(task)

    # Flush remaining buffer
    if buffer:
        store_results(conn, buffer)

    duration = time.perf_counter() - start
    conn.close()

    # Print summary
    console.print(f"\n  [bold green]Done![/bold green] {analyzed} analyzed, {failed} failed, {skipped} skipped")
    console.print(f"  Time: {duration:.1f}s ({duration / max(len(pending), 1):.1f}s per track)")

    return BatchResult(
        total=len(file_paths),
        analyzed=analyzed,
        skipped=skipped,
        failed=failed,
        duration_seconds=duration,
    )
