"""'What Am I Sleeping On?' skill — cross-reference streaming with USB library."""

import re
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cratedigger.digger.profile import DJProfile
from cratedigger.enrichment.spotify import SpotifyProfile
from cratedigger.enrichment.youtube import YouTubeProfile

console = Console()


def _normalize_artist(name: str) -> str:
    """Normalize an artist name for fuzzy matching.

    Strips 'the', punctuation, extra whitespace, and lowercases.
    """
    name = name.lower().strip()
    name = re.sub(r"^the\s+", "", name)
    name = re.sub(r"[''`]", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


@dataclass
class SleepingOnReport:
    """Cross-reference report between streaming and USB library."""

    stream_but_dont_own: list[dict] = field(default_factory=list)
    own_but_dont_stream: list[dict] = field(default_factory=list)
    underrepresented: list[dict] = field(default_factory=list)


def _extract_streamed_artists(
    spotify: SpotifyProfile | None,
    youtube: YouTubeProfile | None,
) -> dict[str, int]:
    """Build a map of normalized artist name -> streaming mention count."""
    counts: dict[str, int] = {}

    if spotify:
        # Weight top artists more heavily
        for a in spotify.top_artists_short:
            key = _normalize_artist(a["name"])
            counts[key] = counts.get(key, 0) + 3
        for a in spotify.top_artists_medium:
            key = _normalize_artist(a["name"])
            counts[key] = counts.get(key, 0) + 2
        for a in spotify.top_artists_long:
            key = _normalize_artist(a["name"])
            counts[key] = counts.get(key, 0) + 1
        for t in spotify.saved_tracks:
            key = _normalize_artist(t["artist"])
            counts[key] = counts.get(key, 0) + 1
        for a in spotify.followed_artists:
            key = _normalize_artist(a["name"])
            counts[key] = counts.get(key, 0) + 1

    if youtube:
        for t in youtube.liked_songs:
            key = _normalize_artist(t["artist"])
            counts[key] = counts.get(key, 0) + 1
        for t in youtube.history:
            key = _normalize_artist(t["artist"])
            counts[key] = counts.get(key, 0) + 1

    return counts


def _extract_library_artists(dj_profile: DJProfile) -> dict[str, int]:
    """Build a map of normalized artist name -> track count from DJ profile."""
    counts: dict[str, int] = {}
    for artist_entry in dj_profile.top_artists:
        key = _normalize_artist(str(artist_entry["name"]))
        counts[key] = int(artist_entry["count"])
    return counts


def find_sleeping_on(
    dj_profile: DJProfile,
    spotify_profile: SpotifyProfile | None = None,
    youtube_profile: YouTubeProfile | None = None,
) -> SleepingOnReport:
    """Cross-reference streaming habits with USB library.

    Returns:
        SleepingOnReport with three categories of gaps.
    """
    streamed = _extract_streamed_artists(spotify_profile, youtube_profile)
    owned = _extract_library_artists(dj_profile)

    report = SleepingOnReport()

    # Stream but don't own — artists you listen to but have 0 tracks for
    for artist_norm, stream_count in sorted(streamed.items(), key=lambda x: -x[1]):
        if artist_norm and artist_norm not in owned:
            report.stream_but_dont_own.append({
                "artist": artist_norm,
                "stream_mentions": stream_count,
            })

    # Own but don't stream — artists in library but absent from streaming
    for artist_norm, track_count in sorted(owned.items(), key=lambda x: -x[1]):
        if artist_norm and artist_norm not in streamed:
            report.own_but_dont_stream.append({
                "artist": artist_norm,
                "library_tracks": track_count,
            })

    # Underrepresented — stream a lot but have few tracks
    for artist_norm, stream_count in sorted(streamed.items(), key=lambda x: -x[1]):
        if artist_norm in owned:
            lib_count = owned[artist_norm]
            # High streaming engagement but few library tracks
            if stream_count >= 3 and lib_count <= 2:
                report.underrepresented.append({
                    "artist": artist_norm,
                    "stream_mentions": stream_count,
                    "library_tracks": lib_count,
                })

    return report


def display_sleeping_on(report: SleepingOnReport) -> None:
    """Render the Sleeping On report with Rich terminal output."""
    console.print()
    console.print(Panel.fit(
        "[bold yellow]What Am I Sleeping On?[/bold yellow] — Library Gap Analysis",
        border_style="yellow",
    ))

    # Stream but don't own
    if report.stream_but_dont_own:
        console.print(f"\n  [bold red]You stream these but own ZERO tracks:[/bold red] "
                      f"({len(report.stream_but_dont_own)} artists)")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Artist", style="cyan")
        table.add_column("Stream Score", justify="right", style="yellow")
        for entry in report.stream_but_dont_own[:20]:
            table.add_row(entry["artist"].title(), str(entry["stream_mentions"]))
        console.print(table)
        if len(report.stream_but_dont_own) > 20:
            console.print(f"  ... and {len(report.stream_but_dont_own) - 20} more")
    else:
        console.print("\n  [green]No streaming artists missing from your library![/green]")

    # Underrepresented
    if report.underrepresented:
        console.print(f"\n  [bold yellow]Underrepresented — you stream a lot but have few tracks:[/bold yellow] "
                      f"({len(report.underrepresented)} artists)")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Artist", style="cyan")
        table.add_column("Stream Score", justify="right", style="yellow")
        table.add_column("Library Tracks", justify="right", style="red")
        for entry in report.underrepresented[:15]:
            table.add_row(
                entry["artist"].title(),
                str(entry["stream_mentions"]),
                str(entry["library_tracks"]),
            )
        console.print(table)

    # Own but don't stream
    if report.own_but_dont_stream:
        console.print(f"\n  [bold blue]In your library but never streamed:[/bold blue] "
                      f"({len(report.own_but_dont_stream)} artists)")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Artist", style="cyan")
        table.add_column("Library Tracks", justify="right", style="green")
        for entry in report.own_but_dont_stream[:15]:
            table.add_row(entry["artist"].title(), str(entry["library_tracks"]))
        console.print(table)
        if len(report.own_but_dont_stream) > 15:
            console.print(f"  ... and {len(report.own_but_dont_stream) - 15} more")

    console.print()
