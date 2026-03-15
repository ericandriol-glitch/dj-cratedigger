"""CLI command for deep artist research."""

from pathlib import Path

import click
from rich.console import Console

from . import cli


@cli.command("dig-artist-deep")
@click.argument("name")
@click.option(
    "--db",
    type=click.Path(resolve_path=True),
    default=None,
    help="Path to CrateDigger database (uses default if omitted).",
)
@click.option(
    "--save",
    is_flag=True,
    default=False,
    help="Save top tracks to wishlist.",
)
def dig_artist_deep(name: str, db: str | None, save: bool) -> None:
    """Deep research on an artist -- discography, labels, related artists.

    Queries MusicBrainz, Spotify (if configured), and your local library
    to build a comprehensive artist profile.

    Example: cratedigger dig-artist-deep "Solomun"
    """
    from ..discovery.artist_profile import research_artist_deep
    from ..discovery.artist_report import print_artist_profile

    console = Console(force_terminal=True, force_jupyter=False)
    console.print(
        f"\n  [bold magenta]DJ CrateDigger[/bold magenta]"
        f" -- Deep research on [bold]{name}[/bold]...\n"
    )

    db_path = Path(db) if db else None
    profile = research_artist_deep(name, db_path=db_path)
    print_artist_profile(profile, console=console)

    if save and profile.top_tracks:
        console.print(
            f"  [yellow]--save not yet implemented. "
            f"{len(profile.top_tracks)} top tracks found.[/yellow]\n"
        )
