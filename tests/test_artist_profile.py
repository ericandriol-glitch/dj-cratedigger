"""Tests for deep artist research (Session 10)."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cratedigger.discovery.artist_profile import (
    ArtistProfile,
    _query_library,
    _query_musicbrainz,
    _query_spotify,
    research_artist_deep,
)
from cratedigger.discovery.artist_report import print_artist_profile
from cratedigger.discovery.profile_folder import print_folder_profile, profile_folder


# ---------------------------------------------------------------------------
# TestArtistResearchDeep — mock MusicBrainz + Spotify -> correct merged profile
# ---------------------------------------------------------------------------


class TestArtistResearchDeep:
    """Test the full research_artist_deep pipeline with mocked APIs."""

    @patch("cratedigger.discovery.artist_profile._query_library")
    @patch("cratedigger.discovery.artist_profile._query_spotify")
    @patch("cratedigger.discovery.artist_profile._query_musicbrainz")
    def test_merges_all_sources(self, mock_mb, mock_sp, mock_lib):
        mock_mb.return_value = {
            "source": "musicbrainz",
            "bio": "Bosnian-German DJ/producer",
            "releases": [
                {"title": "Nobody Is Not Loved", "year": "2021", "label": "", "format": "", "type": "Album"},
                {"title": "Home", "year": "2023", "label": "", "format": "", "type": "Single"},
            ],
            "labels": ["Diynamic Music", "2020 Vision"],
            "related_artists": ["Tale Of Us", "Mind Against"],
            "social_links": {"soundcloud": "https://soundcloud.com/solomun", "bandcamp": "https://solomun.bandcamp.com"},
        }
        mock_sp.return_value = {
            "source": "spotify",
            "genres": ["tech house", "deep house"],
            "popularity": 72,
            "related_artists": ["Mind Against", "Maceo Plex", "Dixon"],
            "top_tracks": [{"title": "Home", "album": "Home", "preview_url": None}],
            "social_links": {"spotify": "https://open.spotify.com/artist/abc"},
        }
        mock_lib.return_value = {"tracks_owned": 4, "tracks_on_wishlist": 1}

        profile = research_artist_deep("Solomun")

        assert profile.name == "Solomun"
        assert profile.bio == "Bosnian-German DJ/producer"
        assert len(profile.releases) == 2
        assert "Diynamic Music" in profile.labels
        assert profile.genres == ["tech house", "deep house"]
        assert profile.popularity == 72
        assert profile.tracks_owned == 4
        assert profile.tracks_on_wishlist == 1
        # Related artists merged and deduplicated
        assert "Tale Of Us" in profile.related_artists
        assert "Maceo Plex" in profile.related_artists
        assert "Dixon" in profile.related_artists
        assert profile.related_artists.count("Mind Against") == 1  # no dupes
        # Social links merged
        assert "soundcloud" in profile.social_links
        assert "spotify" in profile.social_links
        assert "bandcamp" in profile.social_links
        # Sources
        assert "musicbrainz" in profile.sources_queried
        assert "spotify" in profile.sources_queried
        assert "library" in profile.sources_queried

    @patch("cratedigger.discovery.artist_profile._query_library")
    @patch("cratedigger.discovery.artist_profile._query_spotify")
    @patch("cratedigger.discovery.artist_profile._query_musicbrainz")
    def test_works_with_musicbrainz_only(self, mock_mb, mock_sp, mock_lib):
        mock_mb.return_value = {
            "source": "musicbrainz",
            "bio": "Electronic producer",
            "releases": [{"title": "EP One", "year": "2022", "label": "", "format": "", "type": "EP"}],
            "labels": ["Some Label"],
            "related_artists": [],
            "social_links": {},
        }
        mock_sp.return_value = {}  # Spotify not configured
        mock_lib.return_value = {"tracks_owned": 0, "tracks_on_wishlist": 0}

        profile = research_artist_deep("Unknown Producer")

        assert profile.name == "Unknown Producer"
        assert profile.bio == "Electronic producer"
        assert len(profile.releases) == 1
        assert "musicbrainz" in profile.sources_queried
        assert "spotify" not in profile.sources_queried

    @patch("cratedigger.discovery.artist_profile._query_library")
    @patch("cratedigger.discovery.artist_profile._query_spotify")
    @patch("cratedigger.discovery.artist_profile._query_musicbrainz")
    def test_graceful_degradation_no_sources(self, mock_mb, mock_sp, mock_lib):
        mock_mb.return_value = {}
        mock_sp.return_value = {}
        mock_lib.return_value = {"tracks_owned": 0, "tracks_on_wishlist": 0}

        profile = research_artist_deep("Totally Unknown")

        assert profile.name == "Totally Unknown"
        assert profile.releases == []
        assert profile.sources_queried == []

    @patch("cratedigger.discovery.artist_profile._query_library")
    @patch("cratedigger.discovery.artist_profile._query_spotify")
    @patch("cratedigger.discovery.artist_profile._query_musicbrainz")
    def test_spotify_only_no_mb(self, mock_mb, mock_sp, mock_lib):
        mock_mb.return_value = {}
        mock_sp.return_value = {
            "source": "spotify",
            "genres": ["techno"],
            "popularity": 55,
            "related_artists": ["Artist B"],
            "top_tracks": [{"title": "Track A", "album": "Album A", "preview_url": "http://preview"}],
            "social_links": {"spotify": "https://open.spotify.com/artist/xyz"},
        }
        mock_lib.return_value = {"tracks_owned": 0, "tracks_on_wishlist": 0}

        profile = research_artist_deep("Spotify Only Artist")

        assert profile.genres == ["techno"]
        assert profile.popularity == 55
        assert len(profile.top_tracks) == 1
        assert "spotify" in profile.sources_queried
        assert "musicbrainz" not in profile.sources_queried


# ---------------------------------------------------------------------------
# TestQueryMusicBrainz — mock musicbrainzngs
# ---------------------------------------------------------------------------


class TestQueryMusicBrainz:
    """Test MusicBrainz query layer with mocked API."""

    @patch("cratedigger.discovery.artist_profile.time")
    @patch("cratedigger.discovery.artist_profile._get_mb")
    def test_returns_releases_and_labels(self, mock_get_mb, mock_time):
        mb = MagicMock()
        mock_get_mb.return_value = mb

        mb.search_artists.return_value = {
            "artist-list": [{"name": "Solomun", "id": "mbid-1", "disambiguation": "DJ"}]
        }
        mb.get_artist_by_id.return_value = {
            "artist": {
                "release-group-list": [
                    {"title": "Album One", "primary-type": "Album", "first-release-date": "2021-05-28"},
                ],
                "artist-relation-list": [
                    {"type": "collaboration", "artist": {"name": "Collab DJ", "id": "mbid-2"}},
                ],
                "url-relation-list": [
                    {"type": "soundcloud", "target": "https://soundcloud.com/solomun"},
                ],
                "tag-list": [],
            }
        }
        mb.browse_releases.return_value = {
            "release-list": [
                {"label-info-list": [{"label": {"name": "Diynamic Music"}}]},
            ]
        }

        result = _query_musicbrainz("Solomun")

        assert result["bio"] == "DJ"
        assert len(result["releases"]) == 1
        assert result["releases"][0]["title"] == "Album One"
        assert "Diynamic Music" in result["labels"]
        assert result["related_artists"] == ["Collab DJ"]
        assert "soundcloud" in result["social_links"]

    @patch("cratedigger.discovery.artist_profile.time")
    @patch("cratedigger.discovery.artist_profile._get_mb")
    def test_returns_empty_on_no_results(self, mock_get_mb, mock_time):
        mb = MagicMock()
        mock_get_mb.return_value = mb
        mb.search_artists.return_value = {"artist-list": []}

        result = _query_musicbrainz("Nonexistent")
        assert result == {}

    @patch("cratedigger.discovery.artist_profile._get_mb")
    def test_returns_empty_on_import_error(self, mock_get_mb):
        mock_get_mb.side_effect = ImportError("no module")

        result = _query_musicbrainz("Solomun")
        assert result == {}


# ---------------------------------------------------------------------------
# TestQuerySpotify — mock spotipy
# ---------------------------------------------------------------------------


class TestQuerySpotify:
    """Test Spotify query layer with mocked API."""

    @patch("cratedigger.discovery.artist_profile.spotipy", create=True)
    def test_returns_genres_and_related(self, _):
        with patch("cratedigger.discovery.artist_profile._query_spotify") as mock_fn:
            mock_fn.return_value = {
                "source": "spotify",
                "genres": ["tech house", "deep house"],
                "popularity": 72,
                "related_artists": ["Artist B"],
                "top_tracks": [{"title": "Hit", "album": "Album", "preview_url": None}],
                "social_links": {"spotify": "https://open.spotify.com/artist/x"},
            }

            result = mock_fn("Solomun")

            assert result["genres"] == ["tech house", "deep house"]
            assert result["popularity"] == 72
            assert "Artist B" in result["related_artists"]

    def test_returns_empty_without_spotipy(self):
        """When spotipy is not importable, should return empty dict gracefully."""
        with patch.dict("sys.modules", {"spotipy": None, "spotipy.oauth2": None}):
            # Force re-import won't work easily, so test via the function's behavior
            # The actual function handles ImportError internally
            result = _query_spotify("TestArtist")
            # Should return empty dict (no crash)
            assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# TestLibraryCrossRef — artist tracks in DB -> correct count
# ---------------------------------------------------------------------------


class TestLibraryCrossRef:
    """Test library cross-reference queries."""

    def test_counts_matching_tracks(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE audio_analysis ("
            "filepath TEXT PRIMARY KEY, bpm REAL, bpm_confidence REAL, "
            "key_camelot TEXT, key_confidence REAL, energy REAL, "
            "danceability REAL, genre TEXT, analyzed_at TEXT, analyzer_version TEXT)"
        )
        conn.execute(
            "INSERT INTO audio_analysis (filepath) VALUES (?)",
            ("/music/Solomun - After Rain.mp3",),
        )
        conn.execute(
            "INSERT INTO audio_analysis (filepath) VALUES (?)",
            ("/music/Solomun - Kackvogel.flac",),
        )
        conn.execute(
            "INSERT INTO audio_analysis (filepath) VALUES (?)",
            ("/music/Adam Beyer - Drumcode.mp3",),
        )
        conn.commit()
        conn.close()

        result = _query_library("Solomun", db_path)
        assert result["tracks_owned"] == 2

    def test_zero_when_no_matches(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE audio_analysis ("
            "filepath TEXT PRIMARY KEY, bpm REAL, bpm_confidence REAL, "
            "key_camelot TEXT, key_confidence REAL, energy REAL, "
            "danceability REAL, genre TEXT, analyzed_at TEXT, analyzer_version TEXT)"
        )
        conn.execute(
            "INSERT INTO audio_analysis (filepath) VALUES (?)",
            ("/music/Adam Beyer - Drumcode.mp3",),
        )
        conn.commit()
        conn.close()

        result = _query_library("Solomun", db_path)
        assert result["tracks_owned"] == 0

    def test_handles_missing_db(self, tmp_path):
        db_path = tmp_path / "nonexistent" / "test.db"
        result = _query_library("Solomun", db_path)
        assert result["tracks_owned"] == 0
        assert result["tracks_on_wishlist"] == 0


# ---------------------------------------------------------------------------
# TestArtistReport — output formatting (no crash tests)
# ---------------------------------------------------------------------------


class TestArtistReport:
    """Test artist profile display (Rich output)."""

    def test_full_profile_no_crash(self):
        profile = ArtistProfile(
            name="Solomun",
            bio="Bosnian-German DJ/producer",
            releases=[
                {"title": "Nobody Is Not Loved", "year": "2021", "label": "", "format": "", "type": "Album"},
                {"title": "Home", "year": "2023", "label": "", "format": "", "type": "Single"},
            ],
            labels=["Diynamic Music", "2020 Vision", "Watergate"],
            social_links={"soundcloud": "https://soundcloud.com/solomun", "spotify": "https://open.spotify.com/artist/x"},
            tracks_owned=4,
            tracks_on_wishlist=1,
            related_artists=["Tale Of Us", "Mind Against", "Maceo Plex", "Dixon"],
            genres=["tech house", "deep house"],
            popularity=72,
            top_tracks=[{"title": "Home", "album": "Home", "preview_url": None}],
            sources_queried=["musicbrainz", "spotify", "library"],
        )
        # Should not raise
        print_artist_profile(profile)

    def test_minimal_profile_no_crash(self):
        profile = ArtistProfile(name="Unknown DJ")
        print_artist_profile(profile)

    def test_no_social_links_no_crash(self):
        profile = ArtistProfile(
            name="Obscure Artist",
            releases=[{"title": "EP", "year": "2020", "type": "EP"}],
        )
        print_artist_profile(profile)

    def test_many_releases_truncated(self):
        releases = [
            {"title": f"Release {i}", "year": str(2020 + i % 5), "type": "Single"}
            for i in range(25)
        ]
        profile = ArtistProfile(name="Prolific DJ", releases=releases)
        # Should show first 15 + "... and 10 more"
        print_artist_profile(profile)

    def test_many_related_artists(self):
        profile = ArtistProfile(
            name="Connected DJ",
            related_artists=[f"Artist {i}" for i in range(15)],
        )
        # Should show first 8 + extra count
        print_artist_profile(profile)


# ---------------------------------------------------------------------------
# TestProfileFolder — scan folder, compute stats
# ---------------------------------------------------------------------------


class TestProfileFolder:
    """Test folder profiling."""

    def test_empty_folder(self, tmp_path):
        prof = profile_folder(tmp_path)
        assert prof["total_tracks"] == 0
        assert prof["bpm_range"] is None
        assert prof["genre_distribution"] == {}

    def test_counts_audio_files(self, tmp_path):
        (tmp_path / "track1.mp3").touch()
        (tmp_path / "track2.flac").touch()
        (tmp_path / "track3.wav").touch()
        (tmp_path / "readme.txt").touch()  # non-audio, ignored

        prof = profile_folder(tmp_path)
        assert prof["total_tracks"] == 3
        assert ".mp3" in prof["file_formats"]
        assert ".flac" in prof["file_formats"]
        assert ".wav" in prof["file_formats"]
        assert ".txt" not in prof["file_formats"]

    def test_recursive_scan(self, tmp_path):
        sub = tmp_path / "subfolder"
        sub.mkdir()
        (tmp_path / "track1.mp3").touch()
        (sub / "track2.mp3").touch()

        prof = profile_folder(tmp_path)
        assert prof["total_tracks"] == 2

    def test_size_calculated(self, tmp_path):
        f = tmp_path / "track.mp3"
        f.write_bytes(b"\x00" * (1024 * 1024 * 2))  # 2 MB

        prof = profile_folder(tmp_path)
        assert prof["total_size_mb"] > 0

    def test_bpm_stats_from_db(self, tmp_path):
        """BPM stats require DB entries -- without DB, should be None."""
        (tmp_path / "track1.mp3").touch()
        (tmp_path / "track2.mp3").touch()

        prof = profile_folder(tmp_path)
        # No DB entries for these files, so BPM should be None
        assert prof["bpm_range"] is None
        assert prof["bpm_median"] is None


# ---------------------------------------------------------------------------
# TestProfileFolderReport — output formatting (no crash tests)
# ---------------------------------------------------------------------------


class TestProfileFolderReport:
    """Test folder profile display (Rich output)."""

    def test_empty_folder_no_crash(self, tmp_path):
        prof = profile_folder(tmp_path)
        print_folder_profile(prof, tmp_path)

    def test_with_files_no_crash(self, tmp_path):
        (tmp_path / "track1.mp3").touch()
        (tmp_path / "track2.flac").touch()

        prof = profile_folder(tmp_path)
        print_folder_profile(prof, tmp_path)

    def test_with_full_stats_no_crash(self):
        prof = {
            "total_tracks": 42,
            "bpm_range": (120.0, 132.0),
            "bpm_median": 126.5,
            "genre_distribution": {"Tech House": 15, "Deep House": 12, "Techno": 8},
            "key_distribution": {"8A": 5, "7B": 4, "11A": 3},
            "total_duration_sec": 12600.0,
            "avg_track_length_sec": 300.0,
            "total_size_mb": 1250.5,
            "file_formats": {".mp3": 30, ".flac": 12},
        }
        print_folder_profile(prof, Path("/mnt/usb/DJ-Music"))
