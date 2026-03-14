"""Tests for smart playlist builder."""

from cratedigger.gig.playlist_builder import (
    PlaylistTrack,
    _bpm_range_for_slot,
    build_playlist,
    filter_candidates,
    score_pair,
)


def _make_track(
    filepath: str = "/music/track.mp3",
    name: str = "Track",
    artist: str = "Artist",
    genre: str = "deep house",
    bpm: float = 126.0,
    key: str = "8A",
    energy: float = 0.7,
    danceability: float = 0.6,
) -> PlaylistTrack:
    return PlaylistTrack(
        filepath=filepath, name=name, artist=artist, genre=genre,
        bpm=bpm, key=key, energy=energy, danceability=danceability,
    )


def _make_library(n: int = 20) -> list[PlaylistTrack]:
    """Generate a small fake library with varied BPM/key/energy."""
    keys = ["1A", "2A", "3A", "4A", "5A", "6A", "7A", "8A", "9A", "10A", "11A", "12A",
            "1B", "2B", "3B", "4B", "5B", "6B", "7B", "8B"]
    tracks = []
    for i in range(n):
        tracks.append(_make_track(
            filepath=f"/music/track_{i:03d}.mp3",
            name=f"Track {i}",
            artist=f"Artist {i % 5}",
            genre="deep house" if i % 3 != 0 else "techno",
            bpm=120 + i * 0.5,
            key=keys[i % len(keys)],
            energy=0.4 + (i % 8) * 0.08,
            danceability=0.5 + (i % 6) * 0.05,
        ))
    return tracks


class TestBpmRange:
    def test_warmup_allows_increase(self):
        lo, hi = _bpm_range_for_slot(120, "warmup")
        assert lo == 112
        assert hi == 136

    def test_peak_tight_range(self):
        lo, hi = _bpm_range_for_slot(128, "peak")
        assert lo == 124
        assert hi == 132

    def test_closing_allows_decrease(self):
        lo, hi = _bpm_range_for_slot(130, "closing")
        assert lo == 114
        assert hi == 138


class TestFilterCandidates:
    def test_filters_by_genre(self):
        tracks = _make_library()
        result = filter_candidates(tracks, "deep house", 125, "peak")
        assert all("deep house" in t.genre.lower() for t in result)

    def test_filters_by_bpm(self):
        tracks = _make_library()
        result = filter_candidates(tracks, None, 125, "peak")
        for t in result:
            assert 121 <= t.bpm <= 129

    def test_no_genre_returns_all_bpm_match(self):
        tracks = _make_library()
        result_genre = filter_candidates(tracks, "deep house", 125, "peak")
        result_no_genre = filter_candidates(tracks, None, 125, "peak")
        assert len(result_no_genre) >= len(result_genre)

    def test_empty_when_no_match(self):
        tracks = _make_library()
        result = filter_candidates(tracks, "drum and bass", 125, "peak")
        assert result == []


