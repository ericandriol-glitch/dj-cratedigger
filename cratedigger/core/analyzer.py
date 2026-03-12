"""Essentia-based audio analysis: BPM, key, energy, danceability."""

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Camelot wheel mapping: (key, scale) -> Camelot code
CAMELOT_MAP: dict[tuple[str, str], str] = {
    ("C", "major"): "8B",
    ("C", "minor"): "5A",
    ("C#", "major"): "3B",
    ("C#", "minor"): "12A",
    ("D", "major"): "10B",
    ("D", "minor"): "7A",
    ("Eb", "major"): "5B",
    ("Eb", "minor"): "2A",
    ("E", "major"): "12B",
    ("E", "minor"): "9A",
    ("F", "major"): "7B",
    ("F", "minor"): "4A",
    ("F#", "major"): "2B",
    ("F#", "minor"): "11A",
    ("G", "major"): "9B",
    ("G", "minor"): "6A",
    ("Ab", "major"): "4B",
    ("Ab", "minor"): "1A",
    ("A", "major"): "11B",
    ("A", "minor"): "8A",
    ("Bb", "major"): "6B",
    ("Bb", "minor"): "3A",
    ("B", "major"): "1B",
    ("B", "minor"): "10A",
}

# Essentia sometimes returns "Db" instead of "C#", etc.
KEY_NORMALIZE: dict[str, str] = {
    "Db": "C#",
    "Gb": "F#",
}

ANALYZER_VERSION = "essentia-2.1b6"


@dataclass
class AudioFeatures:
    """Analysis results for a single track."""

    bpm: float | None = None
    bpm_confidence: float = 0.0
    key: str | None = None
    key_confidence: float = 0.0
    energy: float | None = None
    danceability: float | None = None


def _to_camelot(key: str, scale: str) -> str | None:
    """Convert Essentia key/scale to Camelot notation."""
    normalized_key = KEY_NORMALIZE.get(key, key)
    return CAMELOT_MAP.get((normalized_key, scale))


def _load_audio(filepath: Path) -> np.ndarray:
    """Load audio file as mono 44100Hz using Essentia."""
    from essentia.standard import MonoLoader

    loader = MonoLoader(filename=str(filepath))
    return loader()


def _detect_bpm(audio: np.ndarray) -> tuple[float | None, float]:
    """Detect BPM using RhythmExtractor2013.

    Returns:
        Tuple of (bpm, confidence). BPM is None if detection fails.
    """
    from essentia.standard import RhythmExtractor2013

    extractor = RhythmExtractor2013(method="multifeature")
    bpm, beats, beats_confidence, _, beats_intervals = extractor(audio)

    if bpm < 50 or bpm > 250:
        return None, 0.0

    # Confidence: use mean beat confidence, clamped to 0-1
    confidence = float(np.clip(np.mean(beats_confidence), 0.0, 1.0)) if len(beats_confidence) > 0 else 0.0

    return round(float(bpm), 1), confidence


def _detect_key(audio: np.ndarray) -> tuple[str | None, float]:
    """Detect musical key using KeyExtractor with EDM profile.

    Returns:
        Tuple of (camelot_key, confidence). Key is None if detection fails.
    """
    from essentia.standard import KeyExtractor

    extractor = KeyExtractor(profileType="edma")
    key, scale, strength = extractor(audio)

    camelot = _to_camelot(key, scale)
    if camelot is None:
        logger.warning("Unknown key/scale from Essentia: %s %s", key, scale)
        return None, 0.0

    return camelot, round(float(strength), 3)


def _detect_energy(audio: np.ndarray) -> float | None:
    """Compute normalized energy (0.0-1.0).

    Uses RMS energy normalized against a reference level.
    """
    from essentia.standard import RMS

    rms = RMS()(audio)
    if rms <= 0:
        return None

    # Convert to dB, normalize to 0-1 range
    # Typical audio RMS: -60dB (silence) to 0dB (full scale)
    db = 20 * np.log10(rms + 1e-10)
    # Map -60..0 dB to 0..1
    normalized = float(np.clip((db + 60) / 60, 0.0, 1.0))
    return round(normalized, 3)


def _detect_danceability(audio: np.ndarray) -> float | None:
    """Compute danceability score normalized to 0.0-1.0."""
    from essentia.standard import Danceability

    danceability_raw, _ = Danceability()(audio)

    # Essentia Danceability returns ~0-3, normalize to 0-1
    normalized = float(np.clip(danceability_raw / 3.0, 0.0, 1.0))
    return round(normalized, 3)


def analyze_track(filepath: Path) -> AudioFeatures:
    """Analyze a single audio track for BPM, key, energy, and danceability.

    Args:
        filepath: Path to the audio file.

    Returns:
        AudioFeatures with all detected values. Fields are None if
        the file can't be decoded or analysis fails.
    """
    features = AudioFeatures()

    try:
        audio = _load_audio(filepath)
    except Exception as e:
        logger.warning("Failed to load %s: %s", filepath.name, e)
        return features

    if len(audio) < 44100 * 2:
        logger.warning("Track too short for analysis: %s", filepath.name)
        return features

    try:
        features.bpm, features.bpm_confidence = _detect_bpm(audio)
    except Exception as e:
        logger.warning("BPM detection failed for %s: %s", filepath.name, e)

    try:
        features.key, features.key_confidence = _detect_key(audio)
    except Exception as e:
        logger.warning("Key detection failed for %s: %s", filepath.name, e)

    try:
        features.energy = _detect_energy(audio)
    except Exception as e:
        logger.warning("Energy detection failed for %s: %s", filepath.name, e)

    try:
        features.danceability = _detect_danceability(audio)
    except Exception as e:
        logger.warning("Danceability detection failed for %s: %s", filepath.name, e)

    return features
