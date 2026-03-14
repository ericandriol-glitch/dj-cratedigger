"""Tests for the player module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cratedigger.player import (
    SUPPORTED_EXTENSIONS,
    format_time,
    is_playable,
    search_library,
)


class TestIsPlayable:
    def test_mp3_supported(self, tmp_path):
        f = tmp_path / "track.mp3"
        assert is_playable(f) is True

    def test_flac_supported(self, tmp_path):
        f = tmp_path / "track.flac"
        assert is_playable(f) is True

    def test_wav_supported(self, tmp_path):
        f = tmp_path / "track.wav"
        assert is_playable(f) is True

    def test_ogg_supported(self, tmp_path):
        f = tmp_path / "track.ogg"
        assert is_playable(f) is True

    def test_m4a_not_supported(self, tmp_path):
        f = tmp_path / "track.m4a"
        assert is_playable(f) is False

    def test_aac_not_supported(self, tmp_path):
        f = tmp_path / "track.aac"
        assert is_playable(f) is False

    def test_case_insensitive(self, tmp_path):
        f = tmp_path / "track.MP3"
        assert is_playable(f) is True

    def test_supported_extensions_set(self):
        assert ".mp3" in SUPPORTED_EXTENSIONS
        assert ".flac" in SUPPORTED_EXTENSIONS
        assert ".wav" in SUPPORTED_EXTENSIONS
        assert ".ogg" in SUPPORTED_EXTENSIONS


class TestFormatTime:
    def test_zero(self):
        assert format_time(0) == "0:00"

    def test_seconds_only(self):
        assert format_time(45) == "0:45"

    def test_minutes_and_seconds(self):
        assert format_time(125) == "2:05"

    def test_exact_minute(self):
        assert format_time(180) == "3:00"

    def test_float_truncates(self):
        assert format_time(61.7) == "1:01"

    def test_long_track(self):
        assert format_time(600) == "10:00"


class TestSearchLibrary:
    def test_finds_matching_files(self, tmp_path):
        (tmp_path / "Bicep - Glue.mp3").touch()
        (tmp_path / "Bicep - Atlas.mp3").touch()
        (tmp_path / "Other - Track.mp3").touch()

        results = search_library("bicep", tmp_path)
        assert len(results) == 2
        names = [r.stem for r in results]
        assert "Bicep - Atlas" in names
        assert "Bicep - Glue" in names

    def test_case_insensitive_search(self, tmp_path):
        (tmp_path / "BICEP - GLUE.mp3").touch()
        results = search_library("bicep", tmp_path)
        assert len(results) == 1

    def test_no_matches(self, tmp_path):
        (tmp_path / "Other - Track.mp3").touch()
        results = search_library("bicep", tmp_path)
        assert len(results) == 0

    def test_searches_subdirectories(self, tmp_path):
        sub = tmp_path / "subfolder"
        sub.mkdir()
        (sub / "Bicep - Glue.mp3").touch()
        results = search_library("bicep", tmp_path)
        assert len(results) == 1

    def test_only_supported_formats(self, tmp_path):
        (tmp_path / "Bicep - Glue.mp3").touch()
        (tmp_path / "Bicep - Glue.m4a").touch()  # Not supported
        (tmp_path / "Bicep - Glue.txt").touch()  # Not audio
        results = search_library("bicep", tmp_path)
        assert len(results) == 1

    def test_results_sorted_by_name(self, tmp_path):
        (tmp_path / "Bicep - Zulu.mp3").touch()
        (tmp_path / "Bicep - Atlas.mp3").touch()
        (tmp_path / "Bicep - Glue.flac").touch()
        results = search_library("bicep", tmp_path)
        names = [r.name for r in results]
        assert names == sorted(names)


class TestSearchLibraryDb:
    @patch("cratedigger.utils.db.get_connection")
    def test_search_returns_results(self, mock_get_conn):
        from cratedigger.player import search_library_db

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("/music/Bicep - Glue.mp3", 128.0, "8B", 0.85, "Tech House"),
        ]
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        results = search_library_db("Bicep")
        assert len(results) == 1
        assert results[0]["bpm"] == 128.0
        assert results[0]["key"] == "8B"

    @patch("cratedigger.utils.db.get_connection")
    def test_search_empty(self, mock_get_conn):
        from cratedigger.player import search_library_db

        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        results = search_library_db("nonexistent")
        assert len(results) == 0


class TestPlayTrack:
    def test_returns_none_for_missing_file(self):
        from cratedigger.player import play_track

        result = play_track(Path("/nonexistent/track.mp3"))
        assert result is None

    def test_returns_none_for_unsupported_format(self, tmp_path):
        from cratedigger.player import play_track

        f = tmp_path / "track.m4a"
        f.touch()
        result = play_track(f)
        assert result is None
