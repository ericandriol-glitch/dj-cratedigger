"""FastAPI backend for CrateDigger web UI."""

import io
import os
import sys
from pathlib import Path

# Ensure cratedigger package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Force UTF-8 output for Rich console in submodules
os.environ["PYTHONIOENCODING"] = "utf-8"

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

app = FastAPI(title="CrateDigger API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Scan ───────────────────────────────────────────────────


@app.post("/api/scan")
def scan_library(path: str = Query(...)):
    """Scan a folder and populate the DB with metadata (no Essentia needed).

    Reads artist, title, BPM, key, genre from file tags via mutagen.
    """
    from cratedigger.metadata import read_metadata
    from cratedigger.scanner import find_audio_files
    from cratedigger.utils.db import get_connection

    scan_path = Path(path)
    if not scan_path.exists():
        return {"error": f"Path not found: {path}", "scanned": 0}

    audio_files = find_audio_files(scan_path)
    if not audio_files:
        return {"error": "No audio files found", "scanned": 0}

    conn = get_connection()
    # Ensure genre column exists
    try:
        conn.execute("ALTER TABLE audio_analysis ADD COLUMN genre TEXT")
    except Exception:
        pass  # column already exists

    inserted = 0
    for fp in audio_files:
        meta = read_metadata(fp)
        filepath = str(fp)

        # Parse BPM as float if tagged
        bpm = None
        if meta.bpm:
            try:
                bpm = float(str(meta.bpm).split(".")[0])
            except (ValueError, TypeError):
                pass

        conn.execute(
            "INSERT OR IGNORE INTO audio_analysis "
            "(filepath, bpm, key_camelot, genre, analyzed_at, analyzer_version) "
            "VALUES (?, ?, ?, ?, datetime('now'), 'metadata-scan')",
            (filepath, bpm, meta.key, meta.genre),
        )
        inserted += 1

    conn.commit()
    conn.close()

    return {"scanned": inserted, "total_files": len(audio_files), "path": str(scan_path)}


# ── Enrich Genres ─────────────────────────────────────────


@app.post("/api/enrich/genres")
def enrich_genres(limit: int = Query(50, ge=1, le=500)):
    """Look up genres via MusicBrainz for tracks missing genre tags."""
    from cratedigger.metadata import read_metadata
    from cratedigger.utils.db import get_connection

    conn = get_connection()
    rows = conn.execute(
        "SELECT filepath FROM audio_analysis "
        "WHERE (genre IS NULL OR genre = '') LIMIT ?",
        (limit,),
    ).fetchall()

    if not rows:
        conn.close()
        return {"enriched": 0, "total_missing": 0}

    enriched = 0
    try:
        from cratedigger.enrichment.musicbrainz import lookup_genre
    except ImportError:
        conn.close()
        return {"enriched": 0, "error": "musicbrainzngs not installed"}

    for (filepath,) in rows:
        fp = Path(filepath)
        try:
            meta = read_metadata(fp)
            if not meta.artist or not meta.title:
                continue
            result = lookup_genre(meta.artist, meta.title)
            if result.genre:
                conn.execute(
                    "UPDATE audio_analysis SET genre = ? WHERE filepath = ?",
                    (result.genre, filepath),
                )
                enriched += 1
        except Exception:
            continue

    conn.commit()
    total_missing = conn.execute(
        "SELECT COUNT(*) FROM audio_analysis WHERE genre IS NULL OR genre = ''"
    ).fetchone()[0]
    conn.close()

    return {"enriched": enriched, "total_missing": total_missing}


# ── Related Tracks ─────────────────────────────────────────


@app.get("/api/library/related")
def related_tracks(
    filepath: str = Query(...),
    limit: int = Query(8, ge=1, le=20),
):
    """Find tracks that mix well with a given track based on BPM + Key compatibility."""
    from cratedigger.utils.db import get_connection

    conn = get_connection()

    # Get the source track's BPM and key
    source = conn.execute(
        "SELECT bpm, key_camelot, energy FROM audio_analysis WHERE filepath = ?",
        (filepath,),
    ).fetchone()

    if not source or not source[0]:
        conn.close()
        return {"tracks": [], "source_bpm": None, "source_key": None}

    src_bpm, src_key, src_energy = source

    # Camelot compatibility: same key, +-1, major/minor swap
    compatible_keys = _camelot_compatible(src_key) if src_key else []
    key_placeholders = ",".join("?" * len(compatible_keys)) if compatible_keys else "''"

    # Find tracks with similar BPM (+-6) and compatible keys
    bpm_min = src_bpm - 6
    bpm_max = src_bpm + 6

    query = f"""
        SELECT filepath, bpm, key_camelot, energy, genre
        FROM audio_analysis
        WHERE filepath != ?
          AND bpm IS NOT NULL AND bpm BETWEEN ? AND ?
          {f"AND key_camelot IN ({key_placeholders})" if compatible_keys else ""}
        ORDER BY ABS(bpm - ?) ASC
        LIMIT ?
    """
    params = [filepath, bpm_min, bpm_max] + compatible_keys + [src_bpm, limit]
    rows = conn.execute(query, params).fetchall()
    conn.close()

    from cratedigger.metadata import read_metadata

    tracks = []
    for fp_str, bpm, key, energy, genre in rows:
        fp = Path(fp_str)
        title = fp.stem
        artist = ""
        try:
            meta = read_metadata(fp)
            if meta.title:
                title = meta.title
            if meta.artist:
                artist = meta.artist
        except Exception:
            if " - " in fp.stem:
                parts = fp.stem.split(" - ", 1)
                artist, title = parts[0].strip(), parts[1].strip()

        tracks.append({
            "filepath": fp_str,
            "title": title,
            "artist": artist,
            "bpm": round(bpm) if bpm else None,
            "key": key,
            "energy": round(energy, 2) if energy else None,
            "genre": genre,
        })

    return {
        "tracks": tracks,
        "source_bpm": round(src_bpm) if src_bpm else None,
        "source_key": src_key,
    }


def _camelot_compatible(key: str) -> list[str]:
    """Return Camelot keys compatible with the given key."""
    if not key or len(key) < 2:
        return []
    try:
        num = int(key[:-1])
        letter = key[-1].upper()
    except (ValueError, IndexError):
        return []

    result = [key]  # Same key
    # Adjacent +-1
    prev_num = 12 if num == 1 else num - 1
    next_num = 1 if num == 12 else num + 1
    result.append(f"{prev_num}{letter}")
    result.append(f"{next_num}{letter}")
    # Major/minor swap (same number)
    other = "B" if letter == "A" else "A"
    result.append(f"{num}{other}")
    return result


# ── Library Stats ──────────────────────────────────────────


@app.get("/api/library/stats")
def library_stats():
    """Library overview: track counts, health score, metadata completeness."""
    from cratedigger.utils.db import get_connection

    conn = get_connection()

    # Total tracks in DB
    total = conn.execute("SELECT COUNT(*) FROM audio_analysis").fetchone()[0]

    # Counts by field presence
    has_bpm = conn.execute("SELECT COUNT(*) FROM audio_analysis WHERE bpm IS NOT NULL").fetchone()[0]
    has_key = conn.execute("SELECT COUNT(*) FROM audio_analysis WHERE key_camelot IS NOT NULL").fetchone()[0]
    has_genre = conn.execute("SELECT COUNT(*) FROM audio_analysis WHERE genre IS NOT NULL AND genre != ''").fetchone()[0]

    conn.close()

    # Read metadata completeness from files (sample if large)
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
    search: str = Query(None),
    sort: str = Query("filepath"),
    order: str = Query("asc"),
):
    """Paginated track list with metadata, server-side search, and sorting."""
    from cratedigger.metadata import read_metadata
    from cratedigger.utils.db import get_connection

    conn = get_connection()

    # Build WHERE clauses
    conditions = []
    params = []

    if filter == "complete":
        conditions.append("bpm IS NOT NULL AND key_camelot IS NOT NULL AND genre IS NOT NULL AND genre != ''")
    elif filter == "partial":
        conditions.append(
            "(bpm IS NOT NULL OR key_camelot IS NOT NULL) "
            "AND NOT (bpm IS NOT NULL AND key_camelot IS NOT NULL AND genre IS NOT NULL AND genre != '')"
        )
    elif filter == "missing":
        conditions.append("bpm IS NULL AND key_camelot IS NULL")

    # Server-side search — matches against filepath (contains artist/title)
    if search and search.strip():
        conditions.append("filepath LIKE ?")
        params.append(f"%{search.strip()}%")

    where = ""
    if conditions:
        where = "WHERE " + " AND ".join(conditions)

    # Validate sort column
    valid_sorts = {"filepath", "bpm", "key_camelot", "energy", "genre"}
    sort_col = sort if sort in valid_sorts else "filepath"
    sort_dir = "DESC" if order.lower() == "desc" else "ASC"

    # Get total for this filter + search
    total = conn.execute(f"SELECT COUNT(*) FROM audio_analysis {where}", params).fetchone()[0]

    # Push NULLs to the bottom regardless of sort direction
    rows = conn.execute(
        f"SELECT filepath, bpm, key_camelot, energy, genre "
        f"FROM audio_analysis {where} "
        f"ORDER BY {sort_col} IS NULL, {sort_col} {sort_dir} LIMIT ? OFFSET ?",
        params + [limit, offset],
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
    from rich.console import Console

    # Patch Rich consoles to write to devnull in server context
    import cratedigger.digger.label as _label_mod
    from cratedigger.digger.label import research_label
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
                    "name": lb.name,
                    "country": lb.country,
                    "type": lb.label_type,
                    "urls": lb.urls,
                    "source": lb.source,
                }
                for lb in report.labels
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
    from rich.console import Console

    import cratedigger.digger.festival as _fest_mod
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


