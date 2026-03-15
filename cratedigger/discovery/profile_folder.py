"""Folder/USB profile — analyze any folder of audio files."""

import statistics
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cratedigger.scanner import AUDIO_EXTENSIONS


def _get_file_size_mb(path: Path) -> float:
    """Get file size in MB."""
    try:
        return path.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


def profile_folder(path: Path) -> dict:
    """Analyze any folder and return a profile summary.

    Scans audio files in the folder (recursively) and queries the DB
    for any matching analysis data (BPM, key, genre).

    Args:
        path: Path to the folder to profile.

    Returns:
        Dict with keys: total_tracks, bpm_range, bpm_median, genre_distribution,
        key_distribution, total_duration_sec, avg_track_length_sec, total_size_mb,
        file_formats.
    """
    # Find audio files
    audio_files: list[Path] = []
    for item in sorted(path.rglob("*")):
        if item.is_file() and item.suffix.lower() in AUDIO_EXTENSIONS:
            audio_files.append(item)

    if not audio_files:
        return {
            "total_tracks": 0,
            "bpm_range": None,
            "bpm_median": None,
            "genre_distribution": {},
            "key_distribution": {},
            "total_duration_sec": 0.0,
            "avg_track_length_sec": 0.0,
            "total_size_mb": 0.0,
            "file_formats": {},
        }

    # File format distribution
    format_counts = Counter(f.suffix.lower() for f in audio_files)

    # Total size
    total_size = sum(_get_file_size_mb(f) for f in audio_files)

    # Query DB for analysis data
    bpms: list[float] = []
    keys: list[str] = []
    genres: list[str] = []
    durations: list[float] = []

    try:
        from cratedigger.utils.db import get_connection

        conn = get_connection()
        file_strs = [str(f) for f in audio_files]

        # Batch query in chunks to avoid SQLite variable limit
        chunk_size = 500
        for i in range(0, len(file_strs), chunk_size):
            chunk = file_strs[i : i + chunk_size]
            placeholders = ",".join("?" * len(chunk))
            rows = conn.execute(
                f"SELECT bpm, key_camelot, genre FROM audio_analysis "
                f"WHERE filepath IN ({placeholders})",
                chunk,
            ).fetchall()
            for row in rows:
                if row[0] and row[0] > 0:
                    bpms.append(row[0])
                if row[1]:
                    keys.append(row[1])
                if row[2]:
                    genres.append(row[2])
        conn.close()
    except Exception:
        pass  # DB not available or table missing

    # Compute stats
    bpm_range = None
    bpm_median = None
    if bpms:
        bpm_range = (round(min(bpms), 1), round(max(bpms), 1))
        bpm_median = round(statistics.median(bpms), 1)

    genre_dist = dict(Counter(genres).most_common(10))
    key_dist = dict(Counter(keys).most_common(12))

    return {
        "total_tracks": len(audio_files),
        "bpm_range": bpm_range,
        "bpm_median": bpm_median,
        "genre_distribution": genre_dist,
        "key_distribution": key_dist,
        "total_duration_sec": sum(durations) if durations else 0.0,
        "avg_track_length_sec": (
            statistics.mean(durations) if durations else 0.0
        ),
        "total_size_mb": round(total_size, 1),
        "file_formats": dict(format_counts),
    }


def print_folder_profile(
    prof: dict,
    path: Path,
    console: Console | None = None,
) -> None:
    """Pretty-print a folder profile.

    Args:
        prof: Profile dict from profile_folder().
        path: The folder path (for display).
        console: Rich Console instance. Creates one if not provided.
    """
    if console is None:
        console = Console(force_terminal=True, force_jupyter=False)

    console.print()
    console.print(Panel.fit(
        f"[bold cyan]{path}[/bold cyan]",
        border_style="magenta",
        title="FOLDER PROFILE",
    ))

    if prof["total_tracks"] == 0:
        console.print("  [yellow]No audio files found.[/yellow]\n")
        return

    console.print(f"  [bold]Tracks:[/bold] {prof['total_tracks']}")
    console.print(f"  [bold]Size:[/bold] {prof['total_size_mb']} MB")

    # File formats
    if prof["file_formats"]:
        fmt_str = ", ".join(
            f"{ext} ({count})" for ext, count in sorted(
                prof["file_formats"].items(), key=lambda x: -x[1]
            )
        )
        console.print(f"  [bold]Formats:[/bold] {fmt_str}")

    console.print()

    # BPM
    if prof["bpm_range"]:
        lo, hi = prof["bpm_range"]
        console.print(f"  [bold]BPM range:[/bold] [cyan]{lo} - {hi}[/cyan]")
        console.print(f"  [bold]BPM median:[/bold] [cyan]{prof['bpm_median']}[/cyan]")
    else:
        console.print("  [bold]BPM:[/bold] [dim]no data (run scan first)[/dim]")

    console.print()

    # Genre distribution
    if prof["genre_distribution"]:
        table = Table(
            title="Genre Distribution",
            show_header=True,
            box=None,
            padding=(0, 2),
        )
        table.add_column("Genre", style="yellow")
        table.add_column("Count", style="cyan", justify="right")
        for genre, count in prof["genre_distribution"].items():
            table.add_row(genre, str(count))
        console.print(table)
        console.print()

    # Key distribution
    if prof["key_distribution"]:
        table = Table(
            title="Key Distribution",
            show_header=True,
            box=None,
            padding=(0, 2),
        )
        table.add_column("Key", style="green")
        table.add_column("Count", style="cyan", justify="right")
        for key, count in prof["key_distribution"].items():
            table.add_row(key, str(count))
        console.print(table)
        console.print()

    console.print()
