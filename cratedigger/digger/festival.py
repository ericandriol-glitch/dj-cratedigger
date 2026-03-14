"""Festival lineup scanner — analyse a lineup against your library and streaming."""

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console(force_terminal=True, force_jupyter=False)

RATE_LIMIT = 1.1  # MusicBrainz requires >= 1s between requests


@dataclass
class LineupArtist:
    """A single artist from a festival lineup with ownership/streaming status."""

    name: str
    category: str = "unknown"  # already-own | stream-but-dont-own | unknown
    library_tracks: int = 0
    stream_score: int = 0
    genres: list[str] = field(default_factory=list)
    genre_match: bool = False  # True if genres overlap with DJ profile


@dataclass
class FestivalReport:
    """Full festival lineup analysis."""

    festival_name: str
    artists: list[LineupArtist] = field(default_factory=list)
    total: int = 0
    already_own: int = 0
    stream_only: int = 0
    unknown_count: int = 0
    genre_matches: int = 0


def parse_lineup(text: str) -> list[str]:
    """Parse a lineup string into clean artist names.

    Accepts comma-separated, newline-separated, or mixed.
    Strips whitespace, removes empties, deduplicates while preserving order.
    """
    # Split on commas or newlines
    raw = re.split(r'[,\n]+', text)
    seen = set()
    artists = []
    for name in raw:
        clean = name.strip()
        # Remove common prefixes like "DJ " numbering "1." etc.
        clean = re.sub(r'^\d+[\.\)]\s*', '', clean)
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            artists.append(clean)
    return artists


