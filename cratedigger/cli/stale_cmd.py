"""CLI command for stale track detection."""

from pathlib import Path

import click
from rich.console import Console

from . import cli


@cli.command("stale")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--since", default=12, type=int, help="Months threshold for dormant detection")
@click.option("--rekordbox", type=click.Path(exists=True, resolve_path=True),
              help="Path to Rekordbox XML for play count analysis")
def stale(path: str, since: int, rekordbox: str | None) -> None:
    """Find stale tracks: never-played, dormant, or outlier.

    Scans your library for tracks that may be candidates for cleanup.
    Optionally uses Rekordbox XML to detect never-played tracks.

    Example: cratedigger stale /path/to/music --since 6 --rekordbox library.xml
    """
    from ..audit.stale import find_stale_tracks
    from ..audit.stale_report import display_stale_report

    console = Console(force_terminal=True, force_jupyter=False)
    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Scanning for stale tracks...\n")

    rb_path = Path(rekordbox) if rekordbox else None
    result = find_stale_tracks(
        library_path=Path(path),
        since_months=since,
        rekordbox_xml=rb_path,
    )
    display_stale_report(result, console=console)