class TestScorePair:
    def test_same_key_same_bpm_scores_high(self):
        a = _make_track(bpm=126, key="8A", energy=0.7)
        b = _make_track(bpm=126, key="8A", energy=0.7, filepath="/music/b.mp3")
        t = score_pair(a, b, "peak", 0.5)
        assert t.combined_score >= 0.9

    def test_clashing_key_scores_low(self):
        a = _make_track(bpm=126, key="1A", energy=0.7)
        b = _make_track(bpm=126, key="6A", energy=0.7, filepath="/music/b.mp3")
        t = score_pair(a, b, "peak", 0.5)
        assert t.combined_score < 0.7

    def test_large_bpm_jump_scores_low(self):
        a = _make_track(bpm=120, key="8A", energy=0.7)
        b = _make_track(bpm=135, key="8A", energy=0.7, filepath="/music/b.mp3")
        t = score_pair(a, b, "peak", 0.5)
        assert t.bpm_score <= 0.2

    def test_combined_uses_correct_weights(self):
        a = _make_track(bpm=126, key="8A", energy=0.7)
        b = _make_track(bpm=126, key="8A", energy=0.7, filepath="/music/b.mp3")
        t = score_pair(a, b, "peak", 0.5)
        expected = round(t.camelot_score * 0.4 + t.bpm_score * 0.3 + t.energy_score * 0.3, 3)
        assert t.combined_score == expected

    def test_warmup_prefers_energy_increase(self):
        a = _make_track(bpm=126, key="8A", energy=0.4)
        up = _make_track(bpm=126, key="8A", energy=0.5, filepath="/music/up.mp3")
        down = _make_track(bpm=126, key="8A", energy=0.3, filepath="/music/down.mp3")
        t_up = score_pair(a, up, "warmup", 0.5)
        t_down = score_pair(a, down, "warmup", 0.5)
        assert t_up.energy_score >= t_down.energy_score

    def test_closing_prefers_energy_decrease(self):
        a = _make_track(bpm=126, key="8A", energy=0.6)
        up = _make_track(bpm=126, key="8A", energy=0.7, filepath="/music/up.mp3")
        down = _make_track(bpm=126, key="8A", energy=0.5, filepath="/music/down.mp3")
        t_up = score_pair(a, up, "closing", 0.5)
        t_down = score_pair(a, down, "closing", 0.5)
        assert t_down.energy_score >= t_up.energy_score

    def test_notes_flag_key_clash(self):
        a = _make_track(key="1A")
        b = _make_track(key="6A", filepath="/music/b.mp3")
        t = score_pair(a, b, "peak", 0.5)
        assert "key clash" in t.notes

    def test_notes_flag_bpm_jump(self):
        a = _make_track(bpm=120)
        b = _make_track(bpm=130, filepath="/music/b.mp3")
        t = score_pair(a, b, "peak", 0.5)
        assert "BPM jump" in t.notes

    def test_good_transition_note(self):
        a = _make_track(bpm=126, key="8A", energy=0.7)
        b = _make_track(bpm=126, key="9A", energy=0.7, filepath="/music/b.mp3")
        t = score_pair(a, b, "peak", 0.5)
        # Adjacent key, same BPM, same energy — no warnings
        assert "clash" not in t.notes
        assert "jump" not in t.notes


class TestBuildPlaylist:
    def test_returns_tracks_within_duration(self):
        tracks = _make_library(30)
        result = build_playlist(tracks, duration_min=30, slot="peak", start_bpm=125)
        assert result.estimated_duration_min <= 40  # Some overshoot is OK
        assert len(result.tracks) > 0

    def test_transitions_count(self):
        tracks = _make_library(30)
        result = build_playlist(tracks, duration_min=30, slot="peak", start_bpm=125)
        assert len(result.transitions) == len(result.tracks) - 1

    def test_no_duplicate_tracks(self):
        tracks = _make_library(30)
        result = build_playlist(tracks, duration_min=60, slot="peak", start_bpm=125)
        paths = [t.filepath for t in result.tracks]
        assert len(paths) == len(set(paths))

    def test_empty_when_no_candidates(self):
        tracks = _make_library()
        result = build_playlist(tracks, genre="drum and bass", duration_min=60, slot="peak", start_bpm=125)
        assert len(result.tracks) == 0
        assert len(result.transitions) == 0

    def test_genre_filter_applied(self):
        tracks = _make_library()
        result = build_playlist(tracks, genre="techno", duration_min=60, slot="peak", start_bpm=125)
        for t in result.tracks:
            assert "techno" in t.genre.lower()

    def test_respects_start_key(self):
        tracks = _make_library(30)
        result = build_playlist(tracks, duration_min=30, slot="peak", start_bpm=125, start_key="8A")
        if result.tracks:
            # First track should be reasonably compatible with start key
            from cratedigger.harmonic.camelot import compatibility_score
            score = compatibility_score("8A", result.tracks[0].key)
            assert score >= 0.5

    def test_slot_stored_in_result(self):
        tracks = _make_library()
        result = build_playlist(tracks, slot="warmup", start_bpm=125)
        assert result.slot == "warmup"

    def test_single_track_library(self):
        tracks = [_make_track(bpm=126)]
        result = build_playlist(tracks, duration_min=60, slot="peak", start_bpm=126)
        assert len(result.tracks) == 1
        assert len(result.transitions) == 0
