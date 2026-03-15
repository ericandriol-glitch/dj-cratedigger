"""Interactive review queue for intake tracks."""

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .models import IntakeTrack

console = Console()


def _genre_to_folder(genre: str | None) -> str:
    """Convert genre to a filesystem-friendly folder name."""
    if not genre:
        return "unsorted"
    return genre.lower().replace(" & ", "-").replace(" ", "-")


def _display_identified_track(track: IntakeTrack, index: int, total: int) -> None:
    """Display a track that has been identified."""
    header = f"TRACK {index} of {total}"
    lines = Text()
    lines.append(f"Source file:    {track.original_filename}\n", style="dim")
    lines.append(
        f"Identified via: {track.identified_via} "
        f"(confidence: {track.identification_confidence:.2f})\n\n",
        style="dim",
    )
    lines.append(f"Artist:     {track.artist or '—'}\n", style="bold")
    lines.append(f"Title:      {track.title or '—'}\n", style="bold")
    if track.bpm:
        lines.append(f"BPM:        {track.bpm:.0f} ({track.bpm_source})\n")
    if track.key_camelot:
        lines.append(f"Key:        {track.key_camelot} ({track.key_source})\n")
    if track.genre:
        lines.append(f"Genre:      {track.genre}\n")
    if track.energy is not None:
        lines.append(f"Energy:     {track.energy:.2f}\n")
    lines.append(f"\nSuggested filename: {track.suggested_filename}\n", style="cyan")

    console.print(Panel(lines, title=header, border_style="green"))


def _display_unidentified_track(track: IntakeTrack, index: int, total: int) -> None:
    """Display a track that could not be identified."""
    header = f"TRACK {index} of {total}  !! UNIDENTIFIED"
    lines = Text()
    lines.append(f"Source file:    {track.original_filename}\n", style="dim")
    if track.bpm:
        lines.append(f"BPM:        {track.bpm:.0f} ({track.bpm_source})\n")
    if track.key_camelot:
        lines.append(f"Key:        {track.key_camelot} ({track.key_source})\n")

    console.print(Panel(lines, title=header, border_style="yellow"))


def _prompt_manual_entry(track: IntakeTrack) -> None:
    """Prompt user to manually enter artist/title for unidentified tracks."""
    artist = console.input("[bold]Artist:[/bold] ").strip()
    title = console.input("[bold]Title:[/bold] ").strip()
    if artist:
        track.artist = artist
    if title:
        track.title = title
    if artist and title:
        track.identified_via = "manual"
        track.identification_confidence = 1.0
        ext = track.filepath.suffix
        track.suggested_filename = f"{artist} - {title}{ext}"


def _prompt_review(track: IntakeTrack, dest: Path) -> str:
    """Prompt user to accept, edit, or skip a track.

    Returns:
        Action taken: "approved", "edited", "skipped", "skip-rest", "auto-rest".
    """
    while True:
        choice = console.input(
            "\nAccept filename? [green][Y][/green]/n/edit/skip-rest/auto-rest: "
        ).strip().lower()

        if choice in ("", "y", "yes"):
            # Accept suggested filename
            folder = console.input(
                f"Destination folder? [{_genre_to_folder(track.genre)}]: "
            ).strip()
            track.destination_folder = folder or _genre_to_folder(track.genre)
            track.status = "approved"
            return "approved"

        elif choice in ("n", "no", "skip"):
            track.status = "skipped"
            return "skipped"

        elif choice == "edit":
            new_name = console.input(
                f"New filename [{track.suggested_filename}]: "
            ).strip()
            if new_name:
                track.suggested_filename = new_name
            folder = console.input(
                f"Destination folder? [{_genre_to_folder(track.genre)}]: "
            ).strip()
            track.destination_folder = folder or _genre_to_folder(track.genre)
            track.status = "edited"
            return "edited"

        elif choice == "skip-rest":
            track.status = "skipped"
            return "skip-rest"

        elif choice == "auto-rest":
            track.destination_folder = _genre_to_folder(track.genre)
            track.status = "approved"
            return "auto-rest"

        else:
            console.print("[dim]Options: Y (accept), n (skip), edit, skip-rest, auto-rest[/dim]")


def _auto_accept(track: IntakeTrack) -> None:
    """Auto-accept a track with default folder assignment."""
    track.destination_folder = _genre_to_folder(track.genre)
    track.status = "approved"


def run_review_queue(
    tracks: list[IntakeTrack],
    dest: Path,
    auto: bool = False,
) -> list[IntakeTrack]:
    """Run the interactive review queue for intake tracks.

    Args:
        tracks: List of IntakeTrack objects from the pipeline.
        dest: Destination root folder.
        auto: If True, auto-accept all tracks without prompting.

    Returns:
        The same track list with updated status and destination fields.
    """
    if auto:
        console.print("\n[bold cyan]Auto-accepting[/bold cyan] all tracks")
        for track in tracks:
            _auto_accept(track)
        approved = sum(1 for t in tracks if t.status == "approved")
        console.print(f"  [green]{approved}[/green] tracks approved")
        return tracks

    console.print(f"\n[bold cyan]Review Queue[/bold cyan] — {len(tracks)} tracks to review\n")
    auto_rest = False

    for i, track in enumerate(tracks, 1):
        if auto_rest:
            _auto_accept(track)
            continue

        is_identified = track.identified_via != "none"

        if is_identified:
            _display_identified_track(track, i, len(tracks))
        else:
            _display_unidentified_track(track, i, len(tracks))
            _prompt_manual_entry(track)
            # Re-generate suggested filename after manual entry
            if track.artist and track.title:
                _display_identified_track(track, i, len(tracks))

        action = _prompt_review(track, dest)

        if action == "skip-rest":
            # Mark all remaining as skipped
            for remaining in tracks[i:]:
                remaining.status = "skipped"
            break
        elif action == "auto-rest":
            auto_rest = True

    approved = sum(1 for t in tracks if t.status in ("approved", "edited"))
    skipped = sum(1 for t in tracks if t.status == "skipped")
    console.print(f"\n  Approved: [green]{approved}[/green] | Skipped: [yellow]{skipped}[/yellow]")

    return tracks
