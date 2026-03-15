"""CLI command for the intake pipeline."""

from pathlib import Path

import click
from rich.console import Console

from . import cli  # noqa: E402

console = Console()


@cli.command()
@click.argument("source", type=click.Path(exists=True))
@click.option("--dest", required=True, type=click.Path(), help="Destination root folder")
@click.option("--dry-run", is_flag=True, help="Show what would happen without changes")
@click.option("--auto", is_flag=True, help="Skip review queue, auto-accept all")
@click.option("--move", is_flag=True, help="Move files instead of copying")
@click.option("--no-fingerprint", is_flag=True, help="Skip AcoustID fingerprinting")
@click.option("--no-analyze", is_flag=True, help="Skip audio analysis (BPM/key)")
@click.option("--no-enrich", is_flag=True, help="Skip MusicBrainz genre enrichment")
@click.option("--force", is_flag=True, help="Overwrite existing files at destination")
def intake(
    source: str,
    dest: str,
    dry_run: bool,
    auto: bool,
    move: bool,
    no_fingerprint: bool,
    no_analyze: bool,
    no_enrich: bool,
    force: bool,
) -> None:
    """Process new tracks: scan, identify, analyze, enrich, review, and organize."""
    from cratedigger.intake.apply import apply_intake
    from cratedigger.intake.pipeline import run_intake
    from cratedigger.intake.report import print_intake_report
    from cratedigger.intake.review import run_review_queue

    source_path = Path(source).resolve()
    dest_path = Path(dest).resolve()

    console.print(f"\n[bold]DJ CrateDigger Intake[/bold]")
    console.print(f"Source: {source_path}")
    console.print(f"Dest:   {dest_path}")
    if dry_run:
        console.print("[yellow]DRY RUN MODE[/yellow]")
    console.rule()

    # Step 1-6: Pipeline (scan, read, fingerprint, analyze, enrich, suggest)
    result = run_intake(
        source=source_path,
        dest=dest_path,
        dry_run=dry_run,
        auto=auto,
        move=move,
        no_fingerprint=no_fingerprint,
        no_analyze=no_analyze,
        no_enrich=no_enrich,
        force=force,
    )

    if not result.tracks:
        return

    # Step 7: Review queue
    result.tracks = run_review_queue(
        tracks=result.tracks,
        dest=dest_path,
        auto=auto,
    )

    # Step 8: Apply changes
    stats = apply_intake(
        tracks=result.tracks,
        dest=dest_path,
        move=move,
        dry_run=dry_run,
    )

    # Update result with final counts
    result.skipped_count = sum(1 for t in result.tracks if t.status == "skipped")
    result.destination_folders = {}
    for track in result.tracks:
        if track.status in ("approved", "edited") and track.destination_folder:
            folder = track.destination_folder
            result.destination_folders[folder] = result.destination_folders.get(folder, 0) + 1

    # Step 9: Report
    console.print()
    print_intake_report(result, console)
