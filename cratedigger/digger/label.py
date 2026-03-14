"""Label research module — discover an artist's labels, roster, and connections."""

import html.parser
import logging
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cratedigger.scanner import find_audio_files


def _get_mb():
    """Lazy-load musicbrainzngs to avoid import errors when not installed."""
    import musicbrainzngs as mb
    mb.set_useragent("DJ CrateDigger", "0.1.0", "eric.andriol@gmail.com")
    return mb

logger = logging.getLogger(__name__)
console = Console(force_terminal=True, force_jupyter=False)

RATE_LIMIT = 1.1  # MusicBrainz requires >= 1 req/sec


WEB_REQUEST_TIMEOUT = 10  # seconds
WEB_RATE_LIMIT = 2.0  # seconds between web requests
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class ArtistInfo:
    """Basic artist information from MusicBrainz."""

    name: str
    mbid: str
    country: Optional[str] = None
    disambiguation: Optional[str] = None
    aliases: list[str] = field(default_factory=list)


@dataclass
class Release:
    """A release (single, EP, album) from MusicBrainz."""

    title: str
    date: Optional[str] = None
    country: Optional[str] = None
    label: Optional[str] = None
    catalog_number: Optional[str] = None
    format: Optional[str] = None
    mbid: Optional[str] = None


@dataclass
class LabelInfo:
    """Record label details from MusicBrainz."""

    name: str
    mbid: str
    country: Optional[str] = None
    label_type: Optional[str] = None
    urls: list[dict[str, str]] = field(default_factory=list)
    source: str = "musicbrainz"


@dataclass
class RosterArtist:
    """An artist on a label's roster."""

    name: str
    mbid: str
    release_count: int = 0
    in_library: bool = False
    library_files: list[str] = field(default_factory=list)


@dataclass
class LabelReport:
    """Full label research report for an artist."""

    artist: ArtistInfo
    releases: list[Release] = field(default_factory=list)
    labels: list[LabelInfo] = field(default_factory=list)
    roster: dict[str, list[RosterArtist]] = field(default_factory=dict)


def search_artist(name: str) -> Optional[ArtistInfo]:
    """Search MusicBrainz for an artist by name.

    Returns the best-matching artist or None if not found.
    """
    mb = _get_mb()
    try:
        time.sleep(RATE_LIMIT)
        result = mb.search_artists(name, limit=5)
        artist_list = result.get("artist-list", [])
        if not artist_list:
            return None

        # Pick the best match — prefer exact name match, then highest score
        for artist in artist_list:
            if artist.get("name", "").lower() == name.lower():
                return ArtistInfo(
                    name=artist["name"],
                    mbid=artist["id"],
                    country=artist.get("country"),
                    disambiguation=artist.get("disambiguation"),
                )

        # Fall back to first result (highest relevance score)
        a = artist_list[0]
        return ArtistInfo(
            name=a["name"],
            mbid=a["id"],
            country=a.get("country"),
            disambiguation=a.get("disambiguation"),
        )
    except Exception as e:
        logger.error("MusicBrainz artist search failed: %s", e)
        return None


def get_artist_releases(artist_mbid: str) -> list[Release]:
    """Get all releases for an artist from MusicBrainz.

    Uses browse_releases with label+media includes to get full label info.
    """
    mb = _get_mb()
    releases = []
    try:
        time.sleep(RATE_LIMIT)
        result = mb.browse_releases(artist=artist_mbid, includes=["labels", "media"], limit=100)
        release_list = result.get("release-list", [])

        for rel in release_list:
            # Extract label info from release
            label_name = None
            catalog_number = None
            label_info_list = rel.get("label-info-list", [])
            if label_info_list:
                li = label_info_list[0]
                label_obj = li.get("label")
                if label_obj:
                    label_name = label_obj.get("name")
                catalog_number = li.get("catalog-number")

            # Extract format from medium-list
            release_format = None
            medium_list = rel.get("medium-list", [])
            if medium_list:
                release_format = medium_list[0].get("format")

            releases.append(Release(
                title=rel.get("title", "Unknown"),
                date=rel.get("date"),
                country=rel.get("country"),
                label=label_name,
                catalog_number=catalog_number,
                format=release_format,
                mbid=rel.get("id"),
            ))
    except Exception as e:
        logger.error("Failed to get releases for artist %s: %s", artist_mbid, e)

    return releases


