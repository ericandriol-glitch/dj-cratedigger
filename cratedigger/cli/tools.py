"""Utility commands (watch, identify, profile) for DJ CrateDigger."""

from pathlib import Path

import click
from rich.console import Console

# Import cli group to register commands
from . import cli


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
