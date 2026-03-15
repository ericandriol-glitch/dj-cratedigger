"""Pretty-print gig crate reports using Rich."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .crate import GigCrate

# Zone display config: (label, emoji, color)
ZONE_DISPLAY = {
    "peak": ("PEAK", "\U0001f525", "red"),
    "build": ("BUILD", "\u26a1", "dark_orange"),
    "groove": ("GROOVE", "\U0001f30a", "cyan"),
    "warmup": ("WARM-UP", "\U0001f319", "blue"),
}


def _format_duration(seconds: float) -> str:
    """Format seconds as 'Xh Ym'."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _genre_summary(dist: dict[str, int], total: int) -> str:
    """Format genre distribution as percentage summary."""
    if not dist:
        return "none"
    parts = []
    for genre, count in list(dist.items())[:5]:
        pct = int(round(100 * count / total)) if total else 0
        parts.append(f"{genre} ({pct}%)")
    return ", ".join(parts)


def print_crate_report(crate: GigCrate, console: Console) -> None:
    """Print a formatted gig crate report to the console.

    Args:
        crate: The GigCrate to display.
        console: Rich Console instance for output.
    """
    total = len(crate.tracks)

    # Header
    header = Text()
    header.append("GIG CRATE: ", style="bold magenta")
    header.append(f"{crate.name}", style="bold white")
    header.append(f" ({total} tracks)", style="dim")
    console.print()
    console.print(Panel(header, border_style="magenta", expand=False))

    # Profile section
    profile_lines = []
    bpm_lo, bpm_hi = crate.bpm_range
    profile_lines.append(
        f"  BPM range:      {bpm_lo:.0f}-{bpm_hi:.0f} (median: {crate.bpm_median:.0f})"
    )
    profile_lines.append(
        f"  Styles:         {_genre_summary(crate.genre_distribution, total)}"
    )
    profile_lines.append(
        f"  Total duration: {_format_duration(crate.total_duration_seconds)}"
    )

    key_check = "\u2713" if crate.key_coverage >= 12 else ""
    profile_lines.append(
        f"  Key coverage:   {crate.key_coverage}/24 Camelot keys {key_check}"
    )

    cue_check = "\u2713" if crate.tracks_without_cues == 0 else ""
    profile_lines.append(
        f"  Hot cues:       {crate.tracks_with_cues}/{total} tracks {cue_check}"
    )

    console.print()
    console.print("[bold]CRATE PROFILE:[/bold]")
    for line in profile_lines:
        console.print(line)

    # Energy zone sections
    zone_order = ["peak", "build", "groove", "warmup"]
    zone_ranges = {
        "peak": "0.8-1.0",
        "build": "0.6-0.8",
        "groove": "0.4-0.6",
        "warmup": "0.2-0.4",
    }

    for zone_key in zone_order:
        label, emoji, color = ZONE_DISPLAY[zone_key]
        zone_tracks = crate.energy_zones.get(zone_key, [])

        console.print()
        zone_header = Text()
        zone_header.append(f"{emoji} {label}", style=f"bold {color}")
        zone_header.append(f" (energy {zone_ranges[zone_key]})", style="dim")
        zone_header.append(f" \u2014 {len(zone_tracks)} tracks", style="dim")
        console.print(zone_header)

        if not zone_tracks:
            console.print(f"  [dim]No tracks in this zone[/dim]")
            continue

        table = Table(show_header=False, box=None, padding=(0, 1), expand=False)
        table.add_column("Track", style=color, min_width=40, max_width=50)
        table.add_column("BPM", justify="right", width=8)
        table.add_column("Key", justify="center", width=5)
        table.add_column("Energy", justify="right", width=12)

        # Sort by energy descending within zone
        sorted_tracks = sorted(zone_tracks, key=lambda t: -t.energy)
        for t in sorted_tracks:
            display_name = f"{t.artist} - {t.title}" if t.artist else t.title
            if len(display_name) > 48:
                display_name = display_name[:45] + "..."
            table.add_row(
                f"  {display_name}",
                f"{t.bpm:.0f} BPM",
                t.key_camelot,
                f"energy: {t.energy:.2f}",
            )

        console.print(table)

    # Warnings
    warnings: list[str] = []
    if crate.tracks_without_cues > 0:
        warnings.append(f"{crate.tracks_without_cues} tracks have no hot cues")

    bpms = [t.bpm for t in crate.tracks if t.bpm > 0]
    if bpms and min(bpms) > 120:
        warnings.append(f"No tracks below {min(bpms):.0f} BPM")

    empty_zones = [z for z in zone_order if not crate.energy_zones.get(z)]
    if empty_zones:
        warnings.append(f"Empty zones: {', '.join(empty_zones)}")

    if warnings:
        console.print()
        console.print("[bold yellow]WARNINGS:[/bold yellow]")
        for w in warnings:
            console.print(f"  [yellow]\u26a0 {w}[/yellow]")

    console.print()
