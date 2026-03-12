"""CLI entry point for DJ CrateDigger."""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

from .scanner import scan_library, find_audio_files
from .analyzers.filename import analyze_filename
from .analyzers.tags import analyze_tags
from .analyzers.duplicates import find_duplicates
from .models import LibraryReport, HealthScore
from .report import print_terminal_report, save_markdown_report


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


@click.group()
def cli():
    """DJ CrateDigger — Library Scanner & Cleanup Tool."""
    pass


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
        from .core.batch_analyzer import batch_analyze

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

    from .fixers.tags import plan_tag_fixes, apply_tag_fixes

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

    from .fixers.duplicates import plan_duplicate_cleanup, apply_duplicate_cleanup

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

    from .fixers.filename import plan_filename_fixes, apply_filename_fixes

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


@cli.command("analyze")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--dry-run", is_flag=True, default=False, help="Preview detections without writing tags")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
@click.option("--workers", "-w", default=4, help="Parallel workers (default 4)")
@click.option("--only-missing", is_flag=True, default=True, help="Only analyze files missing BPM/key")
def analyze(path: str, dry_run: bool, yes: bool, workers: int, only_missing: bool) -> None:
    """Detect BPM and musical key for audio files using audio analysis."""
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from .metadata import read_metadata
    from .audio_analysis.analyzer import analyze_track

    console = Console()
    scan_path = Path(path)

    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] -- Audio Analysis (BPM & Key Detection)\n")
    console.print(f"  Scanning {scan_path}...\n")

    audio_files = find_audio_files(scan_path)

    # Filter to only files missing BPM or key
    if only_missing:
        to_analyze = []
        for f in audio_files:
            meta = read_metadata(f)
            if meta.bpm is None or meta.key is None:
                to_analyze.append(f)
        console.print(f"  {len(to_analyze)} files missing BPM and/or key (of {len(audio_files)} total)\n")
    else:
        to_analyze = audio_files
        console.print(f"  Analyzing all {len(to_analyze)} files\n")

    if not to_analyze:
        console.print("  All files already have BPM and key tags.\n")
        return

    # Run analysis with progress counter
    results = []
    start = time.perf_counter()
    done_count = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(analyze_track, f): f for f in to_analyze}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            done_count += 1
            if done_count % 10 == 0 or done_count == len(to_analyze):
                console.print(f"  [{done_count}/{len(to_analyze)}] analyzed...")

    elapsed = time.perf_counter() - start

    # Build results table
    detected_bpm = sum(1 for r in results if r.bpm is not None)
    detected_key = sum(1 for r in results if r.key is not None)
    errors = [r for r in results if r.error]

    console.print(f"\n  Analysis complete in {elapsed:.0f}s")
    console.print(f"  BPM detected: [green]{detected_bpm}[/green] / {len(results)}")
    console.print(f"  Key detected: [green]{detected_key}[/green] / {len(results)}")
    if errors:
        console.print(f"  Errors: [red]{len(errors)}[/red]")

    # Show sample results
    table = Table(title="Detection Results (sample)")
    table.add_column("File", style="cyan", max_width=50)
    table.add_column("BPM", justify="right", style="yellow")
    table.add_column("Key", style="green")

    # Sort by filename for readability
    results.sort(key=lambda r: r.file_path.name.lower())
    shown = 0
    for r in results:
        if r.bpm or r.key:
            table.add_row(
                r.file_path.name,
                f"{r.bpm:.1f}" if r.bpm else "-",
                r.key or "-",
            )
            shown += 1
            if shown >= 20:
                break

    console.print()
    console.print(table)

    if shown < len(results):
        console.print(f"  ... and {len(results) - shown} more")

    if dry_run:
        console.print("\n  [yellow]Dry run — no tags written.[/yellow]\n")
        return

    # Prepare tag writes
    from .fixers.tags import TagFix, apply_tag_fixes

    fixes = []
    for r in results:
        meta = read_metadata(r.file_path)
        if r.bpm and meta.bpm is None:
            fixes.append(TagFix(
                file_path=r.file_path,
                field="bpm",
                old_value=None,
                new_value=str(round(r.bpm)),
            ))
        if r.key and meta.key is None:
            fixes.append(TagFix(
                file_path=r.file_path,
                field="key",
                old_value=None,
                new_value=r.key,
            ))

    if not fixes:
        console.print("\n  [yellow]No new tags to write.[/yellow]\n")
        return

    console.print(f"\n  Ready to write [bold]{len(fixes)}[/bold] tags ({detected_bpm} BPM + {detected_key} key)")

    if not yes:
        if not Confirm.ask("  Write tags?"):
            console.print("  [yellow]Cancelled.[/yellow]\n")
            return

    success, tag_errors = apply_tag_fixes(fixes)
    console.print(f"\n  [green]Wrote tags to {success} files.[/green]")
    if tag_errors:
        console.print(f"  [red]{len(tag_errors)} errors:[/red]")
        for err in tag_errors:
            console.print(f"    - {err}")
    console.print()


