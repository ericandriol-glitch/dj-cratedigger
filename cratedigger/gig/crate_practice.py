"""Transition analysis for crate-based practice sessions.

Analyzes compatibility between tracks in a gig crate, finds the hardest
transitions, suggests bridge tracks, and logs practice sessions.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..harmonic.camelot import compatibility_score
from ..utils.db import get_connection
from .crate import CrateTrack, GigCrate

PRACTICE_LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS practice_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_a TEXT,
    track_b TEXT,
    confidence TEXT,
    practiced_at TEXT
);
"""


@dataclass
class TransitionAnalysis:
    """Full analysis of a transition between two crate tracks."""

    track_a: CrateTrack
    track_b: CrateTrack
    bpm_delta: float
    key_compatible: bool
    key_score: float  # 0.0-1.0 from camelot compatibility
    energy_delta: float
    difficulty: str  # "easy", "medium", "hard"
    suggestion: str  # mixing advice
    bridge_candidates: list[CrateTrack] = field(default_factory=list)


def _bpm_difficulty(delta: float) -> str:
    """Rate BPM delta difficulty."""
    if delta <= 2:
        return "easy"
    if delta <= 5:
        return "medium"
    return "hard"


def _key_difficulty(score: float) -> str:
    """Rate key compatibility difficulty."""
    if score > 0.8:
        return "easy"
    if score >= 0.5:
        return "medium"
    return "hard"


def _energy_difficulty(delta: float) -> str:
    """Rate energy delta difficulty."""
    if delta < 0.15:
        return "easy"
    if delta <= 0.3:
        return "medium"
    return "hard"


_DIFFICULTY_RANK = {"easy": 0, "medium": 1, "hard": 2}


def _worst_difficulty(*ratings: str) -> str:
    """Return the worst (hardest) difficulty from a set of ratings."""
    return max(ratings, key=lambda r: _DIFFICULTY_RANK[r])


def _build_suggestion(
    bpm_delta: float,
    key_score: float,
    energy_delta: float,
    bridge_candidates: list[CrateTrack],
) -> str:
    """Generate mixing advice based on transition characteristics."""
    parts: list[str] = []

    if bpm_delta > 5:
        parts.append("Loop a section to ride the BPM up/down gradually")
    elif bpm_delta > 2:
        parts.append("Nudge the pitch fader — small BPM gap, manageable")

    if key_score < 0.5:
        parts.append("Use FX or a cappella to mask the key clash")
    elif key_score < 0.8:
        parts.append("Keep the blend short — keys are workable but not ideal")

    if energy_delta > 0.3:
        if bridge_candidates:
            names = [f"{b.artist} - {b.title}" for b in bridge_candidates[:2]]
            parts.append(f"Consider a bridge track: {', '.join(names)}")
        else:
            parts.append("Big energy jump — use a breakdown moment to shift")

    if not parts:
        return "Smooth transition — focus on phrasing"

    return "; ".join(parts)


def find_bridge_tracks(
    a: CrateTrack, b: CrateTrack, crate: GigCrate,
) -> list[CrateTrack]:
    """Find tracks that sit between a and b in BPM + energy, useful as bridge.

    A bridge candidate must:
    - Have BPM between a and b (with 2 BPM tolerance)
    - Have energy between a and b (with 0.05 tolerance)
    - Not be track a or b themselves
    """
    bpm_lo = min(a.bpm, b.bpm) - 2
    bpm_hi = max(a.bpm, b.bpm) + 2
    energy_lo = min(a.energy, b.energy) - 0.05
    energy_hi = max(a.energy, b.energy) + 0.05

    bridges: list[CrateTrack] = []
    for t in crate.tracks:
        if t.filepath in (a.filepath, b.filepath):
            continue
        if bpm_lo <= t.bpm <= bpm_hi and energy_lo <= t.energy <= energy_hi:
            bridges.append(t)

    # Sort by how central the bridge is (closest to midpoint)
    mid_bpm = (a.bpm + b.bpm) / 2
    mid_energy = (a.energy + b.energy) / 2
    bridges.sort(
        key=lambda t: abs(t.bpm - mid_bpm) + abs(t.energy - mid_energy) * 100,
    )
    return bridges


