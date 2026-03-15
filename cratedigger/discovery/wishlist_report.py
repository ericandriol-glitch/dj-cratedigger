"""Pretty-print wishlist report using Rich console."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from .wishlist import WishlistTrack


def _format_track_line(idx: int, track: WishlistTrack) -> Text:
    """Format a single track line for display."""
    line = Text()
    line.append(f"  {idx:>3}. ", style="dim")
    line.append(f"{track.artist}", style="bold")
    line.append(f" - {track.title}", style="")
    # Source and date suffix
    date_short = track.date_added[:10] if track.date_added else ""
    line.append(f"     [{track.source}, {date_short}]", style="dim")
    if track.style_tag:
        line.append(f"  #{track.style_tag}", style="cyan")
    return line


def _format_library_line(track: WishlistTrack) -> Text:
    """Format an in-library track line."""
    line = Text()
    line.append("  ", style="")
    line.append("v ", style="green bold")
    line.append(f"{track.artist} - {track.title}", style="dim strike")
    line.append("  (you own this)", style="green dim")
    return line


def print_wishlist(
    tracks: list[WishlistTrack],
    stats: dict,
    console: Console,
) -> None:
    """Pretty-print the wishlist grouped by priority.

    Args:
        tracks: List of WishlistTrack objects (pre-sorted).
        stats: Stats dict from get_stats().
        console: Rich Console instance.
    """
    total = stats.get("total", 0)
    console.print()
    console.print(f"  [bold magenta]WISHLIST[/bold magenta] ({total} tracks)")
    console.print("  " + "\u2500" * 42)

    if not tracks:
        console.print("  [dim]No tracks in wishlist.[/dim]")
        console.print()
        return

    # Group by priority, with in-library separate
    priority_groups: dict[str, list[WishlistTrack]] = {
        "high": [],
        "medium": [],
        "low": [],
    }
    in_library: list[WishlistTrack] = []

    for track in tracks:
        if track.status == "in-library":
            in_library.append(track)
        elif track.priority in priority_groups:
            priority_groups[track.priority].append(track)

    # Print each priority group
    priority_styles = {
        "high": "bold red",
        "medium": "bold yellow",
        "low": "bold blue",
    }

    idx = 1
    for priority in ("high", "medium", "low"):
        group = priority_groups[priority]
        if not group:
            continue
        console.print()
        label = f"{priority.upper()} PRIORITY ({len(group)})"
        console.print(f"  [{priority_styles[priority]}]{label}[/{priority_styles[priority]}]")
        for track in group:
            console.print(_format_track_line(idx, track))
            idx += 1

    # Print in-library section
    if in_library:
        console.print()
        console.print(f"  [bold green]ALREADY IN LIBRARY ({len(in_library)})[/bold green]")
        for track in in_library:
            console.print(_format_library_line(track))

    console.print()
