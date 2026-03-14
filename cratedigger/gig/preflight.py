"""Pre-flight readiness check for gig playlists."""

import logging
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console
from rich.table import Table

from cratedigger.gig.rekordbox_parser import RekordboxLibrary, RekordboxTrack

logger = logging.getLogger(__name__)
console = Console()


class ReadinessLevel(Enum):
    """Track readiness for a gig."""

    READY = "ready"
    NEEDS_WORK = "needs-work"
    NOT_READY = "not-ready"


@dataclass
class TrackReadiness:
    """Readiness assessment for a single track."""

    track: RekordboxTrack
    level: ReadinessLevel = ReadinessLevel.NOT_READY
    has_bpm: bool = False
    has_key: bool = False
    is_analyzed: bool = False
    has_cue_points: bool = False
    has_hot_cues: bool = False
    has_beatgrid: bool = False
    issues: list[str] = field(default_factory=list)


@dataclass
class PreflightReport:
    """Overall pre-flight report for a playlist."""

    playlist_name: str
    track_results: list[TrackReadiness] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.track_results)

    @property
    def ready_count(self) -> int:
        return sum(1 for t in self.track_results if t.level == ReadinessLevel.READY)

    @property
    def needs_work_count(self) -> int:
        return sum(1 for t in self.track_results if t.level == ReadinessLevel.NEEDS_WORK)

    @property
    def not_ready_count(self) -> int:
        return sum(1 for t in self.track_results if t.level == ReadinessLevel.NOT_READY)

    @property
    def ready_percent(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.ready_count / self.total * 100, 1)


def check_track(track: RekordboxTrack) -> TrackReadiness:
    """Assess readiness of a single track."""
    result = TrackReadiness(track=track)

    # BPM check
    result.has_bpm = track.bpm is not None and track.bpm > 0
    if not result.has_bpm:
        result.issues.append("Missing BPM")

    # Key check
    result.has_key = track.key is not None and track.key.strip() != ""
    if not result.has_key:
        result.issues.append("Missing key")

    # Beatgrid check
    result.has_beatgrid = track.has_beatgrid
    if not result.has_beatgrid:
        result.issues.append("No beatgrid")

    # Analysis check (has TEMPO elements = analyzed in Rekordbox)
    result.is_analyzed = track.has_beatgrid

    # Cue points
    result.has_cue_points = len(track.cue_points) > 0
    result.has_hot_cues = len(track.hot_cues) > 0
    if not result.has_cue_points:
        result.issues.append("No cue points")

    # Determine level
    if result.has_bpm and result.has_key and result.is_analyzed and result.has_hot_cues:
        result.level = ReadinessLevel.READY
    elif result.is_analyzed:
        result.level = ReadinessLevel.NEEDS_WORK
    else:
        result.level = ReadinessLevel.NOT_READY

    return result


def run_preflight(
    library: RekordboxLibrary,
    playlist_name: str,
) -> PreflightReport:
    """Run pre-flight check on a playlist.

    Args:
        library: Parsed Rekordbox library.
        playlist_name: Name of the playlist to check.

    Returns:
        PreflightReport with per-track results.
    """
    tracks = library.get_playlist_tracks(playlist_name)
    report = PreflightReport(playlist_name=playlist_name)

    for track in tracks:
        result = check_track(track)
        report.track_results.append(result)

    return report


def display_preflight(report: PreflightReport) -> None:
    """Display pre-flight report with rich terminal output."""
    console.print(f"\n  [bold magenta]Pre-Flight Check:[/bold magenta] {report.playlist_name}\n")

    if report.total == 0:
        console.print("  [yellow]No tracks in playlist.[/yellow]\n")
        return

    # Summary
    ready_style = "green" if report.ready_percent >= 80 else "yellow" if report.ready_percent >= 50 else "red"
    console.print(f"  [{ready_style}]{report.ready_percent:.0f}% ready[/{ready_style}] "
                  f"({report.ready_count} ready, {report.needs_work_count} needs work, "
                  f"{report.not_ready_count} not ready)")

    # Track table
    table = Table(title=f"\n{report.playlist_name} — {report.total} tracks")
    table.add_column("#", style="dim", justify="right", width=3)
    table.add_column("Track", style="cyan", max_width=35)
    table.add_column("Artist", max_width=20)
    table.add_column("BPM", justify="right", width=6)
    table.add_column("Key", width=5)
    table.add_column("Grid", width=4)
    table.add_column("Cues", width=4)
    table.add_column("Status", width=12)

    for i, result in enumerate(report.track_results, 1):
        t = result.track
        status_style = {
            ReadinessLevel.READY: "green",
            ReadinessLevel.NEEDS_WORK: "yellow",
            ReadinessLevel.NOT_READY: "red",
        }[result.level]

        table.add_row(
            str(i),
            t.name[:35],
            t.artist[:20],
            f"{t.bpm:.0f}" if t.bpm else "[red]--[/red]",
            t.key or "[red]--[/red]",
            "[green]OK[/green]" if result.has_beatgrid else "[red]NO[/red]",
            f"[green]{len(t.hot_cues)}[/green]" if result.has_hot_cues else "[red]0[/red]",
            f"[{status_style}]{result.level.value}[/{status_style}]",
        )

    console.print(table)

    # Action items
    action_items = []
    for result in report.track_results:
        if result.level != ReadinessLevel.READY:
            action_items.append(
                f"  {result.track.artist} - {result.track.name}: {', '.join(result.issues)}"
            )

    if action_items:
        console.print(f"\n  [bold]Action Items ({len(action_items)}):[/bold]")
        for item in action_items:
            console.print(f"  [yellow]{item}[/yellow]")

    console.print()
