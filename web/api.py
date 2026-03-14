"""FastAPI backend for CrateDigger web UI."""

import io
import os
import sys
from pathlib import Path

# Ensure cratedigger package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force UTF-8 output for Rich console in submodules
os.environ["PYTHONIOENCODING"] = "utf-8"

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="CrateDigger API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Library Stats ──────────────────────────────────────────


@app.get("/api/library/stats")
def library_stats():
    """Library overview: track counts, health score, metadata completeness."""
    from cratedigger.utils.db import get_connection
    from cratedigger.digger.profile import load_profile

    conn = get_connection()

    # Total tracks in DB
    total = conn.execute("SELECT COUNT(*) FROM audio_analysis").fetchone()[0]

    # Counts by field presence
    has_bpm = conn.execute("SELECT COUNT(*) FROM audio_analysis WHERE bpm IS NOT NULL").fetchone()[0]
    has_key = conn.execute("SELECT COUNT(*) FROM audio_analysis WHERE key_camelot IS NOT NULL").fetchone()[0]
    has_genre = conn.execute("SELECT COUNT(*) FROM audio_analysis WHERE genre IS NOT NULL AND genre != ''").fetchone()[0]

    conn.close()

    # Read metadata completeness from files (sample if large)
    title_artist_count = total  # DB entries always have filepath, assume tagged
    artwork_count = 0  # Would need mutagen check — skip for now

    # Health score
    if total > 0:
        completeness = (has_bpm + has_key + has_genre) / (total * 3)
        health_score = round(completeness * 100)
    else:
        health_score = 0

    # Categorise tracks
    good = conn_count_good(has_bpm, has_key, has_genre, total)
    missing = total - has_bpm  # tracks with no BPM as proxy for "missing"
    partial = total - good - missing

    return {
        "total_tracks": total,
        "health_score": health_score,
        "good": good,
        "partial": max(0, partial),
        "missing": missing,
        "completeness": {
            "title_artist": {"count": total, "total": total},
            "bpm": {"count": has_bpm, "total": total},
            "key": {"count": has_key, "total": total},
            "genre": {"count": has_genre, "total": total},
            "artwork": {"count": artwork_count, "total": total},
        },
        "issues": {
            "missing_bpm": total - has_bpm,
            "missing_key": total - has_key,
            "missing_genre": total - has_genre,
        },
    }


def conn_count_good(has_bpm, has_key, has_genre, total):
    """Estimate 'good' tracks — those with BPM + key + genre."""
    # Conservative: min of all three
    from cratedigger.utils.db import get_connection

    conn = get_connection()
    good = conn.execute(
        "SELECT COUNT(*) FROM audio_analysis "
        "WHERE bpm IS NOT NULL AND key_camelot IS NOT NULL "
        "AND genre IS NOT NULL AND genre != ''"
    ).fetchone()[0]
    conn.close()
    return good


# ── Genre Distribution ─────────────────────────────────────


@app.get("/api/library/genres")
def library_genres():
    """Genre distribution from the database."""
    from cratedigger.utils.db import get_connection

    conn = get_connection()
    rows = conn.execute(
        "SELECT genre, COUNT(*) as cnt FROM audio_analysis "
        "WHERE genre IS NOT NULL AND genre != '' "
        "GROUP BY genre ORDER BY cnt DESC LIMIT 15"
    ).fetchall()
    conn.close()

    total = sum(r[1] for r in rows)
    if total == 0:
        return {"genres": []}

    return {
        "genres": [
            {"name": r[0], "count": r[1], "pct": round(r[1] / total * 100, 1)}
            for r in rows
        ]
    }


# ── Tracks ─────────────────────────────────────────────────


