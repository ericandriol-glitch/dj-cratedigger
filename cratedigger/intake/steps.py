"""Pipeline steps — scan, read metadata, enrich genres, suggest filenames."""

import logging
import re
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from cratedigger.metadata import read_metadata
from cratedigger.fixers.parse_filename import parse_filename
from cratedigger.scanner import find_audio_files

from .models import IntakeTrack

logger = logging.getLogger(__name__)
console = Console()


def _sanitize_filename(name: str) -> str:
    """Remove characters illegal in filenames."""
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


def build_suggested_filename(track: IntakeTrack) -> str | None:
    """Generate 'Artist - Title.ext' filename from track metadata."""
    if not track.artist or not track.title:
        return None
    clean_artist = _sanitize_filename(track.artist)
    clean_title = _sanitize_filename(track.title)
    if not clean_artist or not clean_title:
        return None
    ext = track.filepath.suffix
    return f"{clean_artist} - {clean_title}{ext}"


def step_scan(source: Path) -> list[Path]:
    """Find all audio files in source folder.

    Args:
        source: Root directory to scan recursively.

    Returns:
        List of audio file paths found.
    """
    console.print(f"\n[bold cyan]Scanning[/bold cyan] {source}")
    files = find_audio_files(source)
    console.print(f"  Found [green]{len(files)}[/green] audio files")
    return files


def step_read_metadata(files: list[Path]) -> list[IntakeTrack]:
    """Read existing tags from each file and parse filenames as fallback.

    Args:
        files: List of audio file paths to read.

    Returns:
        List of IntakeTrack objects with metadata populated.
    """
    tracks: list[IntakeTrack] = []
    console.print("\n[bold cyan]Reading metadata[/bold cyan]")

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"),
        BarColumn(), MofNCompleteColumn(), transient=True,
    ) as progress:
        task = progress.add_task("Reading tags...", total=len(files))
        for fp in files:
            track = IntakeTrack(filepath=fp, original_filename=fp.name)
            try:
                meta = read_metadata(fp)
                track.artist = meta.artist
                track.title = meta.title
                track.album = meta.album
                track.genre = meta.genre
                track.year = str(meta.year) if meta.year else None
                if meta.bpm:
                    track.bpm = meta.bpm
                    track.bpm_source = "tag"
                if meta.key:
                    from cratedigger.core.analyzer import musical_key_to_camelot
                    track.key_camelot = musical_key_to_camelot(meta.key) or meta.key
                    track.key_source = "tag"
                if track.artist and track.title:
                    track.identified_via = "metadata"
                    track.identification_confidence = 1.0
            except Exception as exc:
                logger.warning("Failed to read metadata for %s: %s", fp.name, exc)

            # Fallback: parse filename
            if not track.artist or not track.title:
                try:
                    parsed = parse_filename(fp)
                    if parsed.artist and not track.artist:
                        track.artist = parsed.artist
                    if parsed.title and not track.title:
                        track.title = parsed.title
                    if parsed.year and not track.year:
                        track.year = str(parsed.year)
                    if track.artist and track.title and track.identified_via == "none":
                        track.identified_via = "filename"
                        track.identification_confidence = 0.6
                except Exception as exc:
                    logger.warning("Failed to parse filename %s: %s", fp.name, exc)

            tracks.append(track)
            progress.advance(task)

    identified = sum(1 for t in tracks if t.identified_via != "none")
    console.print(f"  Identified [green]{identified}[/green]/{len(tracks)} from tags/filenames")
    return tracks


def step_enrich(tracks: list[IntakeTrack]) -> None:
    """Genre enrichment via MusicBrainz for tracks missing genre tags.

    Args:
        tracks: List of IntakeTrack objects to enrich in-place.
    """
    need_genre = [t for t in tracks if not t.genre and t.artist and t.title]
    if not need_genre:
        console.print("\n[bold cyan]Enrichment[/bold cyan] — all tracks have genre tags")
        return

    console.print(f"\n[bold cyan]Enriching[/bold cyan] {len(need_genre)} tracks via MusicBrainz")

    try:
        from cratedigger.enrichment.musicbrainz import lookup_genre
    except ImportError:
        console.print("  [yellow]musicbrainzngs not installed — skipping enrichment[/yellow]")
        return

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"),
        BarColumn(), MofNCompleteColumn(), transient=True,
    ) as progress:
        task = progress.add_task("MusicBrainz lookup...", total=len(need_genre))
        for track in need_genre:
            try:
                result = lookup_genre(track.artist, track.title)
                if result.genre:
                    track.genre = result.genre
            except Exception as exc:
                logger.warning("Genre lookup failed for %s: %s", track.filepath.name, exc)
            progress.advance(task)

    enriched = sum(1 for t in need_genre if t.genre)
    console.print(f"  Genre found for [green]{enriched}[/green]/{len(need_genre)} tracks")


def step_suggest_filenames(tracks: list[IntakeTrack]) -> None:
    """Generate suggested filenames for all tracks.

    Uses 'Artist - Title.ext' format when metadata is available,
    falls back to original filename otherwise.

    Args:
        tracks: List of IntakeTrack objects to update in-place.
    """
    for track in tracks:
        track.suggested_filename = build_suggested_filename(track) or track.original_filename
