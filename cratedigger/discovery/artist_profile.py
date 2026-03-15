"""Deep artist research — build comprehensive profiles from multiple sources."""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

RATE_LIMIT = 1.1  # MusicBrainz requires >= 1 req/sec


@dataclass
class ArtistProfile:
    """Comprehensive artist profile merged from multiple sources."""

    name: str
    bio: str | None = None
    # Discography
    releases: list[dict] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    # Social
    social_links: dict = field(default_factory=dict)
    # Cross-reference
    tracks_owned: int = 0
    tracks_on_wishlist: int = 0
    # Related
    related_artists: list[str] = field(default_factory=list)
    # Spotify extras
    genres: list[str] = field(default_factory=list)
    popularity: int | None = None
    top_tracks: list[dict] = field(default_factory=list)
    # Sources used
    sources_queried: list[str] = field(default_factory=list)


def _get_mb():
    """Lazy-load musicbrainzngs to avoid import errors when not installed."""
    import musicbrainzngs as mb

    mb.set_useragent("DJ CrateDigger", "0.1.0", "eric.andriol@gmail.com")
    return mb


def _query_musicbrainz(name: str) -> dict:
    """Query MusicBrainz for artist data.

    Returns:
        Dict with keys: bio, releases, labels, related_artists, social_links.
        Empty dict on failure.
    """
    try:
        mb = _get_mb()
    except ImportError:
        logger.warning("musicbrainzngs not installed, skipping MusicBrainz")
        return {}

    result: dict = {"source": "musicbrainz"}

    # Search for artist
    try:
        time.sleep(RATE_LIMIT)
        search = mb.search_artists(name, limit=5)
        artists = search.get("artist-list", [])
        if not artists:
            return {}

        # Prefer exact name match
        artist = artists[0]
        name_lower = name.lower().strip()
        for a in artists:
            if a.get("name", "").lower().strip() == name_lower:
                artist = a
                break

        mbid = artist.get("id", "")
        result["bio"] = artist.get("disambiguation")
    except Exception as e:
        logger.error("MusicBrainz search failed: %s", e)
        return {}

    if not mbid:
        return result

    # Get full details
    try:
        time.sleep(RATE_LIMIT)
        details = mb.get_artist_by_id(
            mbid,
            includes=["url-rels", "release-groups", "artist-rels", "tags"],
        )
        artist_data = details.get("artist", {})
    except Exception as e:
        logger.error("MusicBrainz details failed: %s", e)
        return result

    # Extract releases
    releases = []
    for rg in artist_data.get("release-group-list", []):
        releases.append({
            "title": rg.get("title", ""),
            "year": (rg.get("first-release-date", "") or "")[:4],
            "label": "",
            "format": "",
            "type": rg.get("primary-type", rg.get("type", "Other")),
        })
    releases.sort(key=lambda r: r.get("year", "") or "0000", reverse=True)
    result["releases"] = releases

    # Extract labels from release browse
    labels = set()
    try:
        time.sleep(RATE_LIMIT)
        browse = mb.browse_releases(artist=mbid, includes=["labels"], limit=100)
        for rel in browse.get("release-list", []):
            for li in rel.get("label-info-list", []):
                label_name = li.get("label", {}).get("name", "")
                if label_name and label_name.lower() != "[no label]":
                    labels.add(label_name)
    except Exception as e:
        logger.debug("MusicBrainz label browse failed: %s", e)
    result["labels"] = sorted(labels)

    # Update releases with label info where possible
    # (labels come from release-level, not release-group)

    # Extract related artists
    related = []
    seen_names: set[str] = set()
    for rel in artist_data.get("artist-relation-list", []):
        rel_artist = rel.get("artist", {})
        rel_name = rel_artist.get("name", "")
        if rel_name and rel_name not in seen_names:
            seen_names.add(rel_name)
            related.append(rel_name)
    result["related_artists"] = related

    # Extract social links
    social: dict[str, str] = {}
    for rel in artist_data.get("url-relation-list", []):
        url = rel.get("target", "")
        url_lower = url.lower()
        if "soundcloud.com" in url_lower:
            social["soundcloud"] = url
        elif "bandcamp.com" in url_lower:
            social["bandcamp"] = url
        elif "instagram.com" in url_lower:
            social["instagram"] = url
        elif "spotify.com" in url_lower or "open.spotify" in url_lower:
            social["spotify"] = url
        elif "youtube.com" in url_lower or "youtu.be" in url_lower:
            social["youtube"] = url
    result["social_links"] = social

    return result