# ── Artist Research ────────────────────────────────────────


@app.get("/api/dig/artist")
def dig_artist(name: str = Query(...)):
    """Research an artist across MusicBrainz, library, and streaming."""
    from rich.console import Console

    # Patch Rich console for server context
    import cratedigger.digger.artist_research as _art_mod
    from cratedigger.digger.artist_research import research_artist
    _null = Console(file=io.StringIO(), force_terminal=False)
    _orig = _art_mod.console
    _art_mod.console = _null
    try:
        report = research_artist(name, include_discogs=True, include_spotify=True)
    finally:
        _art_mod.console = _orig

    if not report:
        return {"report": None}

    return {
        "report": {
            "name": report.name,
            "mbid": report.mbid,
            "country": report.country,
            "disambiguation": report.disambiguation,
            "aliases": report.aliases,
            "genres": report.genres,
            "urls": report.urls,
            "releases": [
                {
                    "title": r.get("title", ""),
                    "type": r.get("type", ""),
                    "date": r.get("date", ""),
                }
                for r in report.releases[:20]
            ],
            "labels": report.labels,
            "related_artists": report.related_artists[:15],
            "library_tracks": report.library_tracks,
            "spotify_status": report.spotify_status,
            "discogs_releases": report.discogs_releases[:15],
            "bpm_profile": report.bpm_profile,
            "key_profile": report.key_profile,
        }
    }


