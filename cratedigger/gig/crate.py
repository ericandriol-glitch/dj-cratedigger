"""Core crate builder for gig preparation.

A crate is a pool of tracks organized by energy zone — not a setlist.
DJs pick from the crate during a gig based on crowd energy.
"""

import json
import random
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..utils.db import get_connection

# Energy zone boundaries
ZONE_PEAK = (0.8, 1.0)
ZONE_BUILD = (0.6, 0.8)
ZONE_GROOVE = (0.4, 0.6)
ZONE_WARMUP = (0.2, 0.4)

ZONE_LABELS = {
    "peak": ZONE_PEAK,
    "build": ZONE_BUILD,
    "groove": ZONE_GROOVE,
    "warmup": ZONE_WARMUP,
}

# Default energy for tracks with no analysis
DEFAULT_ENERGY = 0.5

# Minimum percentage of crate per zone
MIN_ZONE_PERCENT = 0.15

GIG_CRATES_SCHEMA = """
CREATE TABLE IF NOT EXISTS gig_crates (
    name TEXT PRIMARY KEY,
    crate_json TEXT,
    created_at TEXT,
    updated_at TEXT
);
"""


@dataclass
class CrateTrack:
    """A single track in a gig crate."""

    filepath: str
    artist: str
    title: str
    bpm: float
    key_camelot: str
    energy: float
    genre: str | None
    energy_zone: str
    has_cues: bool
    duration_seconds: float


@dataclass
class GigCrate:
    """A curated pool of tracks for a gig, organized by energy zone."""

    name: str
    tracks: list[CrateTrack] = field(default_factory=list)
    created_at: str = ""
    bpm_range: tuple[float, float] = (0.0, 0.0)
    bpm_median: float = 0.0
    genre_distribution: dict[str, int] = field(default_factory=dict)
    energy_zones: dict[str, list[CrateTrack]] = field(default_factory=dict)
    key_coverage: int = 0
    total_duration_seconds: float = 0.0
    tracks_with_cues: int = 0
    tracks_without_cues: int = 0


def _classify_zone(energy: float) -> str:
    """Assign a track to an energy zone based on its energy value."""
    if energy >= ZONE_PEAK[0]:
        return "peak"
    if energy >= ZONE_BUILD[0]:
        return "build"
    if energy >= ZONE_GROOVE[0]:
        return "groove"
    return "warmup"


def _compute_stats(crate: GigCrate) -> None:
    """Compute summary statistics for a crate in place."""
    if not crate.tracks:
        return

    bpms = [t.bpm for t in crate.tracks if t.bpm > 0]
    if bpms:
        crate.bpm_range = (min(bpms), max(bpms))
        crate.bpm_median = statistics.median(bpms)

    # Genre distribution
    genres: dict[str, int] = {}
    for t in crate.tracks:
        g = t.genre or "unknown"
        genres[g] = genres.get(g, 0) + 1
    crate.genre_distribution = dict(sorted(genres.items(), key=lambda x: -x[1]))

    # Energy zones
    zones: dict[str, list[CrateTrack]] = {
        "peak": [], "build": [], "groove": [], "warmup": [],
    }
    for t in crate.tracks:
        zones[t.energy_zone].append(t)
    crate.energy_zones = zones

    # Key coverage
    keys = {t.key_camelot for t in crate.tracks if t.key_camelot}
    crate.key_coverage = len(keys)

    # Duration
    crate.total_duration_seconds = sum(t.duration_seconds for t in crate.tracks)

    # Cue stats
    crate.tracks_with_cues = sum(1 for t in crate.tracks if t.has_cues)
    crate.tracks_without_cues = len(crate.tracks) - crate.tracks_with_cues


