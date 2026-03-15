"""Enhanced DJ profile builder — comprehensive library identity analysis."""

import json
import logging
import statistics
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cratedigger.metadata import read_metadata
from cratedigger.scanner import find_audio_files
from cratedigger.utils.db import get_connection

logger = logging.getLogger(__name__)


@dataclass
class DJProfile:
    """Comprehensive DJ profile derived from library analysis."""

    # Library stats
    total_tracks: int = 0
    genre_distribution: dict[str, float] = field(default_factory=dict)
    bpm_range: tuple[float, float] = (0.0, 0.0)
    bpm_sweet_spot: tuple[float, float] = (0.0, 0.0)  # IQR
    key_preferences: list[str] = field(default_factory=list)  # top 5 Camelot keys
    energy_range: tuple[float, float] = (0.0, 0.0)
    top_artists: list[tuple[str, int]] = field(default_factory=list)
    top_labels: list[tuple[str, int]] = field(default_factory=list)
    # Streaming (optional)
    spotify_divergence: list[dict] | None = None
    # Temporal
    tracks_added_last_3_months: int = 0
    oldest_track_date: str | None = None
    # Identity
    sound_summary: str = ""


def _compute_iqr(values: list[float]) -> tuple[float, float]:
    """Return the interquartile range (Q1, Q3) of a list."""
    if len(values) < 4:
        return (min(values), max(values))
    sorted_v = sorted(values)
    n = len(sorted_v)
    q1 = sorted_v[n // 4]
    q3 = sorted_v[3 * n // 4]
    return (round(q1, 1), round(q3, 1))


def _load_spotify_divergence(db_path: Path | None) -> list[dict] | None:
    """Check for Spotify profile and compute genre divergence.

    Returns list of genres streamed but not well-represented in library,
    or None if no Spotify data available.
    """
    try:
        conn = get_connection(db_path)
        row = conn.execute(
            "SELECT profile_json FROM spotify_profile WHERE id = 1"
        ).fetchone()
        conn.close()
        if not row:
            return None
        data = json.loads(row[0])
        # Spotify profile stores top genres
        spotify_genres = data.get("top_genres", [])
        if isinstance(spotify_genres, list) and spotify_genres:
            return [{"genre": g} for g in spotify_genres[:10]]
    except Exception as exc:
        logger.debug("No Spotify divergence data: %s", exc)
    return None


def build_profile(db_path: Path | None = None, library_path: Path | None = None) -> DJProfile:
    """Build comprehensive DJ profile from library + optional streaming data.

    Args:
        db_path: SQLite database path with audio_analysis table.
        library_path: Optional root directory to scan for metadata.

    Returns:
        DJProfile with all computed fields.
    """
    profile = DJProfile()

    # Gather metadata from files if library path given
    artist_counter: Counter[str] = Counter()
    label_counter: Counter[str] = Counter()
    genre_counter: Counter[str] = Counter()
    file_dates: list[datetime] = []

    if library_path and library_path.is_dir():
        audio_files = find_audio_files(library_path)
        profile.total_tracks = len(audio_files)
        now = datetime.now(timezone.utc)
        three_months_ago = now.timestamp() - (90 * 24 * 3600)
        recent = 0

        for fp in audio_files:
            meta = read_metadata(fp)
            if meta.artist and meta.artist.strip():
                artist_counter[meta.artist.strip()] += 1
            if meta.genre and meta.genre.strip():
                genre_counter[meta.genre.strip()] += 1
            if meta.album and meta.album.strip():
                label_counter[meta.album.strip()] += 1

            mtime = fp.stat().st_mtime
            file_dates.append(datetime.fromtimestamp(mtime, tz=timezone.utc))
            if mtime >= three_months_ago:
                recent += 1

        profile.tracks_added_last_3_months = recent
        if file_dates:
            oldest = min(file_dates)
            profile.oldest_track_date = oldest.strftime("%Y-%m-%d")

    # Genre distribution (percentages)
    total_genre_tracks = sum(genre_counter.values())
    if total_genre_tracks > 0:
        profile.genre_distribution = {
            g: round(c / total_genre_tracks * 100, 1)
            for g, c in genre_counter.most_common(15)
        }

    # Top artists and labels
    profile.top_artists = [
        (name, count) for name, count in artist_counter.most_common(20)
    ]
    profile.top_labels = [
        (name, count) for name, count in label_counter.most_common(10)
    ]

    # DB analysis: BPM, key, energy
    try:
        conn = get_connection(db_path)
        rows = conn.execute(
            "SELECT bpm, key_camelot, energy FROM audio_analysis"
        ).fetchall()
        conn.close()
    except Exception:
        rows = []

    bpms = [r[0] for r in rows if r[0] is not None]
    keys = [r[1] for r in rows if r[1] is not None]
    energies = [r[2] for r in rows if r[2] is not None]

    if bpms:
        profile.bpm_range = (round(min(bpms), 1), round(max(bpms), 1))
        profile.bpm_sweet_spot = _compute_iqr(bpms)

    if keys:
        key_counter = Counter(keys)
        profile.key_preferences = [k for k, _ in key_counter.most_common(5)]

    if energies:
        profile.energy_range = (round(min(energies), 3), round(max(energies), 3))

    # Spotify divergence
    profile.spotify_divergence = _load_spotify_divergence(db_path)

    # Sound summary
    profile.sound_summary = generate_sound_summary(profile)

    return profile


def generate_sound_summary(profile: DJProfile) -> str:
    """Generate a one-paragraph description of the DJ's sound identity.

    Template-based (not LLM). Describes genre focus, BPM sweet spot,
    key preferences, and streaming divergence.
    """
    parts: list[str] = []

    # Genre focus
    genres = list(profile.genre_distribution.keys())
    if len(genres) >= 2:
        parts.append(f"{genres[0]} and {genres[1]} DJ")
    elif len(genres) == 1:
        parts.append(f"{genres[0]} DJ")
    else:
        parts.append("Eclectic DJ")

    # BPM sweet spot
    if profile.bpm_sweet_spot != (0.0, 0.0):
        lo, hi = profile.bpm_sweet_spot
        parts.append(f"with a BPM sweet spot of {lo:.0f}-{hi:.0f}")

    # Key preferences
    if profile.key_preferences:
        minor_count = sum(1 for k in profile.key_preferences if k.endswith("A"))
        major_count = len(profile.key_preferences) - minor_count
        top_keys = ", ".join(profile.key_preferences[:3])
        bias = ""
        if minor_count > major_count:
            bias = " (minor key bias)"
        elif major_count > minor_count:
            bias = " (major key bias)"
        parts.append(f"Favors {top_keys}{bias}.")

    # Top artists
    if profile.top_artists:
        artist_names = [a[0] for a in profile.top_artists[:3]]
        parts.append(f"Top artists: {', '.join(artist_names)}.")

    # Streaming divergence
    if profile.spotify_divergence:
        div_genres = [d["genre"] for d in profile.spotify_divergence[:3]]
        parts.append(
            f"Streaming shows interest in {', '.join(div_genres)} "
            f"not yet reflected in the library."
        )

    return " ".join(parts) if parts else "Profile data insufficient for summary."


def save_enhanced_profile(profile: DJProfile, db_path: Path | None = None) -> None:
    """Store enhanced profile as JSON in the dj_profile table."""
    conn = get_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    # Convert tuples to lists for JSON serialization
    data = asdict(profile)
    profile_json = json.dumps(data, indent=2)
    conn.execute(
        "INSERT OR REPLACE INTO dj_profile (id, profile_json, updated_at) VALUES (2, ?, ?)",
        (profile_json, now),
    )
    conn.commit()
    conn.close()


def load_enhanced_profile(db_path: Path | None = None) -> DJProfile | None:
    """Load enhanced profile from the database."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT profile_json FROM dj_profile WHERE id = 2").fetchone()
    conn.close()
    if not row:
        return None
    data = json.loads(row[0])
    # Convert lists back to tuples where needed
    data["bpm_range"] = tuple(data.get("bpm_range", (0.0, 0.0)))
    data["bpm_sweet_spot"] = tuple(data.get("bpm_sweet_spot", (0.0, 0.0)))
    data["top_artists"] = [tuple(a) for a in data.get("top_artists", [])]
    data["top_labels"] = [tuple(l) for l in data.get("top_labels", [])]
    return DJProfile(**data)
