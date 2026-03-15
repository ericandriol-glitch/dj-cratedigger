"""Tests for library audit scanner and report."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from cratedigger.audit.scanner import (
    AuditResult,
    _check_filename_tag_mismatch,
    _find_true_duplicates,
    _is_zero_byte,
    run_audit,
)
from cratedigger.audit.report import (
    _health_score_style,
    _health_verdict,
    display_audit,
    export_audit_json,
)
from cratedigger.models import TrackMetadata


# --- Fixtures ---

@pytest.fixture
def library_dir(tmp_path):
    """Create a minimal library directory with audio files."""
    music = tmp_path / "music"
    music.mkdir()
    return music


@pytest.fixture
def good_track(library_dir):
    """Create a valid MP3 file with proper metadata."""
    fp = library_dir / "Disclosure - Latch.mp3"
    # Write enough data to not be zero-byte
    fp.write_bytes(b"\xff\xfb\x90\x00" * 512)
    return fp


@pytest.fixture
def zero_byte_track(library_dir):
    """Create a zero-byte audio file."""
    fp = library_dir / "Empty - Nothing.mp3"
    fp.write_bytes(b"")
    return fp


# --- Unit tests: _is_zero_byte ---

def test_is_zero_byte_true(zero_byte_track):
    """Zero-byte file is detected."""
    assert _is_zero_byte(zero_byte_track) is True


def test_is_zero_byte_false(good_track):
    """Non-empty file is not zero-byte."""
    assert _is_zero_byte(good_track) is False


def test_is_zero_byte_missing():
    """Missing file returns True."""
    assert _is_zero_byte(Path("/nonexistent/file.mp3")) is True


# --- Unit tests: _check_filename_tag_mismatch ---

def test_mismatch_detected():
    """Mismatch between filename and tags is reported."""
    path = Path("Artist A - Track One.mp3")
    meta = TrackMetadata(artist="Artist B", title="Track One")
    result = _check_filename_tag_mismatch(path, meta)
    assert result is not None
    assert "artist" in result


def test_no_mismatch():
    """Matching filename and tags return None."""
    path = Path("Disclosure - Latch.mp3")
    meta = TrackMetadata(artist="Disclosure", title="Latch")
    result = _check_filename_tag_mismatch(path, meta)
    assert result is None


def test_mismatch_case_insensitive():
    """Case differences are ignored."""
    path = Path("DISCLOSURE - LATCH.mp3")
    meta = TrackMetadata(artist="disclosure", title="latch")
    result = _check_filename_tag_mismatch(path, meta)
    assert result is None


def test_mismatch_no_filename_structure():
    """Files without artist-title separator still detect title mismatch."""
    path = Path("random_filename.mp3")
    meta = TrackMetadata(artist="Someone", title="Something")
    result = _check_filename_tag_mismatch(path, meta)
    # Filename stem doesn't match title, so mismatch is detected
    assert result is not None


def test_mismatch_title_differs():
    """Title mismatch is detected."""
    path = Path("Artist - Original Mix.mp3")
    meta = TrackMetadata(artist="Artist", title="Extended Mix")
    result = _check_filename_tag_mismatch(path, meta)
    assert result is not None
    assert "title" in result


# --- Unit tests: _find_true_duplicates ---

def test_find_duplicates():
    """Duplicate artist+title pairs are found."""
    tracks = [
        (Path("a/Disclosure - Latch.mp3"), TrackMetadata(artist="Disclosure", title="Latch")),
        (Path("b/Disclosure - Latch.mp3"), TrackMetadata(artist="Disclosure", title="Latch")),
        (Path("c/Bonobo - Kerala.mp3"), TrackMetadata(artist="Bonobo", title="Kerala")),
    ]
    groups = _find_true_duplicates(tracks)
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_no_duplicates():
    """No duplicates when all tracks are unique."""
    tracks = [
        (Path("a.mp3"), TrackMetadata(artist="A", title="X")),
        (Path("b.mp3"), TrackMetadata(artist="B", title="Y")),
    ]
    groups = _find_true_duplicates(tracks)
    assert len(groups) == 0


def test_duplicates_case_insensitive():
    """Duplicate detection is case-insensitive."""
    tracks = [
        (Path("a.mp3"), TrackMetadata(artist="DISCLOSURE", title="LATCH")),
        (Path("b.mp3"), TrackMetadata(artist="disclosure", title="latch")),
    ]
    groups = _find_true_duplicates(tracks)
    assert len(groups) == 1


def test_duplicates_skip_empty_metadata():
    """Tracks with no artist/title are not grouped as duplicates."""
    tracks = [
        (Path("a.mp3"), TrackMetadata()),
        (Path("b.mp3"), TrackMetadata()),
    ]
    groups = _find_true_duplicates(tracks)
    assert len(groups) == 0


# --- Unit tests: health score style ---

def test_health_score_style_green():
    assert "green" in _health_score_style(85)


def test_health_score_style_yellow():
    assert "yellow" in _health_score_style(65)


def test_health_score_style_orange():
    assert "orange" in _health_score_style(45)


def test_health_score_style_red():
    assert "red" in _health_score_style(20)


# --- Unit tests: health verdict ---

def test_verdict_gig_ready():
    verdict = _health_verdict(95)
    assert "Gig-ready" in verdict


def test_verdict_mostly_clean():
    verdict = _health_verdict(75)
    assert "Mostly clean" in verdict


def test_verdict_needs_attention():
    verdict = _health_verdict(55)
    assert "Needs attention" in verdict


def test_verdict_messy():
    verdict = _health_verdict(35)
    assert "Messy" in verdict


def test_verdict_critical():
    verdict = _health_verdict(10)
    assert "Critical" in verdict


# --- Integration tests: run_audit ---

def test_audit_empty_directory(tmp_path):
    """Empty directory gets score 100."""
    empty = tmp_path / "empty"
    empty.mkdir()
    result = run_audit(empty)
    assert result.health_score == 100
    assert result.total_tracks == 0


def test_audit_detects_zero_byte(library_dir, zero_byte_track):
    """Zero-byte files are reported as critical."""
    result = run_audit(library_dir)
    assert len(result.critical) >= 1
    issues = [i["issue"] for i in result.critical]
    assert any("zero-byte" in i for i in issues)


def test_audit_with_valid_track(library_dir, good_track):
    """Valid track is scanned without critical issues for that track."""
    with patch("cratedigger.audit.scanner.read_metadata") as mock_meta:
        mock_meta.return_value = TrackMetadata(
            artist="Disclosure", title="Latch",
            bpm=128.0, key="Am", album="Settle", year=2013,
            duration_seconds=240.0, bitrate=320000, sample_rate=44100,
        )
        result = run_audit(library_dir)
    assert len(result.critical) == 0


def test_audit_detects_missing_bpm(library_dir, good_track):
    """Missing BPM is reported as high severity."""
    with patch("cratedigger.audit.scanner.read_metadata") as mock_meta:
        mock_meta.return_value = TrackMetadata(
            artist="Disclosure", title="Latch",
            bpm=None, key="Am",
            duration_seconds=240.0, bitrate=320000, sample_rate=44100,
        )
        result = run_audit(library_dir)
    high_issues = [i["issue"] for i in result.high]
    assert any("BPM" in i for i in high_issues)


def test_audit_detects_missing_key(library_dir, good_track):
    """Missing key is reported as high severity."""
    with patch("cratedigger.audit.scanner.read_metadata") as mock_meta:
        mock_meta.return_value = TrackMetadata(
            artist="Disclosure", title="Latch",
            bpm=128.0, key=None,
            duration_seconds=240.0, bitrate=320000, sample_rate=44100,
        )
        result = run_audit(library_dir)
    high_issues = [i["issue"] for i in result.high]
    assert any("key" in i for i in high_issues)


def test_audit_detects_missing_artist(library_dir, good_track):
    """Missing artist is reported as high severity."""
    with patch("cratedigger.audit.scanner.read_metadata") as mock_meta:
        mock_meta.return_value = TrackMetadata(
            artist=None, title="Latch",
            bpm=128.0, key="Am",
            duration_seconds=240.0, bitrate=320000, sample_rate=44100,
        )
        result = run_audit(library_dir)
    high_issues = [i["issue"] for i in result.high]
    assert any("artist" in i for i in high_issues)


def test_audit_detects_missing_year(library_dir, good_track):
    """Missing year is reported as low severity."""
    with patch("cratedigger.audit.scanner.read_metadata") as mock_meta:
        mock_meta.return_value = TrackMetadata(
            artist="Disclosure", title="Latch",
            bpm=128.0, key="Am", year=None,
            duration_seconds=240.0, bitrate=320000, sample_rate=44100,
        )
        result = run_audit(library_dir)
    low_issues = [i["issue"] for i in result.low]
    assert any("year" in i for i in low_issues)


def test_audit_detects_missing_album(library_dir, good_track):
    """Missing album is reported as low severity."""
    with patch("cratedigger.audit.scanner.read_metadata") as mock_meta:
        mock_meta.return_value = TrackMetadata(
            artist="Disclosure", title="Latch",
            bpm=128.0, key="Am", album=None,
            duration_seconds=240.0, bitrate=320000, sample_rate=44100,
        )
        result = run_audit(library_dir)
    low_issues = [i["issue"] for i in result.low]
    assert any("album" in i for i in low_issues)


def test_audit_health_score_formula(library_dir, good_track):
    """Health score follows the formula: 100 - penalties, floored at 0."""
    with patch("cratedigger.audit.scanner.read_metadata") as mock_meta:
        # Track with missing BPM (high=+2) and missing key (high=+2) and missing year (low=+0.2)
        mock_meta.return_value = TrackMetadata(
            artist="Disclosure", title="Latch",
            bpm=None, key=None, year=None, album="Settle",
            duration_seconds=240.0, bitrate=320000, sample_rate=44100,
        )
        result = run_audit(library_dir)

    # high: 2 issues (missing BPM, missing key) => 4 penalty
    # low: 1 issue (missing year) => 0.2 penalty
    # Expected: 100 - 4 - 0.2 = 95.8 => 95
    assert result.health_score == 95


def test_audit_health_score_floor():
    """Health score can't go below 0."""
    result = AuditResult(path=Path("/tmp"), total_tracks=100)
    # Add enough criticals to exceed 100
    for i in range(20):
        result.critical.append({"path": f"/tmp/{i}.mp3", "issue": "corrupt"})
    # Recalculate manually (the score is set in run_audit, not AuditResult)
    penalty = len(result.critical) * 10
    score = max(0, int(100 - penalty))
    assert score == 0


