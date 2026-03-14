"""Scan and fix commands for DJ CrateDigger."""

from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from ..analyzers.duplicates import find_duplicates
from ..analyzers.filename import analyze_filename
from ..analyzers.tags import analyze_tags
from ..models import HealthScore, LibraryReport
from ..report import print_terminal_report, save_markdown_report
from ..scanner import find_audio_files, scan_library


def _calculate_health_score(report: LibraryReport) -> float:
    """Calculate overall health score (0-100)."""
    if not report.tracks:
        return 100.0

    total = len(report.tracks)
    score_points = 0.0

    for track in report.tracks:
        track_score = 0.0
        if track.filename_score == HealthScore.CLEAN:
            track_score += 40
        elif track.filename_score == HealthScore.NEEDS_ATTENTION:
            track_score += 20
        if track.metadata_score == HealthScore.CLEAN:
            track_score += 50
        elif track.metadata_score == HealthScore.NEEDS_ATTENTION:
            track_score += 30
        if track.duplicate_group is None:
            track_score += 10
        score_points += track_score

    return round(score_points / total, 1)


def _print_analysis_comparison(
    console: Console,
    tracks: list,
    batch_result: "BatchResult",  # noqa: F821
) -> None:
    """Print comparison between tag metadata and Essentia-detected values."""
    from ..utils.db import get_connection

    conn = get_connection()
    cursor = conn.execute("SELECT filepath, bpm, key_camelot FROM audio_analysis")
    db_results = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    conn.close()

    tag_bpm_count = sum(1 for t in tracks if t.metadata and t.metadata.bpm)
    tag_key_count = sum(1 for t in tracks if t.metadata and t.metadata.key)
    detected_bpm_count = sum(1 for bpm, _ in db_results.values() if bpm is not None)
    detected_key_count = sum(1 for _, key in db_results.values() if key is not None)

    # Find disagreements
    bpm_disagreements = []
    key_disagreements = []
    for track in tracks:
        fp = str(track.file_path)
        if fp not in db_results:
            continue
        detected_bpm, detected_key = db_results[fp]

        if track.metadata and track.metadata.bpm and detected_bpm:
            try:
                tag_bpm = float(track.metadata.bpm)
                if abs(tag_bpm - detected_bpm) > 2.0:
                    bpm_disagreements.append((track.file_path.name, tag_bpm, detected_bpm))
            except (ValueError, TypeError):
                pass

        if track.metadata and track.metadata.key and detected_key:
            from ..core.analyzer import musical_key_to_camelot
            tag_key = track.metadata.key.strip()
            tag_camelot = musical_key_to_camelot(tag_key)
            if tag_camelot and tag_camelot != detected_key:
                key_disagreements.append((track.file_path.name, f"{tag_key} ({tag_camelot})", detected_key))
            elif not tag_camelot and tag_key != detected_key:
                key_disagreements.append((track.file_path.name, tag_key, detected_key))

    total = len(tracks)
    console.print("\n  [bold]Analysis Summary[/bold]")
    console.print(f"  BPM:  {tag_bpm_count} from tags, {detected_bpm_count} from Essentia (of {total} tracks)")
    console.print(f"  Key:  {tag_key_count} from tags, {detected_key_count} from Essentia (of {total} tracks)")

    gaps_filled_bpm = detected_bpm_count - tag_bpm_count
    gaps_filled_key = detected_key_count - tag_key_count
    if gaps_filled_bpm > 0 or gaps_filled_key > 0:
        console.print(
            f"  [green]Essentia fills {max(0, gaps_filled_bpm)} BPM gaps "
            f"and {max(0, gaps_filled_key)} key gaps[/green]"
        )

    if bpm_disagreements:
        console.print(f"\n  [yellow]BPM disagreements (>{2} BPM difference): {len(bpm_disagreements)}[/yellow]")
        table = Table()
        table.add_column("Track", style="cyan", max_width=45)
        table.add_column("Tag BPM", justify="right", style="yellow")
        table.add_column("Detected BPM", justify="right", style="green")
        table.add_column("Diff", justify="right", style="red")
        for name, tag, detected in bpm_disagreements[:10]:
            table.add_row(name[:45], f"{tag:.1f}", f"{detected:.1f}", f"{abs(tag - detected):.1f}")
        console.print(table)

    if key_disagreements:
        console.print(f"\n  [yellow]Key disagreements: {len(key_disagreements)}[/yellow]")
        table = Table()
        table.add_column("Track", style="cyan", max_width=45)
        table.add_column("Tag Key", style="yellow")
        table.add_column("Detected Key", style="green")
        for name, tag, detected in key_disagreements[:10]:
            table.add_row(name[:45], tag, detected)
        console.print(table)


