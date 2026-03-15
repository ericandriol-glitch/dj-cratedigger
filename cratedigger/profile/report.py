"""Rich terminal report for enhanced DJ profile."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .enhanced import DJProfile


def _bpm_histogram_bar(lo: float, hi: float, sweet_lo: float, sweet_hi: float) -> str:
    """Create a simple text-based BPM range visualization."""
    # Show range with sweet spot highlighted
    return (
        f"[dim]{lo:.0f}[/dim] "
        f"{'=' * 5} "
        f"[bold green]{sweet_lo:.0f}-{sweet_hi:.0f}[/bold green] "
        f"{'=' * 5} "
        f"[dim]{hi:.0f}[/dim]"
    )


def display_enhanced_profile(profile: DJProfile, console: Console | None = None) -> None:
    """Render the enhanced DJ profile with rich terminal output.

    Shows genre bars, BPM histogram, key preferences, streaming divergence,
    and the sound summary.

    Args:
        profile: DJProfile to display.
        console: Optional Rich console (creates one if not provided).
    """
    if console is None:
        console = Console(force_terminal=True, force_jupyter=False)

    console.print()
    console.print(Panel.fit(
        "[bold magenta]DJ CrateDigger[/bold magenta] — Enhanced DJ Profile",
        border_style="magenta",
    ))

    # Overview
    console.print(f"\n  [bold]Library:[/bold] {profile.total_tracks} tracks")
    console.print(f"  [bold]Added last 3 months:[/bold] {profile.tracks_added_last_3_months}")
    if profile.oldest_track_date:
        console.print(f"  [bold]Oldest track:[/bold] {profile.oldest_track_date}")

    # BPM
    if profile.bpm_range != (0.0, 0.0):
        console.print(f"\n  [bold]BPM Range:[/bold]")
        bpm_bar = _bpm_histogram_bar(
            profile.bpm_range[0], profile.bpm_range[1],
            profile.bpm_sweet_spot[0], profile.bpm_sweet_spot[1],
        )
        console.print(f"    {bpm_bar}")

    # Energy
    if profile.energy_range != (0.0, 0.0):
        lo, hi = profile.energy_range
        console.print(f"\n  [bold]Energy:[/bold] {lo:.2f} - {hi:.2f}")

    # Genre distribution with bars
    if profile.genre_distribution:
        console.print("\n  [bold]Genre Distribution:[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Genre", style="cyan", min_width=18)
        table.add_column("Share", justify="right", style="green", width=6)
        table.add_column("Bar", min_width=25)
        max_pct = max(profile.genre_distribution.values()) if profile.genre_distribution else 1
        for genre, pct in list(profile.genre_distribution.items())[:12]:
            bar_len = int((pct / max_pct) * 25) if max_pct > 0 else 0
            bar = "[green]" + "\u2588" * bar_len + "[/green]"
            table.add_row(genre, f"{pct:.1f}%", bar)
        console.print(table)

    # Key preferences
    if profile.key_preferences:
        console.print("\n  [bold]Top Keys (Camelot):[/bold]")
        keys_str = "  ".join(
            f"[yellow]{k}[/yellow]" for k in profile.key_preferences
        )
        console.print(f"    {keys_str}")
        # Show minor/major bias
        minor = sum(1 for k in profile.key_preferences if k.endswith("A"))
        major = len(profile.key_preferences) - minor
        if minor > major:
            console.print("    [dim]Minor key bias[/dim]")
        elif major > minor:
            console.print("    [dim]Major key bias[/dim]")

    # Top artists
    if profile.top_artists:
        console.print("\n  [bold]Top Artists:[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("#", style="dim", justify="right", width=3)
        table.add_column("Artist", style="cyan", min_width=20)
        table.add_column("Tracks", justify="right", style="green", width=6)
        for i, (name, count) in enumerate(profile.top_artists[:10], 1):
            table.add_row(str(i), name, str(count))
        console.print(table)

    # Top labels
    if profile.top_labels:
        console.print("\n  [bold]Top Labels:[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("#", style="dim", justify="right", width=3)
        table.add_column("Label", style="cyan", min_width=20)
        table.add_column("Tracks", justify="right", style="green", width=6)
        for i, (name, count) in enumerate(profile.top_labels[:10], 1):
            table.add_row(str(i), name, str(count))
        console.print(table)

    # Streaming divergence
    if profile.spotify_divergence:
        console.print("\n  [bold]Spotify Divergence:[/bold]")
        console.print("    [dim]Genres you stream but don't own:[/dim]")
        for item in profile.spotify_divergence[:5]:
            console.print(f"    [yellow]\u2022[/yellow] {item['genre']}")

    # Sound summary
    if profile.sound_summary:
        console.print()
        console.print(Panel.fit(
            f"[italic]{profile.sound_summary}[/italic]",
            title="[bold]Your Sound[/bold]",
            border_style="cyan",
        ))

    console.print()
