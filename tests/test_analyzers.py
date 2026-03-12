"""Tests for the analyzer modules."""
from pathlib import Path

from cratedigger.analyzers.filename import analyze_filename
from cratedigger.analyzers.tags import analyze_tags
from cratedigger.analyzers.duplicates import find_duplicates
from cratedigger.models import HealthScore, TrackAnalysis, TrackMetadata


# --- Filename analyzer ---

def test_clean_filename():
    score, issues = analyze_filename(Path("Disclosure - Latch.mp3"))
    assert score == HealthScore.CLEAN
    assert len(issues) == 0


def test_messy_filename():
    score, issues = analyze_filename(Path("DJ_Track_(1)_[www.example.com].mp3"))
    assert score in (HealthScore.NEEDS_ATTENTION, HealthScore.MESSY)
    assert len(issues) > 0


def test_no_artist_title_format():
    score, issues = analyze_filename(Path("unknown_track.mp3"))
    assert any("Artist - Title" in i for i in issues)


def test_numbered_prefix():
    score, issues = analyze_filename(Path("01 - Some Track.mp3"))
    assert any("numbered" in i.lower() or "playlist" in i.lower() for i in issues)


# --- Tag analyzer ---

def test_complete_tags():
    meta = TrackMetadata(
        artist="Disclosure", title="Latch", album="Settle",
        genre="House", bpm=122.0, key="Fm", year=2013,
    )
    score, issues = analyze_tags(meta)
    assert score == HealthScore.CLEAN
    assert len(issues) == 0


def test_missing_critical_tags():
    meta = TrackMetadata()  # all None
    score, issues = analyze_tags(meta)
    assert score == HealthScore.MESSY
    assert any("artist" in i.lower() for i in issues)
    assert any("title" in i.lower() for i in issues)


def test_generic_artist():
    meta = TrackMetadata(artist="Unknown Artist", title="Real Title")
    score, issues = analyze_tags(meta)
    assert score == HealthScore.MESSY


# --- Duplicate detector ---

FIXTURES = Path(__file__).parent / "fixtures"


def test_near_duplicates():
    """Two fixture files with same artist+title should be detected as near-dupes."""
    tracks = [
        TrackAnalysis(
            file_path=FIXTURES / "Disclosure - Latch.mp3",
            file_size_mb=0.0, audio_format="MP3",
            metadata=TrackMetadata(artist="Disclosure", title="Latch"),
        ),
        TrackAnalysis(
            file_path=FIXTURES / "Disclosure - Latch (HQ).mp3",
            file_size_mb=0.0, audio_format="MP3",
            metadata=TrackMetadata(artist="Disclosure", title="Latch"),
        ),
    ]
    groups = find_duplicates(tracks)
    # They share same content so will be exact dupes, or near dupes by artist+title
    assert len(groups) >= 1


def test_no_duplicates():
    tracks = [
        TrackAnalysis(
            file_path=FIXTURES / "Disclosure - Latch.mp3",
            file_size_mb=0.0, audio_format="MP3",
            metadata=TrackMetadata(artist="Disclosure", title="Latch"),
        ),
        TrackAnalysis(
            file_path=FIXTURES / "Bonobo - Kerala.wav",
            file_size_mb=0.0, audio_format="WAV",
            metadata=TrackMetadata(artist="Bonobo", title="Kerala"),
        ),
    ]
    groups = find_duplicates(tracks)
    assert len(groups) == 0