# Import cli group to register commands
from . import cli  # noqa: E402


@cli.command()
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--output", "-o", default="library_report.md", help="Output report path")
@click.option("--verbose", "-v", is_flag=True, help="Show details for every file")
@click.option("--analyze/--no-analyze", default=False, help="Run Essentia audio analysis (BPM, key, energy)")
@click.option("--force-reanalyze", is_flag=True, default=False, help="Re-analyze files already in the database")
def scan(path: str, output: str, verbose: bool, analyze: bool, force_reanalyze: bool) -> None:
    """Scan a DJ music library and generate a health report."""
    console = Console()
    scan_path = Path(path)

    console.print(f"\n  [bold magenta]DJ CrateDigger[/bold magenta] scanning [cyan]{scan_path}[/cyan]...\n")

    tracks, duration, total_files = scan_library(scan_path, verbose=verbose)

    if not tracks:
        console.print("  [yellow]No audio files found.[/yellow]")
        return

    for track in tracks:
        score, issues = analyze_filename(track.file_path)
        track.filename_score = score
        track.filename_issues = issues

    for track in tracks:
        score, issues = analyze_tags(track.metadata)
        track.metadata_score = score
        track.metadata_issues = issues

    duplicate_groups = find_duplicates(tracks)
    for group_id, group in enumerate(duplicate_groups):
        for track in group:
            track.duplicate_group = group_id

    total_size_gb = sum(t.file_size_mb for t in tracks) / 1024
    report = LibraryReport(
        scan_path=str(scan_path),
        total_files=total_files,
        audio_files=len(tracks),
        total_size_gb=round(total_size_gb, 2),
        scan_duration_seconds=round(duration, 2),
        tracks=tracks,
        duplicate_groups=duplicate_groups,
    )
    report.health_score = _calculate_health_score(report)

    print_terminal_report(report, verbose=verbose)

    # Run Essentia analysis if requested
    if analyze:
        from ..core.batch_analyzer import batch_analyze

        console.print("\n  [bold magenta]Essentia Audio Analysis[/bold magenta]\n")
        audio_paths = [t.file_path for t in tracks]
        batch_result = batch_analyze(audio_paths, force=force_reanalyze)

        # Print analysis vs tag comparison
        _print_analysis_comparison(console, tracks, batch_result)

    output_path = Path(output)
    save_markdown_report(report, output_path)
    console.print(f"  [green]Full report saved to:[/green] {output_path.resolve()}\n")


@cli.command("fix-tags")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--dry-run", is_flag=True, default=False, help="Preview changes without applying")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
def fix_tags(path: str, dry_run: bool, yes: bool) -> None:
    """Fix missing metadata tags by extracting artist/title from filenames."""
    console = Console()
    scan_path = Path(path)

    from ..fixers.tags import apply_tag_fixes, plan_tag_fixes

    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Fix Tags\n")
    console.print(f"  Scanning [cyan]{scan_path}[/cyan]...\n")

    audio_files = find_audio_files(scan_path)
    fixes = plan_tag_fixes(audio_files)

    if not fixes:
        console.print("  [green]No tag fixes needed — all files have artist/title tags.[/green]\n")
        return

    # Group by file for display
    fixes_by_file: dict[Path, list] = {}
    for fix in fixes:
        fixes_by_file.setdefault(fix.file_path, []).append(fix)

    # Preview table
    table = Table(title=f"Proposed Tag Fixes ({len(fixes)} changes across {len(fixes_by_file)} files)")
    table.add_column("File", style="cyan", max_width=50)
    table.add_column("Field", style="yellow")
    table.add_column("Old Value", style="red")
    table.add_column("New Value", style="green")

    for file_path, file_fixes in sorted(fixes_by_file.items()):
        for i, fix in enumerate(file_fixes):
            fname = fix.file_path.name if i == 0 else ""
            table.add_row(
                fname,
                fix.field,
                fix.old_value or "(empty)",
                fix.new_value,
            )

    console.print(table)
    console.print()

    if dry_run:
        console.print("  [yellow]Dry run — no changes applied.[/yellow]\n")
        return

    if not yes:
        if not Confirm.ask(f"  Apply {len(fixes)} tag fixes?"):
            console.print("  [yellow]Cancelled.[/yellow]\n")
            return

    success, errors = apply_tag_fixes(fixes)
    console.print(f"\n  [green]Fixed tags on {success} files.[/green]")
    if errors:
        console.print(f"  [red]{len(errors)} errors:[/red]")
        for err in errors:
            console.print(f"    - {err}")
    console.print()


