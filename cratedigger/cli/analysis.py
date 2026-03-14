"""Audio analysis and enrichment commands for DJ CrateDigger."""

from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from ..scanner import find_audio_files

# Import cli group to register commands
from . import cli


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

    from ..audio_analysis.analyzer import analyze_track
    from ..metadata import read_metadata

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
    from ..fixers.tags import TagFix, apply_tag_fixes

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


@cli.command("scan-essentia")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--force", is_flag=True, default=False, help="Re-analyze files already in the database")
def scan_essentia(path: str, force: bool) -> None:
    """Run Essentia audio analysis (BPM, key, energy, danceability) on a library."""
    from ..core.batch_analyzer import batch_analyze

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


@cli.command("enrich")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--dry-run", is_flag=True, default=False, help="Preview genre lookups without writing tags")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompt")
@click.option("--rate-limit", default=1.1, help="Seconds between API calls (MusicBrainz requires >=1)")
def enrich(path: str, dry_run: bool, yes: bool, rate_limit: float) -> None:
    """Enrich missing genre tags using MusicBrainz lookups."""
    import time

    from ..enrichment.musicbrainz import clear_cache, lookup_genre
    from ..fixers.tags import TagFix, apply_tag_fixes
    from ..metadata import read_metadata

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

    # Also persist genres to the DB for playlist builder
    from ..utils.db import update_genres
    genre_map = {str(f): result.genre for f, result in lookups if result.genre}
    if genre_map:
        update_genres(genre_map)

    console.print(f"\n  [green]Wrote genre to {success} files.[/green]")
    if errors:
        console.print(f"  [red]{len(errors)} errors:[/red]")
        for err in errors:
            console.print(f"    - {err}")
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
    from ..core.enrich import apply_enrichment, plan_enrichment, print_enrichment_plan

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