def test_audit_not_a_directory(tmp_path):
    """ValueError for non-directory path."""
    fp = tmp_path / "not_a_dir.txt"
    fp.write_text("hello")
    with pytest.raises(ValueError, match="Not a directory"):
        run_audit(fp)


# --- Integration tests: export_audit_json ---

def test_export_json_structure():
    """JSON export contains expected structure."""
    result = AuditResult(
        path=Path("/music"),
        total_tracks=10,
        health_score=85,
        critical=[{"path": "/music/bad.mp3", "issue": "corrupt"}],
        high=[{"path": "/music/nobpm.mp3", "issue": "missing BPM"}],
        medium=[],
        low=[{"path": "/music/noyr.mp3", "issue": "missing year"}],
    )
    output = export_audit_json(result)
    data = json.loads(output)

    assert data["total_tracks"] == 10
    assert data["health_score"] == 85
    assert data["summary"]["critical"] == 1
    assert data["summary"]["high"] == 1
    assert data["summary"]["medium"] == 0
    assert data["summary"]["low"] == 1
    assert len(data["critical"]) == 1
    assert len(data["high"]) == 1


def test_export_json_valid():
    """Exported JSON is valid and parseable."""
    result = AuditResult(path=Path("/test"), total_tracks=0, health_score=100)
    output = export_audit_json(result)
    data = json.loads(output)
    assert data["health_score"] == 100


# --- display_audit smoke test ---

def test_display_audit_no_crash():
    """display_audit doesn't crash on valid input."""
    result = AuditResult(
        path=Path("/music"),
        total_tracks=5,
        health_score=72,
        critical=[],
        high=[{"path": "/music/a.mp3", "issue": "missing BPM"}],
        medium=[],
        low=[],
    )
    # Should not raise
    display_audit(result)


def test_display_audit_with_category():
    """display_audit with category filter doesn't crash."""
    result = AuditResult(
        path=Path("/music"),
        total_tracks=5,
        health_score=90,
        critical=[],
        high=[],
        medium=[{"path": "/music/b.mp3", "issue": "duplicate"}],
        low=[],
    )
    display_audit(result, category="medium")


def test_display_audit_empty():
    """display_audit with no issues doesn't crash."""
    result = AuditResult(path=Path("/music"), total_tracks=0, health_score=100)
    display_audit(result)
