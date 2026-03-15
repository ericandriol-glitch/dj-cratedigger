"""Core wishlist logic — persistent track wishlist for DJ discovery."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from cratedigger.utils.db import get_connection

VALID_PRIORITIES = ("high", "medium", "low")
VALID_STATUSES = ("new", "previewed", "downloaded", "in-library")
PRIORITY_ORDER = {p: i for i, p in enumerate(VALID_PRIORITIES)}

WISHLIST_SCHEMA = """
CREATE TABLE IF NOT EXISTS wishlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT DEFAULT 'manual',
    date_added TEXT NOT NULL,
    priority TEXT DEFAULT 'medium',
    style_tag TEXT,
    preview_url TEXT,
    find_urls TEXT,
    status TEXT DEFAULT 'new',
    notes TEXT,
    UNIQUE(artist, title)
);
"""


@dataclass
class WishlistTrack:
    """A track on the DJ wishlist."""

    id: int | None
    artist: str
    title: str
    source: str
    date_added: str
    priority: str = "medium"
    style_tag: str | None = None
    preview_url: str | None = None
    find_urls: dict = field(default_factory=dict)
    status: str = "new"
    notes: str | None = None


def _ensure_table(conn: sqlite3.Connection) -> None:
    """Create wishlist table if it doesn't exist."""
    conn.executescript(WISHLIST_SCHEMA)


def _row_to_track(row: tuple) -> WishlistTrack:
    """Convert a database row to a WishlistTrack."""
    return WishlistTrack(
        id=row[0],
        artist=row[1],
        title=row[2],
        source=row[3],
        date_added=row[4],
        priority=row[5],
        style_tag=row[6],
        preview_url=row[7],
        find_urls=json.loads(row[8]) if row[8] else {},
        status=row[9],
        notes=row[10],
    )


