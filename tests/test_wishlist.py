"""Tests for the wishlist system — persistent track wishlist for DJ discovery."""

import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from cratedigger.discovery.wishlist import (
    VALID_PRIORITIES,
    VALID_STATUSES,
    WishlistTrack,
    _ensure_table,
    add_track,
    check_library_overlap,
    get_stats,
    get_wishlist,
    remove_track,
    update_priority,
    update_status,
)


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path for testing."""
    return tmp_path / "test.db"


@pytest.fixture
def populated_db(db_path):
    """Create a wishlist with several tracks for query testing."""
    add_track("Solomun", "After Rain", source="dig-label",
              priority="high", style_tag="melodic techno", db_path=db_path)
    add_track("Innellea", "Vigilance", source="dig-weekly",
              priority="high", style_tag="techno", db_path=db_path)
    add_track("Peggy Gou", "Starry Night", source="manual",
              priority="medium", style_tag="deep house", db_path=db_path)
    add_track("Fisher", "Losing It", source="dig-artist",
              priority="medium", style_tag="tech house", db_path=db_path)
    add_track("Boris Brejcha", "Gravity", source="dig-weekly",
              priority="low", style_tag="minimal techno", db_path=db_path)
    return db_path


# --- TestWishlistAdd ---

class TestWishlistAdd:
    """Tests for adding tracks to the wishlist."""

    def test_add_basic_track(self, db_path):
        track = add_track("Solomun", "After Rain", db_path=db_path)
        assert isinstance(track, WishlistTrack)
        assert track.id is not None
        assert track.artist == "Solomun"
        assert track.title == "After Rain"
        assert track.source == "manual"
        assert track.priority == "medium"
        assert track.status == "new"

    def test_add_with_all_fields(self, db_path):
        track = add_track(
            "Innellea", "Vigilance",
            source="dig-weekly",
            priority="high",
            style_tag="techno",
            preview_url="https://example.com/preview",
            notes="Amazing breakdown",
            db_path=db_path,
        )
        assert track.priority == "high"
        assert track.style_tag == "techno"
        assert track.preview_url == "https://example.com/preview"
        assert track.notes == "Amazing breakdown"
        assert track.source == "dig-weekly"

    def test_deduplication_updates_existing(self, db_path):
        """Adding same artist+title again should update, not duplicate."""
        track1 = add_track("Solomun", "After Rain", source="manual",
                           priority="medium", db_path=db_path)
        track2 = add_track("Solomun", "After Rain", source="dig-label",
                           priority="high", db_path=db_path)

        # Should be same row
        assert track2.id == track1.id
        # Source should be merged
        assert "manual" in track2.source
        assert "dig-label" in track2.source
        # Priority should be updated
        assert track2.priority == "high"

        # Should only be one track total
        tracks = get_wishlist(db_path=db_path)
        assert len(tracks) == 1

    def test_deduplication_same_source_no_duplicate(self, db_path):
        """Re-adding with same source should not duplicate the source string."""
        add_track("Solomun", "After Rain", source="manual", db_path=db_path)
        track = add_track("Solomun", "After Rain", source="manual", db_path=db_path)
        assert track.source == "manual"

    def test_add_invalid_priority_raises(self, db_path):
        with pytest.raises(ValueError, match="Invalid priority"):
            add_track("Test", "Track", priority="urgent", db_path=db_path)

    def test_add_sets_date(self, db_path):
        track = add_track("Test", "Track", db_path=db_path)
        assert track.date_added is not None
        assert len(track.date_added) > 10  # ISO format


# --- TestWishlistQuery ---

class TestWishlistQuery:
    """Tests for querying and filtering the wishlist."""

    def test_get_all(self, populated_db):
        tracks = get_wishlist(db_path=populated_db)
        assert len(tracks) == 5

    def test_filter_by_style(self, populated_db):
        tracks = get_wishlist(style="techno", db_path=populated_db)
        # Should match "melodic techno", "techno", "minimal techno", "tech house"
        # (substring match on "techno")
        artists = {t.artist for t in tracks}
        assert "Solomun" in artists
        assert "Innellea" in artists
        assert "Boris Brejcha" in artists

    def test_filter_by_source(self, populated_db):
        tracks = get_wishlist(source="dig-weekly", db_path=populated_db)
        assert len(tracks) == 2
        artists = {t.artist for t in tracks}
        assert "Innellea" in artists
        assert "Boris Brejcha" in artists

    def test_filter_by_status(self, populated_db):
        tracks = get_wishlist(status="new", db_path=populated_db)
        assert len(tracks) == 5

    def test_sort_by_priority(self, populated_db):
        tracks = get_wishlist(sort="priority", db_path=populated_db)
        priorities = [t.priority for t in tracks]
        # High should come first, then medium, then low
        high_indices = [i for i, p in enumerate(priorities) if p == "high"]
        med_indices = [i for i, p in enumerate(priorities) if p == "medium"]
        low_indices = [i for i, p in enumerate(priorities) if p == "low"]
        assert max(high_indices) < min(med_indices)
        assert max(med_indices) < min(low_indices)

    def test_sort_by_artist(self, populated_db):
        tracks = get_wishlist(sort="artist", db_path=populated_db)
        artists = [t.artist for t in tracks]
        assert artists == sorted(artists)

    def test_empty_wishlist(self, db_path):
        tracks = get_wishlist(db_path=db_path)
        assert tracks == []


# --- TestWishlistUpdate ---

class TestWishlistUpdate:
    """Tests for updating and removing wishlist tracks."""

    def test_update_status(self, db_path):
        track = add_track("Test", "Track", db_path=db_path)
        result = update_status(track.id, "previewed", db_path=db_path)
        assert result is True
        tracks = get_wishlist(db_path=db_path)
        assert tracks[0].status == "previewed"

    def test_update_status_invalid(self, db_path):
        track = add_track("Test", "Track", db_path=db_path)
        with pytest.raises(ValueError, match="Invalid status"):
            update_status(track.id, "bought", db_path=db_path)

    def test_update_status_nonexistent(self, db_path):
        # Ensure table exists
        add_track("Test", "Track", db_path=db_path)
        result = update_status(9999, "previewed", db_path=db_path)
        assert result is False

    def test_update_priority(self, db_path):
        track = add_track("Test", "Track", priority="low", db_path=db_path)
        result = update_priority(track.id, "high", db_path=db_path)
        assert result is True
        tracks = get_wishlist(db_path=db_path)
        assert tracks[0].priority == "high"

    def test_update_priority_invalid(self, db_path):
        track = add_track("Test", "Track", db_path=db_path)
        with pytest.raises(ValueError, match="Invalid priority"):
            update_priority(track.id, "critical", db_path=db_path)

    def test_remove_track(self, db_path):
        track = add_track("Test", "Track", db_path=db_path)
        result = remove_track(track.id, db_path=db_path)
        assert result is True
        tracks = get_wishlist(db_path=db_path)
        assert len(tracks) == 0

    def test_remove_nonexistent(self, db_path):
        # Ensure table exists
        add_track("Test", "Track", db_path=db_path)
        result = remove_track(9999, db_path=db_path)
        assert result is False


# --- TestWishlistOverlap ---

class TestWishlistOverlap:
    """Tests for cross-referencing wishlist against the audio library."""

    def _insert_library_track(self, db_path: Path, filepath: str) -> None:
        """Insert a fake track into audio_analysis for overlap testing."""
        from cratedigger.utils.db import get_connection
        conn = get_connection(db_path)
        conn.execute(
            """INSERT OR IGNORE INTO audio_analysis
               (filepath, bpm, key_camelot, analyzed_at, analyzer_version)
               VALUES (?, 128.0, '8A', '2026-01-01', 'test')""",
            (filepath,),
        )
        conn.commit()

    def test_overlap_exact_match(self, db_path):
        add_track("Solomun", "After Rain", db_path=db_path)
        self._insert_library_track(db_path, "/music/Solomun - After Rain.mp3")
        matched = check_library_overlap(db_path=db_path)
        assert len(matched) == 1
        assert matched[0].artist == "Solomun"
        assert matched[0].status == "in-library"

    def test_overlap_no_match(self, db_path):
        add_track("Solomun", "After Rain", db_path=db_path)
        self._insert_library_track(db_path, "/music/Fisher - Losing It.mp3")
        matched = check_library_overlap(db_path=db_path)
        assert len(matched) == 0

    def test_overlap_updates_status(self, db_path):
        add_track("Solomun", "After Rain", db_path=db_path)
        self._insert_library_track(db_path, "/music/Solomun - After Rain.mp3")
        check_library_overlap(db_path=db_path)
        tracks = get_wishlist(db_path=db_path)
        assert tracks[0].status == "in-library"

    def test_overlap_skips_already_in_library(self, db_path):
        track = add_track("Solomun", "After Rain", db_path=db_path)
        update_status(track.id, "in-library", db_path=db_path)
        self._insert_library_track(db_path, "/music/Solomun - After Rain.mp3")
        matched = check_library_overlap(db_path=db_path)
        assert len(matched) == 0  # Already marked, should skip


# --- TestWishlistStats ---

class TestWishlistStats:
    """Tests for wishlist statistics."""

    def test_stats_empty(self, db_path):
        stats = get_stats(db_path=db_path)
        assert stats["total"] == 0
        assert stats["by_priority"] == {}
        assert stats["by_status"] == {}
        assert stats["by_source"] == {}

    def test_stats_populated(self, populated_db):
        stats = get_stats(db_path=populated_db)
        assert stats["total"] == 5
        assert stats["by_priority"]["high"] == 2
        assert stats["by_priority"]["medium"] == 2
        assert stats["by_priority"]["low"] == 1
        assert stats["by_status"]["new"] == 5

    def test_stats_by_source(self, populated_db):
        stats = get_stats(db_path=populated_db)
        assert stats["by_source"]["dig-weekly"] == 2
        assert stats["by_source"]["dig-label"] == 1
        assert stats["by_source"]["manual"] == 1
        assert stats["by_source"]["dig-artist"] == 1


# --- TestWishlistCLI ---

class TestWishlistCLI:
    """Tests for the CLI interface."""

    def test_cli_show_empty(self, db_path, monkeypatch):
        from cratedigger.cli import cli
        monkeypatch.setenv("CRATEDIGGER_DB", str(db_path))
        runner = CliRunner()
        # We can't easily inject db_path into the CLI, so we test the Click
        # command structure is valid.
        result = runner.invoke(cli, ["wishlist", "show"])
        assert result.exit_code == 0

    def test_cli_add_missing_fields(self):
        from cratedigger.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["wishlist", "add"])
        assert result.exit_code != 0

    def test_cli_add_and_show(self, db_path, monkeypatch):
        from cratedigger.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, [
            "wishlist", "add",
            "--artist", "Solomun",
            "--title", "After Rain",
            "--priority", "high",
        ])
        assert result.exit_code == 0
        assert "Added" in result.output

    def test_cli_remove_no_id(self):
        from cratedigger.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["wishlist", "remove"])
        assert result.exit_code != 0

    def test_cli_find(self):
        from cratedigger.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["wishlist", "find"])
        assert result.exit_code == 0

    def test_cli_clear(self):
        from cratedigger.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["wishlist", "clear"])
        assert result.exit_code == 0

    def test_cli_invalid_action(self):
        from cratedigger.cli import cli
        runner = CliRunner()
        result = runner.invoke(cli, ["wishlist", "destroy"])
        assert result.exit_code != 0