def _normalize(name: str) -> str:
    """Normalize an artist name for fuzzy matching."""
    name = name.lower().strip()
    name = re.sub(r"^the\s+", "", name)
    name = re.sub(r"[''`]", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _build_library_artist_map(library_path: Path) -> dict[str, int]:
    """Build normalized artist name -> track count from library metadata."""
    from cratedigger.metadata import read_metadata
    from cratedigger.scanner import find_audio_files

    counts: dict[str, int] = {}
    for fp in find_audio_files(library_path):
        meta = read_metadata(fp)
        if meta.artist and meta.artist.strip():
            key = _normalize(meta.artist)
            counts[key] = counts.get(key, 0) + 1
    return counts


def _build_library_map_from_db(db_path: Path | None = None) -> dict[str, int]:
    """Build normalized artist name -> track count from the DB + metadata.

    Reads filepaths from audio_analysis table, then checks metadata for artist.
    Falls back to filename parsing if metadata unavailable.
    """
    from cratedigger.utils.db import get_connection

    conn = get_connection(db_path)
    rows = conn.execute("SELECT filepath FROM audio_analysis").fetchall()
    conn.close()

    counts: dict[str, int] = {}
    for (filepath,) in rows:
        fp = Path(filepath)
        try:
            from cratedigger.metadata import read_metadata
            meta = read_metadata(fp)
            if meta.artist and meta.artist.strip():
                key = _normalize(meta.artist)
                counts[key] = counts.get(key, 0) + 1
                continue
        except Exception:
            pass
        # Fallback: parse "Artist - Title" from filename
        stem = fp.stem
        if " - " in stem:
            artist_part = stem.split(" - ")[0].strip()
            key = _normalize(artist_part)
            if key:
                counts[key] = counts.get(key, 0) + 1

    return counts


def _build_streaming_map() -> dict[str, int]:
    """Build normalized artist name -> stream score from Spotify/YouTube profiles."""
    counts: dict[str, int] = {}

    # Try Spotify
    try:
        from cratedigger.enrichment.spotify import load_spotify_profile
        sp = load_spotify_profile()
        if sp:
            for a in sp.top_artists_short:
                key = _normalize(a["name"])
                counts[key] = counts.get(key, 0) + 3
            for a in sp.top_artists_medium:
                key = _normalize(a["name"])
                counts[key] = counts.get(key, 0) + 2
            for a in sp.top_artists_long:
                key = _normalize(a["name"])
                counts[key] = counts.get(key, 0) + 1
            for t in sp.saved_tracks:
                key = _normalize(t["artist"])
                counts[key] = counts.get(key, 0) + 1
    except Exception:
        pass

    # Try YouTube
    try:
        from cratedigger.enrichment.youtube import load_youtube_profile
        yt = load_youtube_profile()
        if yt:
            for t in yt.liked_songs:
                key = _normalize(t["artist"])
                counts[key] = counts.get(key, 0) + 1
            for t in yt.history:
                key = _normalize(t["artist"])
                counts[key] = counts.get(key, 0) + 1
    except Exception:
        pass

    return counts


def _get_profile_genres() -> set[str]:
    """Load the DJ profile and return normalized genre names."""
    try:
        from cratedigger.digger.profile import load_profile
        profile = load_profile()
        if profile and profile.genres:
            return {g.lower() for g in profile.genres}
    except Exception:
        pass
    return set()


def _lookup_artist_genres(artist_name: str) -> list[str]:
    """Look up genres for an artist via MusicBrainz tags."""
    try:
        import musicbrainzngs as mb
        mb.set_useragent("DJ CrateDigger", "0.1.0", "eric.andriol@gmail.com")
        time.sleep(RATE_LIMIT)
        result = mb.search_artists(artist_name, limit=1)
        artists = result.get("artist-list", [])
        if artists:
            tags = artists[0].get("tag-list", [])
            # Return top tags sorted by count
            sorted_tags = sorted(tags, key=lambda t: int(t.get("count", 0)), reverse=True)
            return [t["name"] for t in sorted_tags[:5]]
    except Exception:
        pass
    return []


def scan_festival(
    lineup_artists: list[str],
    festival_name: str = "Festival",
    library_path: Optional[Path] = None,
    lookup_genres: bool = True,
) -> FestivalReport:
    """Analyse a festival lineup against your library and streaming history.

    For each artist, categorises as:
    - already-own: have tracks in USB library
    - stream-but-dont-own: listen on Spotify/YouTube but no library tracks
    - unknown: never heard of them

    For unknowns, checks genre against your DJ profile to flag potential matches.

    Args:
        lineup_artists: List of artist names from the lineup.
        festival_name: Name of the festival for display.
        library_path: If provided, scans metadata directly. Otherwise uses DB.
        lookup_genres: Whether to look up MusicBrainz genres for unknowns.
    """
    report = FestivalReport(festival_name=festival_name, total=len(lineup_artists))

    console.print(f"  Checking {len(lineup_artists)} artists...\n")

    # Build ownership and streaming maps
    console.print("  [dim]Loading library data...[/dim]")
    if library_path:
        library_map = _build_library_artist_map(library_path)
    else:
        library_map = _build_library_map_from_db()

    console.print("  [dim]Loading streaming data...[/dim]")
    streaming_map = _build_streaming_map()

    profile_genres = _get_profile_genres()

    console.print(f"  [dim]Library: {sum(library_map.values())} tracks from {len(library_map)} artists[/dim]")
    if streaming_map:
        console.print(f"  [dim]Streaming: {len(streaming_map)} artists tracked[/dim]")
    else:
        console.print("  [dim]No streaming profile synced[/dim]")
    console.print()

    # Categorise each lineup artist
    unknowns_to_lookup = []

    for artist_name in lineup_artists:
        entry = LineupArtist(name=artist_name)
        norm = _normalize(artist_name)

        # Check library
        lib_count = library_map.get(norm, 0)
        if lib_count > 0:
            entry.category = "already-own"
            entry.library_tracks = lib_count
            report.already_own += 1
        elif streaming_map.get(norm, 0) > 0:
            entry.category = "stream-but-dont-own"
            entry.stream_score = streaming_map[norm]
            report.stream_only += 1
        else:
            entry.category = "unknown"
            report.unknown_count += 1
            if lookup_genres:
                unknowns_to_lookup.append(entry)

        report.artists.append(entry)

    # Look up genres for unknowns
    if unknowns_to_lookup and lookup_genres:
        console.print(f"  [dim]Looking up genres for {len(unknowns_to_lookup)} unknown artists...[/dim]")
        for i, entry in enumerate(unknowns_to_lookup):
            genres = _lookup_artist_genres(entry.name)
            entry.genres = genres
            if profile_genres and genres:
                # Check if any genre overlaps with DJ profile
                genre_set = {g.lower() for g in genres}
                if genre_set & profile_genres:
                    entry.genre_match = True
                    report.genre_matches += 1
            if (i + 1) % 10 == 0:
                console.print(f"  [dim]  [{i + 1}/{len(unknowns_to_lookup)}] looked up...[/dim]")

    return report


def display_festival_report(report: FestivalReport) -> None:
    """Render the festival lineup analysis with Rich terminal output."""
    console.print()
    console.print(Panel.fit(
        f"[bold magenta]DJ CrateDigger[/bold magenta] — Festival Scanner: [bold]{report.festival_name}[/bold]",
        border_style="magenta",
    ))

    # Summary bar
    console.print(f"\n  [bold]{report.total}[/bold] artists in lineup")
    console.print(f"  [green]Already own:[/green] {report.already_own}  "
                  f"[yellow]Stream only:[/yellow] {report.stream_only}  "
                  f"[red]Unknown:[/red] {report.unknown_count}")
    if report.genre_matches:
        console.print(f"  [cyan]Genre matches (worth checking):[/cyan] {report.genre_matches}")

    # Already own
    owned = [a for a in report.artists if a.category == "already-own"]
    if owned:
        console.print(f"\n  [bold green]Already in your library ({len(owned)}):[/bold green]")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Artist", style="green")
        table.add_column("Tracks", justify="right", style="bold green")
        for a in sorted(owned, key=lambda x: -x.library_tracks):
            table.add_row(a.name, str(a.library_tracks))
        console.print(table)

    # Stream but don't own
    streamed = [a for a in report.artists if a.category == "stream-but-dont-own"]
    if streamed:
        console.print(f"\n  [bold yellow]You stream but don't own ({len(streamed)}):[/bold yellow]")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Artist", style="yellow")
        table.add_column("Stream Score", justify="right", style="dim")
        for a in sorted(streamed, key=lambda x: -x.stream_score):
            table.add_row(a.name, str(a.stream_score))
        console.print(table)
        console.print("  [dim]Consider buying tracks from these artists![/dim]")

    # Unknown — split into genre matches and the rest
    unknowns = [a for a in report.artists if a.category == "unknown"]
    matches = [a for a in unknowns if a.genre_match]
    no_match = [a for a in unknowns if not a.genre_match]

    if matches:
        console.print(f"\n  [bold cyan]Unknown but similar to your sound ({len(matches)}):[/bold cyan]")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Artist", style="cyan")
        table.add_column("Genres", style="dim", max_width=40)
        for a in matches:
            table.add_row(a.name, ", ".join(a.genres[:3]))
        console.print(table)
        console.print("  [dim]These artists play genres you already dig — check them out![/dim]")

    if no_match:
        console.print(f"\n  [bold red]Unknown — different from your usual ({len(no_match)}):[/bold red]")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Artist", style="red")
        table.add_column("Genres", style="dim", max_width=40)
        for a in no_match:
            genres_str = ", ".join(a.genres[:3]) if a.genres else "no genre info"
            table.add_row(a.name, genres_str)
        console.print(table)

    # Prep score
    if report.total > 0:
        prep_pct = (report.already_own + report.stream_only) / report.total * 100
        console.print(f"\n  [bold]Festival Prep Score:[/bold] {prep_pct:.0f}% "
                      f"({report.already_own + report.stream_only}/{report.total} artists you know)")
        if prep_pct < 30:
            console.print("  [dim]Lots of discovery potential — dig into the unknowns![/dim]")
        elif prep_pct < 60:
            console.print("  [dim]Decent prep — focus on the genre matches above.[/dim]")
        else:
            console.print("  [dim]You're well prepared for this one![/dim]")

    console.print()
