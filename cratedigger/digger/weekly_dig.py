"""Weekly dig module — scan new releases against your DJ profile."""

import html.parser
import json
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

# Beatport genre slugs for DJ-relevant genres
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
    release_date: str = ""
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


class _BeatportPageParser(html.parser.HTMLParser):
    """Parse Beatport genre pages for track listings via JSON-LD or meta tags."""

    def __init__(self):
        super().__init__()
        self.in_script = False
        self.script_type = ""
        self.json_ld_data = []
        self.title = ""
        self.in_title = False
        self._current_data = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "script" and attrs_dict.get("type") == "application/ld+json":
            self.in_script = True
            self._current_data = []
        if tag == "title":
            self.in_title = True
            self._current_data = []

    def handle_data(self, data):
        if self.in_script or self.in_title:
            self._current_data.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_script:
            self.in_script = False
            raw = "".join(self._current_data).strip()
            if raw:
                try:
                    self.json_ld_data.append(json.loads(raw))
                except json.JSONDecodeError:
                    pass
        if tag == "title" and self.in_title:
            self.in_title = False
            self.title = "".join(self._current_data).strip()


class _DuckDuckGoParser(html.parser.HTMLParser):
    """Parse DuckDuckGo HTML results for Beatport new release links."""

    def __init__(self):
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._in_result = False
        self._current_href = ""
        self._current_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "a" and "result__a" in attrs_dict.get("class", ""):
            self._in_result = True
            self._current_href = attrs_dict.get("href", "")
            self._current_text = []

    def handle_data(self, data):
        if self._in_result:
            self._current_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._in_result:
            self._in_result = False
            text = "".join(self._current_text).strip()
            if self._current_href and text:
                self.results.append({"url": self._current_href, "text": text})


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


def _search_beatport_releases(genre: str, genre_slug: str) -> list[NewRelease]:
    """Search for new releases on Beatport via DuckDuckGo (Beatport is a JS SPA)."""
    releases = []

    query = f"site:beatport.com {genre} new releases 2026"
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"

    time.sleep(WEB_RATE_LIMIT)
    html_content = _web_get(url)
    if not html_content:
        return releases

    parser = _DuckDuckGoParser()
    try:
        parser.feed(html_content)
    except Exception:
        return releases

    # Parse search results for track info
    for result in parser.results[:20]:
        text = result["text"]
        href = result["url"]

        # Beatport URLs: /track/name/12345 or /release/name/12345
        if "beatport.com" not in href:
            continue

        # Try to extract artist - title from result text
        # Common format: "Artist - Title on Beatport" or "Title by Artist"
        artist = ""
        title = text

        # Pattern: "Title by Artist"
        by_match = re.match(r"(.+?)\s+by\s+(.+?)(?:\s+on\s+Beatport)?$", text, re.IGNORECASE)
        if by_match:
            title = by_match.group(1).strip()
            artist = by_match.group(2).strip()

        # Pattern: "Artist - Title"
        dash_match = re.match(r"(.+?)\s*[-–—]\s*(.+?)(?:\s+on\s+Beatport)?$", text)
        if dash_match and not artist:
            artist = dash_match.group(1).strip()
            title = dash_match.group(2).strip()

        # Clean up
        title = re.sub(r"\s*\|\s*Beatport.*$", "", title)
        title = re.sub(r"\s*on Beatport.*$", "", title, flags=re.IGNORECASE)

        if title and len(title) > 2:
            releases.append(NewRelease(
                title=title,
                artist=artist,
                genre=genre,
                url=href,
            ))

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
    """Mark releases where artist or title already exists in library."""
    if not library_path:
        return

    try:
        audio_files = find_audio_files(library_path)
    except Exception:
        return

    file_stems = {f.stem.lower() for f in audio_files}
    file_stems_norm = {_normalize_artist(s) for s in file_stems}

    for release in releases:
        artist_norm = _normalize_artist(release.artist)
        title_norm = _normalize_artist(release.title)

        # Check if exact title match exists
        for stem in file_stems_norm:
            if title_norm in stem and artist_norm in stem:
                release.in_library = True
                break

        # Check if artist exists in library
        for stem in file_stems_norm:
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

    # Scan each genre
    all_releases = []
    for genre in scan_genres:
        slug = GENRE_SLUGS.get(genre, genre.lower().replace(" ", "-"))
        console.print(f"  Scanning [yellow]{genre}[/yellow]...")
        releases = _search_beatport_releases(genre, slug)
        all_releases.extend(releases)
        console.print(f"    Found {len(releases)} results")

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

    report.releases = filtered
    report.after_filter = len(filtered)

    return report


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
    console.print(f"  [dim]Genres scanned:[/dim] {', '.join(report.genres_scanned)}")
    console.print(f"  [dim]Total found:[/dim] {report.total_found} → [dim]After filter:[/dim] {report.after_filter}")

    if not report.releases:
        console.print("\n  [yellow]No new releases found matching your profile.[/yellow]\n")
        return

    # High relevance (score > 0.3)
    hot = [r for r in report.releases if r.relevance_score > 0.3]
    if hot:
        console.print(f"\n  [bold red]Hot Picks[/bold red] — matches your profile ({len(hot)})")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Score", justify="right", style="yellow", width=6)
        table.add_column("Artist", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Genre", style="dim")
        table.add_column("Flags", style="green")

        for r in hot[:20]:
            flags = []
            if r.artist_in_library:
                flags.append("in lib")
            if r.artist_in_streaming:
                flags.append("streaming")
            table.add_row(
                f"{r.relevance_score:.1f}",
                r.artist or "?",
                r.title,
                r.genre,
                " ".join(flags),
            )
        console.print(table)

    # All other releases
    others = [r for r in report.releases if r.relevance_score <= 0.3]
    if others:
        console.print(f"\n  [bold]Other New Releases[/bold] ({len(others)})")
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Artist", style="cyan")
        table.add_column("Title", style="white")
        table.add_column("Genre", style="dim")

        for r in others[:15]:
            table.add_row(r.artist or "?", r.title, r.genre)
        console.print(table)
        if len(others) > 15:
            console.print(f"  [dim]... and {len(others) - 15} more[/dim]")

    console.print()
