"""BPM detection using librosa."""

from pathlib import Path

import librosa
import numpy as np


def detect_bpm(file_path: Path, sr: int = 22050, duration: float | None = 120.0) -> float | None:
    """
    Detect the BPM of an audio file.

    Loads up to `duration` seconds from the middle of the track for efficiency,
    since intros/outros often lack a clear beat.

    Returns:
        BPM as a float rounded to 1 decimal, or None on failure.
    """
    try:
        # Get total duration first
        total_dur = librosa.get_duration(path=file_path)

        # For tracks longer than the analysis window, start from 30s in
        # to skip intros that may not have a beat
        offset = 0.0
        if duration and total_dur > duration + 30:
            offset = 30.0

        y, sr_actual = librosa.load(
            file_path,
            sr=sr,
            mono=True,
            offset=offset,
            duration=duration,
        )

        if len(y) < sr_actual * 5:
            # Too short to detect BPM reliably
            return None

        # Use librosa's beat tracker
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr_actual)

        # tempo can be an array in newer librosa versions
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0])
        else:
            tempo = float(tempo)

        if tempo < 50 or tempo > 250:
            return None

        return round(tempo, 1)

    except Exception:
        return None
