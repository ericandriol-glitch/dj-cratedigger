"""Utility commands (watch, identify, profile) for DJ CrateDigger."""

from pathlib import Path

import click
from rich.console import Console

# Import cli group to register commands
from . import cli


@cli.command("report")
@click.option("--output", "-o", default="library_report.html",
              type=click.Path(resolve_path=True),
              help="Output HTML file path (default: library_report.html)")
def report(output: str) -> None:
    """Generate an HTML library insights report with charts.

    Creates a standalone HTML file with BPM distribution, key/genre charts,
    energy stats, and library overview. Opens in any browser.
    """
    from ..report_html import generate_html_report

    console = Console(force_terminal=True, force_jupyter=False)
    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Generating Library Report...\n")

    out_path = generate_html_report(output_path=Path(output))
    console.print(f"  [green]Report saved to:[/green] {out_path}")
    console.print(f"  Open in browser to view charts and stats.\n")


@cli.command("pipeline")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--apply", is_flag=True, default=False,
              help="Write enriched tags back to files (creates backups).")
@click.option("--report", "gen_report", is_flag=True, default=False,
              help="Generate HTML report after pipeline completes.")
def pipeline(path: str, apply: bool, gen_report: bool) -> None:
    """Run the full pipeline: scan → analyse → enrich → profile → report.

    Runs all steps in sequence. Use --apply to write tags, otherwise dry-run.

    Example: cratedigger pipeline /path/to/music --apply --report
    """
    from ..scanner import find_audio_files
    from ..digger.profile import build_profile, save_profile

    console = Console(force_terminal=True, force_jupyter=False)
    library = Path(path)

    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Full Pipeline\n")

    # Step 1: Scan
    console.print("  [bold cyan]Step 1/4:[/bold cyan] Scanning library...")
    files = find_audio_files(library)
    console.print(f"    Found {len(files)} audio files\n")

    if not files:
        console.print("  [yellow]No audio files found. Exiting.[/yellow]\n")
        return

    # Step 2: Essentia analysis (batch)
    console.print("  [bold cyan]Step 2/4:[/bold cyan] Audio analysis (BPM, key, energy)...")
    console.print("    [dim]Run in WSL: cratedigger scan-essentia {path}[/dim]")
    console.print("    [dim]Skipping — requires Essentia in WSL environment[/dim]\n")

    # Step 3: Enrich tags
    if apply:
        console.print("  [bold cyan]Step 3/4:[/bold cyan] Writing enriched tags (with backup)...")
        console.print("    [dim]Run: cratedigger enrich {path} --apply[/dim]\n")
    else:
        console.print("  [bold cyan]Step 3/4:[/bold cyan] Tag enrichment (dry-run, use --apply to write)...")
        console.print("    [dim]Run: cratedigger enrich {path} --dry-run[/dim]\n")

    # Step 4: Build profile
    console.print("  [bold cyan]Step 4/4:[/bold cyan] Building DJ profile...")
    prof = build_profile(library)
    save_profile(prof)
    console.print(f"    Profile saved: {prof.total_tracks} tracks, "
                  f"{len(prof.genres)} genres, "
                  f"BPM {prof.bpm_range.get('min', '?')}-{prof.bpm_range.get('max', '?')}\n")

    # Optional: Generate report
    if gen_report:
        from ..report_html import generate_html_report
        out_path = generate_html_report()
        console.print(f"  [green]HTML report saved:[/green] {out_path}")

    console.print("  [bold green]Pipeline complete.[/bold green]\n")


@cli.command("watch")
@click.argument("watch_path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--target", "-t", required=True, type=click.Path(resolve_path=True),
              help="Target directory for sorted files")
@click.option("--convention", default="{artist} - {title}",
              help='Naming convention (default: "{artist} - {title}")')
def watch(watch_path: str, target: str, convention: str) -> None:
    """Watch a download folder for new audio files and auto-process."""
    from ..core.watcher import WatcherConfig, watch_directory

    config = WatcherConfig(
        watch_dir=Path(watch_path),
        target_dir=Path(target),
        convention=convention,
    )
    watch_directory(config)


@cli.command("identify")
@click.argument("filepath", type=click.Path(exists=True, resolve_path=True))
@click.option("--api-key", envvar="ACOUSTID_API_KEY", required=True,
              help="AcoustID API key (or set ACOUSTID_API_KEY env var)")
def identify(filepath: str, api_key: str) -> None:
    """Identify an unknown track using AcoustID fingerprinting."""
    from ..core.fingerprint import display_result, identify_track

    console = Console()
    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Track Identification\n")

    result = identify_track(Path(filepath), api_key)
    display_result(result)
    console.print()


@cli.group()
def profile():
    """DJ profile commands."""
    pass


@profile.command("build")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
def profile_build(path: str) -> None:
    """Build your DJ profile from library analysis."""
    from ..digger.profile import build_profile, display_profile, save_profile

    console = Console()
    scan_path = Path(path)

    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Building Profile...\n")

    prof = build_profile(scan_path)
    save_profile(prof)
    display_profile(prof)
    console.print("  [green]Profile saved.[/green]\n")


@profile.command("show")
def profile_show() -> None:
    """Display your DJ profile."""
    from ..digger.profile import display_profile, load_profile

    console = Console()
    prof = load_profile()
    if not prof:
        console.print("\n  [yellow]No profile found. Run 'cratedigger profile build <path>' first.[/yellow]\n")
        return

    display_profile(prof)
