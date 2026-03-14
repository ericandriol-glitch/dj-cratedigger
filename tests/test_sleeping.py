"""Tests for 'What Am I Sleeping On?' cross-reference skill."""

from pathlib import Path

from click.testing import CliRunner

from cratedigger.cli import cli
from cratedigger.digger.profile import DJProfile, save_profile
from cratedigger.digger.sleeping import (
    SleepingOnReport,
    _normalize_artist,
    find_sleeping_on,
)
from cratedigger.enrichment.spotify import SpotifyProfile, save_spotify_profile
from cratedigger.enrichment.youtube import YouTubeProfile
from cratedigger.utils.db import get_connection


class TestNormalizeArtist:
    """Test artist name normalization."""

    def test_lowercase(self):
        assert _normalize_artist("Disclosure") == "disclosure"

    def test_strip_the(self):
        assert _normalize_artist("The Black Madonna") == "black madonna"

    def test_strip_punctuation(self):
        assert _normalize_artist("Bicep!") == "bicep"

    def test_collapse_whitespace(self):
        assert _normalize_artist("  Four   Tet  ") == "four tet"

    def test_apostrophe(self):
        assert _normalize_artist("Destiny's Child") == "destinys child"

    def test_ampersand(self):
        # & becomes space after non-alphanumeric removal
        assert _normalize_artist("Simon & Garfunkel") == "simon garfunkel"

    def test_empty_string(self):
        assert _normalize_artist("") == ""


class TestFindSleepingOn:
    """Test cross-reference logic."""

    def _make_dj_profile(self, artists: list[tuple[str, int]]) -> DJProfile:
        return DJProfile(
            top_artists=[{"name": name, "count": count} for name, count in artists],
            total_tracks=sum(c for _, c in artists),
        )

    def _make_spotify(self, top_medium: list[str], saved: list[str]) -> SpotifyProfile:
        return SpotifyProfile(
            top_artists_medium=[{"name": a, "genres": [], "popularity": 50} for a in top_medium],
            saved_tracks=[{"title": "track", "artist": a, "album": "album"} for a in saved],
            synced_at="2025-01-01",
        )

    def test_stream_but_dont_own(self):
        dj = self._make_dj_profile([("Disclosure", 10)])
        spotify = self._make_spotify(["Bonobo", "Disclosure"], [])

        report = find_sleeping_on(dj, spotify_profile=spotify)

        # Bonobo is streamed but not in library
        sleeping = [e["artist"] for e in report.stream_but_dont_own]
        assert "bonobo" in sleeping
        assert "disclosure" not in sleeping

    def test_own_but_dont_stream(self):
        dj = self._make_dj_profile([("Disclosure", 10), ("Four Tet", 5)])
        spotify = self._make_spotify(["Disclosure"], [])

        report = find_sleeping_on(dj, spotify_profile=spotify)

        owned_only = [e["artist"] for e in report.own_but_dont_stream]
        assert "four tet" in owned_only

    def test_underrepresented(self):
        dj = self._make_dj_profile([("Bonobo", 1)])
        # Bonobo in top_medium (2 pts) + saved (1 pt) = 3 mentions, library has 1 track
        spotify = self._make_spotify(["Bonobo"], ["Bonobo"])

        report = find_sleeping_on(dj, spotify_profile=spotify)

        under = [e["artist"] for e in report.underrepresented]
        assert "bonobo" in under

    def test_no_overlap(self):
        dj = self._make_dj_profile([("Disclosure", 10)])
        spotify = self._make_spotify(["Bonobo"], [])

        report = find_sleeping_on(dj, spotify_profile=spotify)

        assert len(report.stream_but_dont_own) == 1
        assert len(report.own_but_dont_stream) == 1
        assert len(report.underrepresented) == 0

    def test_empty_profiles(self):
        dj = DJProfile()
        report = find_sleeping_on(dj)

        assert report.stream_but_dont_own == []
        assert report.own_but_dont_stream == []
        assert report.underrepresented == []

    def test_spotify_only(self):
        dj = self._make_dj_profile([("Disclosure", 10)])
        spotify = self._make_spotify(["Bonobo"], [])

        report = find_sleeping_on(dj, spotify_profile=spotify)
        assert len(report.stream_but_dont_own) >= 1

    def test_youtube_only(self):
        dj = self._make_dj_profile([("Disclosure", 10)])
        youtube = YouTubeProfile(
            liked_songs=[{"title": "Kerala", "artist": "Bonobo", "album": "Migration"}],
            history=[{"title": "Kerala", "artist": "Bonobo"}],
            synced_at="2025-01-01",
        )

        report = find_sleeping_on(dj, youtube_profile=youtube)
        sleeping = [e["artist"] for e in report.stream_but_dont_own]
        assert "bonobo" in sleeping

    def test_both_platforms(self):
        dj = self._make_dj_profile([("Disclosure", 10)])
        spotify = self._make_spotify(["Bicep"], [])
        youtube = YouTubeProfile(
            liked_songs=[{"title": "X", "artist": "Bonobo", "album": "Y"}],
            synced_at="2025-01-01",
        )

        report = find_sleeping_on(dj, spotify_profile=spotify, youtube_profile=youtube)

        sleeping = [e["artist"] for e in report.stream_but_dont_own]
        assert "bicep" in sleeping
        assert "bonobo" in sleeping

    def test_case_insensitive_matching(self):
        """Library has 'disclosure', Spotify has 'Disclosure' — should match."""
        dj = self._make_dj_profile([("disclosure", 10)])
        spotify = self._make_spotify(["Disclosure"], [])

        report = find_sleeping_on(dj, spotify_profile=spotify)

        # Should NOT appear in stream_but_dont_own since they match
        sleeping = [e["artist"] for e in report.stream_but_dont_own]
        assert "disclosure" not in sleeping

    def test_the_prefix_matching(self):
        """'The Black Madonna' in streaming matches 'Black Madonna' in library."""
        dj = self._make_dj_profile([("Black Madonna", 5)])
        spotify = self._make_spotify(["The Black Madonna"], [])

        report = find_sleeping_on(dj, spotify_profile=spotify)

        sleeping = [e["artist"] for e in report.stream_but_dont_own]
        assert "black madonna" not in sleeping


class TestSleepingCLI:
    """Test dig-sleeping CLI command."""

    def test_no_dj_profile(self, tmp_path: Path):
        import cratedigger.utils.db as db_mod

        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = tmp_path / "test.db"
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["dig-sleeping"])
            assert result.exit_code == 0
            assert "No DJ profile found" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_no_streaming_profiles(self, tmp_path: Path):
        import cratedigger.utils.db as db_mod

        db_path = tmp_path / "test.db"
        dj = DJProfile(total_tracks=10, top_artists=[{"name": "Disclosure", "count": 5}])
        save_profile(dj, db_path=db_path)

        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["dig-sleeping"])
            assert result.exit_code == 0
            assert "No streaming profiles found" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_with_profiles(self, tmp_path: Path):
        import cratedigger.utils.db as db_mod

        db_path = tmp_path / "test.db"
        dj = DJProfile(total_tracks=10, top_artists=[{"name": "Disclosure", "count": 5}])
        save_profile(dj, db_path=db_path)

        spotify = SpotifyProfile(
            top_artists_medium=[{"name": "Bonobo", "genres": [], "popularity": 70}],
            synced_at="2025-01-01",
        )
        save_spotify_profile(spotify, db_path=db_path)

        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["dig-sleeping"])
            assert result.exit_code == 0
            assert "Sleeping On" in result.output or "sleeping" in result.output.lower()
        finally:
            db_mod.DEFAULT_DB_PATH = original
