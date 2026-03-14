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


@dig.command("weekly")
@click.option(
    "--genre", "-g",
    multiple=True,
    default=None,
    help="Genre(s) to scan. Defaults to your top genres from DJ profile.",
)
@click.option(
    "--library", "-l",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=None,
    help="Path to music library for cross-reference.",
)
@click.option(
    "--paste",
    is_flag=True,
    default=False,
    help="Paste releases manually (one per line: Artist - Title).",
)
def dig_weekly(genre: tuple, library: str | None, paste: bool) -> None:
    """Scan new releases against your DJ profile.

    Uses Beatport web search + your DJ profile to find relevant new music.

    Examples:\n
      cratedigger dig weekly\n
      cratedigger dig weekly -g "Tech House" -g "Deep House"\n
      cratedigger dig weekly --paste
    """
    from ..digger.weekly_dig import (
        display_weekly_report,
        parse_manual_releases,
        scan_new_releases,
        WeeklyDigReport,
    )

    console = Console(force_terminal=True, force_jupyter=False)
    console.print(f"\n  [bold magenta]DJ CrateDigger[/bold magenta] — Weekly Dig\n")

    library_path = Path(library) if library else None

    if paste:
        console.print("  Paste releases (one per line: Artist - Title [Label])")
        console.print("  Press Enter twice when done:\n")
        lines = []
        while True:
            line = click.get_text_stream("stdin").readline().rstrip("\n")
            if not line:
                break
            lines.append(line)

        releases = parse_manual_releases("\n".join(lines))
        report = WeeklyDigReport(
            releases=releases,
            total_found=len(releases),
            after_filter=len(releases),
            source="manual",
        )
        display_weekly_report(report)
    else:
        genres = list(genre) if genre else None
        report = scan_new_releases(genres=genres, library_path=library_path)
        display_weekly_report(report)


@dig.command("artist")
@click.argument("name")
@click.option(
    "--library", "-l",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
    default=None,
    help="Path to music library for cross-reference.",
)
@click.option(
    "--no-discogs",
    is_flag=True,
    default=False,
    help="Skip Discogs lookup.",
)
@click.option(
    "--no-spotify",
    is_flag=True,
    default=False,
    help="Skip Spotify status check.",
)
def dig_artist(name: str, library: str | None, no_discogs: bool, no_spotify: bool) -> None:
    """Research an artist across MusicBrainz, Discogs, Spotify, and your library.

    Example: cratedigger dig artist "Solomun"
    """
    from ..digger.artist_research import display_artist_report, research_artist

    console = Console(force_terminal=True, force_jupyter=False)
    console.print(f"\n  [bold magenta]DJ CrateDigger[/bold magenta] — Researching [bold]{name}[/bold]...\n")

    library_path = Path(library) if library else None
    report = research_artist(
        name,
        library_path=library_path,
        include_discogs=not no_discogs,
        include_spotify=not no_spotify,
    )

    if report:
        display_artist_report(report)
    else:
        console.print(f"  [yellow]No results found for '{name}'[/yellow]\n")


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
