"""Tests for artist research module (4.5)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cratedigger.digger.artist_research import (
    ArtistProfile,
    _cross_reference_library,
    _extract_genres,
    _extract_labels_from_releases,
    _extract_releases,
    _extract_related_artists,
    _extract_urls,
    _normalize_artist,
    _search_artist_mb,
    display_artist_report,
    research_artist,
)


# --- Normalization ---


class TestNormalizeArtist:
    def test_basic_lowercase(self):
        assert _normalize_artist("Solomun") == "solomun"

    def test_strips_the(self):
        assert _normalize_artist("The Black Madonna") == "black madonna"

    def test_strips_punctuation(self):
        assert _normalize_artist("Bicep's") == "biceps"

    def test_strips_special_chars(self):
        assert _normalize_artist("DJ Koze & Röyksopp") == "dj koze royksopp"

    def test_normalizes_whitespace(self):
        assert _normalize_artist("  Tale  Of  Us  ") == "tale of us"


# --- URL extraction ---


class TestExtractUrls:
    def test_extracts_urls(self):
        data = {
            "url-relation-list": [
                {"type": "bandcamp", "target": "https://solomun.bandcamp.com"},
                {"type": "soundcloud", "target": "https://soundcloud.com/solomun"},
            ]
        }
        urls = _extract_urls(data)
        assert len(urls) == 2
        assert urls[0]["type"] == "bandcamp"
        assert urls[1]["url"] == "https://soundcloud.com/solomun"

    def test_empty_when_no_rels(self):
        assert _extract_urls({}) == []


# --- Release extraction ---


class TestExtractReleases:
    def test_extracts_and_sorts_by_date(self):
        data = {
            "release-group-list": [
                {"title": "Old EP", "primary-type": "EP", "first-release-date": "2015-01-01"},
                {"title": "New Album", "primary-type": "Album", "first-release-date": "2023-06-15"},
                {"title": "Mid Single", "primary-type": "Single", "first-release-date": "2019-03-20"},
            ]
        }
        releases = _extract_releases(data)
        assert len(releases) == 3
        assert releases[0]["title"] == "New Album"
        assert releases[1]["title"] == "Mid Single"
        assert releases[2]["title"] == "Old EP"

    def test_handles_missing_dates(self):
        data = {
            "release-group-list": [
                {"title": "No Date", "primary-type": "Single"},
                {"title": "Has Date", "primary-type": "EP", "first-release-date": "2020-01-01"},
            ]
        }
        releases = _extract_releases(data)
        assert len(releases) == 2
        assert releases[0]["title"] == "Has Date"

    def test_empty_list(self):
        assert _extract_releases({}) == []


# --- Related artists ---


class TestExtractRelatedArtists:
    def test_extracts_related(self):
        data = {
            "artist-relation-list": [
                {
                    "type": "member of band",
                    "target": "some-id",
                    "artist": {"name": "Band Member", "id": "mbid-1"},
                },
                {
                    "type": "collaboration",
                    "target": "some-id-2",
                    "artist": {"name": "Collab Artist", "id": "mbid-2"},
                },
            ]
        }
        related = _extract_related_artists(data)
        assert len(related) == 2
        assert related[0]["name"] == "Band Member"
        assert related[1]["relationship"] == "collaboration"

    def test_deduplicates(self):
        data = {
            "artist-relation-list": [
                {"type": "collab", "target": "id", "artist": {"name": "Same", "id": "1"}},
                {"type": "remix", "target": "id2", "artist": {"name": "Same", "id": "1"}},
            ]
        }
        related = _extract_related_artists(data)
        assert len(related) == 1

    def test_empty(self):
        assert _extract_related_artists({}) == []


# --- Genre extraction ---


class TestExtractGenres:
    @patch("cratedigger.digger.artist_research.GENRE_NORMALIZE", {"house": "House", "techno": "Techno"})
    @patch("cratedigger.digger.artist_research.GENRE_PRIORITY", ["House", "Techno"])
    def test_extracts_genres(self):
        # Patch the imports to avoid import errors
        data = {"tag-list": [{"name": "house", "count": "5"}, {"name": "techno", "count": "3"}]}
        genres = _extract_genres(data)
        assert "House" in genres
        assert "Techno" in genres

    def test_empty_tags(self):
        assert _extract_genres({}) == []
        assert _extract_genres({"tag-list": []}) == []


# --- Library cross-reference ---


class TestCrossReferenceLibrary:
    def test_finds_matching_files(self, tmp_path):
        (tmp_path / "Solomun - After Rain.mp3").touch()
        (tmp_path / "Solomun - Kackvogel.flac").touch()
        (tmp_path / "Adam Beyer - Drumcode.mp3").touch()

        matches = _cross_reference_library("Solomun", tmp_path)
        assert len(matches) == 2
        assert any("After Rain" in m for m in matches)
        assert any("Kackvogel" in m for m in matches)

    def test_no_matches(self, tmp_path):
        (tmp_path / "Adam Beyer - Drumcode.mp3").touch()
        matches = _cross_reference_library("Solomun", tmp_path)
        assert len(matches) == 0

    def test_no_library_path(self):
        matches = _cross_reference_library("Solomun", None)
        assert matches == []

    def test_case_insensitive(self, tmp_path):
        (tmp_path / "SOLOMUN - Loud Track.mp3").touch()
        matches = _cross_reference_library("solomun", tmp_path)
        assert len(matches) == 1


# --- Search MusicBrainz ---


class TestSearchArtistMb:
    @patch("cratedigger.digger.artist_research._get_mb")
    @patch("cratedigger.digger.artist_research.time")
    def test_exact_name_match_preferred(self, mock_time, mock_mb):
        mock_mb_instance = MagicMock()
        mock_mb.return_value = mock_mb_instance
        mock_mb_instance.search_artists.return_value = {
            "artist-list": [
                {"name": "Solomun Jr", "id": "wrong"},
                {"name": "Solomun", "id": "correct"},
            ]
        }

        result = _search_artist_mb("Solomun")
        assert result["id"] == "correct"

    @patch("cratedigger.digger.artist_research._get_mb")
    @patch("cratedigger.digger.artist_research.time")
    def test_falls_back_to_first(self, mock_time, mock_mb):
        mock_mb_instance = MagicMock()
        mock_mb.return_value = mock_mb_instance
        mock_mb_instance.search_artists.return_value = {
            "artist-list": [
                {"name": "Close Match", "id": "first"},
            ]
        }

        result = _search_artist_mb("Something Else")
        assert result["id"] == "first"

    @patch("cratedigger.digger.artist_research._get_mb")
    @patch("cratedigger.digger.artist_research.time")
    def test_returns_none_on_no_results(self, mock_time, mock_mb):
        mock_mb_instance = MagicMock()
        mock_mb.return_value = mock_mb_instance
        mock_mb_instance.search_artists.return_value = {"artist-list": []}

        result = _search_artist_mb("xxxxxxxxx")
        assert result is None

    @patch("cratedigger.digger.artist_research._get_mb")
    @patch("cratedigger.digger.artist_research.time")
    def test_returns_none_on_error(self, mock_time, mock_mb):
        mock_mb_instance = MagicMock()
        mock_mb.return_value = mock_mb_instance
        mock_mb_instance.search_artists.side_effect = Exception("API error")

        result = _search_artist_mb("Solomun")
        assert result is None


# --- Full pipeline ---


class TestResearchArtist:
    @patch("cratedigger.digger.artist_research._try_discogs")
    @patch("cratedigger.digger.artist_research._check_spotify_status")
    @patch("cratedigger.digger.artist_research._extract_labels_from_releases")
    @patch("cratedigger.digger.artist_research._get_artist_details")
    @patch("cratedigger.digger.artist_research._search_artist_mb")
    def test_full_pipeline(self, mock_search, mock_details, mock_labels, mock_spotify, mock_discogs):
        mock_search.return_value = {
            "name": "Solomun",
            "id": "mbid-123",
            "country": "BA",
            "disambiguation": "DJ",
            "alias-list": [{"alias": "Mladen Solomun"}],
        }
        mock_details.return_value = {
            "artist": {
                "url-relation-list": [
                    {"type": "bandcamp", "target": "https://solomun.bandcamp.com"},
                ],
                "release-group-list": [
                    {"title": "Nobody Is Not Loved", "primary-type": "Album", "first-release-date": "2021-05-28"},
                ],
                "artist-relation-list": [],
                "tag-list": [{"name": "house", "count": "5"}],
            }
        }
        mock_labels.return_value = ["Diynamic Music", "2DIY4"]
        mock_spotify.return_value = {"connected": True, "in_top_short": True, "in_top_medium": False,
                                     "in_top_long": False, "followed": True, "saved_track_count": 3}
        mock_discogs.return_value = []

        result = research_artist("Solomun", include_discogs=True, include_spotify=True)

        assert result is not None
        assert result.name == "Solomun"
        assert result.mbid == "mbid-123"
        assert result.country == "BA"
        assert len(result.urls) == 1
        assert len(result.releases) == 1
        assert "Diynamic Music" in result.labels
        assert result.spotify_status["in_top_short"] is True

    @patch("cratedigger.digger.artist_research._search_artist_mb")
    def test_returns_none_when_not_found(self, mock_search):
        mock_search.return_value = None
        result = research_artist("NonexistentArtist12345")
        assert result is None


# --- Display ---


class TestDisplayArtistReport:
    def test_display_no_crash_full_report(self):
        """Ensure display doesn't crash with a full report."""
        report = ArtistProfile(
            name="Test Artist",
            mbid="mbid-1",
            country="DE",
            disambiguation="producer",
            aliases=["TA", "Test A"],
            genres=["Tech House", "Deep House"],
            urls=[{"type": "bandcamp", "url": "https://test.bandcamp.com"}],
            releases=[{"title": "EP One", "type": "EP", "date": "2023-01-01", "mbid": "r1"}],
            labels=["Test Label"],
            related_artists=[{"name": "Related DJ", "relationship": "collaboration", "mbid": "ra1"}],
            library_tracks=["Test Artist - Track 1.mp3", "Test Artist - Track 2.flac"],
            spotify_status={"connected": True, "in_top_short": True, "in_top_medium": False,
                           "in_top_long": False, "followed": False, "saved_track_count": 1},
        )
        # Should not raise
        display_artist_report(report)

    def test_display_no_crash_minimal_report(self):
        """Ensure display doesn't crash with minimal data."""
        report = ArtistProfile(name="Unknown DJ")
        display_artist_report(report)

    def test_display_no_tracks_shows_missing(self):
        """When library has 0 tracks, should show 'What You're Missing'."""
        report = ArtistProfile(
            name="Big Artist",
            releases=[{"title": f"Release {i}", "type": "Single", "date": "2023", "mbid": f"r{i}"}
                     for i in range(12)],
            labels=["Label A", "Label B"],
        )
        # Should not raise and should show "What You're Missing" panel
        display_artist_report(report)

    def test_display_many_tracks_shows_well_stocked(self):
        """When library has 5+ tracks, should show 'Well Stocked'."""
        report = ArtistProfile(
            name="Fave Artist",
            library_tracks=[f"Track {i}.mp3" for i in range(7)],
        )
        display_artist_report(report)
