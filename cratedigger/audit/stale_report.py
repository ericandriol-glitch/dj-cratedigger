"""Rich terminal report for stale track analysis."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .stale import StaleResult

REASON_LABELS = {
    "never_played": "[red]Never Played[/red]",
    "dormant": "[yellow]Dormant[/yellow]",
    "outlier": "[cyan]Outlier[/cyan]",
}


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def display_stale_report(result: StaleResult, console: Console | None = None) -> None:
    """Render stale track analysis with rich output grouped by genre.

    Args:
        result: StaleResult from find_stale_tracks.
        console: Optional Rich console (creates one if not provided).
    """
    if console is None:
        console = Console(force_terminal=True, force_jupyter=False)

    console.print()
    console.print(Panel.fit(
        "[bold magenta]DJ CrateDigger[/bold magenta] — Stale Track Audit",
        border_style="magenta",
    ))

    # Summary
    stale_count = len(result.stale_tracks)
    console.print(f"\n  [bold]Library:[/bold] {result.total_library} tracks")
    console.print(f"  [bold]Stale:[/bold] {stale_count} tracks "
                  f"({stale_count / result.total_library * 100:.1f}%)"
                  if result.total_library > 0
                  else "  [bold]Stale:[/bold] 0 tracks")
    console.print(f"  [bold]Reclaimable:[/bold] {_format_size(result.total_size_bytes)}")

    if not result.stale_tracks:
        console.print("\n  [green]No stale tracks found. Library is fresh![/green]\n")
        return

    # Reason breakdown
    reason_counts: dict[str, int] = {}
    for track in result.stale_tracks:
        reason_counts[track.reason] = reason_counts.get(track.reason, 0) + 1
    console.print("\n  [bold]Breakdown:[/bold]")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
        label = REASON_LABELS.get(reason, reason)
        console.print(f"    {label}: {count}")

    # Per-genre tables
    for genre in sorted(result.by_genre.keys()):
        tracks = result.by_genre[genre]
        console.print(f"\n  [bold cyan]{genre}[/bold cyan] ({len(tracks)} tracks)")

        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("Artist", style="white", max_width=25)
        table.add_column("Title", style="dim", max_width=30)
        table.add_column("Added", style="dim", width=10)
        table.add_column("Reason", width=14)

        for track in tracks[:20]:  # Cap display at 20 per genre
            label = REASON_LABELS.get(track.reason, track.reason)
            table.add_row(
                track.artist,
                track.title,
                track.date_added or "?",
                label,
            )

        if len(tracks) > 20:
            table.add_row("", f"... and {len(tracks) - 20} more", "", "")

        console.print(table)

    console.print()