def extract_labels(releases: list[Release]) -> list[str]:
    """Extract unique label names from a list of releases.

    Filters out common non-label entries like '[no label]'.
    """
    skip = {"[no label]", "not on label", "none", "self-released", ""}
    labels = set()
    for rel in releases:
        if rel.label and rel.label.lower().strip() not in skip:
            labels.add(rel.label)
    return sorted(labels)


def get_label_info(label_name: str) -> Optional[LabelInfo]:
    """Look up a label on MusicBrainz and return its details.

    Searches by name and returns the best match with URL relations.
    """
    if not label_name or not label_name.strip():
        return None
    mb = _get_mb()
    try:
        time.sleep(RATE_LIMIT)
        result = mb.search_labels(label_name, limit=3)
        label_list = result.get("label-list", [])
        if not label_list:
            return None

        # Prefer exact match
        best = label_list[0]
        for lab in label_list:
            if lab.get("name", "").lower() == label_name.lower():
                best = lab
                break

        label_mbid = best["id"]

        # Get full details with URL relations
        time.sleep(RATE_LIMIT)
        detail = mb.get_label_by_id(label_mbid, includes=["url-rels"])
        lab_data = detail.get("label", {})

        urls = []
        for rel in lab_data.get("url-relation-list", []):
            url_type = rel.get("type", "unknown")
            url_target = rel.get("target", "")
            if url_target:
                urls.append({"type": url_type, "url": url_target})

        return LabelInfo(
            name=lab_data.get("name", label_name),
            mbid=label_mbid,
            country=lab_data.get("country"),
            label_type=lab_data.get("type"),
            urls=urls,
        )
    except Exception as e:
        logger.error("Failed to get label info for %s: %s", label_name, e)
        return None


def get_label_roster(label_mbid: str, exclude_artist: str = "") -> list[RosterArtist]:
    """Get other artists who have released on a label.

    Args:
        label_mbid: MusicBrainz label ID.
        exclude_artist: Artist name to exclude (the one being researched).

    Returns:
        List of roster artists with release counts.
    """
    mb = _get_mb()
    try:
        time.sleep(RATE_LIMIT)
        result = mb.browse_releases(label=label_mbid, includes=["artist-credits"], limit=100)
        release_list = result.get("release-list", [])

        # Count releases per artist
        artist_map: dict[str, dict] = {}
        for rel in release_list:
            credit_list = rel.get("artist-credit", [])
            for credit in credit_list:
                if isinstance(credit, dict) and "artist" in credit:
                    art = credit["artist"]
                    art_name = art.get("name", "")
                    art_id = art.get("id", "")
                    if art_name.lower() == exclude_artist.lower():
                        continue
                    if art_id not in artist_map:
                        artist_map[art_id] = {
                            "name": art_name,
                            "mbid": art_id,
                            "count": 0,
                        }
                    artist_map[art_id]["count"] += 1

        roster = [
            RosterArtist(
                name=info["name"],
                mbid=info["mbid"],
                release_count=info["count"],
            )
            for info in artist_map.values()
        ]
        roster.sort(key=lambda a: a.release_count, reverse=True)
        return roster
    except Exception as e:
        logger.error("Failed to get roster for label %s: %s", label_mbid, e)
        return []


def cross_reference_library(
    roster: list[RosterArtist],
    library_path: Path,
) -> list[RosterArtist]:
    """Check which roster artists the user has in their library.

    Uses fuzzy filename matching — checks if the artist name appears
    anywhere in the filename (case-insensitive).

    Args:
        roster: List of roster artists to check.
        library_path: Path to the music library folder.

    Returns:
        Updated roster with in_library flags set.
    """
    audio_files = find_audio_files(library_path)
    filenames_lower = [f.stem.lower() for f in audio_files]
    filepath_map = {f.stem.lower(): str(f) for f in audio_files}

    for artist in roster:
        artist_lower = artist.name.lower()
        matching_files = []
        for fname_lower in filenames_lower:
            if artist_lower in fname_lower:
                matching_files.append(filepath_map[fname_lower])
        if matching_files:
            artist.in_library = True
            artist.library_files = matching_files

    return roster


class _TextExtractor(html.parser.HTMLParser):
    """Simple HTML parser that extracts visible text content."""

    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self.text_parts.append(data)

    def get_text(self) -> str:
        return " ".join(self.text_parts)