def analyze_transition(
    a: CrateTrack,
    b: CrateTrack,
    crate: GigCrate | None = None,
) -> TransitionAnalysis:
    """Analyze the compatibility of two tracks for mixing.

    Args:
        a: Source track.
        b: Destination track.
        crate: Optional crate to search for bridge candidates.

    Returns:
        TransitionAnalysis with difficulty rating and mixing advice.
    """
    bpm_delta = abs(a.bpm - b.bpm)
    energy_delta = abs(a.energy - b.energy)

    try:
        key_score = compatibility_score(a.key_camelot, b.key_camelot)
    except ValueError:
        key_score = 0.2  # Unknown key = assume bad

    key_compatible = key_score >= 0.8

    bpm_diff = _bpm_difficulty(bpm_delta)
    key_diff = _key_difficulty(key_score)
    energy_diff = _energy_difficulty(energy_delta)
    difficulty = _worst_difficulty(bpm_diff, key_diff, energy_diff)

    bridges: list[CrateTrack] = []
    if crate is not None:
        bridges = find_bridge_tracks(a, b, crate)

    suggestion = _build_suggestion(bpm_delta, key_score, energy_delta, bridges)

    return TransitionAnalysis(
        track_a=a,
        track_b=b,
        bpm_delta=bpm_delta,
        key_compatible=key_compatible,
        key_score=key_score,
        energy_delta=energy_delta,
        difficulty=difficulty,
        suggestion=suggestion,
        bridge_candidates=bridges,
    )


def find_hardest_transitions(
    crate: GigCrate, count: int = 5,
) -> list[TransitionAnalysis]:
    """Find the N most challenging transitions in a crate.

    Considers all energy-adjacent pairs: tracks are sorted by energy,
    and each consecutive pair is analyzed. This simulates the natural
    flow a DJ would follow during a set.

    Args:
        crate: The gig crate to analyze.
        count: Number of hardest transitions to return.

    Returns:
        List of TransitionAnalysis sorted by difficulty (hardest first).
    """
    if len(crate.tracks) < 2:
        return []

    # Sort tracks by energy to simulate a natural set flow
    sorted_tracks = sorted(crate.tracks, key=lambda t: t.energy)

    analyses: list[TransitionAnalysis] = []
    for i in range(len(sorted_tracks) - 1):
        analysis = analyze_transition(
            sorted_tracks[i], sorted_tracks[i + 1], crate,
        )
        analyses.append(analysis)

    # Sort: hard first, then medium, then easy. Within same difficulty,
    # sort by combined "badness" (low key_score + high bpm_delta + high energy_delta)
    def _sort_key(a: TransitionAnalysis) -> tuple[int, float]:
        rank = _DIFFICULTY_RANK.get(a.difficulty, 0)
        badness = (1.0 - a.key_score) + a.bpm_delta / 20.0 + a.energy_delta
        return (-rank, -badness)

    analyses.sort(key=_sort_key)
    return analyses[:count]


def _ensure_practice_table(conn: sqlite3.Connection) -> None:
    """Create the practice_log table if it doesn't exist."""
    conn.executescript(PRACTICE_LOG_SCHEMA)


def log_practice(
    track_a_path: str,
    track_b_path: str,
    confidence: str,
    db_path: Path | None = None,
) -> None:
    """Log a practice session for a transition.

    Args:
        track_a_path: Filepath of the source track.
        track_b_path: Filepath of the destination track.
        confidence: Self-rated confidence level ("low", "medium", "high").
        db_path: Optional custom database path.
    """
    conn = get_connection(db_path)
    _ensure_practice_table(conn)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO practice_log (track_a, track_b, confidence, practiced_at) "
        "VALUES (?, ?, ?, ?)",
        (track_a_path, track_b_path, confidence, now),
    )
    conn.commit()
    conn.close()


def get_practice_history(db_path: Path | None = None) -> list[dict]:
    """Get all practice logs, most recent first.

    Returns:
        List of dicts with keys: id, track_a, track_b, confidence, practiced_at.
    """
    conn = get_connection(db_path)
    _ensure_practice_table(conn)
    rows = conn.execute(
        "SELECT id, track_a, track_b, confidence, practiced_at "
        "FROM practice_log ORDER BY practiced_at DESC"
    ).fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "track_a": row[1],
            "track_b": row[2],
            "confidence": row[3],
            "practiced_at": row[4],
        }
        for row in rows
    ]