def add_track(
    artist: str,
    title: str,
    source: str = "manual",
    priority: str = "medium",
    style_tag: str | None = None,
    preview_url: str | None = None,
    notes: str | None = None,
    db_path: Path | None = None,
) -> WishlistTrack:
    """Add a track to the wishlist. Deduplicates by artist+title.

    If a track with the same artist+title already exists, updates
    its source (appends if different), priority, and other fields.

    Args:
        artist: Artist name.
        title: Track title.
        source: Discovery source (dig-weekly, dig-artist, dig-label, manual).
        priority: Priority level (high, medium, low).
        style_tag: Optional style/genre tag.
        preview_url: Optional preview URL.
        notes: Optional notes.
        db_path: Override database path (mainly for testing).

    Returns:
        The added or updated WishlistTrack.
    """
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority: {priority}. Use: {VALID_PRIORITIES}")

    conn = get_connection(db_path)
    _ensure_table(conn)

    # Check for existing track (deduplication)
    cursor = conn.execute(
        "SELECT * FROM wishlist WHERE artist = ? AND title = ?",
        (artist, title),
    )
    existing = cursor.fetchone()

    now = datetime.now(timezone.utc).isoformat()

    if existing:
        track = _row_to_track(existing)
        # Merge source: append new source if different
        existing_sources = {s.strip() for s in track.source.split(",")}
        if source not in existing_sources:
            existing_sources.add(source)
            merged_source = ",".join(sorted(existing_sources))
        else:
            merged_source = track.source

        conn.execute(
            """UPDATE wishlist
               SET source = ?, priority = ?, style_tag = COALESCE(?, style_tag),
                   preview_url = COALESCE(?, preview_url),
                   notes = COALESCE(?, notes)
               WHERE id = ?""",
            (merged_source, priority, style_tag, preview_url, notes, track.id),
        )
        conn.commit()
        cursor = conn.execute("SELECT * FROM wishlist WHERE id = ?", (track.id,))
        return _row_to_track(cursor.fetchone())

    conn.execute(
        """INSERT INTO wishlist
           (artist, title, source, date_added, priority, style_tag,
            preview_url, find_urls, status, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (artist, title, source, now, priority, style_tag,
         preview_url, json.dumps({}), "new", notes),
    )
    conn.commit()
    cursor = conn.execute(
        "SELECT * FROM wishlist WHERE artist = ? AND title = ?",
        (artist, title),
    )
    return _row_to_track(cursor.fetchone())


def remove_track(track_id: int, db_path: Path | None = None) -> bool:
    """Remove a track from the wishlist by ID.

    Args:
        track_id: Database row ID of the track.
        db_path: Override database path (mainly for testing).

    Returns:
        True if a track was removed, False if ID not found.
    """
    conn = get_connection(db_path)
    _ensure_table(conn)
    cursor = conn.execute("DELETE FROM wishlist WHERE id = ?", (track_id,))
    conn.commit()
    return cursor.rowcount > 0


def update_status(
    track_id: int, status: str, db_path: Path | None = None
) -> bool:
    """Update track status.

    Args:
        track_id: Database row ID.
        status: New status (new, previewed, downloaded, in-library).
        db_path: Override database path.

    Returns:
        True if updated, False if ID not found.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Use: {VALID_STATUSES}")
    conn = get_connection(db_path)
    _ensure_table(conn)
    cursor = conn.execute(
        "UPDATE wishlist SET status = ? WHERE id = ?", (status, track_id)
    )
    conn.commit()
    return cursor.rowcount > 0


def update_priority(
    track_id: int, priority: str, db_path: Path | None = None
) -> bool:
    """Update track priority.

    Args:
        track_id: Database row ID.
        priority: New priority (high, medium, low).
        db_path: Override database path.

    Returns:
        True if updated, False if ID not found.
    """
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority: {priority}. Use: {VALID_PRIORITIES}")
    conn = get_connection(db_path)
    _ensure_table(conn)
    cursor = conn.execute(
        "UPDATE wishlist SET priority = ? WHERE id = ?", (priority, track_id)
    )
    conn.commit()
    return cursor.rowcount > 0


def get_wishlist(
    style: str | None = None,
    source: str | None = None,
    status: str | None = None,
    sort: str = "priority",
    db_path: Path | None = None,
) -> list[WishlistTrack]:
    """Get wishlist tracks with optional filters and sorting.

    Args:
        style: Filter by style_tag (substring match).
        source: Filter by source (substring match).
        status: Filter by status (exact match).
        sort: Sort order — priority, date, artist, or source.
        db_path: Override database path.

    Returns:
        List of matching WishlistTrack objects.
    """
    conn = get_connection(db_path)
    _ensure_table(conn)

    query = "SELECT * FROM wishlist WHERE 1=1"
    params: list = []

    if style:
        query += " AND style_tag LIKE ?"
        params.append(f"%{style}%")
    if source:
        query += " AND source LIKE ?"
        params.append(f"%{source}%")
    if status:
        query += " AND status = ?"
        params.append(status)

    # Sorting
    sort_map = {
        "priority": "CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 "
                     "WHEN 'low' THEN 2 END, date_added DESC",
        "date": "date_added DESC",
        "artist": "artist ASC, title ASC",
        "source": "source ASC, artist ASC",
    }
    query += f" ORDER BY {sort_map.get(sort, sort_map['priority'])}"

    cursor = conn.execute(query, params)
    return [_row_to_track(row) for row in cursor.fetchall()]


def check_library_overlap(db_path: Path | None = None) -> list[WishlistTrack]:
    """Cross-reference wishlist against library. Update status for matches.

    Checks the audio_analysis table for tracks matching wishlist entries.
    Uses rapidfuzz for fuzzy matching if available, falls back to exact match.

    Args:
        db_path: Override database path.

    Returns:
        List of wishlist tracks found in the library.
    """
    conn = get_connection(db_path)
    _ensure_table(conn)

    # Get all wishlist tracks not already marked in-library
    cursor = conn.execute(
        "SELECT * FROM wishlist WHERE status != 'in-library'"
    )
    wishlist_tracks = [_row_to_track(row) for row in cursor.fetchall()]

    if not wishlist_tracks:
        return []

    # Get library tracks (artist + title from filepath)
    lib_cursor = conn.execute("SELECT filepath FROM audio_analysis")
    library_paths = [row[0] for row in lib_cursor.fetchall()]

    # Extract artist - title from filenames
    library_entries: list[tuple[str, str]] = []
    for fp in library_paths:
        name = Path(fp).stem
        if " - " in name:
            parts = name.split(" - ", 1)
            library_entries.append((parts[0].strip().lower(), parts[1].strip().lower()))

    # Try fuzzy matching
    try:
        from rapidfuzz import fuzz

        def _is_match(w_artist: str, w_title: str, l_artist: str, l_title: str) -> bool:
            return (
                fuzz.ratio(w_artist.lower(), l_artist) >= 85
                and fuzz.ratio(w_title.lower(), l_title) >= 85
            )
    except ImportError:
        def _is_match(w_artist: str, w_title: str, l_artist: str, l_title: str) -> bool:
            return w_artist.lower() == l_artist and w_title.lower() == l_title

    matched: list[WishlistTrack] = []
    for track in wishlist_tracks:
        for lib_artist, lib_title in library_entries:
            if _is_match(track.artist, track.title, lib_artist, lib_title):
                conn.execute(
                    "UPDATE wishlist SET status = 'in-library' WHERE id = ?",
                    (track.id,),
                )
                track.status = "in-library"
                matched.append(track)
                break

    conn.commit()
    return matched


def get_stats(db_path: Path | None = None) -> dict:
    """Return wishlist stats: total, by priority, by status, by source.

    Args:
        db_path: Override database path.

    Returns:
        Dict with keys: total, by_priority, by_status, by_source.
    """
    conn = get_connection(db_path)
    _ensure_table(conn)

    total = conn.execute("SELECT COUNT(*) FROM wishlist").fetchone()[0]

    by_priority: dict[str, int] = {}
    for row in conn.execute(
        "SELECT priority, COUNT(*) FROM wishlist GROUP BY priority"
    ):
        by_priority[row[0]] = row[1]

    by_status: dict[str, int] = {}
    for row in conn.execute(
        "SELECT status, COUNT(*) FROM wishlist GROUP BY status"
    ):
        by_status[row[0]] = row[1]

    by_source: dict[str, int] = {}
    for row in conn.execute("SELECT source FROM wishlist"):
        for src in row[0].split(","):
            src = src.strip()
            by_source[src] = by_source.get(src, 0) + 1

    return {
        "total": total,
        "by_priority": by_priority,
        "by_status": by_status,
        "by_source": by_source,
    }