def _query_candidates(
    vibe: list[str] | None,
    bpm_range: tuple[float, float] | None,
    energy_range: tuple[float, float] | None,
    db_path: Path | None,
) -> list[dict]:
    """Query the DB for candidate tracks matching filters."""
    conn = get_connection(db_path)
    _ensure_crates_table(conn)

    query = "SELECT filepath, bpm, key_camelot, energy, genre, analyzed_at FROM audio_analysis WHERE 1=1"
    params: list = []

    if bpm_range:
        query += " AND bpm >= ? AND bpm <= ?"
        params.extend([bpm_range[0], bpm_range[1]])

    if energy_range:
        query += " AND (energy >= ? AND energy <= ? OR energy IS NULL)"
        params.extend([energy_range[0], energy_range[1]])

    rows = conn.execute(query, params).fetchall()
    conn.close()

    candidates = []
    for filepath, bpm, key_camelot, energy, genre, analyzed_at in rows:
        # Apply vibe filter in Python (case-insensitive substring)
        if vibe:
            track_genre = (genre or "").lower()
            if not any(v.lower() in track_genre for v in vibe):
                continue
        candidates.append({
            "filepath": filepath,
            "bpm": bpm or 0.0,
            "key_camelot": key_camelot or "",
            "energy": energy if energy is not None else DEFAULT_ENERGY,
            "genre": genre,
            "analyzed_at": analyzed_at or "",
        })

    return candidates


def _smart_select(candidates: list[dict], size: int) -> list[dict]:
    """Select tracks ensuring energy, BPM, and key diversity."""
    if len(candidates) <= size:
        return candidates

    # Bucket by energy zone
    buckets: dict[str, list[dict]] = {
        "peak": [], "build": [], "groove": [], "warmup": [],
    }
    for c in candidates:
        zone = _classify_zone(c["energy"])
        buckets[zone].append(c)

    # Sort each bucket by BPM for diversity sampling
    for zone in buckets:
        buckets[zone].sort(key=lambda t: t["bpm"])

    min_per_zone = max(1, int(size * MIN_ZONE_PERCENT))
    selected: list[dict] = []
    remaining_budget = size

    # Phase 1: guarantee minimum per zone
    for zone_name, zone_tracks in buckets.items():
        take = min(min_per_zone, len(zone_tracks))
        if take > 0:
            # Evenly space across BPM range for diversity
            step = max(1, len(zone_tracks) // take)
            picked = [zone_tracks[i * step] for i in range(take) if i * step < len(zone_tracks)]
            selected.extend(picked[:take])
            remaining_budget -= len(picked[:take])

    # Phase 2: fill remaining budget from all unpicked candidates
    selected_fps = {t["filepath"] for t in selected}
    unpicked = [c for c in candidates if c["filepath"] not in selected_fps]

    # Prefer key diversity and recency
    keys_seen: dict[str, int] = {}
    for t in selected:
        k = t["key_camelot"]
        keys_seen[k] = keys_seen.get(k, 0) + 1

    def _diversity_score(track: dict) -> tuple[int, str]:
        """Lower is better: prefer unseen keys, then recent analysis."""
        k = track["key_camelot"]
        count = keys_seen.get(k, 0)
        recency = track.get("analyzed_at", "")
        return (count, recency)

    unpicked.sort(key=_diversity_score)

    for t in unpicked:
        if remaining_budget <= 0:
            break
        selected.append(t)
        k = t["key_camelot"]
        keys_seen[k] = keys_seen.get(k, 0) + 1
        remaining_budget -= 1

    return selected


def build_crate(
    name: str,
    vibe: list[str] | None = None,
    bpm_range: tuple[float, float] | None = None,
    energy_range: tuple[float, float] | None = None,
    size: int = 80,
    db_path: Path | None = None,
) -> GigCrate:
    """Build a gig crate from the library.

    Args:
        name: Gig name for the crate.
        vibe: Genre filter terms (case-insensitive substring match).
        bpm_range: Min and max BPM to include.
        energy_range: Min and max energy to include.
        size: Target number of tracks in the crate.
        db_path: Optional custom database path.

    Returns:
        A GigCrate with tracks organized by energy zone.
    """
    candidates = _query_candidates(vibe, bpm_range, energy_range, db_path)
    selected = _smart_select(candidates, size)

    # Build CrateTrack objects (read metadata for artist/title/duration)
    tracks: list[CrateTrack] = []
    for row in selected:
        fp = Path(row["filepath"])
        artist = ""
        title = fp.stem
        duration = 0.0
        has_cues = False

        # Try to parse artist - title from filename
        stem = fp.stem
        if " - " in stem:
            parts = stem.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].strip()

        tracks.append(CrateTrack(
            filepath=row["filepath"],
            artist=artist,
            title=title,
            bpm=row["bpm"],
            key_camelot=row["key_camelot"],
            energy=row["energy"],
            genre=row["genre"],
            energy_zone=_classify_zone(row["energy"]),
            has_cues=has_cues,
            duration_seconds=duration,
        ))

    crate = GigCrate(
        name=name,
        tracks=tracks,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _compute_stats(crate)
    return crate


def _ensure_crates_table(conn) -> None:
    """Create the gig_crates table if it doesn't exist."""
    conn.executescript(GIG_CRATES_SCHEMA)


def _crate_to_json(crate: GigCrate) -> str:
    """Serialize a GigCrate to JSON."""
    data = {
        "name": crate.name,
        "created_at": crate.created_at,
        "tracks": [asdict(t) for t in crate.tracks],
    }
    return json.dumps(data)


def _crate_from_json(raw: str) -> GigCrate:
    """Deserialize a GigCrate from JSON."""
    data = json.loads(raw)
    tracks = [CrateTrack(**t) for t in data["tracks"]]
    crate = GigCrate(
        name=data["name"],
        tracks=tracks,
        created_at=data.get("created_at", ""),
    )
    _compute_stats(crate)
    return crate


def save_crate(crate: GigCrate, db_path: Path | None = None) -> None:
    """Save crate to SQLite for later retrieval."""
    conn = get_connection(db_path)
    _ensure_crates_table(conn)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO gig_crates (name, crate_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?)",
        (crate.name, _crate_to_json(crate), crate.created_at, now),
    )
    conn.commit()
    conn.close()


