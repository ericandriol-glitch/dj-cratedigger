"""Dig commands — research labels, artists, and connections."""

from pathlib import Path

import click
from rich.console import Console

from . import cli


@cli.group()
def dig():
    """Dig deeper — research labels, artists, and connections."""
    pass


@dig.command("label")
@click.argument("artist")
@click.option(
    "--library", "-l",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=None,
    help="Path to music library for cross-reference.",
)
@click.option(
    "--no-web",
    is_flag=True,
    default=False,
    help="Disable web search enrichment (RA, Beatport, Google).",
)
def dig_label(artist: str, library: str | None, no_web: bool) -> None:
    """Research which labels an artist releases on and discover similar artists.

    Example: cratedigger dig label "Vitess"
    """
    from ..digger.label import display_label_report, research_label

    console = Console()
    console.print(f"\n  [bold magenta]DJ CrateDigger[/bold magenta] — Researching labels for [bold]{artist}[/bold]...")

    library_path = Path(library) if library else None
    report = research_label(artist, library_path=library_path, web_search=not no_web)

    if report:
        display_label_report(report)


@dig.command("festival")
@click.argument("name", required=False, default=None)
@click.option(
    "--lineup", "-l",
    default=None,
    help='Comma-separated artist list: "Tale Of Us, Adam Beyer, Charlotte de Witte"',
)
@click.option(
    "--library",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=None,
    help="Path to music library (uses DB if not provided).",
)
@click.option(
    "--no-genres",
    is_flag=True,
    default=False,
    help="Skip MusicBrainz genre lookups for unknown artists.",
)
def dig_festival(name: str | None, lineup: str | None, library: str | None, no_genres: bool) -> None:
    """Scan a festival lineup against your library and streaming history.

    Two modes:\n
      cratedigger dig festival "Sonar 2026"\n
      cratedigger dig festival --lineup "Tale Of Us, Adam Beyer, Charlotte de Witte"

    Without an EDMTrain API key, use --lineup to paste artist names directly.
    """
    from ..digger.festival import (
        display_festival_report,
        parse_lineup,
        scan_festival,
    )

    console = Console(force_terminal=True, force_jupyter=False)

    if not name and not lineup:
        console.print("\n  [red]Provide a festival name or --lineup with artist names.[/red]")
        console.print('  Example: cratedigger dig festival --lineup "Tale Of Us, Adam Beyer"')
        console.print('  Example: cratedigger dig festival "Sonar 2026"\n')
        return

    # Festival name mode — needs EDMTrain API key
    if name and not lineup:
        console.print(f"\n  [bold magenta]DJ CrateDigger[/bold magenta] — Festival Scanner: [bold]{name}[/bold]\n")
        console.print("  [yellow]EDMTrain API key not configured.[/yellow]")
        console.print("  Get a free key at https://edmtrain.com/api and add it to ~/.cratedigger/config.yaml")
        console.print(f'\n  For now, paste the lineup manually:')
        console.print(f'  cratedigger dig festival --lineup "Artist1, Artist2, Artist3"\n')
        return

    # Lineup mode
    festival_label = name or "Lineup"
    artists = parse_lineup(lineup)

    if not artists:
        console.print("\n  [yellow]No artists found in lineup text.[/yellow]\n")
        return

    console.print(f"\n  [bold magenta]DJ CrateDigger[/bold magenta] — Festival Scanner: [bold]{festival_label}[/bold]\n")

    library_path = Path(library) if library else None
    report = scan_festival(
        lineup_artists=artists,
        festival_name=festival_label,
        library_path=library_path,
        lookup_genres=not no_genres,
    )
    display_festival_report(report)
