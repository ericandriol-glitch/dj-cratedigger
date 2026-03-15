"""Core intake orchestration — coordinates all pipeline steps."""

from pathlib import Path

from rich.console import Console

from .identify import step_analyze, step_fingerprint
from .models import IntakeResult
from .steps import (
    step_enrich,
    step_read_metadata,
    step_scan,
    step_suggest_filenames,
)

console = Console()


def run_intake(
    source: Path,
    dest: Path,
    dry_run: bool = False,
    auto: bool = False,
    move: bool = False,
    no_fingerprint: bool = False,
    no_analyze: bool = False,
    no_enrich: bool = False,
    force: bool = False,
) -> IntakeResult:
    """Run the full intake pipeline on a source folder.

    Orchestrates: scan -> read metadata -> fingerprint -> analyze ->
    enrich -> suggest filenames.

    Args:
        source: Folder containing new audio files to process.
        dest: Destination root folder for organized tracks.
        dry_run: If True, show what would happen without making changes.
        auto: If True, auto-accept all suggestions (skip review queue).
        move: If True, move files instead of copying.
        no_fingerprint: Skip AcoustID fingerprinting.
        no_analyze: Skip audio analysis (BPM/key detection).
        no_enrich: Skip MusicBrainz genre enrichment.
        force: Overwrite existing files at destination.

    Returns:
        IntakeResult with all processed tracks and summary stats.
    """
    source = Path(source).resolve()
    dest = Path(dest).resolve()

    if not source.is_dir():
        console.print(f"[red]Error:[/red] Source is not a directory: {source}")
        return IntakeResult()

    # Step 1: Scan
    files = step_scan(source)
    if not files:
        console.print("[yellow]No audio files found.[/yellow]")
        return IntakeResult()

    # Step 2: Read metadata
    tracks = step_read_metadata(files)

    # Step 3: Fingerprint
    if not no_fingerprint:
        step_fingerprint(tracks)

    # Step 4: Analyze
    if not no_analyze:
        step_analyze(tracks)

    # Step 5: Enrich
    if not no_enrich:
        step_enrich(tracks)

    # Step 6: Suggest filenames
    step_suggest_filenames(tracks)

    # Build result
    identified = sum(1 for t in tracks if t.identified_via != "none")
    result = IntakeResult(
        tracks=tracks,
        total_processed=len(tracks),
        identified_count=identified,
        unidentified_count=len(tracks) - identified,
    )

    return result