@cli.command("enrich")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--dry-run", is_flag=True, default=False, help="Preview genre lookups without writing tags")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
@click.option("--rate-limit", default=1.1, help="Seconds between API calls (MusicBrainz requires >=1)")
def enrich(path: str, dry_run: bool, yes: bool, rate_limit: float) -> None:
    """Enrich missing genre tags using MusicBrainz lookups."""
    import time

    from .metadata import read_metadata
    from .enrichment.musicbrainz import lookup_genre, clear_cache
    from .fixers.tags import TagFix, apply_tag_fixes

    console = Console()
    scan_path = Path(path)

    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] -- Genre Enrichment (MusicBrainz)\n")
    console.print(f"  Scanning {scan_path}...\n")

    audio_files = find_audio_files(scan_path)

    # Filter to files missing genre that have artist+title
    to_enrich = []
    for f in audio_files:
        meta = read_metadata(f)
        if not meta.genre and meta.artist and meta.title:
            to_enrich.append((f, meta.artist, meta.title))

    console.print(f"  {len(to_enrich)} files missing genre with artist+title available\n")

    if not to_enrich:
        console.print("  All files already have genre tags (or lack artist/title for lookup).\n")
        return

    # Estimate time — unique artists reduce API calls due to caching
    unique_artists = len(set(a.strip().lower() for _, a, _ in to_enrich))
    est_seconds = unique_artists * rate_limit
    console.print(f"  {unique_artists} unique artists to look up")
    console.print(f"  Estimated time: ~{est_seconds / 60:.0f} minutes (MusicBrainz rate limit: {rate_limit}s/req)\n")

    # Run lookups
    clear_cache()
    lookups = []
    found = 0
    start = time.perf_counter()

    for i, (f, artist, title) in enumerate(to_enrich):
        result = lookup_genre(artist, title, rate_limit=rate_limit)
        lookups.append((f, result))
        if result.genre:
            found += 1

        if (i + 1) % 20 == 0 or i + 1 == len(to_enrich):
            elapsed = time.perf_counter() - start
            console.print(f"  [{i + 1}/{len(to_enrich)}] {found} genres found ({elapsed:.0f}s)")

    elapsed = time.perf_counter() - start

    console.print(f"\n  Lookup complete in {elapsed:.0f}s")
    console.print(f"  Genres found: [green]{found}[/green] / {len(to_enrich)}")
    console.print(f"  Not found: [yellow]{len(to_enrich) - found}[/yellow]")

    # Show results table
    table = Table(title="Genre Lookups (sample)")
    table.add_column("File", style="cyan", max_width=45)
    table.add_column("Genre", style="green")
    table.add_column("Source", style="dim")
    table.add_column("All Tags", style="dim", max_width=30)

    shown = 0
    for f, result in lookups:
        if result.genre:
            table.add_row(
                f.name[:45],
                result.genre,
                result.source,
                ", ".join(result.all_tags[:3]),
            )
            shown += 1
            if shown >= 25:
                break

    console.print()
    console.print(table)

    # Show not-found
    not_found = [(f, r) for f, r in lookups if not r.genre]
    if not_found:
        console.print(f"\n  [yellow]Not found ({len(not_found)} files):[/yellow]")
        shown_nf = 0
        for f, r in not_found:
            console.print(f"    - {r.artist} - {r.title}")
            shown_nf += 1
            if shown_nf >= 15:
                console.print(f"    ... and {len(not_found) - shown_nf} more")
                break

    if dry_run:
        console.print("\n  Dry run -- no tags written.\n")
        return

    # Prepare fixes
    fixes = []
    for f, result in lookups:
        if result.genre:
            fixes.append(TagFix(
                file_path=f,
                field="genre",
                old_value=None,
                new_value=result.genre,
            ))

    if not fixes:
        console.print("\n  No genres to write.\n")
        return

    console.print(f"\n  Ready to write genre tags to [bold]{len(fixes)}[/bold] files")

    if not yes:
        if not Confirm.ask("  Write genre tags?"):
            console.print("  Cancelled.\n")
            return

    success, errors = apply_tag_fixes(fixes)
    console.print(f"\n  [green]Wrote genre to {success} files.[/green]")
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


