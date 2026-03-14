"""Weekly dig module — scan new releases against your DJ profile."""

import html.parser
import logging
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cratedigger.scanner import find_audio_files

logger = logging.getLogger(__name__)
console = Console(force_terminal=True, force_jupyter=False)

WEB_REQUEST_TIMEOUT = 15
WEB_RATE_LIMIT = 2.0
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Genre slugs for Traxsource (server-rendered, has actual track data)
GENRE_SLUGS = {
    "Tech House": "tech-house",
    "Deep House": "deep-house",
    "House": "house",
    "Techno": "techno",
    "Progressive House": "progressive-house",
    "Afro House": "afro-house",
    "Melodic House & Techno": "melodic-house-techno",
    "Minimal / Deep Tech": "minimal-deep-tech",
    "Nu Disco / Disco": "nu-disco-disco",
    "Electronica": "electronica",
    "Indie Dance": "indie-dance",
    "Funky / Groove / Jackin' House": "funky-groove-jackin-house",
    "Organic House / Downtempo": "organic-house-downtempo",
    "Drum & Bass": "drum-and-bass",
    "Trance": "trance",
    "Breaks": "breaks",
}

# Traxsource genre IDs (for their URL structure: /genre/ID/slug)
TRAXSOURCE_GENRE_IDS = {
    "Tech House": 11,
    "Deep House": 12,
    "House": 2,
    "Techno": 6,
    "Progressive House": 15,
    "Afro House": 42,
    "Minimal / Deep Tech": 14,
    "Nu Disco / Disco": 3,
    "Soulful House": 13,
    "Funky / Groove / Jackin' House": 35,
    "Organic House / Downtempo": 49,
    "Drum & Bass": 7,
    "Trance": 8,
    "Breaks": 25,
    "Indie Dance": 37,
    "Electronica": 18,
}


@dataclass
class NewRelease:
    """A new release found during weekly dig."""

    title: str
    artist: str
    label: str = ""
    bpm: Optional[float] = None
    key: Optional[str] = None
    genre: str = ""
    url: str = ""
    preview_url: str = ""
    release_date: str = ""
    source: str = "web"
    in_library: bool = False
    artist_in_streaming: bool = False
    artist_in_library: bool = False
    relevance_score: float = 0.0


@dataclass
class WeeklyDigReport:
    """Report from a weekly dig session."""

    genres_scanned: list[str] = field(default_factory=list)
    releases: list[NewRelease] = field(default_factory=list)
    profile_bpm_range: Optional[tuple[float, float]] = None
    profile_genres: list[str] = field(default_factory=list)
    scanned_at: str = ""
    source: str = "web"
    total_found: int = 0
    after_filter: int = 0


class _TraxsourceParser(html.parser.HTMLParser):
    """Parse Traxsource new releases page for track listings.

    Traxsource HTML structure (2026):
    - Track container: <div class="top-item play-trk ptk-{id}">
    - Title: <a class="com-title">Track Name</a>
    - Artist: <a class="com-artists">Artist Name</a> (multiple for collabs)
    - Label: <a class="com-label">Label Name</a>
    - Track URL: <a class="com-title" href="/title/{id}/...">
    """

    def __init__(self):
        super().__init__()
        self.tracks: list[dict] = []
        self._in_track = False
        self._in_title = False
        self._in_artists = False
        self._in_label = False
        self._current: dict = {}
        self._current_text: list[str] = []
        self._current_href = ""

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        cls = attrs_dict.get("class", "")

        # Detect track row containers: <div class="top-item play-trk ptk-xxxxx">
        if tag == "div" and "play-trk" in cls:
            self._in_track = True
            self._current = {}
            # Extract track ID from data attribute
            trid = attrs_dict.get("data-trid", "")
            if trid:
                self._current["url"] = f"https://www.traxsource.com/track/{trid}"

        if not self._in_track:
            return

        # Track title: <a class="com-title">
        if tag == "a" and "com-title" in cls:
            self._in_title = True
            self._current_text = []
            href = attrs_dict.get("href", "")
            if href:
                self._current["url"] = f"https://www.traxsource.com{href}" if href.startswith("/") else href

        # Artist: <a class="com-artists">
        if tag == "a" and "com-artists" in cls:
            self._in_artists = True
            self._current_text = []

        # Label: <a class="com-label">
        if tag == "a" and "com-label" in cls:
            self._in_label = True
            self._current_text = []

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self._current_text.append(text)
        elif self._in_artists:
            self._current_text.append(text)
        elif self._in_label:
            self._current_text.append(text)

    def handle_endtag(self, tag):
        if tag == "a" and self._in_title:
            self._in_title = False
            self._current["title"] = " ".join(self._current_text).strip()

        if tag == "a" and self._in_artists:
            self._in_artists = False
            artist = " ".join(self._current_text).strip()
            if artist:
                existing = self._current.get("artist", "")
                self._current["artist"] = f"{existing}, {artist}" if existing else artist

        if tag == "a" and self._in_label:
            self._in_label = False
            self._current["label"] = " ".join(self._current_text).strip()

        # End of track container
        if tag == "div" and self._in_track and self._current.get("title"):
            self.tracks.append(self._current)
            self._in_track = False
            self._current = {}


