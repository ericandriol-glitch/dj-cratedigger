"""Tests for YouTube Music connector."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from cratedigger.cli import cli
from cratedigger.enrichment.youtube import (
    YouTubeProfile,
    load_youtube_profile,
    save_youtube_profile,
    sync_youtube,
)
from cratedigger.utils.db import get_connection


class TestYouTubeProfile:
    """Test YouTubeProfile save/load round-trip."""

    def test_save_and_load(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        profile = YouTubeProfile(
            liked_songs=[
                {"title": "Kerala", "artist": "Bonobo", "album": "Migration"},
                {"title": "Latch", "artist": "Disclosure", "album": "Settle"},
            ],
            playlists=[{"name": "DJ Sets", "track_count": 42}],
            history=[{"title": "Do It Again", "artist": "Royksopp"}],
            synced_at="2025-01-15T12:00:00+00:00",
        )

        save_youtube_profile(profile, db_path=db_path)
        loaded = load_youtube_profile(db_path=db_path)

        assert loaded is not None
        assert len(loaded.liked_songs) == 2
        assert loaded.liked_songs[0]["title"] == "Kerala"
        assert len(loaded.playlists) == 1
        assert loaded.playlists[0]["name"] == "DJ Sets"
        assert len(loaded.history) == 1
        assert loaded.synced_at == "2025-01-15T12:00:00+00:00"

    def test_load_empty_db(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        get_connection(db_path).close()
        loaded = load_youtube_profile(db_path=db_path)
        assert loaded is None

    def test_save_overwrites(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        p1 = YouTubeProfile(synced_at="old")
        p2 = YouTubeProfile(synced_at="new", liked_songs=[{"title": "X", "artist": "Y", "album": "Z"}])

        save_youtube_profile(p1, db_path=db_path)
        save_youtube_profile(p2, db_path=db_path)

        loaded = load_youtube_profile(db_path=db_path)
        assert loaded is not None
        assert loaded.synced_at == "new"
        assert len(loaded.liked_songs) == 1


class TestSyncYouTube:
    """Test sync_youtube with mocked YTMusic client."""

    def test_missing_auth_file(self, tmp_path: Path):
        """sync_youtube raises FileNotFoundError for missing auth JSON."""
        import pytest
        with pytest.raises(FileNotFoundError, match="YouTube auth file not found"):
            sync_youtube(str(tmp_path / "nonexistent.json"))

    @patch("cratedigger.enrichment.youtube._yt_get")
    @patch("cratedigger.enrichment.youtube._get_token", return_value="fake-token")
    def test_sync_pulls_all_data(self, mock_token, mock_yt_get, tmp_path: Path):
        auth_file = tmp_path / "oauth.json"
        auth_file.write_text('{"access_token": "fake"}')

        def yt_get_side_effect(token, endpoint, params):
            if endpoint == "videos":
                return {
                    "items": [{
                        "snippet": {
                            "title": "Kerala",
                            "videoOwnerChannelTitle": "Bonobo - Topic",
                        }
                    }],
                }
            if endpoint == "playlists":
                return {
                    "items": [{
                        "snippet": {"title": "House Vibes"},
                        "contentDetails": {"itemCount": 30},
                    }],
                }
            return {"items": []}

        mock_yt_get.side_effect = yt_get_side_effect

        profile = sync_youtube(str(auth_file))

        assert len(profile.liked_songs) == 1
        assert profile.liked_songs[0]["artist"] == "Bonobo"
        assert profile.liked_songs[0]["title"] == "Kerala"
        assert len(profile.playlists) == 1
        assert profile.playlists[0]["name"] == "House Vibes"
        assert profile.synced_at  # non-empty

    @patch("cratedigger.enrichment.youtube._yt_get")
    @patch("cratedigger.enrichment.youtube._get_token", return_value="fake-token")
    def test_sync_handles_api_errors_gracefully(self, mock_token, mock_yt_get, tmp_path: Path):
        auth_file = tmp_path / "oauth.json"
        auth_file.write_text('{"access_token": "fake"}')

        # All API calls raise
        mock_yt_get.side_effect = Exception("API error")

        profile = sync_youtube(str(auth_file))

        assert len(profile.liked_songs) == 0
        assert len(profile.playlists) == 0
        assert len(profile.history) == 0


class TestYouTubeCLI:
    """Test YouTube CLI commands."""

    def test_youtube_show_no_profile(self, tmp_path: Path):
        import cratedigger.utils.db as db_mod

        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = tmp_path / "test.db"
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["youtube", "show"])
            assert result.exit_code == 0
            assert "No YouTube profile found" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original

    def test_youtube_show_with_profile(self, tmp_path: Path):
        import cratedigger.utils.db as db_mod

        db_path = tmp_path / "test.db"
        profile = YouTubeProfile(
            liked_songs=[{"title": "Kerala", "artist": "Bonobo", "album": "Migration"}],
            history=[{"title": "Latch", "artist": "Disclosure"}],
            synced_at="2025-01-15T12:00:00+00:00",
        )
        save_youtube_profile(profile, db_path=db_path)

        original = db_mod.DEFAULT_DB_PATH
        db_mod.DEFAULT_DB_PATH = db_path
        try:
            runner = CliRunner()
            result = runner.invoke(cli, ["youtube", "show"])
            assert result.exit_code == 0
            assert "Bonobo" in result.output
        finally:
            db_mod.DEFAULT_DB_PATH = original
