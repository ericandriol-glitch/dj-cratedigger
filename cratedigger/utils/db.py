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
    analyzed_at TEXT,
    analyzer_version TEXT
);

CREATE TABLE IF NOT EXISTS dj_profile (
    id INTEGER PRIMARY KEY DEFAULT 1,
    profile_json TEXT,
    updated_at TEXT
);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a SQLite connection, creating the DB and tables if needed."""
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA_SQL)
    return conn


def get_analyzed_paths(conn: sqlite3.Connection) -> set[str]:
    """Return set of filepaths already in audio_analysis table."""
    cursor = conn.execute("SELECT filepath FROM audio_analysis")
    return {row[0] for row in cursor.fetchall()}


def store_results(
    conn: sqlite3.Connection,
    results: list[tuple[str, AudioFeatures]],
) -> None:
    """Batch insert/replace analysis results.

    Args:
        conn: SQLite connection.
        results: List of (filepath_str, AudioFeatures) tuples.
    """
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
            now,
            ANALYZER_VERSION,
        )
        for filepath, features in results
    ]
    conn.executemany(
        """INSERT OR REPLACE INTO audio_analysis
           (filepath, bpm, bpm_confidence, key_camelot, key_confidence,
            energy, danceability, analyzed_at, analyzer_version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
