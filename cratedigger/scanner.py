"""Walk a folder tree and find all audio files."""

import time
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from .metadata import read_metadata
from .models import TrackAnalysis

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".wav", ".aiff", ".aif",
    ".m4a", ".aac", ".ogg", ".wma",
}

SKIP_DIRS = {
    ".Spotlight-V100", ".Trashes", ".fseventsd",
    "System Volume Information", "$RECYCLE.BIN", ".DS_Store",
}


def find_audio_files(root: Path) -> list[Path]:
    """Recursively find all audio files under root, skipping hidden/system dirs."""
    audio_files = []
    for item in sorted(root.rglob("*")):
        # Skip hidden files and system directories
        if any(part.startswith(".") or part in SKIP_DIRS for part in item.parts):
            continue
        if item.is_file() and item.suffix.lower() in AUDIO_EXTENSIONS:
            audio_files.append(item)
    return audio_files


def scan_library(root: Path, verbose: bool = False) -> tuple[list[TrackAnalysis], float, int]:
    """
    Scan a music library folder and return track analyses.

    Returns:
        (tracks, scan_duration_seconds, total_files_seen)
    """
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {root}")

    start = time.perf_counter()

    # Count all files for stats
    all_files = list(root.rglob("*"))
    total_files = sum(1 for f in all_files if f.is_file())

    # Find audio files
    audio_paths = find_audio_files(root)

    tracks: list[TrackAnalysis] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning audio files...", total=len(audio_paths))

        for path in audio_paths:
            metadata = read_metadata(path)
            file_size_mb = path.stat().st_size / (1024 * 1024)
            audio_format = path.suffix.lstrip(".").upper()

            track = TrackAnalysis(
                file_path=path,
                file_size_mb=round(file_size_mb, 2),
                audio_format=audio_format,
                metadata=metadata,
            )
            tracks.append(track)
            progress.advance(task)

    duration = time.perf_counter() - start
    return tracks, duration, total_files
