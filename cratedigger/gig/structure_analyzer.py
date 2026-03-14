"""Track structure detection using Essentia energy segmentation.

Detects intros, breakdowns, drops, and outros by analysing the
energy envelope of a track against its beat grid.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class TrackStructure:
    """Structural landmarks detected in a track."""

    intro_end: float | None = None         # seconds
    first_breakdown: float | None = None
    first_drop: float | None = None
    second_breakdown: float | None = None
    second_drop: float | None = None
    outro_start: float | None = None
    confidence: float = 0.0                # 0-1


def _compute_energy_envelope(
    audio: np.ndarray,
    sample_rate: float,
    window_sec: float = 4.0,
    hop_sec: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute RMS energy envelope with timestamps.

    Returns:
        Tuple of (timestamps_array, energy_array).
    """
    window_samples = int(window_sec * sample_rate)
    hop_samples = int(hop_sec * sample_rate)

    timestamps = []
    energies = []

    for start in range(0, len(audio) - window_samples, hop_samples):
        window = audio[start : start + window_samples]
        rms = float(np.sqrt(np.mean(window ** 2)))
        time_sec = (start + window_samples / 2) / sample_rate
        timestamps.append(time_sec)
        energies.append(rms)

    return np.array(timestamps), np.array(energies)


def _smooth(values: np.ndarray, window: int = 7) -> np.ndarray:
    """Moving average smoothing."""
    if len(values) < window:
        return values
    kernel = np.ones(window) / window
    # Pad to avoid edge effects
    padded = np.pad(values, (window // 2, window // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")[: len(values)]


def _snap_to_downbeat(
    position: float,
    beats: np.ndarray,
    bar_size: int = 4,
) -> float:
    """Snap a position to the nearest downbeat (4-bar boundary)."""
    if len(beats) < bar_size:
        return position

    # Find downbeats (every bar_size beats)
    downbeats = beats[::bar_size]

    if len(downbeats) == 0:
        return position

    idx = int(np.argmin(np.abs(downbeats - position)))
    return float(downbeats[idx])


def _find_breakdowns(
    timestamps: np.ndarray,
    energy: np.ndarray,
    mean_energy: float,
    beats: np.ndarray,
    bpm: float,
    threshold: float = 0.4,
    min_beats: int = 8,
) -> list[float]:
    """Find positions where energy drops below threshold for sustained period."""
    if bpm <= 0:
        return []

    beat_duration = 60.0 / bpm
    min_duration = min_beats * beat_duration

    low_mask = energy < (threshold * mean_energy)
    breakdowns = []
    start_idx = None

    for i, is_low in enumerate(low_mask):
        if is_low and start_idx is None:
            start_idx = i
        elif not is_low and start_idx is not None:
            duration = timestamps[i] - timestamps[start_idx]
            if duration >= min_duration:
                breakdowns.append(float(timestamps[start_idx]))
            start_idx = None

    # Handle case where track ends in a low-energy section
    if start_idx is not None:
        duration = timestamps[-1] - timestamps[start_idx]
        if duration >= min_duration:
            breakdowns.append(float(timestamps[start_idx]))

    return breakdowns


def _find_drops(
    timestamps: np.ndarray,
    energy: np.ndarray,
    mean_energy: float,
    breakdowns: list[float],
    threshold: float = 0.8,
) -> list[float]:
    """Find energy rises above threshold after each breakdown."""
    drops = []

    for bd_time in breakdowns:
        # Look for first high-energy point after the breakdown
        for i, t in enumerate(timestamps):
            if t > bd_time and energy[i] >= (threshold * mean_energy):
                drops.append(float(t))
                break

    return drops


def analyze_structure(filepath: Path | str, bpm: float | None = None) -> TrackStructure:
    """Detect structural landmarks in a track.

    Args:
        filepath: Path to audio file.
        bpm: Known BPM (optional, detected if not given).

    Returns:
        TrackStructure with detected landmarks.
    """
    try:
        import essentia.standard as es
    except ImportError:
        return TrackStructure(confidence=0.0)

    filepath = Path(filepath)
    if not filepath.exists():
        return TrackStructure(confidence=0.0)

    try:
        audio = es.MonoLoader(filename=str(filepath))()
    except Exception:
        return TrackStructure(confidence=0.0)

    sample_rate = 44100.0
    duration = len(audio) / sample_rate

    if duration < 30:
        return TrackStructure(confidence=0.0)

    # Get beats
    try:
        rhythm_extractor = es.RhythmExtractor2013(method="multifeature")
        detected_bpm, beats, beats_confidence, _, _ = rhythm_extractor(audio)
    except Exception:
        return TrackStructure(confidence=0.0)

    if bpm is None:
        bpm = float(detected_bpm)

    if bpm <= 0 or len(beats) < 16:
        return TrackStructure(confidence=0.0)

    # Compute and smooth energy envelope
    timestamps, energy = _compute_energy_envelope(audio, sample_rate)
    energy = _smooth(energy)

    if len(energy) == 0:
        return TrackStructure(confidence=0.0)

    mean_energy = float(np.mean(energy))
    if mean_energy <= 0:
        return TrackStructure(confidence=0.0)

    # Detect intro end: first moment energy exceeds 60% of mean
    intro_end = None
    for i, e in enumerate(energy):
        if e >= 0.6 * mean_energy:
            intro_end = _snap_to_downbeat(float(timestamps[i]), beats)
            break

    # Detect outro start: last moment energy drops below 60% and stays low
    outro_start = None
    for i in range(len(energy) - 1, -1, -1):
        if energy[i] >= 0.6 * mean_energy:
            if i + 1 < len(timestamps):
                outro_start = _snap_to_downbeat(float(timestamps[i + 1]), beats)
            break

    # Detect breakdowns and drops
    breakdowns = _find_breakdowns(timestamps, energy, mean_energy, beats, bpm)
    drops = _find_drops(timestamps, energy, mean_energy, breakdowns)

    # Snap to downbeats
    breakdowns = [_snap_to_downbeat(b, beats) for b in breakdowns]
    drops = [_snap_to_downbeat(d, beats) for d in drops]

    # Build result
    structure = TrackStructure()
    structure.intro_end = intro_end
    structure.outro_start = outro_start

    if breakdowns:
        structure.first_breakdown = breakdowns[0]
    if len(breakdowns) >= 2:
        structure.second_breakdown = breakdowns[1]
    if drops:
        structure.first_drop = drops[0]
    if len(drops) >= 2:
        structure.second_drop = drops[1]

    # Confidence based on how many landmarks we found
    found = sum(1 for v in [
        structure.intro_end, structure.first_breakdown,
        structure.first_drop, structure.outro_start,
    ] if v is not None)
    structure.confidence = round(found / 4, 2)

    return structure


def store_structure(filepath: str, structure: TrackStructure, db_path: Path | None = None) -> None:
    """Store track structure in the database."""
    from datetime import datetime, timezone

    from cratedigger.utils.db import get_connection

    conn = get_connection(db_path)

    # Ensure table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS track_structure (
            filepath TEXT PRIMARY KEY,
            intro_end REAL,
            first_breakdown REAL,
            first_drop REAL,
            second_breakdown REAL,
            second_drop REAL,
            outro_start REAL,
            confidence REAL,
            analyzed_at TEXT
        )
    """)

    conn.execute(
        """INSERT OR REPLACE INTO track_structure
           (filepath, intro_end, first_breakdown, first_drop,
            second_breakdown, second_drop, outro_start, confidence, analyzed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            filepath,
            structure.intro_end,
            structure.first_breakdown,
            structure.first_drop,
            structure.second_breakdown,
            structure.second_drop,
            structure.outro_start,
            structure.confidence,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
