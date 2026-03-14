"""Tests for weekly dig module (5.3)."""

from unittest.mock import patch

from cratedigger.digger.weekly_dig import (
    GENRE_SLUGS,
    NewRelease,
    WeeklyDigReport,
    _check_library_overlap,
    _check_streaming_overlap,
    _normalize_artist,
    _score_relevance,
    display_weekly_report,
    parse_manual_releases,
    scan_new_releases,
)

# --- NewRelease dataclass ---


class TestNewRelease:
    def test_defaults(self):
        r = NewRelease(title="Track", artist="DJ")
        assert r.in_library is False
        assert r.artist_in_streaming is False
        assert r.relevance_score == 0.0
        assert r.label == ""

    def test_full_creation(self):
        r = NewRelease(
            title="My Track",
            artist="Test DJ",
            label="Drumcode",
            bpm=128.0,
            key="8A",
            genre="Techno",
            url="https://beatport.com/track/my-track/123",
        )
        assert r.bpm == 128.0
        assert r.key == "8A"


# --- Normalize ---


class TestNormalizeArtist:
    def test_basic(self):
        assert _normalize_artist("Solomun") == "solomun"

    def test_strips_the(self):
        assert _normalize_artist("The Chemical Brothers") == "chemical brothers"

    def test_special_chars(self):
        assert _normalize_artist("DJ Koze & Friends") == "dj koze friends"


# --- Parse manual releases ---


class TestParseManualReleases:
    def test_basic_format(self):
        text = "Solomun - After Rain\nAdam Beyer - Drumcode"
        releases = parse_manual_releases(text)
        assert len(releases) == 2
        assert releases[0].artist == "Solomun"
        assert releases[0].title == "After Rain"
        assert releases[1].artist == "Adam Beyer"

    def test_with_label_brackets(self):
        text = "Solomun - After Rain [Diynamic]"
        releases = parse_manual_releases(text)
        assert len(releases) == 1
        assert releases[0].label == "Diynamic"
        assert releases[0].title == "After Rain"

    def test_with_label_parens(self):
        text = "Adam Beyer - Sequence (Drumcode)"
        releases = parse_manual_releases(text)
        assert len(releases) == 1
        assert releases[0].label == "Drumcode"

    def test_title_only(self):
        text = "Unknown Track"
        releases = parse_manual_releases(text)
        assert len(releases) == 1
        assert releases[0].title == "Unknown Track"
        assert releases[0].artist == ""

    def test_empty_lines_skipped(self):
        text = "Solomun - Track\n\n\nBeyer - Track2\n"
        releases = parse_manual_releases(text)
        assert len(releases) == 2

    def test_empty_input(self):
        assert parse_manual_releases("") == []
        assert parse_manual_releases("  \n  \n  ") == []

    def test_em_dash(self):
        text = "Solomun — After Rain"
        releases = parse_manual_releases(text)
        assert len(releases) == 1
        assert releases[0].artist == "Solomun"

    def test_en_dash(self):
        text = "Solomun – After Rain"
        releases = parse_manual_releases(text)
        assert len(releases) == 1
        assert releases[0].artist == "Solomun"


# --- Library overlap ---


class TestCheckLibraryOverlap:
    def test_marks_existing_tracks(self, tmp_path):
        (tmp_path / "Solomun - After Rain.mp3").touch()
        (tmp_path / "Adam Beyer - Drumcode.flac").touch()

        releases = [
            NewRelease(title="After Rain", artist="Solomun"),
            NewRelease(title="New Track", artist="Solomun"),
            NewRelease(title="Other", artist="Nobody"),
        ]
        _check_library_overlap(releases, tmp_path)

        assert releases[0].in_library is True
        assert releases[0].artist_in_library is True
        assert releases[1].in_library is False
        assert releases[1].artist_in_library is True  # Solomun exists in lib
        assert releases[2].in_library is False
        assert releases[2].artist_in_library is False

    def test_no_library_path(self):
        releases = [NewRelease(title="Track", artist="DJ")]
        _check_library_overlap(releases, None)
        assert releases[0].in_library is False

    def test_empty_library(self, tmp_path):
        releases = [NewRelease(title="Track", artist="DJ")]
        _check_library_overlap(releases, tmp_path)
        assert releases[0].in_library is False


# --- Streaming overlap ---


class TestCheckStreamingOverlap:
    def test_marks_streaming_artists(self):
        releases = [
            NewRelease(title="Track 1", artist="Solomun"),
            NewRelease(title="Track 2", artist="Unknown DJ"),
        ]
        _check_streaming_overlap(releases, ["Solomun", "Adam Beyer"])

        assert releases[0].artist_in_streaming is True
        assert releases[1].artist_in_streaming is False

    def test_case_insensitive(self):
        releases = [NewRelease(title="Track", artist="SOLOMUN")]
        _check_streaming_overlap(releases, ["solomun"])
        assert releases[0].artist_in_streaming is True

    def test_empty_streaming(self):
        releases = [NewRelease(title="Track", artist="DJ")]
        _check_streaming_overlap(releases, [])
        assert releases[0].artist_in_streaming is False


# --- Relevance scoring ---


