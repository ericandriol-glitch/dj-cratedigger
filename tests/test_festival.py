"""Tests for festival lineup scanner."""

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from cratedigger.cli import cli
from cratedigger.digger.festival import (
    FestivalReport,
    LineupArtist,
    _normalize,
    display_festival_report,
    parse_lineup,
    scan_festival,
)


class TestParseLineup:
    def test_comma_separated(self):
        result = parse_lineup("Tale Of Us, Adam Beyer, Charlotte de Witte")
        assert result == ["Tale Of Us", "Adam Beyer", "Charlotte de Witte"]

    def test_newline_separated(self):
        result = parse_lineup("Tale Of Us\nAdam Beyer\nCharlotte de Witte")
        assert result == ["Tale Of Us", "Adam Beyer", "Charlotte de Witte"]

    def test_mixed_separators(self):
        result = parse_lineup("Tale Of Us, Adam Beyer\nCharlotte de Witte")
        assert result == ["Tale Of Us", "Adam Beyer", "Charlotte de Witte"]

    def test_strips_whitespace(self):
        result = parse_lineup("  Tale Of Us ,  Adam Beyer  ")
        assert result == ["Tale Of Us", "Adam Beyer"]

    def test_removes_empty(self):
        result = parse_lineup("Tale Of Us,,, Adam Beyer,")
        assert result == ["Tale Of Us", "Adam Beyer"]

    def test_deduplicates(self):
        result = parse_lineup("Adam Beyer, adam beyer, ADAM BEYER")
        assert result == ["Adam Beyer"]

    def test_strips_numbering(self):
        result = parse_lineup("1. Tale Of Us\n2. Adam Beyer\n3) Charlotte de Witte")
        assert result == ["Tale Of Us", "Adam Beyer", "Charlotte de Witte"]

    def test_empty_string(self):
        assert parse_lineup("") == []

    def test_single_artist(self):
        assert parse_lineup("Vitess") == ["Vitess"]


class TestNormalize:
    def test_basic(self):
        assert _normalize("Adam Beyer") == "adam beyer"

    def test_strips_the(self):
        assert _normalize("The Chemical Brothers") == "chemical brothers"

    def test_removes_punctuation(self):
        assert _normalize("Oden & Fatzo") == "oden fatzo"

    def test_apostrophes(self):
        assert _normalize("DJ's Choice") == "djs choice"


class TestScanFestival:
    @patch("cratedigger.digger.festival._build_library_map_from_db")
    @patch("cratedigger.digger.festival._build_streaming_map")
    @patch("cratedigger.digger.festival._get_profile_genres")
    @patch("cratedigger.digger.festival._lookup_artist_genres")
    def test_categorises_owned(self, mock_lookup, mock_genres, mock_stream, mock_lib):
        mock_lib.return_value = {"vitess": 5, "adam beyer": 12}
        mock_stream.return_value = {}
        mock_genres.return_value = set()

        report = scan_festival(["Vitess", "Adam Beyer"], lookup_genres=False)

        assert report.already_own == 2
        assert report.stream_only == 0
        assert report.unknown_count == 0
        assert report.artists[0].category == "already-own"
        assert report.artists[0].library_tracks == 5

    @patch("cratedigger.digger.festival._build_library_map_from_db")
    @patch("cratedigger.digger.festival._build_streaming_map")
    @patch("cratedigger.digger.festival._get_profile_genres")
    def test_categorises_stream_only(self, mock_genres, mock_stream, mock_lib):
        mock_lib.return_value = {}
        mock_stream.return_value = {"adam beyer": 6}
        mock_genres.return_value = set()

        report = scan_festival(["Adam Beyer"], lookup_genres=False)

        assert report.stream_only == 1
        assert report.artists[0].category == "stream-but-dont-own"
        assert report.artists[0].stream_score == 6

    @patch("cratedigger.digger.festival._build_library_map_from_db")
    @patch("cratedigger.digger.festival._build_streaming_map")
    @patch("cratedigger.digger.festival._get_profile_genres")
    def test_categorises_unknown(self, mock_genres, mock_stream, mock_lib):
        mock_lib.return_value = {}
        mock_stream.return_value = {}
        mock_genres.return_value = set()

        report = scan_festival(["Some New Artist"], lookup_genres=False)

        assert report.unknown_count == 1
        assert report.artists[0].category == "unknown"

    @patch("cratedigger.digger.festival._build_library_map_from_db")
    @patch("cratedigger.digger.festival._build_streaming_map")
    @patch("cratedigger.digger.festival._get_profile_genres")
    @patch("cratedigger.digger.festival._lookup_artist_genres")
    def test_genre_match_for_unknowns(self, mock_lookup, mock_genres, mock_stream, mock_lib):
        mock_lib.return_value = {}
        mock_stream.return_value = {}
        mock_genres.return_value = {"house", "techno"}
        mock_lookup.return_value = ["house", "deep house"]

        report = scan_festival(["Unknown DJ"], lookup_genres=True)

        assert report.genre_matches == 1
        assert report.artists[0].genre_match is True
        assert report.artists[0].genres == ["house", "deep house"]

    @patch("cratedigger.digger.festival._build_library_map_from_db")
    @patch("cratedigger.digger.festival._build_streaming_map")
    @patch("cratedigger.digger.festival._get_profile_genres")
    @patch("cratedigger.digger.festival._lookup_artist_genres")
    def test_no_genre_match(self, mock_lookup, mock_genres, mock_stream, mock_lib):
        mock_lib.return_value = {}
        mock_stream.return_value = {}
        mock_genres.return_value = {"house", "techno"}
        mock_lookup.return_value = ["metal", "rock"]

        report = scan_festival(["Metal Band"], lookup_genres=True)

        assert report.genre_matches == 0
        assert report.artists[0].genre_match is False

    @patch("cratedigger.digger.festival._build_library_artist_map")
    @patch("cratedigger.digger.festival._build_streaming_map")
    @patch("cratedigger.digger.festival._get_profile_genres")
    def test_uses_library_path_when_provided(self, mock_genres, mock_stream, mock_lib):
        mock_lib.return_value = {"vitess": 3}
        mock_stream.return_value = {}
        mock_genres.return_value = set()

        report = scan_festival(
            ["Vitess"],
            library_path=Path("/fake/music"),
            lookup_genres=False,
        )

        mock_lib.assert_called_once_with(Path("/fake/music"))
        assert report.already_own == 1

    @patch("cratedigger.digger.festival._build_library_map_from_db")
    @patch("cratedigger.digger.festival._build_streaming_map")
    @patch("cratedigger.digger.festival._get_profile_genres")
    @patch("cratedigger.digger.festival._lookup_artist_genres")
    def test_mixed_categories(self, mock_lookup, mock_genres, mock_stream, mock_lib):
        mock_lib.return_value = {"vitess": 5}
        mock_stream.return_value = {"charlotte de witte": 8}
        mock_genres.return_value = set()
        mock_lookup.return_value = []

        report = scan_festival(
            ["Vitess", "Charlotte de Witte", "Unknown DJ"],
            lookup_genres=True,
        )

        assert report.total == 3
        assert report.already_own == 1
        assert report.stream_only == 1
        assert report.unknown_count == 1

    @patch("cratedigger.digger.festival._build_library_map_from_db")
    @patch("cratedigger.digger.festival._build_streaming_map")
    @patch("cratedigger.digger.festival._get_profile_genres")
    def test_skips_genre_lookup_when_disabled(self, mock_genres, mock_stream, mock_lib):
        mock_lib.return_value = {}
        mock_stream.return_value = {}
        mock_genres.return_value = set()

        report = scan_festival(["Unknown DJ"], lookup_genres=False)

        assert report.artists[0].genres == []
        assert report.genre_matches == 0


