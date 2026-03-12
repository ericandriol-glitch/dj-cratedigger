"""Tests for Camelot wheel compatibility engine."""

import pytest

from cratedigger.harmonic.camelot import (
    camelot_distance,
    compatibility_score,
    compatible_keys,
    parse_camelot,
)


class TestParseCamelot:
    def test_simple(self):
        assert parse_camelot("8A") == (8, "A")

    def test_double_digit(self):
        assert parse_camelot("11B") == (11, "B")

    def test_with_whitespace(self):
        assert parse_camelot(" 5A ") == (5, "A")

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_camelot("13A")

    def test_invalid_letter_raises(self):
        with pytest.raises(ValueError):
            parse_camelot("8C")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_camelot("")


class TestCamelotDistance:
    def test_same_key(self):
        assert camelot_distance("8A", "8A") == 0

    def test_adjacent(self):
        assert camelot_distance("8A", "9A") == 1

    def test_wrap_around(self):
        assert camelot_distance("1A", "12A") == 1

    def test_opposite(self):
        assert camelot_distance("1A", "7A") == 6

    def test_cross_inner_outer(self):
        # Distance is based on number only
        assert camelot_distance("8A", "8B") == 0


class TestCompatibilityScore:
    def test_same_key(self):
        assert compatibility_score("8A", "8A") == 1.0

    def test_adjacent_same_letter(self):
        assert compatibility_score("8A", "9A") == 0.95
        assert compatibility_score("8A", "7A") == 0.95

    def test_inner_outer_swap(self):
        assert compatibility_score("8A", "8B") == 0.9

    def test_wrap_around_adjacent(self):
        assert compatibility_score("12B", "1B") == 0.95

    def test_energy_boost(self):
        # +7 on wheel
        assert compatibility_score("1A", "8A") == 0.8
        assert compatibility_score("5B", "12B") == 0.8

    def test_two_steps(self):
        assert compatibility_score("8A", "10A") == 0.5

    def test_incompatible(self):
        assert compatibility_score("1A", "6A") == 0.2

    def test_symmetric(self):
        assert compatibility_score("3A", "8B") == compatibility_score("8B", "3A")

    def test_all_scores_in_range(self):
        from cratedigger.harmonic.camelot import VALID_KEYS
        for a in VALID_KEYS:
            for b in VALID_KEYS:
                score = compatibility_score(a, b)
                assert 0.0 <= score <= 1.0, f"{a} -> {b} = {score}"


class TestCompatibleKeys:
    def test_returns_list(self):
        result = compatible_keys("8A")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_excludes_self(self):
        result = compatible_keys("8A")
        assert "8A" not in result

    def test_includes_adjacent(self):
        result = compatible_keys("8A", min_score=0.9)
        assert "7A" in result
        assert "9A" in result
        assert "8B" in result

    def test_min_score_filter(self):
        result_high = compatible_keys("8A", min_score=0.9)
        result_low = compatible_keys("8A", min_score=0.5)
        assert len(result_low) >= len(result_high)

    def test_sorted_by_score_descending(self):
        result = compatible_keys("8A", min_score=0.5)
        scores = [compatibility_score("8A", k) for k in result]
        assert scores == sorted(scores, reverse=True)
