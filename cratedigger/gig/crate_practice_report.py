"""Rich display for crate practice analysis."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from .crate_practice import TransitionAnalysis

DIFFICULTY_STYLES = {
    "easy": "green",
    "medium": "yellow",
    "hard": "red bold",
}


def print_transition_table(
    analyses: list[TransitionAnalysis],
    console: Console,
    title: str = "Transition Practice",
) -> None:
    """Print a table of transition analyses.

    Args:
        analyses: List of TransitionAnalysis to display.
        console: Rich Console instance.
        title: Header title for the table.
    """
    if not analyses:
        console.print("\n  [yellow]No transitions to display.[/yellow]\n")
        return

    console.print()
    header = Text()
    header.append("  DJ CrateDigger", style="bold magenta")
    header.append(f" -- {title}", style="bold white")
    console.print(header)
    console.print()

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("From", style="cyan", max_width=28)
    table.add_column("To", style="cyan", max_width=28)
    table.add_column("BPM", justify="center", width=11)
    table.add_column("Key", justify="center", width=9)
    table.add_column("Energy", justify="center", width=8)
    table.add_column("Diff", justify="center", width=6)
    table.add_column("Advice", style="dim", max_width=45)

    for i, a in enumerate(analyses, 1):
        from_name = f"{a.track_a.artist} - {a.track_a.title}"
        to_name = f"{a.track_b.artist} - {a.track_b.title}"
        if len(from_name) > 26:
            from_name = from_name[:23] + "..."
        if len(to_name) > 26:
            to_name = to_name[:23] + "..."

        diff_style = DIFFICULTY_STYLES.get(a.difficulty, "white")
        key_display = f"{a.track_a.key_camelot}->{a.track_b.key_camelot}"

        table.add_row(
            str(i),
            from_name,
            to_name,
            f"{a.track_a.bpm:.0f}->{a.track_b.bpm:.0f}",
            key_display,
            f"{a.energy_delta:.2f}",
            f"[{diff_style}]{a.difficulty.upper()}[/{diff_style}]",
            a.suggestion[:45],
        )

    console.print(table)
    console.print()


def print_practice_history(
    history: list[dict],
    console: Console,
) -> None:
    """Print practice history log.

    Args:
        history: List of practice log dicts.
        console: Rich Console instance.
    """
    if not history:
        console.print("\n  [yellow]No practice history yet.[/yellow]\n")
        return

    console.print()
    console.print("  [bold magenta]Practice History[/bold magenta]")
    console.print()

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("From", style="cyan", max_width=30)
    table.add_column("To", style="cyan", max_width=30)
    table.add_column("Confidence", justify="center", width=12)
    table.add_column("Date", style="dim", width=20)

    for entry in history[:20]:  # Show last 20
        conf = entry["confidence"]
        conf_style = {"high": "green", "medium": "yellow", "low": "red"}.get(
            conf, "white",
        )
        # Extract just the filename for display
        track_a = entry["track_a"].rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        track_b = entry["track_b"].rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

        table.add_row(
            str(entry["id"]),
            track_a[:28],
            track_b[:28],
            f"[{conf_style}]{conf}[/{conf_style}]",
            entry["practiced_at"][:19],
        )

    console.print(table)
    console.print()