_JUNK_PATTERNS = re.compile(
    r"top\s*\d+|top\s*200|all\s*releases|collection\s*\d{4}|"
    r"best\s*of\s*\d{4}|chart|essential|various\s*artists|"
    r"traxsource\s*[-–—]|on\s+traxsource|beatport\s*[-–—]",
    re.IGNORECASE,
)


def _is_junk_result(text: str) -> bool:
    """Return True if the text looks like a chart/compilation page, not a track."""
    return bool(_JUNK_PATTERNS.search(text))


def _get_spotify_client():
    """Get a Spotify client using client credentials (no user OAuth needed).

    Returns spotipy.Spotify instance or None if unavailable.
    """
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
    except ImportError:
        return None

    try:
        from cratedigger.utils.config import get_config
        config = get_config()
        sp_config = config.get("spotify", {})
        client_id = sp_config.get("client_id")
        client_secret = sp_config.get("client_secret")
        if client_id and client_secret:
            auth = SpotifyClientCredentials(
                client_id=client_id,
                client_secret=client_secret,
            )
            return spotipy.Spotify(auth_manager=auth)
        return spotipy.Spotify(auth_manager=SpotifyClientCredentials())
    except Exception:
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyClientCredentials
            return spotipy.Spotify(auth_manager=SpotifyClientCredentials())
        except Exception:
            return None


def _search_spotify_new_releases(genre: str) -> list[NewRelease]:
    """Search Spotify for new tracks in a genre using the search API.

    Uses client credentials flow — no user OAuth needed.
    Searches for recent tracks tagged with the genre and returns
    individual tracks (not compilations).
    """
    sp = _get_spotify_client()
    if not sp:
        logger.debug("Spotify client unavailable, skipping new release search")
        return []

    releases = []
    # Search Spotify for recent tracks in this genre
    from datetime import date
    current_year = date.today().year
    # Use simple keyword search — Spotify's genre: filter is strict
    query = f"{genre.lower()} year:{current_year}"

    try:
        results = sp.search(q=query, type="track", limit=20)
        tracks = results.get("tracks", {}).get("items", [])

        for track in tracks:
            # Skip compilations — they have "various" type albums
            album = track.get("album", {})
            album_type = album.get("album_type", "")
            if album_type == "compilation":
                continue

            artists = ", ".join(a["name"] for a in track.get("artists", []))
            title = track.get("name", "")
            if not title or not artists:
                continue

            # Extract label from album (not always available in search)
            label = ""

            # Release date from album
            release_date = album.get("release_date", "")

            releases.append(NewRelease(
                title=title,
                artist=artists,
                label=label,
                genre=genre,
                url=track.get("external_urls", {}).get("spotify", ""),
                preview_url=track.get("preview_url") or "",
                release_date=release_date,
                source="spotify",
            ))

        logger.debug("Spotify returned %d tracks for genre '%s'", len(releases), genre)
    except Exception as e:
        logger.debug("Spotify new release search failed for %s: %s", genre, e)

    return releases