def _print_analysis_comparison(
    console: Console,
    tracks: list,
    batch_result: "BatchResult",  # noqa: F821
) -> None:
    """Print comparison between tag metadata and Essentia-detected values."""
    from .utils.db import get_connection

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
            from .core.analyzer import musical_key_to_camelot
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


@cli.command("scan-essentia")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--force", is_flag=True, default=False, help="Re-analyze files already in the database")
def scan_essentia(path: str, force: bool) -> None:
    """Run Essentia audio analysis (BPM, key, energy, danceability) on a library."""
    from .core.batch_analyzer import batch_analyze

    console = Console()
    scan_path = Path(path)

    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Essentia Analysis\n")

    audio_paths = find_audio_files(scan_path)
    if not audio_paths:
        console.print("  [yellow]No audio files found.[/yellow]\n")
        return

    console.print(f"  Found {len(audio_paths)} audio files in [cyan]{scan_path}[/cyan]\n")
    batch_analyze(audio_paths, force=force)
    console.print()


@cli.command("enrich-essentia")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--dry-run", is_flag=True, default=True, help="Preview changes without writing (default)")
@click.option("--apply", "do_apply", is_flag=True, default=False, help="Write tags to files")
@click.option("--force", is_flag=True, default=False, help="Overwrite existing tags with Essentia values")
@click.option("--backup-dir", type=click.Path(), default=None,
              help="Backup directory (default: _backups/ under scanned folder)")
def enrich_essentia(path: str, dry_run: bool, do_apply: bool, force: bool, backup_dir: str | None) -> None:
    """Write Essentia-detected BPM/key back to file tags.

    Default is --dry-run (preview only). Use --apply to write tags.
    Only fills gaps unless --force is used.
    """
    from .core.enrich import apply_enrichment, plan_enrichment, print_enrichment_plan

    console = Console()
    scan_path = Path(path)

    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Enrich from Essentia\n")

    audio_paths = find_audio_files(scan_path)
    if not audio_paths:
        console.print("  [yellow]No audio files found.[/yellow]\n")
        return

    actions = plan_enrichment(audio_paths, force=force)
    print_enrichment_plan(actions)

    if not actions:
        return

    if not do_apply:
        console.print("  [yellow]Dry run — no tags written. Use --apply to write.[/yellow]\n")
        return

    # Determine backup directory
    backup = Path(backup_dir) if backup_dir else scan_path / "_backups"
    console.print(f"  Backing up files to [cyan]{backup}[/cyan]")

    success, errors = apply_enrichment(actions, backup_dir=backup)
    console.print(f"\n  [green]Enriched {success} files.[/green]")
    if errors:
        console.print(f"  [red]{len(errors)} errors:[/red]")
        for err in errors:
            console.print(f"    - {err}")
    console.print()


def main():
    cli()


if __name__ == "__main__":
    main()
