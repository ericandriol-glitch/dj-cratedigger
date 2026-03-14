"""Tests for download folder watcher."""

from pathlib import Path
from unittest.mock import patch

from cratedigger.core.watcher import (
    WatcherConfig,
    _build_filename,
    _is_audio_file,
    process_file,
)


class TestIsAudioFile:
    def test_mp3(self):
        assert _is_audio_file(Path("track.mp3"))

    def test_flac(self):
        assert _is_audio_file(Path("track.flac"))

    def test_wav(self):
        assert _is_audio_file(Path("track.wav"))

    def test_m4a(self):
        assert _is_audio_file(Path("track.m4a"))

    def test_not_audio(self):
        assert not _is_audio_file(Path("readme.txt"))
        assert not _is_audio_file(Path("image.jpg"))

    def test_case_insensitive(self):
        assert _is_audio_file(Path("track.MP3"))
        assert _is_audio_file(Path("track.Flac"))


class TestBuildFilename:
    def test_standard_convention(self):
        tags = {"artist": "Disclosure", "title": "Latch"}
        result = _build_filename(tags, "{artist} - {title}", ".mp3")
        assert result == "Disclosure - Latch.mp3"

    def test_missing_artist_returns_none(self):
        tags = {"artist": None, "title": "Latch"}
        result = _build_filename(tags, "{artist} - {title}", ".mp3")
        assert result is None

    def test_missing_title_returns_none(self):
        tags = {"artist": "Disclosure", "title": None}
        result = _build_filename(tags, "{artist} - {title}", ".mp3")
        assert result is None

    def test_sanitizes_special_chars(self):
        tags = {"artist": "Artist/Name", "title": "Track: Test?"}
        result = _build_filename(tags, "{artist} - {title}", ".mp3")
        assert "/" not in result
        assert ":" not in result
        assert "?" not in result

    def test_preserves_extension(self):
        tags = {"artist": "A", "title": "B"}
        assert _build_filename(tags, "{artist} - {title}", ".flac").endswith(".flac")


class TestProcessFile:
    def test_nonexistent_file(self, tmp_path):
        config = WatcherConfig(
            watch_dir=tmp_path,
            target_dir=tmp_path / "target",
            auto_analyze=False,
        )
        result = process_file(tmp_path / "missing.mp3", config)
        assert result.error == "File not found"

    def test_moves_file_to_unsorted(self, tmp_path):
        # Create a dummy audio file (no tags)
        src = tmp_path / "watch" / "track.mp3"
        src.parent.mkdir()
        src.write_bytes(b"\x00" * 100)

        target = tmp_path / "target"
        config = WatcherConfig(
            watch_dir=src.parent,
            target_dir=target,
            auto_analyze=False,
        )

        result = process_file(src, config)
        assert result.error is None
        assert result.final_path is not None
        assert result.final_path.exists()
        assert "Unsorted" in str(result.final_path)
        assert not src.exists()  # Original moved

    def test_avoids_overwrite(self, tmp_path):
        src_dir = tmp_path / "watch"
        src_dir.mkdir()
        target = tmp_path / "target"
        unsorted = target / "Unsorted"
        unsorted.mkdir(parents=True)

        # Create existing file at target
        existing = unsorted / "track.mp3"
        existing.write_bytes(b"\x00" * 50)

        # New file with same name
        src = src_dir / "track.mp3"
        src.write_bytes(b"\x00" * 100)

        config = WatcherConfig(
            watch_dir=src_dir,
            target_dir=target,
            auto_analyze=False,
        )

        result = process_file(src, config)
        assert result.final_path is not None
        assert result.final_path != existing
        assert result.final_path.exists()
        assert existing.exists()  # Original not overwritten

    def test_creates_genre_subfolder(self, tmp_path):
        src = tmp_path / "watch" / "track.mp3"
        src.parent.mkdir()
        src.write_bytes(b"\x00" * 100)

        target = tmp_path / "target"
        config = WatcherConfig(
            watch_dir=src.parent,
            target_dir=target,
            auto_analyze=False,
        )

        # Mock tags with genre
        with patch("cratedigger.core.watcher._read_tags") as mock_tags:
            mock_tags.return_value = {
                "artist": "Disclosure",
                "title": "Latch",
                "genre": "Deep House",
            }
            result = process_file(src, config)

        assert result.final_path is not None
        assert "Deep House" in str(result.final_path)
