"""DJ profile builder — derives your DJ identity from library analysis."""

import json
import logging
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cratedigger.metadata import read_metadata
from cratedigger.scanner import find_audio_files
from cratedigger.utils.db import get_connection

logger = logging.getLogger(__name__)
console = Console()


@dataclass
class DJProfile:
    """Aggregated DJ profile from library analysis."""

    genres: dict[str, float] = field(default_factory=dict)
    bpm_range: dict[str, float] = field(default_factory=dict)
    key_distribution: dict[str, float] = field(default_factory=dict)
    energy_range: dict[str, float] = field(default_factory=dict)
    top_artists: list[dict[str, object]] = field(default_factory=list)
    top_labels: list[dict[str, object]] = field(default_factory=list)
    total_tracks: int = 0
    analyzed_tracks: int = 0
    health_score: float = 0.0


def build_profile(
    library_path: Path,
    db_path: Path | None = None,
) -> DJProfile:
    """Build a DJ profile from scanned metadata + Essentia analysis.

    Args:
        library_path: Root directory of music library.
        db_path: SQLite database path.

    Returns:
        DJProfile with aggregated stats.
    """
    audio_files = find_audio_files(library_path)
    if not audio_files:
        return DJProfile()

    # Read metadata from tags
    artist_counter: Counter[str] = Counter()
    genre_counter: Counter[str] = Counter()
    tracks_with_genre = 0

    for fp in audio_files:
        meta = read_metadata(fp)
        if meta.artist and meta.artist.strip():
            artist_counter[meta.artist.strip()] += 1
        if meta.genre and meta.genre.strip():
            genre_counter[meta.genre.strip()] += 1
            tracks_with_genre += 1
        # Album artist or label from tags (if available)
        if meta.album and meta.album.strip():
            # Not a perfect proxy for label, but best we have from tags
            pass

    # Read Essentia analysis from DB
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT bpm, key_camelot, energy, danceability FROM audio_analysis"
    ).fetchall()
    conn.close()

    bpms = [r[0] for r in rows if r[0] is not None]
    keys = [r[1] for r in rows if r[1] is not None]
    energies = [r[2] for r in rows if r[2] is not None]

    # Build profile
    profile = DJProfile(total_tracks=len(audio_files), analyzed_tracks=len(rows))

    # Genres (as proportions)
    if tracks_with_genre > 0:
        profile.genres = {
            genre: round(count / tracks_with_genre, 3)
            for genre, count in genre_counter.most_common(15)
        }

    # BPM range
    if bpms:
        sorted_bpms = sorted(bpms)
        profile.bpm_range = {
            "min": sorted_bpms[0],
            "max": sorted_bpms[-1],
            "median": sorted_bpms[len(sorted_bpms) // 2],
        }

    # Key distribution (as proportions)
    if keys:
        key_counter = Counter(keys)
        total_keys = sum(key_counter.values())
        profile.key_distribution = {
            key: round(count / total_keys, 3)
            for key, count in key_counter.most_common(12)
        }

    # Energy range
    if energies:
        sorted_energies = sorted(energies)
        profile.energy_range = {
            "min": round(sorted_energies[0], 3),
            "max": round(sorted_energies[-1], 3),
            "median": round(sorted_energies[len(sorted_energies) // 2], 3),
        }

    # Top artists
    profile.top_artists = [
        {"name": name, "count": count}
        for name, count in artist_counter.most_common(20)
    ]

    # Health score: proportion of tracks with BPM + key + genre
    if len(audio_files) > 0:
        scored = 0
        for fp in audio_files:
            meta = read_metadata(fp)
            points = 0
            if meta.artist:
                points += 25
            if meta.title:
                points += 25
            if meta.bpm or str(fp) in {r[0] for r in []}:
                points += 20
            if meta.key:
                points += 15
            if meta.genre:
                points += 15
            scored += points
        profile.health_score = round(scored / len(audio_files), 1)

    return profile


def save_profile(profile: DJProfile, db_path: Path | None = None) -> None:
    """Store profile in the database."""
    conn = get_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    profile_json = json.dumps(asdict(profile), indent=2)
    conn.execute(
        "INSERT OR REPLACE INTO dj_profile (id, profile_json, updated_at) VALUES (1, ?, ?)",
        (profile_json, now),
    )
    conn.commit()
    conn.close()


def load_profile(db_path: Path | None = None) -> DJProfile | None:
    """Load profile from the database."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT profile_json FROM dj_profile WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return None
    data = json.loads(row[0])
    return DJProfile(**data)


def display_profile(profile: DJProfile) -> None:
    """Render the DJ profile with rich terminal output."""
    console.print()
    console.print(Panel.fit(
        "[bold magenta]DJ CrateDigger[/bold magenta] — Your DJ Profile",
        border_style="magenta",
    ))

    # Overview
    console.print(f"\n  [bold]Library:[/bold] {profile.total_tracks} tracks "
                  f"({profile.analyzed_tracks} analyzed)")
    console.print(f"  [bold]Health Score:[/bold] {profile.health_score}/100")

    # BPM Range
    if profile.bpm_range:
        console.print(f"\n  [bold]BPM Range:[/bold] "
                      f"{profile.bpm_range['min']:.0f} – {profile.bpm_range['max']:.0f} "
                      f"(median: {profile.bpm_range['median']:.0f})")

    # Energy Range
    if profile.energy_range:
        console.print(f"  [bold]Energy:[/bold] "
                      f"{profile.energy_range['min']:.2f} – {profile.energy_range['max']:.2f} "
                      f"(median: {profile.energy_range['median']:.2f})")

    # Top Genres
    if profile.genres:
        console.print("\n  [bold]Top Genres:[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Genre", style="cyan")
        table.add_column("Share", justify="right", style="green")
        table.add_column("Bar")
        for genre, share in list(profile.genres.items())[:10]:
            bar_len = int(share * 40)
            bar = "[green]" + "█" * bar_len + "[/green]"
            table.add_row(genre, f"{share:.0%}", bar)
        console.print(table)

    # Key Distribution
    if profile.key_distribution:
        console.print("\n  [bold]Top Keys (Camelot):[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="yellow")
        table.add_column("Share", justify="right", style="green")
        table.add_column("Bar")
        for key, share in list(profile.key_distribution.items())[:8]:
            bar_len = int(share * 40)
            bar = "[yellow]" + "█" * bar_len + "[/yellow]"
            table.add_row(key, f"{share:.0%}", bar)
        console.print(table)

    # Top Artists
    if profile.top_artists:
        console.print("\n  [bold]Top Artists:[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("#", style="dim", justify="right")
        table.add_column("Artist", style="cyan")
        table.add_column("Tracks", justify="right", style="green")
        for i, artist in enumerate(profile.top_artists[:15], 1):
            table.add_row(str(i), str(artist["name"]), str(artist["count"]))
        console.print(table)

    console.print()
