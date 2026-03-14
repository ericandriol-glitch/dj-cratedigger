"""SQLite database operations for CrateDigger."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from cratedigger.core.analyzer import ANALYZER_VERSION, AudioFeatures

# Default DB location
DEFAULT_DB_PATH = Path.home() / ".cratedigger" / "cratedigger.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audio_analysis (
    filepath TEXT PRIMARY KEY,
    bpm REAL,
    bpm_confidence REAL,
    key_camelot TEXT,
    key_confidence REAL,
    energy REAL,
    danceability REAL,
    genre TEXT,
    analyzed_at TEXT,
    analyzer_version TEXT
);

CREATE TABLE IF NOT EXISTS dj_profile (
    id INTEGER PRIMARY KEY DEFAULT 1,
    profile_json TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS spotify_profile (
    id INTEGER PRIMARY KEY DEFAULT 1,
    profile_json TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS youtube_profile (
    id INTEGER PRIMARY KEY DEFAULT 1,
    profile_json TEXT,
    updated_at TEXT
);
"""


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Apply schema migrations for existing databases."""
    # Check if genre column exists in audio_analysis
    cursor = conn.execute("PRAGMA table_info(audio_analysis)")
    columns = {row[1] for row in cursor.fetchall()}
    if "genre" not in columns:
        conn.execute("ALTER TABLE audio_analysis ADD COLUMN genre TEXT")
        conn.commit()


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a SQLite connection, creating the DB and tables if needed."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)
    _migrate_schema(conn)
    return conn


def get_analyzed_paths(conn: sqlite3.Connection) -> set[str]:
    """Return set of filepaths already in audio_analysis table."""
    cursor = conn.execute("SELECT filepath FROM audio_analysis")
    return {row[0] for row in cursor.fetchall()}


def store_results(
    conn: sqlite3.Connection,
    results: list[tuple[str, AudioFeatures]],
    genres: dict[str, str] | None = None,
) -> None:
    """Batch insert/replace analysis results.

    Args:
        conn: SQLite connection.
        results: List of (filepath_str, AudioFeatures) tuples.
        genres: Optional mapping of filepath -> genre string.
    """
    genres = genres or {}
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            filepath,
            features.bpm,
            features.bpm_confidence,
            features.key,
            features.key_confidence,
            features.energy,
            features.danceability,
            genres.get(filepath),
            now,
            ANALYZER_VERSION,
        )
        for filepath, features in results
    ]
    conn.executemany(
        """INSERT OR REPLACE INTO audio_analysis
           (filepath, bpm, bpm_confidence, key_camelot, key_confidence,
            energy, danceability, genre, analyzed_at, analyzer_version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()


def update_genres(
    conn: sqlite3.Connection,
    genres: dict[str, str],
) -> int:
    """Update genre for tracks already in the database.

    Args:
        conn: SQLite connection.
        genres: Mapping of filepath -> genre string.

    Returns:
        Number of rows updated.
    """
    updated = 0
    for filepath, genre in genres.items():
        cursor = conn.execute(
            "UPDATE audio_analysis SET genre = ? WHERE filepath = ?",
            (genre, filepath),
        )
        updated += cursor.rowcount
    conn.commit()
    return updated