class TestDisplayFestivalReport:
    def test_display_does_not_crash(self):
        report = FestivalReport(
            festival_name="Test Fest",
            total=3,
            already_own=1,
            stream_only=1,
            unknown_count=1,
            genre_matches=1,
            artists=[
                LineupArtist(name="Vitess", category="already-own", library_tracks=5),
                LineupArtist(name="Adam Beyer", category="stream-but-dont-own", stream_score=8),
                LineupArtist(name="New DJ", category="unknown", genres=["house"], genre_match=True),
            ],
        )
        display_festival_report(report)

    def test_display_empty_report(self):
        report = FestivalReport(festival_name="Empty Fest")
        display_festival_report(report)

    def test_display_all_owned(self):
        report = FestivalReport(
            festival_name="My Fest",
            total=2,
            already_own=2,
            artists=[
                LineupArtist(name="A", category="already-own", library_tracks=10),
                LineupArtist(name="B", category="already-own", library_tracks=3),
            ],
        )
        display_festival_report(report)

    def test_display_all_unknown(self):
        report = FestivalReport(
            festival_name="New Fest",
            total=2,
            unknown_count=2,
            artists=[
                LineupArtist(name="X", category="unknown", genres=["techno"], genre_match=True),
                LineupArtist(name="Y", category="unknown", genres=["rock"], genre_match=False),
            ],
        )
        display_festival_report(report)


class TestDigFestivalCLI:
    def test_no_args_shows_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["dig", "festival"])
        assert "Provide a festival name or --lineup" in result.output

    def test_festival_name_without_api_key(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["dig", "festival", "Sonar 2026"])
        assert "EDMTrain API key not configured" in result.output

    @patch("cratedigger.digger.festival._build_library_map_from_db")
    @patch("cratedigger.digger.festival._build_streaming_map")
    @patch("cratedigger.digger.festival._get_profile_genres")
    def test_lineup_flag(self, mock_genres, mock_stream, mock_lib):
        mock_lib.return_value = {}
        mock_stream.return_value = {}
        mock_genres.return_value = set()

        runner = CliRunner()
        result = runner.invoke(cli, [
            "dig", "festival",
            "--lineup", "Adam Beyer, Charlotte de Witte",
            "--no-genres",
        ])
        assert result.exit_code == 0
        assert "Adam Beyer" in result.output
        assert "Charlotte de Witte" in result.output

    @patch("cratedigger.digger.festival._build_library_map_from_db")
    @patch("cratedigger.digger.festival._build_streaming_map")
    @patch("cratedigger.digger.festival._get_profile_genres")
    def test_lineup_with_name(self, mock_genres, mock_stream, mock_lib):
        mock_lib.return_value = {"adam beyer": 10}
        mock_stream.return_value = {}
        mock_genres.return_value = set()

        runner = CliRunner()
        result = runner.invoke(cli, [
            "dig", "festival", "Sonar 2026",
            "--lineup", "Adam Beyer",
            "--no-genres",
        ])
        assert result.exit_code == 0
        assert "Sonar 2026" in result.output
        assert "Already in your library" in result.output
