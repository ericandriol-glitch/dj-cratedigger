"""Musical key detection using librosa chroma features + Krumhansl-Schmuckler."""

from pathlib import Path

import librosa
import numpy as np

# Krumhansl-Kessler key profiles
# Major and minor key profiles for correlation-based key detection
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

PITCH_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]


def detect_key(file_path: Path, sr: int = 22050, duration: float | None = 120.0) -> str | None:
    """
    Detect the musical key of an audio file using chroma analysis
    and the Krumhansl-Schmuckler key-finding algorithm.

    Returns:
        Key string like "Am", "Eb", "F#m", or None on failure.
    """
    try:
        total_dur = librosa.get_duration(path=file_path)

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
            return None

        # Compute chroma features (CQT-based for better frequency resolution)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr_actual)

        # Average chroma across time to get a pitch class distribution
        chroma_mean = np.mean(chroma, axis=1)

        # Normalize
        chroma_mean = chroma_mean / (np.linalg.norm(chroma_mean) + 1e-10)

        # Correlate with all major and minor key profiles
        best_corr = -2.0
        best_key = None

        for shift in range(12):
            # Rotate the profile to match each possible root
            major_rotated = np.roll(MAJOR_PROFILE, shift)
            minor_rotated = np.roll(MINOR_PROFILE, shift)

            # Normalize profiles
            major_norm = major_rotated / (np.linalg.norm(major_rotated) + 1e-10)
            minor_norm = minor_rotated / (np.linalg.norm(minor_rotated) + 1e-10)

            corr_major = np.corrcoef(chroma_mean, major_norm)[0, 1]
            corr_minor = np.corrcoef(chroma_mean, minor_norm)[0, 1]

            if corr_major > best_corr:
                best_corr = corr_major
                best_key = PITCH_NAMES[shift]

            if corr_minor > best_corr:
                best_corr = corr_minor
                best_key = PITCH_NAMES[shift] + "m"

        return best_key

    except Exception:
        return None
