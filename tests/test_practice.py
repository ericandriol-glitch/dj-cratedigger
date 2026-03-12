"""Tests for transition practice prioritiser."""

from cratedigger.gig.practice import (
    Transition,
    prioritise_practice,
    score_transition,
    suggest_approach,
)


def _make_transition(
    bpm_a: float = 126.0, bpm_b: float = 126.0,
    key_a: str = "8A", key_b: str = "8A",
    energy_a: float = 0.7, energy_b: float = 0.7,
) -> Transition:
    return Transition(
        track_a_name="Track A", track_b_name="Track B",
        bpm_a=bpm_a, bpm_b=bpm_b,
        key_a=key_a, key_b=key_b,
        energy_a=energy_a, energy_b=energy_b,
    )


class TestScoreTransition:
    def test_perfect_transition(self):
        t = _make_transition()
        assert score_transition(t) == 0.0

    def test_bpm_gap_medium(self):
        t = _make_transition(bpm_a=120, bpm_b=126)
        score = score_transition(t)
        assert score > 0.0

    def test_bpm_gap_large(self):
        t = _make_transition(bpm_a=120, bpm_b=130)
        score = score_transition(t)
        assert score >= 0.33

    def test_key_clash(self):
        t = _make_transition(key_a="1A", key_b="6A")
        score = score_transition(t)
        assert score > 0.0

    def test_energy_jump(self):
        t = _make_transition(energy_a=0.3, energy_b=0.9)
        score = score_transition(t)
        assert score > 0.0

    def test_all_bad(self):
        t = _make_transition(
            bpm_a=120, bpm_b=135,
            key_a="1A", key_b="6A",
            energy_a=0.2, energy_b=0.9,
        )
        score = score_transition(t)
        assert score == 1.0

    def test_score_range(self):
        t = _make_transition(bpm_a=120, bpm_b=128, key_a="1A", key_b="3B")
        score = score_transition(t)
        assert 0.0 <= score <= 1.0


class TestSuggestApproach:
    def test_perfect_mix(self):
        t = _make_transition()
        assert "no issues" in suggest_approach(t).lower()

    def test_bpm_suggestion(self):
        t = _make_transition(bpm_a=120, bpm_b=130)
        assert "filter" in suggest_approach(t).lower() or "loop" in suggest_approach(t).lower()

    def test_key_clash_suggestion(self):
        t = _make_transition(key_a="1A", key_b="6A")
        assert "bass swap" in suggest_approach(t).lower()

    def test_energy_suggestion(self):
        t = _make_transition(energy_a=0.3, energy_b=0.8)
        assert "breakdown" in suggest_approach(t).lower()


class TestPrioritisePractice:
    def test_sorted_hardest_first(self):
        transitions = [
            _make_transition(),  # easy
            _make_transition(bpm_a=120, bpm_b=135, key_a="1A", key_b="6A"),  # hard
            _make_transition(bpm_a=124, bpm_b=126),  # medium
        ]
        result = prioritise_practice(transitions)
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True)

    def test_returns_all(self):
        transitions = [_make_transition() for _ in range(5)]
        result = prioritise_practice(transitions)
        assert len(result) == 5
