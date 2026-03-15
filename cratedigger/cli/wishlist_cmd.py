"""CLI commands for wishlist management."""

from __future__ import annotations

import click
from rich.console import Console

from . import cli


@cli.command("wishlist")
@click.argument(
    "action",
    type=click.Choice(["show", "add", "remove", "find", "clear"]),
)
@click.option("--artist", help="Artist name (for add).")
@click.option("--title", help="Track title (for add).")
@click.option("--source", help="Discovery source (for add/filter).")
@click.option(
    "--priority",
    type=click.Choice(["high", "medium", "low"]),
    default="medium",
    help="Priority level.",
)
@click.option("--style", help="Filter by style tag.")
@click.option(
    "--sort",
    type=click.Choice(["priority", "date", "artist", "source"]),
    default="priority",
    help="Sort order for show.",
)
@click.option(
    "--status",
    type=click.Choice(["new", "previewed", "downloaded", "in-library"]),
    help="Filter or set status.",
)
@click.option("--id", "track_id", type=int, help="Track ID (for remove/update).")
@click.option("--notes", help="Optional notes (for add).")
def wishlist(
    action: str,
    artist: str | None,
    title: str | None,
    source: str | None,
    priority: str,
    style: str | None,
    sort: str,
    status: str | None,
    track_id: int | None,
    notes: str | None,
) -> None:
    """Manage your track wishlist.

    Actions:
      show    — Display wishlist (with optional filters)
      add     — Add a track (requires --artist and --title)
      remove  — Remove a track by --id
      find    — Cross-reference wishlist against your library
      clear   — Remove all tracks with status 'in-library'
    """
    from cratedigger.discovery.wishlist import (
        add_track,
        check_library_overlap,
        get_stats,
        get_wishlist,
        remove_track,
        update_status,
    )
    from cratedigger.discovery.wishlist_report import print_wishlist

    console = Console()

    if action == "show":
        tracks = get_wishlist(style=style, source=source, status=status, sort=sort)
        stats = get_stats()
        print_wishlist(tracks, stats, console)

    elif action == "add":
        if not artist or not title:
            console.print("[red]  --artist and --title are required for add.[/red]")
            raise SystemExit(1)
        track = add_track(
            artist=artist,
            title=title,
            source=source or "manual",
            priority=priority,
            style_tag=style,
            notes=notes,
        )
        console.print(
            f"\n  [green]Added:[/green] {track.artist} - {track.title} "
            f"[dim](priority={track.priority}, source={track.source})[/dim]\n"
        )

    elif action == "remove":
        if not track_id:
            console.print("[red]  --id is required for remove.[/red]")
            raise SystemExit(1)
        if remove_track(track_id):
            console.print(f"\n  [green]Removed track #{track_id}.[/green]\n")
        else:
            console.print(f"\n  [red]Track #{track_id} not found.[/red]\n")

    elif action == "find":
        matched = check_library_overlap()
        if matched:
            console.print(f"\n  [green]Found {len(matched)} wishlist track(s) in your library:[/green]")
            for t in matched:
                console.print(f"    [dim]v[/dim] {t.artist} - {t.title}")
        else:
            console.print("\n  [dim]No wishlist tracks found in library.[/dim]")
        console.print()

    elif action == "clear":
        tracks = get_wishlist(status="in-library")
        for t in tracks:
            remove_track(t.id)
        console.print(
            f"\n  [green]Cleared {len(tracks)} track(s) with status 'in-library'.[/green]\n"
        )