@app.get("/api/library/tracks")
def library_tracks(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    filter: str = Query("all"),
):
    """Paginated track list with metadata from DB + file tags."""
    from cratedigger.utils.db import get_connection
    from cratedigger.metadata import read_metadata

    conn = get_connection()

    # Build WHERE clause based on filter
    where = ""
    if filter == "complete":
        where = "WHERE bpm IS NOT NULL AND key_camelot IS NOT NULL AND genre IS NOT NULL AND genre != ''"
    elif filter == "partial":
        where = (
            "WHERE (bpm IS NOT NULL OR key_camelot IS NOT NULL) "
            "AND NOT (bpm IS NOT NULL AND key_camelot IS NOT NULL AND genre IS NOT NULL AND genre != '')"
        )
    elif filter == "missing":
        where = "WHERE bpm IS NULL AND key_camelot IS NULL"

    # Get total for this filter
    total = conn.execute(f"SELECT COUNT(*) FROM audio_analysis {where}").fetchone()[0]

    rows = conn.execute(
        f"SELECT filepath, bpm, key_camelot, energy, genre "
        f"FROM audio_analysis {where} "
        f"ORDER BY filepath LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    conn.close()

    tracks = []
    for filepath, bpm, key, energy, genre in rows:
        fp = Path(filepath)

        # Try reading metadata for title/artist
        title = fp.stem
        artist = ""
        try:
            meta = read_metadata(fp)
            if meta.title:
                title = meta.title
            if meta.artist:
                artist = meta.artist
        except Exception:
            # Parse "Artist - Title" from filename
            if " - " in fp.stem:
                parts = fp.stem.split(" - ", 1)
                artist = parts[0].strip()
                title = parts[1].strip()

        # Determine status
        if bpm and key and genre:
            status = "complete"
        elif bpm or key:
            status = "partial"
        else:
            status = "missing"

        tracks.append({
            "filepath": str(fp),
            "title": title,
            "artist": artist,
            "bpm": round(bpm) if bpm else None,
            "key": key or None,
            "energy": round(energy, 2) if energy else None,
            "genre": genre or None,
            "status": status,
        })

    return {"tracks": tracks, "total": total, "offset": offset, "limit": limit}


# ── DJ Profile ─────────────────────────────────────────────


@app.get("/api/profile")
def dj_profile():
    """Load the saved DJ profile."""
    from cratedigger.digger.profile import load_profile

    profile = load_profile()
    if not profile:
        return {"profile": None}

    return {
        "profile": {
            "genres": profile.genres,
            "bpm_range": profile.bpm_range,
            "key_distribution": profile.key_distribution,
            "energy_range": profile.energy_range,
            "top_artists": profile.top_artists,
            "total_tracks": profile.total_tracks,
            "analyzed_tracks": profile.analyzed_tracks,
            "health_score": profile.health_score,
        }
    }


# ── Label Research ─────────────────────────────────────────


@app.get("/api/dig/label")
def dig_label(artist: str = Query(...)):
    """Research labels for an artist."""
    from cratedigger.digger.label import research_label

    # Patch Rich consoles to write to devnull in server context
    import cratedigger.digger.label as _label_mod
    from rich.console import Console
    _null = Console(file=io.StringIO(), force_terminal=False)
    _orig = _label_mod.console
    _label_mod.console = _null
    try:
        report = research_label(artist, web_search=True)
    finally:
        _label_mod.console = _orig
    if not report:
        return {"report": None}

    return {
        "report": {
            "artist": {
                "name": report.artist.name,
                "country": report.artist.country,
                "disambiguation": report.artist.disambiguation,
                "aliases": report.artist.aliases,
            },
            "releases": [
                {
                    "title": r.title,
                    "label": r.label,
                    "catalog": r.catalog_number,
                    "date": r.date,
                    "format": r.format,
                }
                for r in report.releases[:30]
            ],
            "labels": [
                {
                    "name": l.name,
                    "country": l.country,
                    "type": l.label_type,
                    "urls": l.urls,
                    "source": l.source,
                }
                for l in report.labels
            ],
            "roster": {
                label_name: [
                    {"name": a.name, "release_count": a.release_count, "in_library": a.in_library}
                    for a in artists[:15]
                ]
                for label_name, artists in report.roster.items()
            },
        }
    }


# ── Festival Scanner ───────────────────────────────────────


@app.get("/api/dig/festival")
def dig_festival(lineup: str = Query(...), name: str = Query("Festival")):
    """Scan a festival lineup."""
    from cratedigger.digger.festival import parse_lineup, scan_festival

    artists = parse_lineup(lineup)
    if not artists:
        return {"report": None}

    # Patch Rich console for server context
    import cratedigger.digger.festival as _fest_mod
    from rich.console import Console
    _null = Console(file=io.StringIO(), force_terminal=False)
    _orig = _fest_mod.console
    _fest_mod.console = _null
    try:
        report = scan_festival(artists, festival_name=name, lookup_genres=True)
    finally:
        _fest_mod.console = _orig

    return {
        "report": {
            "festival_name": report.festival_name,
            "total": report.total,
            "already_own": report.already_own,
            "stream_only": report.stream_only,
            "unknown": report.unknown_count,
            "genre_matches": report.genre_matches,
            "artists": [
                {
                    "name": a.name,
                    "category": a.category,
                    "library_tracks": a.library_tracks,
                    "stream_score": a.stream_score,
                    "genres": a.genres,
                    "genre_match": a.genre_match,
                }
                for a in report.artists
            ],
        }
    }


# ── Run ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