def _query_spotify(name: str) -> dict:
    """Query Spotify for artist data via spotipy.

    Returns:
        Dict with keys: genres, popularity, related_artists, top_tracks, social_links.
        Empty dict on failure or if spotipy is not configured.
    """
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
    except ImportError:
        logger.debug("spotipy not installed, skipping Spotify")
        return {}

    try:
        sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())
    except Exception:
        logger.debug("Spotify credentials not configured, skipping")
        return {}

    result: dict = {"source": "spotify"}

    try:
        search = sp.search(q=f"artist:{name}", type="artist", limit=5)
        items = search.get("artists", {}).get("items", [])
        if not items:
            return {}

        # Pick best match
        artist = items[0]
        name_lower = name.lower().strip()
        for item in items:
            if item.get("name", "").lower().strip() == name_lower:
                artist = item
                break

        artist_id = artist["id"]
        result["genres"] = artist.get("genres", [])
        result["popularity"] = artist.get("popularity", 0)
        result["social_links"] = {"spotify": artist.get("external_urls", {}).get("spotify", "")}

        # Related artists
        try:
            related = sp.artist_related_artists(artist_id)
            result["related_artists"] = [
                a["name"] for a in related.get("artists", [])[:10]
            ]
        except Exception:
            result["related_artists"] = []

        # Top tracks
        try:
            top = sp.artist_top_tracks(artist_id)
            result["top_tracks"] = [
                {
                    "title": t["name"],
                    "album": t.get("album", {}).get("name", ""),
                    "preview_url": t.get("preview_url"),
                }
                for t in top.get("tracks", [])[:5]
            ]
        except Exception:
            result["top_tracks"] = []

    except Exception as e:
        logger.debug("Spotify lookup failed: %s", e)
        return {}

    return result


def _query_library(name: str, db_path: Path | None = None) -> dict:
    """Cross-reference artist against the local library DB.

    Returns:
        Dict with keys: tracks_owned, tracks_on_wishlist.
    """
    result: dict = {"tracks_owned": 0, "tracks_on_wishlist": 0}

    try:
        from cratedigger.utils.db import get_connection

        conn = get_connection(db_path)
        pattern = f"%{name}%"

        # Tracks in library
        row = conn.execute(
            "SELECT COUNT(*) FROM audio_analysis WHERE filepath LIKE ?",
            (pattern,),
        ).fetchone()
        result["tracks_owned"] = row[0] if row else 0

        # Wishlist tracks (table may not exist)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM wishlist WHERE artist LIKE ?",
                (pattern,),
            ).fetchone()
            result["tracks_on_wishlist"] = row[0] if row else 0
        except Exception:
            pass  # wishlist table may not exist

        conn.close()
    except Exception as e:
        logger.debug("Library cross-reference failed: %s", e)

    return result


def research_artist_deep(
    name: str,
    db_path: Path | None = None,
) -> ArtistProfile:
    """Build a comprehensive artist profile from multiple sources.

    Layer 1: MusicBrainz -- discography, labels, release dates
    Layer 2: Spotify -- genre tags, popularity, related artists, top tracks
    Layer 3: Library cross-reference -- tracks owned, on wishlist

    Args:
        name: Artist name to research.
        db_path: Optional path to SQLite database. Uses default if None.

    Returns:
        ArtistProfile with all gathered data. Always returns a profile,
        even if no sources yielded data (graceful degradation).
    """
    profile = ArtistProfile(name=name)

    # Layer 1: MusicBrainz
    mb_data = _query_musicbrainz(name)
    if mb_data:
        profile.sources_queried.append("musicbrainz")
        profile.bio = mb_data.get("bio") or profile.bio
        profile.releases = mb_data.get("releases", [])
        profile.labels = mb_data.get("labels", [])
        profile.related_artists = mb_data.get("related_artists", [])
        profile.social_links.update(mb_data.get("social_links", {}))

    # Layer 2: Spotify (optional)
    sp_data = _query_spotify(name)
    if sp_data:
        profile.sources_queried.append("spotify")
        profile.genres = sp_data.get("genres", [])
        profile.popularity = sp_data.get("popularity")
        profile.top_tracks = sp_data.get("top_tracks", [])
        # Merge social links
        for key, val in sp_data.get("social_links", {}).items():
            if val and key not in profile.social_links:
                profile.social_links[key] = val
        # Merge related artists (deduplicate)
        existing = set(profile.related_artists)
        for artist in sp_data.get("related_artists", []):
            if artist not in existing:
                profile.related_artists.append(artist)
                existing.add(artist)

    # Layer 3: Library cross-reference
    lib_data = _query_library(name, db_path)
    profile.tracks_owned = lib_data.get("tracks_owned", 0)
    profile.tracks_on_wishlist = lib_data.get("tracks_on_wishlist", 0)
    if lib_data.get("tracks_owned", 0) > 0 or lib_data.get("tracks_on_wishlist", 0) > 0:
        profile.sources_queried.append("library")

    return profile