# ── Weekly Dig ─────────────────────────────────────────────


@app.get("/api/dig/weekly")
def dig_weekly(genres: str = Query(None)):
    """Scan new releases matching DJ profile."""
    from rich.console import Console

    # Patch Rich console for server context
    import cratedigger.digger.weekly_dig as _dig_mod
    from cratedigger.digger.weekly_dig import scan_new_releases
    _null = Console(file=io.StringIO(), force_terminal=False)
    _orig = _dig_mod.console
    _dig_mod.console = _null
    try:
        genre_list = [g.strip() for g in genres.split(",")] if genres else None
        report = scan_new_releases(genres=genre_list)
    finally:
        _dig_mod.console = _orig

    return {
        "report": {
            "genres_scanned": report.genres_scanned,
            "total_found": report.total_found,
            "after_filter": report.after_filter,
            "profile_genres": report.profile_genres,
            "profile_bpm_range": report.profile_bpm_range,
            "releases": [
                {
                    "title": r.title,
                    "artist": r.artist,
                    "label": r.label,
                    "genre": r.genre,
                    "url": r.url,
                    "relevance_score": r.relevance_score,
                    "artist_in_library": r.artist_in_library,
                    "artist_in_streaming": r.artist_in_streaming,
                    "in_library": r.in_library,
                }
                for r in report.releases[:50]
            ],
        }
    }


