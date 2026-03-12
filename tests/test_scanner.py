"""Tests for the scanner module."""
from pathlib import Path

from cratedigger.scanner import find_audio_files

FIXTURES = Path(__file__).parent / "fixtures"


def test_finds_audio_files():
    files = find_audio_files(FIXTURES)
    assert len(files) >= 4
    extensions = {f.suffix.lower() for f in files}
    assert ".mp3" in extensions


def test_returns_path_objects():
    files = find_audio_files(FIXTURES)
    for f in files:
        assert isinstance(f, Path)
        assert f.is_file()


def test_skips_non_audio():
    # Create a non-audio file in fixtures temporarily
    txt = FIXTURES / "notes.txt"
    txt.write_text("not audio")
    try:
        files = find_audio_files(FIXTURES)
        assert txt not in files
    finally:
        txt.unlink()
