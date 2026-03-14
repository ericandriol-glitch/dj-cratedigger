"""Smoke tests to verify Essentia installation and algorithm availability."""

import pytest

essentia = pytest.importorskip("essentia", reason="Essentia not installed (requires Linux/WSL)")


def test_essentia_imports():
    """Essentia standard module imports successfully."""
    import essentia.standard  # noqa: F401


def test_rhythm_extractor_available():
    """RhythmExtractor2013 algorithm is available."""
    from essentia.standard import RhythmExtractor2013

    extractor = RhythmExtractor2013(method="multifeature")
    assert extractor is not None


def test_key_extractor_available():
    """KeyExtractor algorithm is available."""
    from essentia.standard import KeyExtractor

    extractor = KeyExtractor()
    assert extractor is not None


def test_energy_algorithm_available():
    """Energy algorithm is available."""
    from essentia.standard import Energy

    algo = Energy()
    assert algo is not None


def test_danceability_algorithm_available():
    """Danceability algorithm is available."""
    from essentia.standard import Danceability

    algo = Danceability()
    assert algo is not None


def test_mono_loader_available():
    """MonoLoader for audio file loading is available."""
    from essentia.standard import MonoLoader

    assert MonoLoader is not None


def test_analyze_sine_wave():
    """Run full analysis pipeline on a generated sine wave to verify integration."""
    import numpy as np
    from essentia.standard import (
        Danceability,
        Energy,
        KeyExtractor,
        RhythmExtractor2013,
    )

    # Generate a 5-second 440Hz sine wave at 44100Hz
    sr = 44100
    duration = 5.0
    t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t).astype(np.float32)

    # BPM — sine wave won't have a real BPM, just verify it runs
    rhythm_extractor = RhythmExtractor2013(method="multifeature")
    bpm, beats, beats_confidence, _, beats_intervals = rhythm_extractor(audio)
    assert isinstance(bpm, float)

    # Key — verify it returns a key and scale
    key_extractor = KeyExtractor()
    key, scale, key_strength = key_extractor(audio)
    assert isinstance(key, str)
    assert scale in ("major", "minor")
    assert 0.0 <= key_strength <= 1.0

    # Energy — verify it returns a float
    energy = Energy()(audio)
    assert isinstance(energy, float)
    assert energy > 0.0

    # Danceability — verify it returns a float
    danceability, _ = Danceability()(audio)
    assert isinstance(danceability, float)
