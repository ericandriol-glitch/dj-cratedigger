"""Tests for gig export to USB."""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cratedigger.gig.crate import CrateTrack, GigCrate, _compute_stats, save_crate
from cratedigger.gig.export import export_crate_to_usb


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test.db"


@pytest.fixture
def sample_tracks(tmp_path):
    """Create sample audio files and return CrateTrack list."""
    tracks = []
    for i in range(3):
        fp = tmp_path / "music" / f"Artist{i} - Track{i}.mp3"
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_bytes(b"\xff\xfb\x90\x00" * 256 * (i + 1))  # fake MP3 data
        tracks.append(CrateTrack(
            filepath=str(fp),
            artist=f"Artist{i}",
            title=f"Track{i}",
            bpm=125.0 + i,
            key_camelot=f"{i + 1}A",
            energy=0.5 + i * 0.15,
            genre="tech house",
            energy_zone="groove",
            has_cues=True,
            duration_seconds=300.0,
        ))
    return tracks


@pytest.fixture
def saved_crate(sample_tracks, tmp_db):
    """Save a test crate to the database."""
    crate = GigCrate(
        name="test-gig",
        tracks=sample_tracks,
        created_at="2026-03-15T00:00:00+00:00",
    )
    _compute_stats(crate)
    save_crate(crate, db_path=tmp_db)
    return crate


def test_export_copies_tracks(saved_crate, tmp_path, tmp_db):
    """Tracks are copied to USB music directory."""
    usb = tmp_path / "usb"
    usb.mkdir()

    result = export_crate_to_usb(
        crate_name="test-gig",
        usb_path=usb,
        generate_xml=False,
        run_preflight_check=False,
        db_path=tmp_db,
    )

    assert result["tracks_copied"] == 3
    assert result["tracks_skipped"] == 0
    assert result["total_bytes"] > 0

    music_dir = usb / "Music" / "test-gig"
    assert music_dir.is_dir()
    assert len(list(music_dir.glob("*.mp3"))) == 3


def test_export_skips_existing(saved_crate, tmp_path, tmp_db):
    """Already-copied tracks are skipped on re-export."""
    usb = tmp_path / "usb"
    usb.mkdir()

    # First export
    export_crate_to_usb(
        crate_name="test-gig",
        usb_path=usb,
        generate_xml=False,
        run_preflight_check=False,
        db_path=tmp_db,
    )

    # Second export should skip all
    result = export_crate_to_usb(
        crate_name="test-gig",
        usb_path=usb,
        generate_xml=False,
        run_preflight_check=False,
        db_path=tmp_db,
    )

    assert result["tracks_copied"] == 0
    assert result["tracks_skipped"] == 3


def test_export_generates_xml(saved_crate, tmp_path, tmp_db):
    """Rekordbox XML is generated on USB."""
    usb = tmp_path / "usb"
    usb.mkdir()

    result = export_crate_to_usb(
        crate_name="test-gig",
        usb_path=usb,
        generate_xml=True,
        run_preflight_check=False,
        db_path=tmp_db,
    )

    assert result["xml_path"] is not None
    assert result["xml_path"].exists()
    assert result["xml_path"].suffix == ".xml"

    # Verify XML content
    content = result["xml_path"].read_text(encoding="utf-8")
    assert "DJ_PLAYLISTS" in content
    assert "test-gig" in content


def test_export_no_xml_flag(saved_crate, tmp_path, tmp_db):
    """No XML generated when flag is off."""
    usb = tmp_path / "usb"
    usb.mkdir()

    result = export_crate_to_usb(
        crate_name="test-gig",
        usb_path=usb,
        generate_xml=False,
        run_preflight_check=False,
        db_path=tmp_db,
    )

    assert result["xml_path"] is None


def test_export_crate_not_found(tmp_path, tmp_db):
    """ValueError raised for non-existent crate."""
    usb = tmp_path / "usb"
    usb.mkdir()

    with pytest.raises(ValueError, match="not found"):
        export_crate_to_usb(
            crate_name="nonexistent",
            usb_path=usb,
            db_path=tmp_db,
        )


def test_export_usb_not_found(tmp_path, tmp_db):
    """FileNotFoundError raised when USB path doesn't exist."""
    with pytest.raises(FileNotFoundError, match="does not exist"):
        export_crate_to_usb(
            crate_name="test-gig",
            usb_path=tmp_path / "nonexistent",
            db_path=tmp_db,
        )


def test_export_empty_crate(tmp_path, tmp_db):
    """Empty crate returns zero stats."""
    crate = GigCrate(name="empty-gig", tracks=[], created_at="2026-03-15T00:00:00")
    save_crate(crate, db_path=tmp_db)

    usb = tmp_path / "usb"
    usb.mkdir()

    result = export_crate_to_usb(
        crate_name="empty-gig",
        usb_path=usb,
        generate_xml=True,
        run_preflight_check=False,
        db_path=tmp_db,
    )

    assert result["tracks_copied"] == 0
    assert result["tracks_skipped"] == 0
    assert result["xml_path"] is None


def test_export_missing_source_file(tmp_path, tmp_db):
    """Missing source files are skipped gracefully."""
    tracks = [CrateTrack(
        filepath=str(tmp_path / "nonexistent.mp3"),
        artist="Ghost", title="Vanished",
        bpm=128.0, key_camelot="5A", energy=0.7,
        genre="techno", energy_zone="build",
        has_cues=False, duration_seconds=200.0,
    )]
    crate = GigCrate(name="ghost-gig", tracks=tracks, created_at="2026-03-15T00:00:00")
    save_crate(crate, db_path=tmp_db)

    usb = tmp_path / "usb"
    usb.mkdir()

    result = export_crate_to_usb(
        crate_name="ghost-gig",
        usb_path=usb,
        generate_xml=False,
        run_preflight_check=False,
        db_path=tmp_db,
    )

    assert result["tracks_copied"] == 0
    assert result["tracks_skipped"] == 1


def test_export_result_keys(saved_crate, tmp_path, tmp_db):
    """Result dict contains all expected keys."""
    usb = tmp_path / "usb"
    usb.mkdir()

    result = export_crate_to_usb(
        crate_name="test-gig",
        usb_path=usb,
        generate_xml=False,
        run_preflight_check=False,
        db_path=tmp_db,
    )

    expected_keys = {"tracks_copied", "tracks_skipped", "total_bytes",
                     "xml_path", "preflight_report"}
    assert set(result.keys()) == expected_keys