def _web_get(url: str) -> Optional[str]:
    """Fetch a URL with browser-like headers."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=WEB_REQUEST_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug("Web request failed for %s: %s", url, e)
        return None


def _search_traxsource_releases(genre: str, genre_slug: str) -> list[NewRelease]:
    """Scrape Traxsource new releases page for a genre.

    Traxsource is server-rendered HTML with actual track data (artist, title,
    label, BPM, key) unlike Beatport which is a JS SPA.
    """
    releases = []

    # Try direct Traxsource genre page first
    genre_id = TRAXSOURCE_GENRE_IDS.get(genre)
    if genre_id:
        url = f"https://www.traxsource.com/genre/{genre_id}/{genre_slug}/tracks?cn=new"
        time.sleep(WEB_RATE_LIMIT)
        html_content = _web_get(url)
        if html_content:
            parser = _TraxsourceParser()
            try:
                parser.feed(html_content)
            except Exception:
                pass
            for t in parser.tracks:
                bpm = None
                if t.get("bpm"):
                    try:
                        bpm = float(t["bpm"])
                    except (ValueError, TypeError):
                        pass
                releases.append(NewRelease(
                    title=t.get("title", ""),
                    artist=t.get("artist", ""),
                    label=t.get("label", ""),
                    bpm=bpm,
                    key=t.get("key"),
                    genre=t.get("genre_tag", genre),
                    url=t.get("url", ""),
                ))

    # Fallback: DuckDuckGo search for Traxsource tracks
    if not releases:
        query = f"site:traxsource.com {genre} new releases"
        encoded = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        time.sleep(WEB_RATE_LIMIT)
        html_content = _web_get(url)
        if html_content:
            # Parse DuckDuckGo results — only accept actual track pages
            for match in re.finditer(
                r'class="result__a"[^>]*href="([^"]*traxsource[^"]*)"[^>]*>([^<]+)',
                html_content,
            ):
                href, text = match.group(1), match.group(2).strip()
                # Skip non-track URLs (chart pages, category listings, etc.)
                if not re.search(r"/track/|/title/", href):
                    continue
                # Skip obvious compilation/chart page titles
                if _is_junk_result(text):
                    continue
                # Try to extract artist - title
                parts = re.split(r"\s*[-–—]\s*", text, maxsplit=1)
                if len(parts) == 2:
                    releases.append(NewRelease(
                        title=parts[1].strip(),
                        artist=parts[0].strip(),
                        genre=genre,
                        url=href,
                    ))

    # Fallback 2: Spotify search for new tracks in this genre
    if not releases:
        releases = _search_spotify_new_releases(genre)

    return releases


def _load_dj_profile() -> Optional[dict]:
    """Load DJ profile from database."""
    try:
        from cratedigger.digger.profile import load_profile
        profile = load_profile()
        if not profile:
            return None
        return {
            "genres": profile.genres,
            "bpm_range": profile.bpm_range,
            "top_artists": [a["name"] for a in profile.top_artists],
            "top_labels": [la["name"] for la in profile.top_labels] if profile.top_labels else [],
        }
    except Exception:
        return None


def _normalize_artist(name: str) -> str:
    """Normalize an artist name for matching."""
    name = name.lower().strip()
    name = re.sub(r"^the\s+", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _check_library_overlap(
    releases: list[NewRelease],
    library_path: Optional[Path] = None,
) -> None:
    """Mark releases where artist or title already exists in library (DB-first)."""
    # Method 1: DB cross-reference (fast, reliable)
    db_paths = set()
    try:
        from cratedigger.utils.db import get_connection
        conn = get_connection()
        rows = conn.execute("SELECT filepath FROM audio_analysis").fetchall()
        conn.close()
        db_paths = {_normalize_artist(Path(r[0]).stem) for r in rows}
    except Exception:
        pass

    # Method 2: Filesystem fallback
    if not db_paths and library_path:
        try:
            audio_files = find_audio_files(library_path)
            db_paths = {_normalize_artist(f.stem) for f in audio_files}
        except Exception:
            pass

    if not db_paths:
        return

    for release in releases:
        artist_norm = _normalize_artist(release.artist)
        title_norm = _normalize_artist(release.title)

        # Check if exact title match exists
        for stem in db_paths:
            if title_norm and artist_norm and title_norm in stem and artist_norm in stem:
                release.in_library = True
                break

        # Check if artist exists in library
        if not release.in_library:
            for stem in db_paths:
                if artist_norm and artist_norm in stem:
                    release.artist_in_library = True
                    break


def _check_streaming_overlap(
    releases: list[NewRelease],
    streaming_artists: list[str],
) -> None:
    """Mark releases where artist appears in streaming data."""
    streaming_norm = {_normalize_artist(a) for a in streaming_artists}

    for release in releases:
        artist_norm = _normalize_artist(release.artist)
        if artist_norm in streaming_norm:
            release.artist_in_streaming = True


def _score_relevance(
    release: NewRelease,
    profile_genres: list[str],
    profile_artists: list[str],
    profile_labels: list[str],
) -> float:
    """Score how relevant a release is to the DJ's profile."""
    score = 0.0

    # Genre match
    if release.genre:
        for pg in profile_genres:
            if pg.lower() in release.genre.lower() or release.genre.lower() in pg.lower():
                score += 0.3
                break

    # Artist already in library
    if release.artist_in_library:
        score += 0.3

    # Artist in streaming
    if release.artist_in_streaming:
        score += 0.2

    # Label match
    if release.label:
        label_norm = _normalize_artist(release.label)
        for pl in profile_labels:
            if _normalize_artist(pl) == label_norm:
                score += 0.2
                break

    # Already owned = not relevant
    if release.in_library:
        score = 0.0

    return min(score, 1.0)


