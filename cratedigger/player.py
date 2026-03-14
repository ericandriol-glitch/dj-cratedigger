"""Audio player for DJ CrateDigger using pygame.mixer."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from cratedigger.metadata import read_metadata
from cratedigger.models import TrackMetadata


@dataclass
class NowPlaying:
    """Current playback state."""

    filepath: Path
    metadata: TrackMetadata
    duration: float = 0.0
    position: float = 0.0
    paused: bool = False
    stopped: bool = False
    volume: float = 1.0
    db_info: dict = field(default_factory=dict)


SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg"}


def is_playable(filepath: Path) -> bool:
    """Check if the file format is supported by pygame.mixer."""
    return filepath.suffix.lower() in SUPPORTED_EXTENSIONS


def get_track_info(filepath: Path) -> TrackMetadata:
    """Read metadata for display during playback."""
    return read_metadata(filepath)


def search_library(query: str, library_path: Path) -> list[Path]:
    """Search for tracks matching a query string in the library.

    Searches filenames for the query (case-insensitive).
    """
    query_lower = query.lower()
    results = []
    for ext in SUPPORTED_EXTENSIONS:
        for f in library_path.rglob(f"*{ext}"):
            if query_lower in f.stem.lower():
                results.append(f)
    return sorted(results, key=lambda p: p.name)


def search_library_db(query: str, db_path: Path | None = None) -> list[dict]:
    """Search the CrateDigger database for tracks matching a query.

    Returns dicts with filepath and analysis data (BPM, key, energy).
    """
    from cratedigger.utils.db import get_connection

    conn = get_connection(db_path)
    cursor = conn.execute(
        """SELECT filepath, bpm, key_camelot, energy, genre
           FROM audio_analysis
           WHERE filepath LIKE ?
           ORDER BY filepath""",
        (f"%{query}%",),
    )
    results = []
    for row in cursor.fetchall():
        results.append({
            "filepath": row[0],
            "bpm": row[1],
            "key": row[2],
            "energy": row[3],
            "genre": row[4],
        })
    conn.close()
    return results


def play_track(filepath: Path, volume: float = 1.0) -> Optional[NowPlaying]:
    """Play a track and return a NowPlaying handle for control.

    Uses pygame.mixer for playback. The returned NowPlaying object
    tracks state and can be used to control playback (pause, stop, volume).

    Args:
        filepath: Path to audio file.
        volume: Initial volume (0.0 to 1.0).

    Returns:
        NowPlaying object, or None if file not found/unsupported.
    """
    if not filepath.exists():
        return None

    if not is_playable(filepath):
        return None

    import pygame

    metadata = get_track_info(filepath)
    duration = metadata.duration_seconds or 0.0

    # Initialize pygame mixer (suppress the hello message)
    import os
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)

    vol = max(0.0, min(1.0, volume))

    state = NowPlaying(
        filepath=filepath,
        metadata=metadata,
        duration=duration,
        volume=vol,
    )

    # Load and play
    pygame.mixer.music.load(str(filepath))
    pygame.mixer.music.set_volume(vol)
    pygame.mixer.music.play()

    def _position_tracker():
        """Track playback position in background."""
        start_time = time.time()
        paused_at = 0.0
        total_paused = 0.0

        while not state.stopped:
            if state.paused:
                if paused_at == 0.0:
                    paused_at = time.time()
            else:
                if paused_at > 0.0:
                    total_paused += time.time() - paused_at
                    paused_at = 0.0
                state.position = time.time() - start_time - total_paused

            # Check if playback finished naturally
            if not pygame.mixer.music.get_busy() and not state.paused:
                state.stopped = True
                break

            # Apply volume changes
            pygame.mixer.music.set_volume(state.volume)

            time.sleep(0.1)

    thread = threading.Thread(target=_position_tracker, daemon=True)
    thread.start()

    return state


def pause_track() -> None:
    """Pause current playback."""
    import pygame

    if pygame.mixer.get_init():
        pygame.mixer.music.pause()


def unpause_track() -> None:
    """Resume paused playback."""
    import pygame

    if pygame.mixer.get_init():
        pygame.mixer.music.unpause()


def stop_track() -> None:
    """Stop current playback."""
    import pygame

    if pygame.mixer.get_init():
        pygame.mixer.music.stop()


def format_time(seconds: float) -> str:
    """Format seconds as MM:SS."""
    mins = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{mins}:{secs:02d}"