def load_crate(name: str, db_path: Path | None = None) -> GigCrate | None:
    """Load a saved crate by name."""
    conn = get_connection(db_path)
    _ensure_crates_table(conn)
    row = conn.execute(
        "SELECT crate_json FROM gig_crates WHERE name = ?", (name,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return _crate_from_json(row[0])


def list_crates(db_path: Path | None = None) -> list[dict]:
    """List all saved crates with basic stats."""
    conn = get_connection(db_path)
    _ensure_crates_table(conn)
    rows = conn.execute(
        "SELECT name, crate_json, created_at, updated_at FROM gig_crates ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()

    results = []
    for name, crate_json, created_at, updated_at in rows:
        data = json.loads(crate_json)
        results.append({
            "name": name,
            "track_count": len(data.get("tracks", [])),
            "created_at": created_at,
            "updated_at": updated_at,
        })
    return results


def export_crate(crate: GigCrate, output_path: Path) -> Path:
    """Export crate as Rekordbox 7 XML with energy zone sub-playlists."""
    from .rekordbox_writer import write_rekordbox_xml

    track_dicts: list[dict] = []
    zone_indices: dict[str, list[int]] = {
        "PEAK": [], "BUILD": [], "GROOVE": [], "WARM-UP": [],
    }
    zone_key_map = {
        "peak": "PEAK", "build": "BUILD", "groove": "GROOVE", "warmup": "WARM-UP",
    }

    for i, t in enumerate(crate.tracks):
        track_dicts.append({
            "filepath": Path(t.filepath),
            "artist": t.artist,
            "title": t.title,
            "bpm": t.bpm,
            "key_camelot": t.key_camelot,
            "genre": t.genre or "",
            "duration_seconds": t.duration_seconds,
            "album": "",
            "year": "",
            "bitrate": 0,
            "sample_rate": 0,
        })
        xml_zone = zone_key_map.get(t.energy_zone, "GROOVE")
        zone_indices[xml_zone].append(i)

    # Only include non-empty zones
    sub_playlists = {k: v for k, v in zone_indices.items() if v}

    return write_rekordbox_xml(
        track_dicts, crate.name, output_path, sub_playlists=sub_playlists,
    )
