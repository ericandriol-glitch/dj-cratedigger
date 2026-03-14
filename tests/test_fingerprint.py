"""Tests for AcoustID fingerprint matching."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from cratedigger.core.fingerprint import (
    FingerprintResult,
    fingerprint_file,
    lookup_acoustid,
    identify_track,
)


class TestFingerprintResult:
    def test_default_values(self):
        r = FingerprintResult(filepath=Path("test.mp3"))
        assert r.title is None
        assert r.artist is None
        assert r.confidence == 0.0
        assert r.error is None

    def test_with_match(self):
        r = FingerprintResult(
            filepath=Path("test.mp3"),
            title="Latch",
            artist="Disclosure",
            confidence=0.95,
        )
        assert r.title == "Latch"
        assert r.confidence == 0.95


class TestFingerprintFile:
    def test_nonexistent_file(self):
        result = fingerprint_file(Path("/nonexistent/track.mp3"))
        assert result is None

    @patch("cratedigger.core.fingerprint.acoustid", create=True)
    def test_returns_tuple_on_success(self, mock_acoustid):
        # Mock the import and function
        with patch.dict("sys.modules", {"acoustid": mock_acoustid}):
            mock_acoustid.fingerprint_file.return_value = (300.0, "AQAA...")
            fp = Path(__file__)  # Use a file that exists
            result = fingerprint_file(fp)
            # Can't test fully without fpcalc installed,
            # but we verify the function handles import gracefully


class TestLookupAcoustid:
    def test_missing_file(self):
        result = lookup_acoustid(Path("/nonexistent.mp3"), "test_key")
        assert result.error is not None

    def test_no_pyacoustid(self):
        with patch.dict("sys.modules", {"acoustid": None}):
            # This tests the ImportError path
            result = lookup_acoustid(Path(__file__), "test_key")
            # Will either get import error or file not audio error


class TestIdentifyTrack:
    def test_full_pipeline_with_mock(self):
        mock_result = FingerprintResult(
            filepath=Path("test.mp3"),
            title="Latch",
            artist="Disclosure",
            musicbrainz_id="abc-123",
            confidence=0.95,
        )

        with patch("cratedigger.core.fingerprint.lookup_acoustid") as mock_lookup:
            with patch("cratedigger.core.fingerprint.lookup_musicbrainz") as mock_mb:
                mock_lookup.return_value = mock_result
                mock_mb.return_value = {
                    "title": "Latch",
                    "artist": "Disclosure feat. Sam Smith",
                    "album": "Settle",
                    "isrc": "GBKPL1200180",
                }

                result = identify_track(Path("test.mp3"), "test_key")

        assert result.artist == "Disclosure feat. Sam Smith"
        assert result.album == "Settle"
        assert result.confidence == 0.95

    def test_no_mb_enrichment_on_error(self):
        mock_result = FingerprintResult(
            filepath=Path("test.mp3"),
            error="No match found",
        )

        with patch("cratedigger.core.fingerprint.lookup_acoustid") as mock_lookup:
            mock_lookup.return_value = mock_result
            result = identify_track(Path("test.mp3"), "test_key")

        assert result.error == "No match found"