@cli.command("fix-dupes")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--dry-run", is_flag=True, default=False, help="Preview changes without applying")
@click.option("--trash-dir", type=click.Path(), default=None, help="Move dupes here instead of deleting")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
def fix_dupes(path: str, dry_run: bool, trash_dir: str | None, yes: bool) -> None:
    """Find and remove duplicate audio files."""
    console = Console()
    scan_path = Path(path)

    from ..fixers.duplicates import apply_duplicate_cleanup, plan_duplicate_cleanup

    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Fix Duplicates\n")
    console.print(f"  Scanning [cyan]{scan_path}[/cyan]...\n")

    tracks, _, _ = scan_library(scan_path)
    duplicate_groups = find_duplicates(tracks)

    if not duplicate_groups:
        console.print("  [green]No duplicates found.[/green]\n")
        return

    actions = plan_duplicate_cleanup(duplicate_groups)

    # Preview
    total_remove = sum(len(a.remove) for a in actions)
    total_save_mb = sum(t.file_size_mb for a in actions for t in a.remove)

    table = Table(title=f"Duplicate Cleanup Plan ({len(actions)} groups, {total_remove} files to remove)")
    table.add_column("Keep", style="green", max_width=55)
    table.add_column("Remove", style="red", max_width=55)
    table.add_column("Size", justify="right")
    table.add_column("Reason", style="dim")

    for action in actions:
        for i, track in enumerate(action.remove):
            table.add_row(
                action.keep.file_path.name if i == 0 else "",
                track.file_path.name,
                f"{track.file_size_mb:.1f} MB",
                action.reason if i == 0 else "",
            )

    console.print(table)
    console.print(f"\n  Total space to recover: [bold]{total_save_mb:.1f} MB[/bold]")

    if dry_run:
        console.print("  [yellow]Dry run — no changes applied.[/yellow]\n")
        return

    trash = Path(trash_dir) if trash_dir else None
    action_word = "move to trash" if trash else "permanently delete"

    if not yes:
        if not Confirm.ask(f"\n  {action_word.capitalize()} {total_remove} duplicate files?"):
            console.print("  [yellow]Cancelled.[/yellow]\n")
            return

    removed, errors = apply_duplicate_cleanup(actions, trash_dir=trash)
    console.print(f"\n  [green]Removed {removed} duplicate files.[/green]")
    if trash:
        console.print(f"  [dim]Moved to: {trash.resolve()}[/dim]")
    if errors:
        console.print(f"  [red]{len(errors)} errors:[/red]")
        for err in errors:
            console.print(f"    - {err}")
    console.print()


@cli.command("fix-filenames")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--dry-run", is_flag=True, default=False, help="Preview changes without applying")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
def fix_filenames(path: str, dry_run: bool, yes: bool) -> None:
    """Clean up messy filenames (remove junk, watermarks, etc.)."""
    console = Console()
    scan_path = Path(path)

    from ..fixers.filename import apply_filename_fixes, plan_filename_fixes

    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Fix Filenames\n")
    console.print(f"  Scanning [cyan]{scan_path}[/cyan]...\n")

    audio_files = find_audio_files(scan_path)
    renames = plan_filename_fixes(audio_files)

    if not renames:
        console.print("  [green]No filename fixes needed.[/green]\n")
        return

    table = Table(title=f"Proposed Renames ({len(renames)} files)")
    table.add_column("Current Name", style="red", max_width=60)
    table.add_column("New Name", style="green", max_width=60)
    table.add_column("Reason", style="dim")

    for rename in renames:
        table.add_row(rename.old_path.name, rename.new_path.name, rename.reason)

    console.print(table)

    if dry_run:
        console.print("\n  [yellow]Dry run — no changes applied.[/yellow]\n")
        return

    if not yes:
        if not Confirm.ask(f"\n  Rename {len(renames)} files?"):
            console.print("  [yellow]Cancelled.[/yellow]\n")
            return

    success, errors = apply_filename_fixes(renames)
    console.print(f"\n  [green]Renamed {success} files.[/green]")
    if errors:
        console.print(f"  [red]{len(errors)} errors:[/red]")
        for err in errors:
            console.print(f"    - {err}")
    console.print()


@cli.command("fix-all")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--dry-run", is_flag=True, default=False, help="Preview all changes without applying")
@click.option("--trash-dir", type=click.Path(), default=None, help="Move dupes here instead of deleting")
def fix_all(path: str, dry_run: bool, trash_dir: str | None) -> None:
    """Run all fixes: tags, duplicates, and filenames (with confirmation for each)."""
    ctx = click.get_current_context()

    # Run each sub-fix in order with dry-run to preview
    ctx.invoke(fix_tags, path=path, dry_run=dry_run, yes=False)
    ctx.invoke(fix_dupes, path=path, dry_run=dry_run, trash_dir=trash_dir, yes=False)
    ctx.invoke(fix_filenames, path=path, dry_run=dry_run, yes=False)