def scan_new_releases(
    genres: Optional[list[str]] = None,
    library_path: Optional[Path] = None,
) -> WeeklyDigReport:
    """Scan for new releases matching the DJ profile.

    Args:
        genres: List of genres to scan. If None, uses top genres from DJ profile.
        library_path: Path to music library for cross-reference.

    Returns:
        WeeklyDigReport with scored and filtered releases.
    """
    report = WeeklyDigReport(
        scanned_at=datetime.now(timezone.utc).isoformat(),
    )

    # Load profile
    profile = _load_dj_profile()
    profile_genres = []
    profile_artists = []
    profile_labels = []

    if profile:
        # Get top genres from profile
        sorted_genres = sorted(profile["genres"].items(), key=lambda x: -x[1])
        profile_genres = [g for g, _ in sorted_genres[:5]]
        profile_artists = profile.get("top_artists", [])
        profile_labels = profile.get("top_labels", [])
        bpm = profile.get("bpm_range", {})
        if bpm:
            report.profile_bpm_range = (bpm.get("min", 0), bpm.get("max", 999))
        report.profile_genres = profile_genres

    # Determine genres to scan
    scan_genres = genres or profile_genres
    if not scan_genres:
        scan_genres = ["Tech House", "Deep House", "House"]  # Sensible defaults

    report.genres_scanned = scan_genres

    # Build case-insensitive lookup for genre dicts
    _slug_lower = {k.lower(): v for k, v in GENRE_SLUGS.items()}
    _id_lower = {k.lower(): v for k, v in TRAXSOURCE_GENRE_IDS.items()}

    # Scan each genre via Traxsource
    all_releases = []
    for genre in scan_genres:
        genre_key = genre.lower()
        slug = _slug_lower.get(genre_key, genre_key.replace(" ", "-"))
        # Patch genre ID lookup to also be case-insensitive
        _orig_id = TRAXSOURCE_GENRE_IDS.get(genre)
        if not _orig_id:
            _ci_id = _id_lower.get(genre_key)
            if _ci_id:
                TRAXSOURCE_GENRE_IDS[genre] = _ci_id
        console.print(f"  Scanning [yellow]{genre}[/yellow] on Traxsource...")
        releases = _search_traxsource_releases(genre, slug)
        all_releases.extend(releases)
        console.print(f"    Found {len(releases)} tracks")

    report.total_found = len(all_releases)

    # Deduplicate by title+artist
    seen = set()
    unique = []
    for r in all_releases:
        key = (_normalize_artist(r.title), _normalize_artist(r.artist))
        if key not in seen:
            seen.add(key)
            unique.append(r)

    # Cross-reference
    if library_path:
        console.print("  Cross-referencing library...")
        _check_library_overlap(unique, library_path)

    # Streaming overlap
    if profile_artists:
        _check_streaming_overlap(unique, profile_artists)

    # Score relevance
    for r in unique:
        r.relevance_score = _score_relevance(r, profile_genres, profile_artists, profile_labels)

    # Filter out already owned and sort by relevance
    filtered = [r for r in unique if not r.in_library]
    filtered.sort(key=lambda r: -r.relevance_score)

    # Enrich with Spotify preview URLs where missing
    _enrich_preview_urls(filtered)

    report.releases = filtered
    report.after_filter = len(filtered)

    return report


def _enrich_preview_urls(releases: list[NewRelease]) -> None:
    """Find preview URLs for releases via Deezer's free API.

    Deezer consistently provides 30-second MP3 preview URLs without
    requiring authentication (unlike Spotify which deprecated previews).
    """
    needs_preview = [r for r in releases if not r.preview_url and r.artist and r.title]
    if not needs_preview:
        return

    import json

    console.print("  Fetching preview URLs from Deezer...")
    found = 0
    for r in needs_preview[:20]:  # Cap lookups to avoid rate limits
        try:
            # Clean title: strip "(Extended Mix)", "(Original Mix)" etc.
            clean_title = re.sub(r"\s*\((?:Extended|Original|Radio|Club)\s+(?:Mix|Edit|Dub)\)", "", r.title, flags=re.IGNORECASE).strip()
            query = f'artist:"{r.artist}" track:"{clean_title}"'
            encoded = urllib.parse.quote_plus(query)
            url = f"https://api.deezer.com/search?q={encoded}&limit=1"
            resp = _web_get(url)
            if resp:
                data = json.loads(resp)
                items = data.get("data", [])
                if items and items[0].get("preview"):
                    r.preview_url = items[0]["preview"]
                    found += 1
            time.sleep(0.3)  # Respect rate limits
        except Exception:
            continue
    if found:
        console.print(f"    Found {found} preview clips")


