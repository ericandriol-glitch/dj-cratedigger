"""Weekly dig session orchestrator — aggregates multiple discovery sources."""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Normalize artist/title for deduplication and matching."""
    text = text.lower().strip()
    text = re.sub(r"^the\s+", "", text)
    text = re.sub(r"[''`]", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class DiscoveryResult:
    """Tracks found from a single discovery source.

    Attributes:
        source: Origin identifier ("weekly", "artist", "sleeping").
        tracks: List of track dicts with artist, title, genre, bpm,
                preview_url, source_url keys.
    """

    source: str
    tracks: list[dict] = field(default_factory=list)


@dataclass
class SessionReport:
    """Aggregated report from a complete dig session.

    Attributes:
        results: Per-source discovery results.
        total_found: Raw count before deduplication.
        new_to_you: Tracks not in library and not on wishlist.
        already_owned: Tracks found in library.
        already_on_wishlist: Tracks already saved to wishlist.
        tracks: Deduplicated master track list.
    """

    results: list[DiscoveryResult] = field(default_factory=list)
    total_found: int = 0
    new_to_you: int = 0
    already_owned: int = 0
    already_on_wishlist: int = 0
    tracks: list[dict] = field(default_factory=list)


def _styles_from_profile(db_path: Path | None = None) -> list[str]:
    """Read preferred styles from DJ profile in DB."""
    try:
        from cratedigger.digger.profile import load_profile

        profile = load_profile(db_path=db_path)
        if profile and profile.genres:
            sorted_genres = sorted(profile.genres.items(), key=lambda x: -x[1])
            return [g for g, _ in sorted_genres[:5]]
    except Exception:
        pass
    return []


def _gather_weekly(styles: list[str]) -> DiscoveryResult:
    """Step 1: Scan new releases via Traxsource + Spotify."""
    result = DiscoveryResult(source="weekly")
    try:
        from cratedigger.digger.weekly_dig import scan_new_releases

        report = scan_new_releases(genres=styles)
        for r in report.releases:
            result.tracks.append({
                "artist": r.artist,
                "title": r.title,
                "genre": r.genre,
                "bpm": r.bpm,
                "preview_url": r.preview_url,
                "source_url": r.url,
                "label": r.label,
            })
    except Exception as exc:
        logger.warning("Weekly scan failed: %s", exc)
    return result


def _gather_artist(artists: list[str]) -> DiscoveryResult:
    """Step 2: Get recent releases for specified artists."""
    result = DiscoveryResult(source="artist")
    try:
        from cratedigger.digger.artist_research import research_artist

        for name in artists:
            try:
                profile = research_artist(
                    name,
                    include_discogs=False,
                    include_spotify=False,
                )
                if profile and profile.releases:
                    for rel in profile.releases[:5]:
                        result.tracks.append({
                            "artist": profile.name,
                            "title": rel.get("title", ""),
                            "genre": ", ".join(profile.genres[:2]) if profile.genres else "",
                            "bpm": None,
                            "preview_url": "",
                            "source_url": "",
                            "label": "",
                        })
            except Exception as exc:
                logger.warning("Artist research failed for %s: %s", name, exc)
    except ImportError:
        logger.warning("artist_research module not available")
    return result


def _gather_sleeping(db_path: Path | None = None) -> DiscoveryResult:
    """Step 3: Find tracks you stream but don't own."""
    result = DiscoveryResult(source="sleeping")
    try:
        from cratedigger.digger.profile import load_profile
        from cratedigger.digger.sleeping import find_sleeping_on
        from cratedigger.enrichment.spotify import load_spotify_profile

        profile = load_profile(db_path=db_path)
        spotify = load_spotify_profile(db_path=db_path)
        if not profile or not spotify:
            return result

        # Try YouTube too, but don't fail if unavailable
        youtube = None
        try:
            from cratedigger.enrichment.youtube import load_youtube_profile
            youtube = load_youtube_profile(db_path=db_path)
        except Exception:
            pass

        report = find_sleeping_on(profile, spotify, youtube)
        for entry in report.stream_but_dont_own[:20]:
            result.tracks.append({
                "artist": entry["artist"].title(),
                "title": "(streaming gap)",
                "genre": "",
                "bpm": None,
                "preview_url": "",
                "source_url": "",
                "label": "",
            })
    except Exception as exc:
        logger.warning("Sleeping-on scan failed: %s", exc)
    return result


