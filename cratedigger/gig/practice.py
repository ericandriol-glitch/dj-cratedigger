"""Transition practice prioritiser — find the tricky mixes in your set."""

from dataclasses import dataclass

from rich.console import Console
from rich.table import Table

from cratedigger.harmonic.camelot import compatibility_score

console = Console()


@dataclass
class Transition:
    """A transition between two adjacent tracks."""

    track_a_name: str
    track_b_name: str
    bpm_a: float
    bpm_b: float
    key_a: str  # Camelot notation
    key_b: str
    energy_a: float
    energy_b: float

    @property
    def bpm_delta(self) -> float:
        return abs(self.bpm_a - self.bpm_b)

    @property
    def energy_delta(self) -> float:
        return abs(self.energy_a - self.energy_b)

    @property
    def harmonic_score(self) -> float:
        try:
            return compatibility_score(self.key_a, self.key_b)
        except ValueError:
            return 0.2


def score_transition(transition: Transition) -> float:
    """Score transition difficulty (0.0 = easy, 1.0 = hardest).

    Scoring:
        BPM delta: >4 = 0.5, >8 = 1.0
        Camelot distance: non-adjacent = 0.5, >3 steps = 1.0
        Energy delta: >0.3 = 0.5, >0.5 = 1.0
        Combined = sum / 3
    """
    # BPM difficulty
    if transition.bpm_delta > 8:
        bpm_score = 1.0
    elif transition.bpm_delta > 4:
        bpm_score = 0.5
    else:
        bpm_score = 0.0

    # Key difficulty (inverse of compatibility)
    harmonic = transition.harmonic_score
    if harmonic <= 0.2:
        key_score = 1.0
    elif harmonic < 0.9:
        key_score = 0.5
    else:
        key_score = 0.0

    # Energy difficulty
    if transition.energy_delta > 0.5:
        energy_score = 1.0
    elif transition.energy_delta > 0.3:
        energy_score = 0.5
    else:
        energy_score = 0.0

    return round((bpm_score + key_score + energy_score) / 3, 2)


def suggest_approach(transition: Transition) -> str:
    """Suggest a mixing approach for a tricky transition."""
    suggestions = []

    if transition.bpm_delta > 4:
        suggestions.append("Use filter/loop transition for BPM change")
    if transition.harmonic_score < 0.5:
        suggestions.append("Short mix with bass swap — keys clash")
    elif transition.harmonic_score < 0.9:
        suggestions.append("Keep mix short — keys are close but not perfect")
    if transition.energy_delta > 0.3:
        suggestions.append("Use breakdown moment for energy shift")

    return "; ".join(suggestions) if suggestions else "Smooth mix — no issues"


def prioritise_practice(transitions: list[Transition]) -> list[tuple[Transition, float]]:
    """Score and sort transitions by difficulty (hardest first).

    Returns:
        List of (transition, difficulty_score) sorted descending.
    """
    scored = [(t, score_transition(t)) for t in transitions]
    scored.sort(key=lambda x: -x[1])
    return scored


def display_practice(scored_transitions: list[tuple[Transition, float]]) -> None:
    """Display practice priorities with rich output."""
    if not scored_transitions:
        console.print("  [yellow]No transitions to practice.[/yellow]\n")
        return

    # Split into "must nail" and "safe"
    must_nail = [(t, s) for t, s in scored_transitions if s > 0.3]
    safe = [(t, s) for t, s in scored_transitions if s <= 0.3]

    if must_nail:
        console.print("\n  [bold red]MUST NAIL:[/bold red]")
        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("#", style="dim", width=3)
        table.add_column("From", style="cyan", max_width=25)
        table.add_column("To", style="cyan", max_width=25)
        table.add_column("BPM", justify="center", width=11)
        table.add_column("Keys", justify="center", width=9)
        table.add_column("Diff", justify="right", width=5)
        table.add_column("Approach", style="yellow", max_width=40)

        for i, (t, score) in enumerate(must_nail, 1):
            table.add_row(
                str(i),
                t.track_a_name[:25],
                t.track_b_name[:25],
                f"{t.bpm_a:.0f}→{t.bpm_b:.0f}",
                f"{t.key_a}→{t.key_b}",
                f"{score:.2f}",
                suggest_approach(t),
            )
        console.print(table)

    if safe:
        console.print(f"\n  [green]SAFE ({len(safe)} transitions):[/green] smooth mixes, no special prep needed")

    console.print()
