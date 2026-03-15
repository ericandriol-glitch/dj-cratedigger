"""CLI command for crate-based transition practice."""

from pathlib import Path

import click
from rich.console import Console

from . import cli


@cli.command("gig-practice")
@click.option("--crate", required=True, help="Crate name to practice with")
@click.option(
    "--focus",
    type=click.Choice(["hard", "medium", "all"]),
    default="hard",
    help="Filter transitions by difficulty",
)
@click.option("--count", default=5, type=int, help="Number of transitions to show")
@click.option("--history", is_flag=True, help="Show practice history instead")
@click.option(
    "--db-path",
    default=None,
    type=click.Path(resolve_path=True),
    help="Custom database path",
)
def gig_practice(
    crate: str,
    focus: str,
    count: int,
    history: bool,
    db_path: str | None,
) -> None:
    """Analyze transitions in a crate and prioritize practice."""
    from ..gig.crate import load_crate
    from ..gig.crate_practice import find_hardest_transitions, get_practice_history
    from ..gig.crate_practice_report import (
        print_practice_history,
        print_transition_table,
    )

    console = Console()
    db = Path(db_path) if db_path else None

    # History mode
    if history:
        logs = get_practice_history(db_path=db)
        print_practice_history(logs, console)
        return

    # Load the crate
    loaded = load_crate(crate, db_path=db)
    if loaded is None:
        console.print(f"\n  [red]Crate '{crate}' not found.[/red]")
        console.print("  Use [bold]cratedigger gig-crate --list[/bold] to see saved crates.\n")
        return

    if len(loaded.tracks) < 2:
        console.print("\n  [yellow]Need at least 2 tracks for practice analysis.[/yellow]\n")
        return

    # Find transitions
    analyses = find_hardest_transitions(loaded, count=len(loaded.tracks))

    # Filter by focus
    if focus == "hard":
        filtered = [a for a in analyses if a.difficulty == "hard"]
        title = f"Hard Transitions in '{crate}'"
    elif focus == "medium":
        filtered = [a for a in analyses if a.difficulty in ("hard", "medium")]
        title = f"Medium+ Transitions in '{crate}'"
    else:
        filtered = analyses
        title = f"All Transitions in '{crate}'"

    # Limit to requested count
    filtered = filtered[:count]

    if not filtered:
        console.print(f"\n  [green]No {focus} transitions found — crate flows smoothly![/green]\n")
        return

    print_transition_table(filtered, console, title=title)
