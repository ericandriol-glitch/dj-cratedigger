"""Artist research module — deep-dive into an artist across MusicBrainz, library, and streaming."""

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cratedigger.scanner import find_audio_files

logger = logging.getLogger(__name__)
console = Console(force_terminal=True, force_jupyter=False)

RATE_LIMIT = 1.1  # MusicBrainz requires >= 1 req/sec


def _get_mb():
    """Lazy-load musicbrainzngs to avoid import errors when not installed."""
    import musicbrainzngs as mb
    mb.set_useragent("DJ CrateDigger", "0.1.0", "eric.andriol@gmail.com")
    return mb


def _normalize_artist(name: str) -> str:
    """Normalize an artist name for fuzzy matching."""
    name = name.lower().strip()
    name = re.sub(r"^the\s+", "", name)
    name = re.sub(r"[''`]", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


@dataclass
class ArtistProfile:
    """Full artist research profile."""

    name: str
    mbid: Optional[str] = None
    country: Optional[str] = None
    disambiguation: Optional[str] = None
    aliases: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    urls: list[dict[str, str]] = field(default_factory=list)
    releases: list[dict] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    related_artists: list[dict] = field(default_factory=list)
    library_tracks: list[str] = field(default_factory=list)
    spotify_status: Optional[dict] = None
    discogs_releases: list[dict] = field(default_factory=list)


def _search_artist_mb(name: str) -> Optional[dict]:
    """Search MusicBrainz for an artist and return the best match."""
    mb = _get_mb()
    try:
        time.sleep(RATE_LIMIT)
        result = mb.search_artists(name, limit=5)
        artists = result.get("artist-list", [])
        if not artists:
            return None

        # Prefer exact name match
        name_lower = name.lower().strip()
        for a in artists:
            if a.get("name", "").lower().strip() == name_lower:
                return a

        # Fall back to first result
        return artists[0]
    except Exception as e:
        logger.error("MusicBrainz artist search failed: %s", e)
        return None


def _get_artist_details(mbid: str) -> Optional[dict]:
    """Fetch full artist details including URL relations and release groups."""
    mb = _get_mb()
    try:
        time.sleep(RATE_LIMIT)
        return mb.get_artist_by_id(
            mbid,
            includes=["url-rels", "tags", "aliases", "release-groups", "artist-rels"],
        )
    except Exception as e:
        logger.error("MusicBrainz artist details failed: %s", e)
        return None


def _extract_urls(artist_data: dict) -> list[dict[str, str]]:
    """Extract URL relations (Bandcamp, SoundCloud, Discogs, etc.)."""
    urls = []
    for rel in artist_data.get("url-relation-list", []):
        url = rel.get("target", "")
        rel_type = rel.get("type", "")
        if url:
            urls.append({"type": rel_type, "url": url})
    return urls


def _extract_releases(artist_data: dict) -> list[dict]:
    """Extract release groups (albums, EPs, singles) sorted by date."""
    releases = []
    for rg in artist_data.get("release-group-list", []):
        release = {
            "title": rg.get("title", ""),
            "type": rg.get("primary-type", rg.get("type", "Other")),
            "date": rg.get("first-release-date", ""),
            "mbid": rg.get("id", ""),
        }
        releases.append(release)

    # Sort by date descending (most recent first)
    releases.sort(key=lambda r: r.get("date", "") or "0000", reverse=True)
    return releases


def _extract_labels_from_releases(mbid: str) -> list[str]:
    """Get unique labels from an artist's releases."""
    mb = _get_mb()
    labels = set()
    try:
        time.sleep(RATE_LIMIT)
        result = mb.browse_releases(artist=mbid, includes=["labels"], limit=100)
        for release in result.get("release-list", []):
            for label_info in release.get("label-info-list", []):
                label = label_info.get("label", {})
                label_name = label.get("name", "")
                if label_name and label_name.lower() != "[no label]":
                    labels.add(label_name)
    except Exception as e:
        logger.error("MusicBrainz label browse failed: %s", e)

    return sorted(labels)


def _extract_related_artists(artist_data: dict) -> list[dict]:
    """Extract related artists from MusicBrainz artist relations."""
    related = []
    seen = set()
    for rel in artist_data.get("artist-relation-list", []):
        rel_type = rel.get("type", "")
        artist_info = rel.get("artist", {})
        name = artist_info.get("name", "")
        if name and name not in seen:
            seen.add(name)
            related.append({
                "name": name,
                "relationship": rel_type,
                "mbid": artist_info.get("id", ""),
            })
    return related


def _extract_genres(artist_data: dict) -> list[str]:
    """Extract genre tags from MusicBrainz artist data."""
    tags = artist_data.get("tag-list", [])
    if not tags:
        return []

    try:
        from cratedigger.enrichment.musicbrainz import GENRE_NORMALIZE, GENRE_PRIORITY
    except (ImportError, ModuleNotFoundError):
        # musicbrainzngs not installed (e.g. WSL without it) — return raw tags
        return [tag["name"] for tag in tags[:5]]

    normalized = []
    for tag in tags:
        name = tag["name"].lower().strip()
        count = int(tag.get("count", 0))
        mapped = GENRE_NORMALIZE.get(name)
        if mapped:
            normalized.append((mapped, count))

    if not normalized:
        return [tag["name"] for tag in tags[:5]]

    # Sort by priority order, then by count
    def sort_key(item):
        genre, count = item
        try:
            priority = GENRE_PRIORITY.index(genre)
        except ValueError:
            priority = 999
        return (priority, -count)

    normalized.sort(key=sort_key)
    return [g for g, _ in normalized[:5]]


def _cross_reference_library(
    artist_name: str,
    library_path: Optional[Path] = None,
) -> list[str]:
    """Find tracks by this artist in the DJ's library."""
    if not library_path:
        return []

    try:
        audio_files = find_audio_files(library_path)
    except Exception:
        return []

    artist_norm = _normalize_artist(artist_name)
    matches = []

    for fp in audio_files:
        stem = fp.stem.lower()
        # Check if artist name appears in filename (common format: "Artist - Title")
        if artist_norm in _normalize_artist(stem):
            matches.append(fp.name)

    return sorted(matches)


def _check_spotify_status(artist_name: str) -> Optional[dict]:
    """Check if artist appears in Spotify streaming data."""
    try:
        from cratedigger.enrichment.spotify import load_spotify_profile
        profile = load_spotify_profile()
        if not profile:
            return None

        artist_norm = _normalize_artist(artist_name)
        status = {
            "connected": True,
            "in_top_short": False,
            "in_top_medium": False,
            "in_top_long": False,
            "followed": False,
            "saved_track_count": 0,
        }

        for a in profile.top_artists_short:
            if _normalize_artist(a["name"]) == artist_norm:
                status["in_top_short"] = True
                break

        for a in profile.top_artists_medium:
            if _normalize_artist(a["name"]) == artist_norm:
                status["in_top_medium"] = True
                break

        for a in profile.top_artists_long:
            if _normalize_artist(a["name"]) == artist_norm:
                status["in_top_long"] = True
                break

        for a in profile.followed_artists:
            if _normalize_artist(a["name"]) == artist_norm:
                status["followed"] = True
                break

        for t in profile.saved_tracks:
            if _normalize_artist(t["artist"]) == artist_norm:
                status["saved_track_count"] += 1

        return status
    except Exception:
        return None


def _try_discogs(artist_name: str) -> list[dict]:
    """Try to fetch releases from Discogs if python3-discogs-client is installed."""
    try:
        import discogs_client
    except ImportError:
        logger.debug("python3-discogs-client not installed, skipping Discogs")
        return []

    try:
        from cratedigger.utils.config import load_config
        config = load_config()
        token = config.get("discogs", {}).get("token")
        if not token:
            logger.debug("No Discogs token in config, skipping")
            return []

        d = discogs_client.Client("DJCrateDigger/0.1", user_token=token)
        results = d.search(artist_name, type="artist")

        if not results or len(results) == 0:
            return []

        artist = results[0]
        releases = []
        for r in artist.releases[:30]:  # Cap at 30 to respect rate limits
            time.sleep(0.5)  # Discogs: 60 req/min
            releases.append({
                "title": getattr(r, "title", ""),
                "year": str(getattr(r, "year", "")),
                "label": ", ".join(getattr(r, "labels", [])) if hasattr(r, "labels") else "",
                "format": ", ".join(getattr(r, "formats", [])) if hasattr(r, "formats") else "",
                "source": "discogs",
            })

        return releases
    except Exception as e:
        logger.debug("Discogs lookup failed: %s", e)
        return []


def research_artist(
    artist_name: str,
    library_path: Optional[Path] = None,
    include_discogs: bool = True,
    include_spotify: bool = True,
) -> Optional[ArtistProfile]:
    """Full artist research pipeline.

    Args:
        artist_name: Artist to research.
        library_path: Path to music library for cross-reference.
        include_discogs: Try Discogs if available.
        include_spotify: Check Spotify streaming status.

    Returns:
        ArtistProfile with all gathered data, or None if artist not found.
    """
    console.print(f"  Searching MusicBrainz for [bold]{artist_name}[/bold]...")

    # Step 1: Search MusicBrainz
    artist_match = _search_artist_mb(artist_name)
    if not artist_match:
        console.print(f"  [yellow]No MusicBrainz results for '{artist_name}'[/yellow]")
        return None

    mbid = artist_match.get("id", "")
    profile = ArtistProfile(
        name=artist_match.get("name", artist_name),
        mbid=mbid,
        country=artist_match.get("country"),
        disambiguation=artist_match.get("disambiguation"),
        aliases=[a.get("alias", "") for a in artist_match.get("alias-list", [])],
    )

    # Step 2: Get full artist details
    if mbid:
        console.print("  Fetching artist details...")
        details = _get_artist_details(mbid)
        if details and "artist" in details:
            artist_data = details["artist"]
            profile.urls = _extract_urls(artist_data)
            profile.releases = _extract_releases(artist_data)
            profile.related_artists = _extract_related_artists(artist_data)
            profile.genres = _extract_genres(artist_data)

        # Step 3: Get labels from releases
        console.print("  Fetching labels...")
        profile.labels = _extract_labels_from_releases(mbid)

    # Step 4: Library cross-reference
    if library_path:
        console.print("  Cross-referencing library...")
        profile.library_tracks = _cross_reference_library(artist_name, library_path)

    # Step 5: Spotify status
    if include_spotify:
        console.print("  Checking Spotify status...")
        profile.spotify_status = _check_spotify_status(artist_name)

    # Step 6: Discogs enrichment (optional)
    if include_discogs:
        console.print("  Checking Discogs...")
        profile.discogs_releases = _try_discogs(artist_name)

    return profile


def display_artist_report(report: ArtistProfile) -> None:
    """Render artist research report with Rich terminal output."""
    console.print()

    # Header
    title = f"[bold cyan]{report.name}[/bold cyan]"
    if report.country:
        title += f"  [dim]({report.country})[/dim]"
    if report.disambiguation:
        title += f"  [dim italic]{report.disambiguation}[/dim italic]"

    console.print(Panel.fit(title, border_style="magenta", title="Artist Research"))

    # Aliases
    if report.aliases:
        aliases_str = ", ".join(report.aliases[:5])
        console.print(f"  [dim]Also known as:[/dim] {aliases_str}")

    # Genres
    if report.genres:
        genres_str = ", ".join(report.genres)
        console.print(f"  [dim]Genres:[/dim] [yellow]{genres_str}[/yellow]")

    # Your relationship with this artist
    console.print()
    console.print("  [bold]Your Relationship[/bold]")

    lib_count = len(report.library_tracks)
    if lib_count > 0:
        console.print(f"  Library: [green]{lib_count} track{'s' if lib_count != 1 else ''}[/green]")
        for track in report.library_tracks[:5]:
            console.print(f"    [dim]{track}[/dim]")
        if lib_count > 5:
            console.print(f"    [dim]... and {lib_count - 5} more[/dim]")
    else:
        console.print("  Library: [red]0 tracks[/red]")

    if report.spotify_status:
        sp = report.spotify_status
        parts = []
        if sp["in_top_short"]:
            parts.append("[green]Top artist (4 weeks)[/green]")
        if sp["in_top_medium"]:
            parts.append("[green]Top artist (6 months)[/green]")
        if sp["in_top_long"]:
            parts.append("[green]Top artist (all time)[/green]")
        if sp["followed"]:
            parts.append("[green]Following[/green]")
        if sp["saved_track_count"] > 0:
            parts.append(f"[green]{sp['saved_track_count']} saved tracks[/green]")
        if parts:
            console.print(f"  Spotify: {', '.join(parts)}")
        else:
            console.print("  Spotify: [dim]Not in your streaming data[/dim]")
    else:
        console.print("  Spotify: [dim]Not connected[/dim]")

    # Labels
    if report.labels:
        console.print()
        console.print(f"  [bold]Labels[/bold] ({len(report.labels)})")
        for label in report.labels[:10]:
            console.print(f"    [cyan]{label}[/cyan]")
        if len(report.labels) > 10:
            console.print(f"    [dim]... and {len(report.labels) - 10} more[/dim]")

    # Discography
    if report.releases:
        console.print()
        table = Table(
            title=f"Discography ({len(report.releases)} release groups)",
            show_header=True,
            box=None,
            padding=(0, 2),
        )
        table.add_column("Date", style="dim", width=12)
        table.add_column("Title", style="cyan")
        table.add_column("Type", style="yellow", width=10)

        for r in report.releases[:15]:
            table.add_row(
                r.get("date", "") or "?",
                r.get("title", ""),
                r.get("type", ""),
            )
        console.print(table)
        if len(report.releases) > 15:
            console.print(f"  [dim]... and {len(report.releases) - 15} more releases[/dim]")

    # Discogs releases (if different from MB)
    if report.discogs_releases:
        console.print()
        table = Table(
            title=f"Discogs Releases ({len(report.discogs_releases)})",
            show_header=True,
            box=None,
            padding=(0, 2),
        )
        table.add_column("Year", style="dim", width=6)
        table.add_column("Title", style="cyan")
        table.add_column("Label", style="magenta")
        table.add_column("Format", style="dim")

        for r in report.discogs_releases[:15]:
            table.add_row(
                r.get("year", ""),
                r.get("title", ""),
                r.get("label", ""),
                r.get("format", ""),
            )
        console.print(table)

    # Links
    if report.urls:
        console.print()
        console.print("  [bold]Links[/bold]")
        # Prioritize DJ-relevant links
        priority_types = [
            "bandcamp", "soundcloud", "youtube", "spotify",
            "discogs", "official homepage", "social network",
        ]
        shown = set()
        for ptype in priority_types:
            for url_entry in report.urls:
                url_type = url_entry["type"].lower()
                url = url_entry["url"]
                if ptype in url_type and url not in shown:
                    shown.add(url)
                    console.print(f"    [dim]{url_entry['type']}:[/dim] {url}")
        # Show any remaining
        for url_entry in report.urls:
            if url_entry["url"] not in shown:
                shown.add(url_entry["url"])
                console.print(f"    [dim]{url_entry['type']}:[/dim] {url_entry['url']}")

    # Related artists
    if report.related_artists:
        console.print()
        console.print(f"  [bold]Related Artists[/bold] ({len(report.related_artists)})")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Artist", style="cyan")
        table.add_column("Relationship", style="dim")
        for ra in report.related_artists[:10]:
            table.add_row(ra["name"], ra["relationship"])
        console.print(table)

    # What you're missing
    console.print()
    if lib_count == 0 and report.releases:
        console.print(Panel.fit(
            f"[bold yellow]You have 0 tracks by {report.name}.[/bold yellow]\n"
            f"They have {len(report.releases)} releases across {len(report.labels)} labels.\n"
            + (f"Labels to check: [cyan]{', '.join(report.labels[:3])}[/cyan]" if report.labels else ""),
            border_style="yellow",
            title="What You're Missing",
        ))
    elif lib_count > 0 and lib_count < 5 and len(report.releases) > 10:
        console.print(Panel.fit(
            f"[bold yellow]You have {lib_count} tracks but they have {len(report.releases)} releases.[/bold yellow]\n"
            "Consider digging deeper into their recent output.",
            border_style="yellow",
            title="Room to Dig",
        ))
    elif lib_count >= 5:
        console.print(Panel.fit(
            f"[bold green]Solid collection — {lib_count} tracks by {report.name}.[/bold green]",
            border_style="green",
            title="Well Stocked",
        ))

    console.print()
