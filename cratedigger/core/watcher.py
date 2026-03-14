"""Download folder watcher — auto-tag, analyse, and sort new audio files."""

import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

console = Console()

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".aif", ".aiff", ".m4a", ".ogg", ".opus"}

# Default naming template
DEFAULT_CONVENTION = "{artist} - {title}"


@dataclass
class WatcherConfig:
    """Configuration for the download watcher."""

    watch_dir: Path
    target_dir: Path
    convention: str = DEFAULT_CONVENTION
    wait_seconds: float = 5.0
    auto_analyze: bool = True


@dataclass
class ProcessResult:
    """Result of processing a single file."""

    original_path: Path
    final_path: Path | None = None
    artist: str | None = None
    title: str | None = None
    genre: str | None = None
    analyzed: bool = False
    error: str | None = None


def _is_audio_file(path: Path) -> bool:
    """Check if a file is an audio file by extension."""
    return path.suffix.lower() in AUDIO_EXTENSIONS


def _read_tags(filepath: Path) -> dict[str, str | None]:
    """Read basic tags from an audio file using mutagen."""
    try:
        from mutagen import File as MutagenFile

        audio = MutagenFile(filepath, easy=True)
        if audio is None:
            return {}

        tags = {}
        for key in ("artist", "title", "album", "genre"):
            values = audio.get(key)
            if values:
                tags[key] = values[0]
            else:
                tags[key] = None
        return tags
    except Exception:
        return {}


def _build_filename(tags: dict[str, str | None], convention: str, extension: str) -> str | None:
    """Build a filename from tags and a naming convention.

    Returns None if required fields (artist, title) are missing.
    """
    artist = tags.get("artist")
    title = tags.get("title")

    if not artist or not title:
        return None

    # Clean the values for filesystem safety
    def _clean(val: str) -> str:
        # Remove characters that are problematic in filenames
        for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            val = val.replace(char, '_')
        return val.strip()

    name = convention.format(
        artist=_clean(artist),
        title=_clean(title),
    )

    return f"{name}{extension}"


def process_file(filepath: Path, config: WatcherConfig) -> ProcessResult:
    """Process a single new audio file.

    Steps:
    1. Read tags with mutagen
    2. Run Essentia analysis (if enabled)
    3. Rename using convention
    4. Move to genre subfolder under target
    5. Add to library DB
    """
    result = ProcessResult(original_path=filepath)

    if not filepath.exists():
        result.error = "File not found"
        return result

    # Step 1: Read tags
    tags = _read_tags(filepath)
    result.artist = tags.get("artist")
    result.title = tags.get("title")
    result.genre = tags.get("genre")

    # Step 2: Essentia analysis
    if config.auto_analyze:
        try:
            from cratedigger.core.analyzer import analyze_track
            from cratedigger.utils.db import get_connection, store_results

            features = analyze_track(filepath)
            if features.bpm is not None:
                conn = get_connection()
                genres = {str(filepath): result.genre} if result.genre else {}
                store_results(conn, [(str(filepath), features)], genres)
                conn.close()
                result.analyzed = True
        except Exception:
            pass  # Non-fatal — analysis is a bonus

    # Step 3: Build target filename
    ext = filepath.suffix
    new_name = _build_filename(tags, config.convention, ext)

    if new_name is None:
        # Can't rename without artist/title, keep original name
        new_name = filepath.name

    # Step 4: Determine target directory (genre subfolder)
    genre_folder = tags.get("genre") or "Unsorted"
    # Clean genre for folder name
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        genre_folder = genre_folder.replace(char, '_')

    target_subdir = config.target_dir / genre_folder
    target_subdir.mkdir(parents=True, exist_ok=True)

    target_path = target_subdir / new_name

    # Avoid overwriting
    if target_path.exists():
        stem = target_path.stem
        suffix = target_path.suffix
        counter = 1
        while target_path.exists():
            target_path = target_subdir / f"{stem} ({counter}){suffix}"
            counter += 1

    # Step 5: Move file
    try:
        shutil.move(str(filepath), str(target_path))
        result.final_path = target_path
    except Exception as e:
        result.error = f"Move failed: {e}"

    return result


def watch_directory(config: WatcherConfig) -> None:
    """Watch a directory for new audio files using watchdog.

    Blocks until interrupted (Ctrl+C).
    """
    try:
        from watchdog.events import FileCreatedEvent, FileSystemEventHandler
        from watchdog.observers import Observer
    except ImportError:
        console.print("  [red]watchdog not installed. Run: pip install watchdog[/red]")
        return

    processed: set[str] = set()

    class AudioHandler(FileSystemEventHandler):
        def on_created(self, event: FileCreatedEvent) -> None:
            if event.is_directory:
                return

            filepath = Path(event.src_path)
            if not _is_audio_file(filepath):
                return

            if str(filepath) in processed:
                return

            # Wait for file to finish downloading
            console.print(f"  [dim]New file detected: {filepath.name}[/dim]")
            time.sleep(config.wait_seconds)

            # Check file is still there and stable
            if not filepath.exists():
                return

            try:
                size1 = filepath.stat().st_size
                time.sleep(1)
                size2 = filepath.stat().st_size
                if size1 != size2:
                    # Still downloading, wait more
                    time.sleep(config.wait_seconds)
            except OSError:
                return

            processed.add(str(filepath))
            console.print(f"  [cyan]Processing: {filepath.name}[/cyan]")

            result = process_file(filepath, config)

            if result.error:
                console.print(f"  [red]Error: {result.error}[/red]")
            else:
                dest = result.final_path or filepath
                console.print(f"  [green]→ {dest.relative_to(config.target_dir)}[/green]")
                if result.analyzed:
                    console.print("    [dim]Essentia analysis stored[/dim]")

    handler = AudioHandler()
    observer = Observer()
    observer.schedule(handler, str(config.watch_dir), recursive=False)
    observer.start()

    console.print(f"\n  [bold magenta]Watching[/bold magenta] {config.watch_dir}")
    console.print(f"  [dim]Target: {config.target_dir}[/dim]")
    console.print(f"  [dim]Convention: {config.convention}[/dim]")
    console.print("  [dim]Press Ctrl+C to stop[/dim]\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        console.print("\n  [yellow]Watcher stopped.[/yellow]\n")

    observer.join()