def parse_manual_releases(text: str) -> list[NewRelease]:
    """Parse manually pasted release info (one per line).

    Accepts formats:
        Artist - Title
        Artist - Title [Label]
        Artist - Title (Label) BPM Key
    """
    releases = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Try to extract label in brackets
        label = ""
        label_match = re.search(r"\[([^\]]+)\]|\(([^)]+)\)$", line)
        if label_match:
            label = (label_match.group(1) or label_match.group(2) or "").strip()
            line = line[:label_match.start()].strip()

        # Split on dash
        parts = re.split(r"\s*[-–—]\s*", line, maxsplit=1)
        if len(parts) == 2:
            releases.append(NewRelease(
                title=parts[1].strip(),
                artist=parts[0].strip(),
                label=label,
                source="manual",
            ))
        elif len(parts) == 1 and parts[0]:
            releases.append(NewRelease(
                title=parts[0].strip(),
                artist="",
                label=label,
                source="manual",
            ))

    return releases


def display_weekly_report(report: WeeklyDigReport) -> None:
    """Render weekly dig report with Rich terminal output."""
    console.print()
    console.print(Panel.fit(
        "[bold green]Weekly Dig[/bold green] — New Release Scanner",
        border_style="green",
    ))

    # Profile summary
    if report.profile_genres:
        console.print(f"  [dim]Your genres:[/dim] {', '.join(report.profile_genres)}")
    if report.profile_bpm_range:
        console.print(f"  [dim]Your BPM range:[/dim] {report.profile_bpm_range[0]:.0f}-{report.profile_bpm_range[1]:.0f}")
    # Show source(s) used
    sources = {r.source for r in report.releases} if report.releases else {"web"}
    source_label = ", ".join(sorted(sources - {"manual"})) or "web"
    console.print(f"  [dim]Genres scanned:[/dim] {', '.join(report.genres_scanned)}")
    console.print(f"  [dim]Source:[/dim] {source_label}")
    console.print(f"  [dim]Total found:[/dim] {report.total_found} → [dim]After filter:[/dim] {report.after_filter}")

    if not report.releases:
        console.print("\n  [yellow]No new releases found matching your profile.[/yellow]\n")
        return

    # Build numbered list for preview selection
    numbered: list[NewRelease] = []
    idx = 0

    # High relevance (score > 0.3)
    hot = [r for r in report.releases if r.relevance_score > 0.3]
    if hot:
        console.print(f"\n  [bold red]Hot Picks[/bold red] — matches your profile ({len(hot)})")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("#", justify="right", style="dim", width=4)
        table.add_column("Score", justify="right", style="yellow", width=6)
        table.add_column("Artist", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Genre", style="dim")
        table.add_column("", width=2)  # preview indicator

        for r in hot[:20]:
            idx += 1
            numbered.append(r)
            flags = ""
            if r.artist_in_library:
                flags += "L"
            if r.artist_in_streaming:
                flags += "S"
            preview_icon = "[green]>>[/green]" if r.preview_url else ""
            table.add_row(
                str(idx),
                f"{r.relevance_score:.1f}",
                r.artist or "?",
                r.title,
                r.genre,
                preview_icon,
            )
        console.print(table)

    # All other releases
    others = [r for r in report.releases if r.relevance_score <= 0.3]
    if others:
        console.print(f"\n  [bold]Other New Releases[/bold] ({len(others)})")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("#", justify="right", style="dim", width=4)
        table.add_column("Artist", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Genre", style="dim")
        table.add_column("", width=2)

        for r in others[:15]:
            idx += 1
            numbered.append(r)
            preview_icon = "[green]>>[/green]" if r.preview_url else ""
            table.add_row(str(idx), r.artist or "?", r.title, r.genre, preview_icon)
        console.print(table)
        if len(others) > 15:
            console.print(f"  [dim]... and {len(others) - 15} more[/dim]")

    # Preview hint
    previewable = sum(1 for r in numbered if r.preview_url)
    if previewable:
        console.print(f"\n  [dim][green]>>[/green] = preview available ({previewable} tracks)[/dim]")

    # Store for interactive preview
    report._numbered_releases = numbered  # type: ignore[attr-defined]
    console.print()