# ── Related Tracks (Harmonic Mixing) ──────────────────────


@app.get("/api/library/related")
def library_related(
    filepath: str = Query(...),
    limit: int = Query(5, ge=1, le=20),
):
    """Find tracks compatible for harmonic mixing (BPM ±3, compatible Camelot keys)."""
    from cratedigger.harmonic.camelot import compatible_keys, VALID_KEYS
    from cratedigger.metadata import read_metadata
    from cratedigger.utils.db import get_connection

    conn = get_connection()

    # Get source track's BPM and key
    row = conn.execute(
        "SELECT bpm, key_camelot FROM audio_analysis WHERE filepath = ?",
        (filepath,),
    ).fetchone()
    if not row or not row[0]:
        conn.close()
        return {"tracks": []}

    src_bpm, src_key = row
    bpm_lo, bpm_hi = src_bpm - 3, src_bpm + 3

    # Find BPM-compatible tracks (exclude self)
    candidates = conn.execute(
        "SELECT filepath, bpm, key_camelot, energy, genre "
        "FROM audio_analysis "
        "WHERE bpm BETWEEN ? AND ? AND filepath != ? "
        "LIMIT 200",
        (bpm_lo, bpm_hi, filepath),
    ).fetchall()
    conn.close()

    # Score and rank by key compatibility
    compat_keys = set()
    if src_key and src_key.strip() in VALID_KEYS:
        compat_keys = set(compatible_keys(src_key.strip(), min_score=0.7))
        compat_keys.add(src_key.strip())

    scored = []
    for fp, bpm, key, energy, genre in candidates:
        key_score = 1.0 if key and key.strip() == src_key else (
            0.9 if key and key.strip() in compat_keys else 0.3
        )
        bpm_score = 1.0 - abs(bpm - src_bpm) / 3.0
        score = key_score * 0.6 + bpm_score * 0.4
        scored.append((fp, bpm, key, energy, genre, score))

    scored.sort(key=lambda x: -x[5])
    top = scored[:limit]

    tracks = []
    for fp, bpm, key, energy, genre, score in top:
        p = Path(fp)
        title = p.stem
        artist = ""
        try:
            meta = read_metadata(p)
            if meta.title:
                title = meta.title
            if meta.artist:
                artist = meta.artist
        except Exception:
            if " - " in p.stem:
                parts = p.stem.split(" - ", 1)
                artist, title = parts[0].strip(), parts[1].strip()

        tracks.append({
            "filepath": str(p), "title": title, "artist": artist,
            "bpm": round(bpm) if bpm else None, "key": key or None,
            "energy": round(energy, 2) if energy else None, "genre": genre or None,
            "status": "complete" if bpm and key and genre else "partial" if bpm or key else "missing",
        })

    return {"tracks": tracks}


# ── Audio Streaming ───────────────────────────────────────


MIME_MAP = {
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
}


@app.get("/api/audio/stream")
def stream_audio(filepath: str = Query(...), request: Request = None):
    """Serve an audio file with range request support for reliable browser playback."""
    fp = Path(filepath)
    if not fp.exists():
        raise HTTPException(status_code=404, detail="File not found")

    suffix = fp.suffix.lower()
    media_type = MIME_MAP.get(suffix, "application/octet-stream")
    file_size = fp.stat().st_size

    # Handle Range header for seeking/buffering
    range_header = request.headers.get("range") if request else None
    if range_header:
        # Parse "bytes=START-END"
        range_spec = range_header.replace("bytes=", "")
        parts = range_spec.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if parts[1] else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        def iter_range():
            with open(fp, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(8192, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(length),
                "Accept-Ranges": "bytes",
            },
        )

    return FileResponse(
        path=str(fp),
        media_type=media_type,
        filename=fp.name,
        headers={"Accept-Ranges": "bytes"},
    )


# ── Run ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
