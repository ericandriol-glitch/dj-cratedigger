"""Identification and analysis steps — fingerprinting and audio analysis."""

import logging

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from .models import IntakeTrack

logger = logging.getLogger(__name__)
console = Console()


def _get_acoustid_key() -> str | None:
    """Load AcoustID API key from config, or None if unavailable."""
    try:
        from cratedigger.utils.config import get_config
        config = get_config()
        return config.get("acoustid", {}).get("api_key")
    except (FileNotFoundError, ValueError, KeyError):
        return None


def step_fingerprint(tracks: list[IntakeTrack]) -> None:
    """AcoustID fingerprint identification for unidentified tracks.

    Looks up tracks with no artist/title via the AcoustID service.
    Requires an API key in ~/.cratedigger/config.yaml under acoustid.api_key.
    Gracefully skips if the key is missing or the service is unreachable.
    """
    api_key = _get_acoustid_key()
    if not api_key:
        console.print(
            "\n[yellow]Skipping fingerprinting[/yellow] — "
            "no acoustid.api_key in ~/.cratedigger/config.yaml"
        )
        return

    unidentified = [t for t in tracks if t.identified_via == "none"]
    if not unidentified:
        console.print("\n[bold cyan]Fingerprinting[/bold cyan] — all tracks already identified")
        return

    console.print(f"\n[bold cyan]Fingerprinting[/bold cyan] {len(unidentified)} unidentified tracks")
    from cratedigger.core.fingerprint import identify_track

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"),
        BarColumn(), MofNCompleteColumn(), transient=True,
    ) as progress:
        task = progress.add_task("AcoustID lookup...", total=len(unidentified))
        for track in unidentified:
            try:
                result = identify_track(track.filepath, api_key)
                if not result.error and result.artist and result.title:
                    track.artist = result.artist
                    track.title = result.title
                    if result.album:
                        track.album = result.album
                    track.identified_via = "acoustid"
                    track.identification_confidence = result.confidence
            except Exception as exc:
                logger.warning("Fingerprint failed for %s: %s", track.filepath.name, exc)
            progress.advance(task)

    matched = sum(1 for t in unidentified if t.identified_via == "acoustid")
    console.print(f"  Matched [green]{matched}[/green]/{len(unidentified)} via AcoustID")


def step_analyze(tracks: list[IntakeTrack]) -> None:
    """Audio analysis — detect BPM, key, and energy via Essentia or librosa.

    Tries Essentia first for higher-quality results. Falls back to librosa
    if Essentia is not installed. Skips tracks that already have BPM and key.
    """
    need_analysis = [t for t in tracks if t.bpm is None or t.key_camelot is None]
    if not need_analysis:
        console.print("\n[bold cyan]Analysis[/bold cyan] — all tracks have BPM/key from tags")
        return

    console.print(f"\n[bold cyan]Analyzing[/bold cyan] {len(need_analysis)} tracks")

    essentia_available = True
    try:
        from cratedigger.core.analyzer import analyze_track as essentia_analyze
    except ImportError:
        essentia_available = False
        console.print("  [dim]Essentia not available, using librosa fallback[/dim]")

    librosa_available = True
    try:
        from cratedigger.audio_analysis.analyzer import analyze_track as librosa_analyze
    except ImportError:
        librosa_available = False

    if not essentia_available and not librosa_available:
        console.print("  [yellow]No analyzer available — skipping analysis[/yellow]")
        return

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"),
        BarColumn(), MofNCompleteColumn(), transient=True,
    ) as progress:
        task = progress.add_task("Analyzing audio...", total=len(need_analysis))
        for track in need_analysis:
            try:
                if essentia_available:
                    features = essentia_analyze(track.filepath)
                    if features.bpm and track.bpm is None:
                        track.bpm = features.bpm
                        track.bpm_source = "essentia"
                    if features.key and track.key_camelot is None:
                        track.key_camelot = features.key
                        track.key_source = "essentia"
                    if features.energy is not None:
                        track.energy = features.energy
                elif librosa_available:
                    result = librosa_analyze(track.filepath)
                    if result.bpm and track.bpm is None:
                        track.bpm = result.bpm
                        track.bpm_source = "librosa"
                    if result.key and track.key_camelot is None:
                        track.key_camelot = result.key
                        track.key_source = "librosa"
            except Exception as exc:
                logger.warning("Analysis failed for %s: %s", track.filepath.name, exc)
            progress.advance(task)

    bpm_count = sum(1 for t in tracks if t.bpm is not None)
    key_count = sum(1 for t in tracks if t.key_camelot is not None)
    console.print(
        f"  BPM: [green]{bpm_count}[/green]/{len(tracks)} | "
        f"Key: [green]{key_count}[/green]/{len(tracks)}"
    )
