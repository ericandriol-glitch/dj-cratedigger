"""Genre enrichment using MusicBrainz API."""

import time
from dataclasses import dataclass, field
from typing import Optional

import musicbrainzngs as mb

mb.set_useragent("DJ CrateDigger", "0.1.0", "cratedigger@example.com")

# DJ-relevant genre mappings — normalize MusicBrainz tags to clean genre names
GENRE_NORMALIZE = {
    "house": "House",
    "deep house": "Deep House",
    "tech house": "Tech House",
    "acid house": "Acid House",
    "progressive house": "Progressive House",
    "vocal house": "Vocal House",
    "afro house": "Afro House",
    "funky house": "Funky House",
    "soulful house": "Soulful House",
    "disco house": "Disco House",
    "electro house": "Electro House",
    "future house": "Future House",
    "uk garage": "UK Garage",
    "future garage": "Future Garage",
    "garage": "Garage",
    "techno": "Techno",
    "minimal techno": "Minimal Techno",
    "detroit techno": "Detroit Techno",
    "dub techno": "Dub Techno",
    "disco": "Disco",
    "nu-disco": "Nu-Disco",
    "nu disco": "Nu-Disco",
    "italo-disco": "Italo Disco",
    "italo disco": "Italo Disco",
    "euro-disco": "Euro Disco",
    "electro-disco": "Electro Disco",
    "electronic": "Electronic",
    "electronica": "Electronic",
    "electro": "Electro",
    "edm": "EDM",
    "dance": "Dance",
    "dance-pop": "Dance-Pop",
    "synth-pop": "Synth-Pop",
    "synthpop": "Synth-Pop",
    "pop": "Pop",
    "europop": "Europop",
    "funk": "Funk",
    "soul": "Soul",
    "r&b": "R&B",
    "hip-hop": "Hip-Hop",
    "hip hop": "Hip-Hop",
    "rap": "Hip-Hop",
    "reggae": "Reggae",
    "dancehall": "Dancehall",
    "afrobeat": "Afrobeat",
    "afrobeats": "Afrobeats",
    "latin": "Latin",
    "reggaeton": "Reggaeton",
    "downtempo": "Downtempo",
    "chillout": "Chillout",
    "lounge": "Lounge",
    "ambient": "Ambient",
    "trance": "Trance",
    "progressive trance": "Progressive Trance",
    "drum and bass": "Drum & Bass",
    "drum & bass": "Drum & Bass",
    "jungle": "Jungle",
    "breakbeat": "Breakbeat",
    "breaks": "Breakbeat",
    "dubstep": "Dubstep",
    "bass music": "Bass Music",
    "uk funky": "UK Funky",
    "jazz": "Jazz",
    "jazz-funk": "Jazz-Funk",
    "acid jazz": "Acid Jazz",
    "nu-jazz": "Nu-Jazz",
    "world": "World",
    "balearic": "Balearic",
    "cosmic disco": "Cosmic Disco",
    "rock": "Rock",
    "indie": "Indie",
    "new wave": "New Wave",
    "post-punk": "Post-Punk",
    "boogie": "Boogie",
    "gospel": "Gospel",
}

# Priority order for DJ-relevant genres (prefer specific over generic)
GENRE_PRIORITY = [
    "Deep House", "Tech House", "Acid House", "Progressive House",
    "Afro House", "Funky House", "Soulful House", "Disco House",
    "Vocal House", "Electro House", "Future House", "House",
    "UK Garage", "Future Garage", "Garage",
    "Minimal Techno", "Detroit Techno", "Dub Techno", "Techno",
    "Nu-Disco", "Italo Disco", "Euro Disco", "Electro Disco",
    "Cosmic Disco", "Disco",
    "Afrobeat", "Afrobeats", "Dancehall", "Reggaeton", "Latin",
    "Drum & Bass", "Jungle", "Breakbeat", "Dubstep", "Bass Music",
    "Trance", "Progressive Trance",
    "Synth-Pop", "Dance-Pop", "New Wave",
    "Funk", "Boogie", "Soul", "R&B", "Gospel",
    "Jazz-Funk", "Acid Jazz", "Nu-Jazz", "Jazz",
    "Balearic", "Downtempo", "Chillout", "Lounge", "Ambient",
    "Hip-Hop", "Reggae",
    "Electro", "Electronic", "EDM", "Dance",
    "Europop", "Pop", "Rock", "Indie", "World",
]


@dataclass
class GenreLookup:
    artist: str
    title: str
    genre: Optional[str] = None
    all_tags: list[str] = field(default_factory=list)
    source: str = ""


def _pick_best_genre(tags: list[dict]) -> tuple[Optional[str], list[str]]:
    """Pick the best DJ-relevant genre from a list of MusicBrainz tags."""
    if not tags:
        return None, []

    # Normalize all tags
    normalized = []
    for tag in tags:
        name = tag["name"].lower().strip()
        count = int(tag.get("count", 0))
        mapped = GENRE_NORMALIZE.get(name)
        if mapped:
            normalized.append((mapped, count))

    all_genres = [g for g, _ in normalized]

    if not normalized:
        return None, [tag["name"] for tag in tags[:5]]

    # Pick by priority order
    for priority_genre in GENRE_PRIORITY:
        for genre, count in normalized:
            if genre == priority_genre:
                return genre, all_genres

    # Fallback: highest count
    normalized.sort(key=lambda x: x[1], reverse=True)
    return normalized[0][0], all_genres


# Cache artist lookups to avoid redundant API calls
_artist_cache: dict[str, tuple[Optional[str], list[str]]] = {}


def lookup_genre(artist: str, title: str, rate_limit: float = 1.0) -> GenreLookup:
    """
    Look up genre for a track using MusicBrainz.

    Strategy:
    1. Check artist cache
    2. Search for artist, get artist-level genre tags (best coverage)
    3. Fall back to recording-level search

    Args:
        rate_limit: Seconds between API calls (MusicBrainz requires >= 1s)
    """
    result = GenreLookup(artist=artist, title=title)
    artist_key = artist.strip().lower()

    # Check cache
    if artist_key in _artist_cache:
        genre, tags = _artist_cache[artist_key]
        if genre:
            result.genre = genre
            result.all_tags = tags
            result.source = "artist (cached)"
            return result

    # --- Pass 1: Artist-level tags ---
    try:
        time.sleep(rate_limit)
        search = mb.search_artists(artist, limit=1)
        if search["artist-list"]:
            a = search["artist-list"][0]
            tags = a.get("tag-list", [])
            genre, all_tags = _pick_best_genre(tags)
            _artist_cache[artist_key] = (genre, all_tags)
            if genre:
                result.genre = genre
                result.all_tags = all_tags
                result.source = "artist"
                return result
    except Exception:
        pass

    # --- Pass 2: Recording-level tags ---
    try:
        time.sleep(rate_limit)
        search = mb.search_recordings(title, artistname=artist, limit=3)
        for rec in search.get("recording-list", []):
            tags = rec.get("tag-list", [])
            genre, all_tags = _pick_best_genre(tags)
            if genre:
                result.genre = genre
                result.all_tags = all_tags
                result.source = "recording"
                return result
    except Exception:
        pass

    # Cache the miss too
    if artist_key not in _artist_cache:
        _artist_cache[artist_key] = (None, [])

    return result


def clear_cache():
    """Clear the artist lookup cache."""
    _artist_cache.clear()
