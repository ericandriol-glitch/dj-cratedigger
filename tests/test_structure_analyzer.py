"""Tests for track structure detection."""

import numpy as np
import pytest

from cratedigger.gig.structure_analyzer import (
    TrackStructure,
    _compute_energy_envelope,
    _find_breakdowns,
    _find_drops,
    _smooth,
    _snap_to_downbeat,
)


class TestEnergyEnvelope:
    def test_returns_arrays(self):
        audio = np.random.randn(44100 * 10).astype(np.float32)
        timestamps, energy = _compute_energy_envelope(audio, 44100.0)
        assert len(timestamps) == len(energy)
        assert len(timestamps) > 0

    def test_timestamps_increase(self):
        audio = np.random.randn(44100 * 10).astype(np.float32)
        timestamps, _ = _compute_energy_envelope(audio, 44100.0)
        assert all(timestamps[i] < timestamps[i + 1] for i in range(len(timestamps) - 1))

    def test_energy_non_negative(self):
        audio = np.random.randn(44100 * 10).astype(np.float32)
        _, energy = _compute_energy_envelope(audio, 44100.0)
        assert all(e >= 0 for e in energy)

    def test_loud_section_higher_energy(self):
        # Quiet then loud
        quiet = np.random.randn(44100 * 5).astype(np.float32) * 0.01
        loud = np.random.randn(44100 * 5).astype(np.float32) * 1.0
        audio = np.concatenate([quiet, loud])
        timestamps, energy = _compute_energy_envelope(audio, 44100.0)

        mid_idx = len(energy) // 2
        avg_first = np.mean(energy[:mid_idx])
        avg_second = np.mean(energy[mid_idx:])
        assert avg_second > avg_first


class TestSmooth:
    def test_output_same_length(self):
        values = np.array([1.0, 5.0, 2.0, 8.0, 3.0, 7.0, 4.0])
        result = _smooth(values)
        assert len(result) == len(values)

    def test_reduces_variance(self):
        values = np.array([1.0, 10.0, 1.0, 10.0, 1.0, 10.0, 1.0, 10.0, 1.0, 10.0])
        result = _smooth(values, window=5)
        assert np.std(result) < np.std(values)

    def test_short_array_unchanged(self):
        values = np.array([1.0, 2.0])
        result = _smooth(values, window=7)
        np.testing.assert_array_equal(result, values)


class TestSnapToDownbeat:
    def test_snaps_to_nearest(self):
        beats = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0])
        # Downbeats at 0, 2, 4 (every 4 beats)
        result = _snap_to_downbeat(1.8, beats, bar_size=4)
        assert result == 2.0

    def test_snaps_to_start(self):
        beats = np.array([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5])
        result = _snap_to_downbeat(0.1, beats, bar_size=4)
        assert result == 0.0

    def test_few_beats_returns_position(self):
        beats = np.array([0.0, 0.5])
        result = _snap_to_downbeat(1.0, beats, bar_size=4)
        assert result == 1.0


class TestFindBreakdowns:
    def test_detects_low_energy_section(self):
        # Energy: high, low (long enough), high
        timestamps = np.arange(0, 30, 0.5)
        energy = np.ones(len(timestamps))
        # Drop energy in the middle (10s-20s)
        energy[20:40] = 0.1
        mean_energy = 1.0
        beats = np.arange(0, 30, 0.5)  # 120 BPM

        breakdowns = _find_breakdowns(
            timestamps, energy, mean_energy, beats, bpm=120.0,
            threshold=0.4, min_beats=8,
        )
        assert len(breakdowns) >= 1
        assert 9.0 <= breakdowns[0] <= 11.0

    def test_no_breakdown_if_too_short(self):
        timestamps = np.arange(0, 30, 0.5)
        energy = np.ones(len(timestamps))
        # Very brief dip
        energy[20:22] = 0.1
        mean_energy = 1.0
        beats = np.arange(0, 30, 0.5)

        breakdowns = _find_breakdowns(
            timestamps, energy, mean_energy, beats, bpm=120.0,
            threshold=0.4, min_beats=8,
        )
        assert len(breakdowns) == 0

    def test_no_breakdown_in_constant_energy(self):
        timestamps = np.arange(0, 30, 0.5)
        energy = np.ones(len(timestamps))
        mean_energy = 1.0
        beats = np.arange(0, 30, 0.5)

        breakdowns = _find_breakdowns(
            timestamps, energy, mean_energy, beats, bpm=120.0,
        )
        assert len(breakdowns) == 0


class TestFindDrops:
    def test_finds_drop_after_breakdown(self):
        timestamps = np.arange(0, 30, 0.5)
        energy = np.ones(len(timestamps)) * 0.5
        # High energy after breakdown at t=15
        energy[30:] = 1.0
        mean_energy = 0.75

        drops = _find_drops(timestamps, energy, mean_energy, [10.0], threshold=0.8)
        assert len(drops) == 1
        assert drops[0] >= 10.0

    def test_no_drop_without_breakdown(self):
        timestamps = np.arange(0, 30, 0.5)
        energy = np.ones(len(timestamps))
        mean_energy = 1.0

        drops = _find_drops(timestamps, energy, mean_energy, [], threshold=0.8)
        assert len(drops) == 0


class TestTrackStructure:
    def test_default_values(self):
        s = TrackStructure()
        assert s.intro_end is None
        assert s.first_breakdown is None
        assert s.first_drop is None
        assert s.outro_start is None
        assert s.confidence == 0.0

    def test_confidence_field(self):
        s = TrackStructure(confidence=0.75)
        assert s.confidence == 0.75