def _deduplicate(tracks: list[dict]) -> list[dict]:
    """Remove duplicate tracks by normalized artist+title."""
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for t in tracks:
        key = (_normalize(t.get("artist", "")), _normalize(t.get("title", "")))
        if key not in seen:
            seen.add(key)
            unique.append(t)
    return unique


def _check_library(tracks: list[dict], db_path: Path | None = None) -> set[int]:
    """Return indices of tracks that exist in the library DB."""
    owned: set[int] = set()
    try:
        from cratedigger.utils.db import get_connection

        conn = get_connection(db_path)
        rows = conn.execute("SELECT filepath FROM audio_analysis").fetchall()
        conn.close()
        stems = {_normalize(Path(r[0]).stem) for r in rows}
        if not stems:
            return owned
        for i, t in enumerate(tracks):
            artist_n = _normalize(t.get("artist", ""))
            title_n = _normalize(t.get("title", ""))
            for stem in stems:
                if artist_n and title_n and artist_n in stem and title_n in stem:
                    owned.add(i)
                    break
    except Exception as exc:
        logger.debug("Library cross-ref failed: %s", exc)
    return owned


def _check_wishlist(tracks: list[dict], db_path: Path | None = None) -> set[int]:
    """Return indices of tracks already on the wishlist."""
    on_wishlist: set[int] = set()
    try:
        from cratedigger.discovery.wishlist import get_wishlist

        existing = get_wishlist(db_path=db_path)
        if not existing:
            return on_wishlist
        wish_keys = set()
        for w in existing:
            key = (_normalize(w.get("artist", "")), _normalize(w.get("title", "")))
            wish_keys.add(key)
        for i, t in enumerate(tracks):
            key = (_normalize(t.get("artist", "")), _normalize(t.get("title", "")))
            if key in wish_keys:
                on_wishlist.add(i)
    except (ImportError, Exception) as exc:
        logger.debug("Wishlist cross-ref skipped: %s", exc)
    return on_wishlist


def run_dig_session(
    styles: list[str] | None = None,
    artists: list[str] | None = None,
    quick: bool = False,
    include_weekly: bool = True,
    include_sleeping: bool = True,
    db_path: Path | None = None,
) -> SessionReport:
    """Run a complete weekly digging session.

    Aggregates tracks from up to three sources, deduplicates, and
    cross-references against the library and wishlist.

    Args:
        styles: Genre/style filter for weekly scan. Reads from profile if None.
        artists: Artist names for targeted research.
        quick: If True, skip interactive prompts (for automation).
        include_weekly: Run the weekly new-releases scan.
        include_sleeping: Run the streaming-gap analysis.
        db_path: Override database path (mainly for testing).

    Returns:
        SessionReport with aggregated, deduplicated results.
    """
    report = SessionReport()

    # Resolve styles from profile if not provided
    effective_styles = styles or _styles_from_profile(db_path)
    if not effective_styles:
        effective_styles = ["Tech House", "Deep House", "House"]

    # Step 1: Weekly releases
    if include_weekly:
        weekly = _gather_weekly(effective_styles)
        report.results.append(weekly)

    # Step 2: Artist releases
    if artists:
        artist_result = _gather_artist(artists)
        report.results.append(artist_result)

    # Step 3: Sleeping on
    if include_sleeping:
        sleeping = _gather_sleeping(db_path)
        if sleeping.tracks:
            report.results.append(sleeping)

    # Aggregate raw count
    all_tracks: list[dict] = []
    for dr in report.results:
        all_tracks.extend(dr.tracks)
    report.total_found = len(all_tracks)

    # Step 4: Deduplicate
    unique = _deduplicate(all_tracks)

    # Step 5: Library cross-reference
    owned_idx = _check_library(unique, db_path)

    # Step 6: Wishlist cross-reference
    wish_idx = _check_wishlist(unique, db_path)

    # Tag each track
    for i, t in enumerate(unique):
        t["owned"] = i in owned_idx
        t["on_wishlist"] = i in wish_idx

    report.already_owned = len(owned_idx)
    report.already_on_wishlist = len(wish_idx)
    report.new_to_you = len(unique) - len(owned_idx) - len(wish_idx - owned_idx)
    report.tracks = unique

    return report
