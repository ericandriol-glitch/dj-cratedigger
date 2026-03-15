"""Pretty-print a dig session report using Rich."""

from datetime import date

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cratedigger.discovery.session import SessionReport


def print_session_report(report: SessionReport, console: Console) -> None:
    """Render a SessionReport to the terminal with Rich formatting.

    Args:
        report: The completed session report to display.
        console: Rich Console instance for output.
    """
    today = date.today().strftime("%B %d, %Y")

    console.print()
    console.print(Panel.fit(
        f"[bold green]WEEKLY DIG SESSION[/bold green] -- {today}",
        border_style="green",
    ))

    # Per-source summary
    for dr in report.results:
        source_label = {
            "weekly": "New releases (Traxsource)",
            "artist": "Artist releases",
            "sleeping": "Sleeping on (Spotify)",
        }.get(dr.source, dr.source)

        found = len(dr.tracks)
        # Count how many from this source are new (not owned, not on wishlist)
        new_count = 0
        for t in dr.tracks:
            if not t.get("owned") and not t.get("on_wishlist"):
                new_count += 1

        console.print(
            f"  {source_label + ':':<35s} "
            f"[cyan]{found:>3}[/cyan] found, "
            f"[green]{new_count:>3}[/green] new to you"
        )

    # Divider and totals
    console.print("  " + "-" * 50)
    console.print(
        f"  [bold]Total new discoveries:[/bold] [green]{report.new_to_you}[/green]"
        f"  |  Already owned: [dim]{report.already_owned}[/dim]"
        f"  |  On wishlist: [dim]{report.already_on_wishlist}[/dim]"
    )

    # Track listing — only show tracks that are new
    new_tracks = [t for t in report.tracks if not t.get("owned") and not t.get("on_wishlist")]
    if not new_tracks:
        console.print("\n  [yellow]No new discoveries this session.[/yellow]\n")
        return

    console.print()

    # Group by source if we can, otherwise flat list
    table = Table(
        show_header=True,
        box=None,
        padding=(0, 2),
        title="NEW DISCOVERIES",
        title_style="bold",
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Artist", style="cyan", max_width=30)
    table.add_column("Title", style="white", max_width=35)
    table.add_column("BPM", justify="right", style="yellow", width=5)
    table.add_column("Genre", style="dim", max_width=20)
    table.add_column("", width=2)  # preview indicator

    for idx, t in enumerate(new_tracks[:30], 1):
        bpm_str = str(int(t["bpm"])) if t.get("bpm") else ""
        preview = "[green]>>[/green]" if t.get("preview_url") else ""
        table.add_row(
            str(idx),
            t.get("artist", "?"),
            t.get("title", ""),
            bpm_str,
            t.get("genre", ""),
            preview,
        )

    console.print(table)
    if len(new_tracks) > 30:
        console.print(f"  [dim]... and {len(new_tracks) - 30} more[/dim]")

    # Preview hint
    previewable = sum(1 for t in new_tracks[:30] if t.get("preview_url"))
    if previewable:
        console.print(
            f"\n  [dim][green]>>[/green] = preview available ({previewable} tracks)[/dim]"
        )

    console.print()