class TestScoreRelevance:
    def test_genre_match(self):
        r = NewRelease(title="Track", artist="DJ", genre="Tech House")
        score = _score_relevance(r, ["Tech House"], [], [])
        assert score >= 0.3

    def test_artist_in_library(self):
        r = NewRelease(title="Track", artist="DJ")
        r.artist_in_library = True
        score = _score_relevance(r, [], [], [])
        assert score >= 0.3

    def test_artist_in_streaming(self):
        r = NewRelease(title="Track", artist="DJ")
        r.artist_in_streaming = True
        score = _score_relevance(r, [], [], [])
        assert score >= 0.2

    def test_in_library_zeroes_score(self):
        r = NewRelease(title="Track", artist="DJ", genre="Tech House")
        r.in_library = True
        r.artist_in_library = True
        score = _score_relevance(r, ["Tech House"], [], [])
        assert score == 0.0

    def test_combined_score(self):
        r = NewRelease(title="Track", artist="DJ", genre="Tech House")
        r.artist_in_library = True
        r.artist_in_streaming = True
        score = _score_relevance(r, ["Tech House"], [], [])
        assert score >= 0.8

    def test_max_score_capped(self):
        r = NewRelease(title="Track", artist="DJ", genre="Tech House", label="Drumcode")
        r.artist_in_library = True
        r.artist_in_streaming = True
        score = _score_relevance(r, ["Tech House"], [], ["Drumcode"])
        assert score <= 1.0

    def test_no_matches(self):
        r = NewRelease(title="Track", artist="DJ", genre="Classical")
        score = _score_relevance(r, ["Tech House"], [], [])
        assert score == 0.0


# --- Genre slugs ---


class TestGenreSlugs:
    def test_common_genres_have_slugs(self):
        assert "Tech House" in GENRE_SLUGS
        assert "Deep House" in GENRE_SLUGS
        assert "Techno" in GENRE_SLUGS
        assert "House" in GENRE_SLUGS

    def test_slugs_are_lowercase_hyphenated(self):
        for genre, slug in GENRE_SLUGS.items():
            assert slug == slug.lower()
            assert " " not in slug


# --- Full scan (mocked) ---


class TestScanNewReleases:
    @patch("cratedigger.digger.weekly_dig._search_beatport_releases")
    @patch("cratedigger.digger.weekly_dig._load_dj_profile")
    def test_scan_with_profile(self, mock_profile, mock_search):
        mock_profile.return_value = {
            "genres": {"Tech House": 0.4, "Deep House": 0.3},
            "bpm_range": {"min": 120, "max": 130},
            "top_artists": ["Solomun", "Adam Beyer"],
            "top_labels": ["Drumcode"],
        }
        mock_search.return_value = [
            NewRelease(title="New Track", artist="Solomun", genre="Tech House"),
            NewRelease(title="Old Track", artist="Unknown", genre="Tech House"),
        ]

        report = scan_new_releases()

        assert report.total_found >= 2
        assert len(report.genres_scanned) > 0
        assert report.profile_genres == ["Tech House", "Deep House"]

    @patch("cratedigger.digger.weekly_dig._search_beatport_releases")
    @patch("cratedigger.digger.weekly_dig._load_dj_profile")
    def test_scan_without_profile(self, mock_profile, mock_search):
        mock_profile.return_value = None
        mock_search.return_value = [
            NewRelease(title="Track", artist="DJ", genre="Tech House"),
        ]

        report = scan_new_releases()

        # Should use defaults
        assert "Tech House" in report.genres_scanned
        assert len(report.releases) >= 0

    @patch("cratedigger.digger.weekly_dig._search_beatport_releases")
    @patch("cratedigger.digger.weekly_dig._load_dj_profile")
    def test_scan_with_explicit_genres(self, mock_profile, mock_search):
        mock_profile.return_value = None
        mock_search.return_value = []

        report = scan_new_releases(genres=["Trance", "Breaks"])

        assert report.genres_scanned == ["Trance", "Breaks"]

    @patch("cratedigger.digger.weekly_dig._search_beatport_releases")
    @patch("cratedigger.digger.weekly_dig._load_dj_profile")
    def test_deduplication(self, mock_profile, mock_search):
        mock_profile.return_value = None
        mock_search.return_value = [
            NewRelease(title="Same Track", artist="Same DJ", genre="House"),
            NewRelease(title="Same Track", artist="Same DJ", genre="House"),
            NewRelease(title="Different", artist="Other", genre="House"),
        ]

        report = scan_new_releases(genres=["House"])

        titles = [r.title for r in report.releases]
        assert titles.count("Same Track") == 1


# --- Display ---


class TestDisplayWeeklyReport:
    def test_display_no_crash_with_releases(self):
        report = WeeklyDigReport(
            genres_scanned=["Tech House"],
            releases=[
                NewRelease(title="Hot Track", artist="Top DJ", genre="Tech House",
                          relevance_score=0.8, artist_in_library=True),
                NewRelease(title="Normal Track", artist="Other DJ", genre="Tech House",
                          relevance_score=0.1),
            ],
            profile_genres=["Tech House", "Deep House"],
            profile_bpm_range=(120, 130),
            total_found=10,
            after_filter=2,
        )
        display_weekly_report(report)

    def test_display_no_crash_empty(self):
        report = WeeklyDigReport(
            genres_scanned=["Techno"],
            total_found=0,
            after_filter=0,
        )
        display_weekly_report(report)

    def test_display_no_crash_many_releases(self):
        releases = [
            NewRelease(title=f"Track {i}", artist=f"DJ {i}", genre="House",
                      relevance_score=0.1)
            for i in range(25)
        ]
        report = WeeklyDigReport(
            genres_scanned=["House"],
            releases=releases,
            total_found=25,
            after_filter=25,
        )
        display_weekly_report(report)