def _web_fetch(url: str) -> str:
    """Fetch a URL and return the response body as text.

    Uses stdlib urllib with a browser User-Agent and timeout.
    Returns empty string on any error.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(req, timeout=WEB_REQUEST_TIMEOUT) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except Exception as e:
        logger.debug("Web fetch failed for %s: %s", url, e)
        return ""


def _extract_text_from_html(html_content: str) -> str:
    """Extract visible text from HTML using stdlib html.parser."""
    parser = _TextExtractor()
    try:
        parser.feed(html_content)
    except Exception:
        pass
    return parser.get_text()


def _extract_labels_from_beatport(html_content: str) -> list[str]:
    """Extract label names from Beatport HTML content.

    Looks for label link patterns: /label/label-name/12345
    """
    labels = set()
    # Beatport label links: /label/some-label-name/12345
    for match in re.finditer(r'/label/([\w-]+)/\d+', html_content):
        slug = match.group(1)
        # Convert slug to label name: "some-label-name" -> "Some Label Name"
        name = slug.replace("-", " ").title()
        if len(name) > 2:
            labels.add(name)
    return sorted(labels)


def _extract_labels_from_ra(html_content: str) -> list[str]:
    """Extract label names from Resident Advisor HTML content.

    Looks for label link patterns and text content referencing labels.
    """
    labels = set()
    # RA label links: /labels/12345 or /record-labels/label-name
    for match in re.finditer(r'/record-labels/([\w-]+)', html_content):
        slug = match.group(1)
        name = slug.replace("-", " ").title()
        if len(name) > 2:
            labels.add(name)
    # Also try /labels/ pattern with name in link text
    for match in re.finditer(r'/labels/\d+["\'][^>]*>([^<]+)<', html_content):
        name = match.group(1).strip()
        if len(name) > 2:
            labels.add(name)
    return sorted(labels)


def _extract_labels_from_snippets(html_content: str) -> list[str]:
    """Extract label names from search result snippets (DuckDuckGo/Google).

    Looks for patterns like 'released on X, Y, Z', 'signed to [Label]', etc.
    Also extracts from Bandcamp and Beatport URLs.
    """
    labels = set()
    text = _extract_text_from_html(html_content)

    # Pattern: "releases on X, Y, Z and W" — comma/and-separated label lists
    list_patterns = [
        r'(?:released?|releases?)\s+on\s+((?:[A-Z][\w\s&/]+(?:,\s*)?)+(?:\s+and\s+[A-Z][\w\s&/]+)?)',
        r'(?:labels?)\s+(?:like|such as|including)\s+((?:[A-Z][\w\s&/]+(?:,\s*)?)+(?:\s+and\s+[A-Z][\w\s&/]+)?)',
        r'(?:backed|signed|managed)\s+by\s+([A-Z][\w\s&]+?)(?:\.|,|\s*\n|$)',
    ]
    for pattern in list_patterns:
        for match in re.finditer(pattern, text):
            chunk = match.group(1).strip()
            # Split on commas and "and"/"or"
            parts = re.split(r',\s*|\s+and\s+|\s+or\s+', chunk)
            for part in parts:
                name = part.strip().rstrip('.')
                # Remove trailing common words that aren't part of label names
                name = re.sub(r'\s+(?:this|his|her|the|a|an|in|on|at|with|for|from|is|was|has|he|she)(?:\s.*)?$', '', name, flags=re.IGNORECASE)
                if 3 < len(name) < 60 and not name[0].islower():
                    labels.add(name)

    # Simple patterns: "on X Records", "on X Music", or standalone "X Records/Agency/Music"
    for match in re.finditer(r'(?:on\s+)?([\w\s&]+?\s+(?:Records|Music|Agency|Recordings|Discs))\b', text):
        name = match.group(1).strip()
        if 3 < len(name) < 60 and name[0].isupper():
            labels.add(name)

    # "launched his label X" pattern
    for match in re.finditer(r'(?:his|her|own)\s+label\s+([A-Z][\w\s&]+?)(?:\.|,|\s+with|\s+and|\s*\n|$)', text):
        name = match.group(1).strip()
        if 3 < len(name) < 60:
            labels.add(name)

    # Bandcamp URLs: labelname.bandcamp.com
    for match in re.finditer(r'([\w-]+)\.bandcamp\.com', html_content):
        slug = match.group(1)
        if slug not in ("daily", "www", "support", "help", "s", "2Fvitess"):
            name = slug.replace("-", " ").title()
            if len(name) > 2:
                labels.add(name)

    # Beatport label links
    labels.update(_extract_labels_from_beatport(html_content))

    # Filter out the artist's own name and common false positives
    skip_lower = {"various artists", "dj", "live", "remix", "ep", "lp", "album",
                   "music", "records", "recordings", "discs", "agency"}
    return sorted(name for name in labels if name.lower() not in skip_lower)


def _extract_aliases_from_text(text: str, artist_name: str) -> list[str]:
    """Extract artist aliases from text content.

    Looks for patterns like 'aka X', 'also known as X', 'alias X'.
    """
    aliases = set()
    name_esc = re.escape(artist_name)

    patterns = [
        rf'{name_esc}\s*\(?\s*(?:aka|a\.k\.a\.?|also\s+known\s+as)\s+([\w\s.-]+?)(?:\s+(?:is|was|has|produces?|from|based|born|signed|released)\b|[,.);\n]|$)',
        rf'([^,.(;\n]+?)\s*(?:aka|a\.k\.a\.?|also\s+known\s+as)\s+{name_esc}',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if match.lastindex and match.lastindex >= 1:
                alias = match.group(1).strip()
                if 2 < len(alias) < 50 and alias.lower() != artist_name.lower():
                    aliases.add(alias)

    return sorted(aliases)


def _fetch_ra_page(artist_name: str) -> tuple[list[str], list[str]]:
    """Fetch Resident Advisor page for an artist.

    Returns (label_names, aliases).
    Note: RA is a JS SPA, so this often returns empty. Kept as a fallback.
    """
    slug = re.sub(r'[^a-z0-9]+', '', artist_name.lower())
    url = f"https://ra.co/dj/{slug}"
    console.print("  [dim]Checking Resident Advisor...[/dim]")
    html_content = _web_fetch(url)
    if not html_content:
        return [], []

    labels = _extract_labels_from_ra(html_content)
    text = _extract_text_from_html(html_content)
    aliases = _extract_aliases_from_text(text, artist_name)
    return labels, aliases


def _fetch_beatport_search(artist_name: str) -> list[str]:
    """Search Beatport for an artist and extract label names.

    Note: Beatport is a JS SPA, direct fetch may not return results.
    """
    query = urllib.parse.quote(artist_name)
    url = f"https://www.beatport.com/search?q={query}&type=artists"
    console.print("  [dim]Checking Beatport...[/dim]")
    html_content = _web_fetch(url)
    if not html_content:
        return []
    return _extract_labels_from_beatport(html_content)


def _fetch_ddg_search(artist_name: str, extra_terms: str = "") -> tuple[list[str], list[str]]:
    """Search DuckDuckGo HTML for artist label info.

    Uses DuckDuckGo's HTML-only endpoint (no JavaScript required).
    Returns (label_names, aliases).
    """
    search_terms = f"{artist_name} DJ producer label releases discography"
    if extra_terms:
        search_terms += f" {extra_terms}"
    query = urllib.parse.quote(search_terms)
    url = f"https://html.duckduckgo.com/html/?q={query}"
    console.print("  [dim]Searching web for additional labels...[/dim]")
    html_content = _web_fetch(url)
    if not html_content:
        return [], []

    labels = _extract_labels_from_snippets(html_content)
    text = _extract_text_from_html(html_content)
    aliases = _extract_aliases_from_text(text, artist_name)
    return labels, aliases


def _fetch_google_search(artist_name: str) -> tuple[list[str], list[str]]:
    """Search Google for artist label info (legacy, may be blocked).

    Returns (label_names, aliases).
    """
    return _fetch_ddg_search(artist_name)


def enrich_with_web_search(artist_name: str, report: LabelReport) -> LabelReport:
    """Augment a LabelReport with web-scraped label and alias data.

    Performs up to 3 targeted web fetches (RA, Beatport, Google) to discover
    labels and aliases that MusicBrainz may be missing.

    Each discovered label is first looked up on MusicBrainz for structured data.
    If not found there, a LabelInfo with source="web" is created.

    Args:
        artist_name: The artist name being researched.
        report: Existing LabelReport (from MusicBrainz pipeline).

    Returns:
        The enriched LabelReport (mutated in place and returned).
    """
    console.print("\n  [bold]Web enrichment[/bold]")

    known_labels = {label.name.lower() for label in report.labels}
    all_web_labels: list[str] = []
    all_aliases: list[str] = []

    # 1. Resident Advisor
    try:
        ra_labels, ra_aliases = _fetch_ra_page(artist_name)
        all_web_labels.extend(ra_labels)
        all_aliases.extend(ra_aliases)
    except Exception as e:
        logger.debug("RA fetch failed: %s", e)

    time.sleep(WEB_RATE_LIMIT)

    # 2. Beatport
    try:
        bp_labels = _fetch_beatport_search(artist_name)
        all_web_labels.extend(bp_labels)
    except Exception as e:
        logger.debug("Beatport fetch failed: %s", e)

    time.sleep(WEB_RATE_LIMIT)

    # 3. Google
    try:
        google_labels, google_aliases = _fetch_google_search(artist_name)
        all_web_labels.extend(google_labels)
        all_aliases.extend(google_aliases)
    except Exception as e:
        logger.debug("Google fetch failed: %s", e)

    # Deduplicate aliases and add to artist info
    unique_aliases = sorted(set(a for a in all_aliases if a.lower() != artist_name.lower()))
    if unique_aliases:
        existing = set(report.artist.aliases)
        for alias in unique_aliases:
            if alias not in existing:
                report.artist.aliases.append(alias)
        console.print(f"  [dim]Found aliases: {', '.join(unique_aliases)}[/dim]")

    # Deduplicate labels and merge new ones (filter out artist's own name and variants)
    artist_lower = artist_name.lower()

    def _is_artist_variant(label_name: str) -> bool:
        """Filter labels that are just the artist name or artist + suffix."""
        lower = label_name.lower()
        return lower == artist_lower or lower.startswith(artist_lower + " ")

    new_label_names = sorted(set(
        name for name in all_web_labels
        if name.strip()
        and name.lower() not in known_labels
        and not _is_artist_variant(name)
    ))

    if new_label_names:
        console.print(f"  [dim]Found {len(new_label_names)} new label(s) from web: "
                       f"{', '.join(new_label_names)}[/dim]")

    for label_name in new_label_names:
        # Skip if this is a substring of an existing label (e.g. "The Stuss" vs "Up the Stuss")
        if any(label_name.lower() in k for k in known_labels if k != label_name.lower()):
            continue

        # Try MusicBrainz first for structured data
        info = get_label_info(label_name)
        if info:
            # Only accept if MB name closely matches what we searched for
            mb_lower = info.name.lower()
            search_lower = label_name.lower()
            name_match = (mb_lower == search_lower
                          or search_lower in mb_lower
                          or (mb_lower in search_lower and len(mb_lower) > len(search_lower) * 0.6))
            if name_match:
                info.source = "web+musicbrainz"
                if info.name.lower() not in known_labels:
                    report.labels.append(info)
                    known_labels.add(info.name.lower())
            else:
                # MB returned a different label — use web-only entry
                report.labels.append(LabelInfo(
                    name=label_name,
                    mbid="",
                    source="web",
                ))
                known_labels.add(label_name.lower())
        else:
            # Create a web-only LabelInfo
            report.labels.append(LabelInfo(
                name=label_name,
                mbid="",
                source="web",
            ))
            known_labels.add(label_name.lower())

    if not new_label_names and not unique_aliases:
        console.print("  [dim]No additional labels or aliases found on the web.[/dim]")

    return report


def research_label(
    artist_name: str,
    library_path: Optional[Path] = None,
    web_search: bool = True,
) -> Optional[LabelReport]:
    """Full label research pipeline for an artist.

    1. Search for artist on MusicBrainz
    2. Get their releases and extract labels
    3. Look up each label's details and roster
    4. Cross-reference roster with user's library (if path provided)
    5. Enrich with web search (RA, Beatport, Google) unless disabled

    Args:
        artist_name: Artist name to research.
        library_path: Optional path to music library for cross-reference.
        web_search: Whether to augment results with web scraping (default True).

    Returns:
        LabelReport with all findings, or None if artist not found.
    """
    # Step 1: Find the artist
    artist = search_artist(artist_name)
    if not artist:
        console.print(f"\n  [yellow]Artist '{artist_name}' not found on MusicBrainz.[/yellow]\n")
        return None

    report = LabelReport(artist=artist)

    # Step 2: Get releases
    console.print(f"\n  [dim]Fetching releases for {artist.name}...[/dim]")
    report.releases = get_artist_releases(artist.mbid)

    # Step 3: Extract and research labels
    label_names = extract_labels(report.releases)
    console.print(f"  [dim]Found {len(label_names)} label(s), fetching details...[/dim]")

    for label_name in label_names:
        info = get_label_info(label_name)
        if info:
            report.labels.append(info)

            # Step 4: Get roster for each label
            console.print(f"  [dim]Getting roster for {info.name}...[/dim]")
            roster = get_label_roster(info.mbid, exclude_artist=artist.name)

            # Step 5: Cross-reference with library
            if library_path and roster:
                console.print("  [dim]Cross-referencing with library...[/dim]")
                roster = cross_reference_library(roster, library_path)

            report.roster[info.name] = roster

    # Step 6: Web enrichment
    if web_search:
        report = enrich_with_web_search(artist_name, report)

        # Fetch rosters for any newly discovered labels that have MusicBrainz IDs
        for label in report.labels:
            if label.source in ("web+musicbrainz",) and label.name not in report.roster:
                console.print(f"  [dim]Getting roster for {label.name}...[/dim]")
                roster = get_label_roster(label.mbid, exclude_artist=artist.name)
                if library_path and roster:
                    console.print("  [dim]Cross-referencing with library...[/dim]")
                    roster = cross_reference_library(roster, library_path)
                report.roster[label.name] = roster

    return report


def display_label_report(report: LabelReport) -> None:
    """Render a label research report with rich terminal output."""
    console.print()
    console.print(Panel.fit(
        f"[bold magenta]DJ CrateDigger[/bold magenta] — Label Research: [bold]{report.artist.name}[/bold]",
        border_style="magenta",
    ))

    # Artist info
    parts = [f"  [bold]Artist:[/bold] {report.artist.name}"]
    if report.artist.country:
        parts.append(f"  [bold]Country:[/bold] {report.artist.country}")
    if report.artist.disambiguation:
        parts.append(f"  [bold]Note:[/bold] {report.artist.disambiguation}")
    if report.artist.aliases:
        parts.append(f"  [bold]Aliases:[/bold] {', '.join(report.artist.aliases)}")
    console.print("\n".join(parts))

    # Releases summary
    console.print(f"\n  [bold]Releases:[/bold] {len(report.releases)} found")
    if report.releases:
        table = Table(show_header=True, box=None, padding=(0, 2))
        table.add_column("Title", style="cyan")
        table.add_column("Label", style="green")
        table.add_column("Cat#", style="dim")
        table.add_column("Date", style="dim")
        table.add_column("Format", style="dim")

        for rel in report.releases[:20]:
            table.add_row(
                rel.title,
                rel.label or "-",
                rel.catalog_number or "-",
                rel.date or "-",
                rel.format or "-",
            )
        console.print(table)
        if len(report.releases) > 20:
            console.print(f"  [dim]... and {len(report.releases) - 20} more[/dim]")

    # Labels detail
    for label in report.labels:
        console.print()
        label_header = f"[bold green]{label.name}[/bold green]"
        if label.source and label.source != "musicbrainz":
            label_header += f" [dim cyan]\\[{label.source}][/dim cyan]"
        if label.country:
            label_header += f" ({label.country})"
        if label.label_type:
            label_header += f" — {label.label_type}"
        console.print(Panel.fit(label_header, border_style="green"))

        # Label URLs
        if label.urls:
            for url_info in label.urls:
                console.print(f"    {url_info['type']}: [link]{url_info['url']}[/link]")

        # Roster
        roster = report.roster.get(label.name, [])
        if roster:
            in_lib = [a for a in roster if a.in_library]
            not_in_lib = [a for a in roster if not a.in_library]

            if in_lib:
                console.print(f"\n  [bold]Artists you already have ({len(in_lib)}):[/bold]")
                table = Table(show_header=False, box=None, padding=(0, 2))
                table.add_column("Artist", style="cyan")
                table.add_column("Releases", justify="right", style="green")
                table.add_column("Files", style="dim")
                for a in in_lib[:15]:
                    file_count = f"{len(a.library_files)} track(s)"
                    table.add_row(a.name, str(a.release_count), file_count)
                console.print(table)

            if not_in_lib:
                console.print(f"\n  [bold yellow]You might also like ({len(not_in_lib)}):[/bold yellow]")
                table = Table(show_header=False, box=None, padding=(0, 2))
                table.add_column("Artist", style="yellow")
                table.add_column("Releases", justify="right", style="green")
                for a in not_in_lib[:15]:
                    table.add_row(a.name, str(a.release_count))
                console.print(table)
                if len(not_in_lib) > 15:
                    console.print(f"  [dim]... and {len(not_in_lib) - 15} more[/dim]")
        else:
            console.print("  [dim]No other artists found on this label.[/dim]")

    console.print()
