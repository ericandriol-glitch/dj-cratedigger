"""CLI commands for enhanced DJ profile."""

from pathlib import Path

import click
from rich.console import Console

from . import cli


@cli.command("profile-build")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--refresh", is_flag=True, help="Force rebuild even if profile exists")
def profile_build(path: str, refresh: bool) -> None:
    """Build your enhanced DJ profile from library analysis.

    Scans metadata, combines with Essentia analysis and optional Spotify data
    to create a comprehensive DJ identity profile.

    Example: cratedigger profile-build /path/to/music --refresh
    """
    from ..profile.enhanced import (
        build_profile,
        load_enhanced_profile,
        save_enhanced_profile,
    )
    from ..profile.report import display_enhanced_profile

    console = Console(force_terminal=True, force_jupyter=False)

    if not refresh:
        existing = load_enhanced_profile()
        if existing and existing.total_tracks > 0:
            console.print("\n  [yellow]Profile exists. Use --refresh to rebuild.[/yellow]\n")
            display_enhanced_profile(existing, console=console)
            return

    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Building Enhanced Profile...\n")

    profile = build_profile(library_path=Path(path))
    save_enhanced_profile(profile)
    display_enhanced_profile(profile, console=console)
    console.print("  [green]Enhanced profile saved.[/green]\n")


@cli.command("profile-show")
def profile_show_enhanced() -> None:
    """Show your enhanced DJ profile.

    Displays the full profile including genre distribution, BPM sweet spot,
    key preferences, streaming divergence, and sound summary.
    """
    from ..profile.enhanced import load_enhanced_profile
    from ..profile.report import display_enhanced_profile

    console = Console(force_terminal=True, force_jupyter=False)
    profile = load_enhanced_profile()

    if not profile:
        console.print(
            "\n  [yellow]No enhanced profile found. "
            "Run 'cratedigger profile-build <path>' first.[/yellow]\n"
        )
        return

    display_enhanced_profile(profile, console=console)
