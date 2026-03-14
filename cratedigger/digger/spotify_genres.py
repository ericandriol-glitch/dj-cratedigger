"""Spotify artist genre lookup — no OAuth required, uses public search API via spotipy."""

import logging

logger = logging.getLogger(__name__)

# Cache to avoid redundant API calls
_genre_cache: dict[str, list[str]] = {}


def lookup_spotify_genres(artist_name: str) -> list[str]:
    """Look up genres for an artist via Spotify's search API.

    This uses spotipy's client credentials flow (no user OAuth needed).
    Falls back to empty list if spotipy not installed or search fails.

    Returns:
        List of Spotify genre strings (e.g. ['melodic techno', 'deep house']).
    """
    cache_key = artist_name.strip().lower()
    if cache_key in _genre_cache:
        return _genre_cache[cache_key]

    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
    except ImportError:
        logger.debug("spotipy not installed, skipping Spotify genre lookup")
        return []

    try:
        # Try client credentials (no user auth needed)
        # This works if SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET env vars are set,
        # or if ~/.cratedigger/config.yaml has spotify credentials
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
                sp = spotipy.Spotify(auth_manager=auth)
            else:
                # Try env vars
                sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())
        except Exception:
            sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())

        results = sp.search(q=f"artist:{artist_name}", type="artist", limit=3)
        artists = results.get("artists", {}).get("items", [])

        if not artists:
            _genre_cache[cache_key] = []
            return []

        # Prefer exact name match
        name_lower = artist_name.strip().lower()
        for a in artists:
            if a.get("name", "").lower().strip() == name_lower:
                genres = a.get("genres", [])
                _genre_cache[cache_key] = genres
                return genres

        # Fall back to first result
        genres = artists[0].get("genres", [])
        _genre_cache[cache_key] = genres
        return genres

    except Exception as e:
        logger.debug("Spotify genre lookup failed for %s: %s", artist_name, e)
        _genre_cache[cache_key] = []
        return []


def clear_cache():
    """Clear the genre lookup cache."""
    _genre_cache.clear()
