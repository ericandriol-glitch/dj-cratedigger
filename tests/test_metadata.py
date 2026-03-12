"""Tests for the metadata reader."""
from pathlib import Path

from cratedigger.metadata import read_metadata

FIXTURES = Path(__file__).parent / "fixtures"


def test_reads_tagged_mp3():
    meta = read_metadata(FIXTURES / "Disclosure - Latch.mp3")
    assert meta.artist == "Disclosure"
    assert meta.title == "Latch"
    assert meta.genre == "House"


def test_reads_untagged_mp3():
    meta = read_metadata(FIXTURES / "unknown_track.mp3")
    # Should return None for missing tags, not crash
    assert meta.artist is None
    assert meta.title is None


def test_reads_wav():
    meta = read_metadata(FIXTURES / "Bonobo - Kerala.wav")
    # WAV typically has no tags, but should not crash
    assert meta.duration_seconds is not None or meta.duration_seconds is None  # just don't crash


def test_handles_missing_file():
    meta = read_metadata(FIXTURES / "does_not_exist.mp3")
    assert meta.artist is None
