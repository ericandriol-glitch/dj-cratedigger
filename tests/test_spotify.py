"""Tests for Spotify connector."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from cratedigger.cli import cli
from cratedigger.enrichment.spotify import (
    SpotifyProfile,
    load_spotify_profile,
    save_spotify_profile,
    sync_spotify,
)
from cratedigger.utils.db import get_connection


class TestSpotifyProfile:
    """Test SpotifyProfile save/load round-trip."""

    def test_save_and_load(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        profile = SpotifyProfile(
            top_artists_short=[{"name": "Disclosure", "genres": ["house"], "popularity": 75}],
            top_artists_medium=[{"name": "Bonobo", "genres": ["downtempo"], "popularity": 70}],
            top_artists_long=[{"name": "Four Tet", "genres": ["electronic"], "popularity": 65}],
            top_tracks=[{"title": "Latch", "artist": "Disclosure", "album": "Settle"}],
            saved_tracks=[
                {"title": "Kerala", "artist": "Bonobo", "album": "Migration"},
                {"title": "Latch", "artist": "Disclosure", "album": "Settle"},
            ],
            followed_artists=[{"name": "Bicep", "genres": ["electronic"]}],
            synced_at="2025-01-15T12:00:00+00:00",
        )

        save_spotify_profile(profile, db_path=db_path)
        loaded = load_spotify_profile(db_path=db_path)

        assert loaded is not None
        assert len(loaded.top_artists_short) == 1
        assert loaded.top_artists_short[0]["name"] == "Disclosure"
        assert len(loaded.top_artists_medium) == 1
        assert loaded.top_artists_medium[0]["name"] == "Bonobo"
        assert len(loaded.saved_tracks) == 2
        assert loaded.synced_at == "2025-01-15T12:00:00+00:00"
        assert len(loaded.followed_artists) == 1

    def test_load_empty_db(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        get_connection(db_path).close()
        loaded = load_spotify_profile(db_path=db_path)
        assert loaded is None

    def test_save_overwrites(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        p1 = SpotifyProfile(synced_at="old")
        p2 = SpotifyProfile(synced_at="new", saved_tracks=[{"title": "X", "artist": "Y", "album": "Z"}])

        save_spotify_profile(p1, db_path=db_path)
        save_spotify_profile(p2, db_path=db_path)

        loaded = load_spotify_profile(db_path=db_path)
        assert loaded is not None
        assert loaded.synced_at == "new"
        assert len(loaded.saved_tracks) == 1


class TestSyncSpotify:
    """Test sync_spotify with mocked spotipy client."""

    @patch("cratedigger.enrichment.spotify.spotipy.Spotify")
    @patch("cratedigger.enrichment.spotify.SpotifyOAuth")
    def test_sync_pulls_all_data(self, mock_auth_cls, mock_sp_cls):
        mock_sp = MagicMock()
        mock_sp_cls.return_value = mock_sp

        # Top artists returns
        mock_sp.current_user_top_artists.return_value = {
            "items": [{"name": "Disclosure", "genres": ["house"], "popularity": 80}]
        }

        # Top tracks
        mock_sp.current_user_top_tracks.return_value = {
            "items": [{
                "name": "Latch",
                "artists": [{"name": "Disclosure"}],
                "album": {"name": "Settle"},
            }]
        }

        # Saved tracks — return one page then empty
        mock_sp.current_user_saved_tracks.side_effect = [
            {"items": [{"track": {
                "name": "Kerala", "artists": [{"name": "Bonobo"}],
                "album": {"name": "Migration"},
            }}]},
            {"items": []},
        ]

        # Followed artists
        mock_sp.current_user_followed_artists.return_value = {
            "artists": {
                "items": [{"id": "1", "name": "Bicep", "genres": ["electronic"]}],
                "next": None,
            }
        }

        profile = sync_spotify("fake_id", "fake_secret")

        assert len(profile.top_artists_short) == 1
        assert profile.top_artists_short[0]["name"] == "Disclosure"
        # Called 3 times for short/medium/long
        assert mock_sp.current_user_top_artists.call_count == 3
        assert len(profile.top_tracks) == 1
        assert profile.top_tracks[0]["title"] == "Latch"
        assert len(profile.saved_tracks) == 1
        assert len(profile.followed_artists) == 1
        assert profile.synced_at  # non-empty


class TestSpotifyCLI:
    """Test Spotify CLI commands."""

    def test_spotify_show_no_profile(self, tmp_path: Path):
        import cratedigger.utils.db as db_mod

        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = tmp_path / "test.db"
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["spotify", "show"])
            assert result.exit_code == 0
            assert "No Spotify profile found" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_spotify_show_with_profile(self, tmp_path: Path):
        import cratedigger.utils.db as db_mod

        db_path = tmp_path / "test.db"
        profile = SpotifyProfile(
            top_artists_medium=[{"name": "Bonobo", "genres": ["downtempo"], "popularity": 70}],
            saved_tracks=[{"title": "Kerala", "artist": "Bonobo", "album": "Migration"}],
            synced_at="2025-01-15T12:00:00+00:00",
        )
        save_spotify_profile(profile, db_path=db_path)

        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["spotify", "show"])
            assert result.exit_code == 0
            assert "Bonobo" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original
