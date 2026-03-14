"""Tests for label research module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from cratedigger.cli import cli
from cratedigger.digger.label import (
    ArtistInfo,
    LabelInfo,
    LabelReport,
    Release,
    RosterArtist,
    _extract_aliases_from_text,
    _extract_labels_from_beatport,
    _extract_labels_from_snippets,
    _extract_labels_from_ra,
    cross_reference_library,
    display_label_report,
    enrich_with_web_search,
    extract_labels,
    get_artist_releases,
    get_label_info,
    get_label_roster,
    research_label,
    search_artist,
)


# --- Mock MusicBrainz module ---

def _make_mock_mb():
    """Create a mock musicbrainzngs module."""
    mock = MagicMock()
    mock.set_useragent = MagicMock()
    return mock


# --- Fixtures ---

MOCK_ARTIST_SEARCH = {
    "artist-list": [
        {
            "id": "abc-123",
            "name": "Vitess",
            "country": "DE",
            "disambiguation": "German electronic artist",
        },
        {
            "id": "xyz-999",
            "name": "Vitesse",
            "country": "NL",
        },
    ]
}

MOCK_ARTIST_RELEASES = {
    "release-list": [
            {
                "id": "rel-001",
                "title": "Desire Path",
                "date": "2023-06-15",
                "country": "XW",
                "label-info-list": [
                    {
                        "catalog-number": "AFULAB001",
                        "label": {"name": "Afulab", "id": "lab-001"},
                    }
                ],
                "medium-list": [{"format": "Digital Media"}],
            },
            {
                "id": "rel-002",
                "title": "Night Drive",
                "date": "2022-11-01",
                "country": "XW",
                "label-info-list": [
                    {
                        "catalog-number": "RH001",
                        "label": {"name": "Running Hot", "id": "lab-002"},
                    }
                ],
                "medium-list": [{"format": '12" Vinyl'}],
            },
            {
                "id": "rel-003",
                "title": "Self Released EP",
                "date": "2021-01-01",
                "label-info-list": [
                    {
                        "label": {"name": "[no label]"},
                    }
                ],
                "medium-list": [],
            },
        ]
}

MOCK_LABEL_SEARCH = {
    "label-list": [
        {
            "id": "lab-001",
            "name": "Afulab",
            "country": "DE",
            "type": "Original Production",
        }
    ]
}

MOCK_LABEL_DETAIL = {
    "label": {
        "name": "Afulab",
        "id": "lab-001",
        "country": "DE",
        "type": "Original Production",
        "url-relation-list": [
            {"type": "official homepage", "target": "https://afulab.com"},
            {"type": "bandcamp", "target": "https://afulab.bandcamp.com"},
        ],
    }
}

MOCK_LABEL_ROSTER = {
    "release-list": [
            {
                "title": "Desire Path",
                "artist-credit": [
                    {"artist": {"name": "Vitess", "id": "abc-123"}},
                ],
            },
            {
                "title": "Dawn Chorus",
                "artist-credit": [
                    {"artist": {"name": "Otik", "id": "art-002"}},
                ],
            },
            {
                "title": "Silk Road",
                "artist-credit": [
                    {"artist": {"name": "Otik", "id": "art-002"}},
                ],
            },
            {
                "title": "Midnight Sun",
                "artist-credit": [
                    {"artist": {"name": "Laksa", "id": "art-003"}},
                ],
            },
        ]
}


class TestSearchArtist:
    """Test artist search on MusicBrainz."""

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_finds_exact_match(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.search_artists.return_value = MOCK_ARTIST_SEARCH
        mock_get_mb.return_value = mock_mb

        result = search_artist("Vitess")

        assert result is not None
        assert result.name == "Vitess"
        assert result.mbid == "abc-123"
        assert result.country == "DE"
        mock_mb.search_artists.assert_called_once_with("Vitess", limit=5)

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_falls_back_to_first_result(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.search_artists.return_value = {
            "artist-list": [
                {"id": "xyz-999", "name": "Vitesse", "country": "NL"},
            ]
        }
        mock_get_mb.return_value = mock_mb

        result = search_artist("Vites")

        assert result is not None
        assert result.name == "Vitesse"
        assert result.mbid == "xyz-999"

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_returns_none_when_not_found(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.search_artists.return_value = {"artist-list": []}
        mock_get_mb.return_value = mock_mb

        result = search_artist("NonexistentArtist12345")
        assert result is None

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_handles_api_error(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.search_artists.side_effect = Exception("Network error")
        mock_get_mb.return_value = mock_mb

        result = search_artist("Vitess")
        assert result is None


class TestGetArtistReleases:
    """Test fetching releases for an artist."""

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_extracts_releases(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.browse_releases.return_value = MOCK_ARTIST_RELEASES
        mock_get_mb.return_value = mock_mb

        releases = get_artist_releases("abc-123")

        assert len(releases) == 3
        assert releases[0].title == "Desire Path"
        assert releases[0].label == "Afulab"
        assert releases[0].catalog_number == "AFULAB001"
        assert releases[0].date == "2023-06-15"
        assert releases[0].format == "Digital Media"

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_vinyl_format(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.browse_releases.return_value = MOCK_ARTIST_RELEASES
        mock_get_mb.return_value = mock_mb

        releases = get_artist_releases("abc-123")
        assert releases[1].format == '12" Vinyl'

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_handles_api_error(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.browse_releases.side_effect = Exception("Network error")
        mock_get_mb.return_value = mock_mb

        releases = get_artist_releases("abc-123")
        assert releases == []


class TestExtractLabels:
    """Test label extraction from releases."""

    def test_extracts_unique_labels(self):
        releases = [
            Release(title="A", label="Afulab"),
            Release(title="B", label="Running Hot"),
            Release(title="C", label="Afulab"),
        ]
        labels = extract_labels(releases)
        assert labels == ["Afulab", "Running Hot"]

    def test_filters_no_label(self):
        releases = [
            Release(title="A", label="Afulab"),
            Release(title="B", label="[no label]"),
            Release(title="C", label=None),
            Release(title="D", label="self-released"),
        ]
        labels = extract_labels(releases)
        assert labels == ["Afulab"]

    def test_empty_releases(self):
        assert extract_labels([]) == []


class TestGetLabelInfo:
    """Test label detail lookup."""

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_gets_label_with_urls(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.search_labels.return_value = MOCK_LABEL_SEARCH
        mock_mb.get_label_by_id.return_value = MOCK_LABEL_DETAIL
        mock_get_mb.return_value = mock_mb

        info = get_label_info("Afulab")

        assert info is not None
        assert info.name == "Afulab"
        assert info.country == "DE"
        assert info.label_type == "Original Production"
        assert len(info.urls) == 2
        assert info.urls[0]["type"] == "official homepage"
        assert info.urls[1]["url"] == "https://afulab.bandcamp.com"

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_returns_none_when_not_found(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.search_labels.return_value = {"label-list": []}
        mock_get_mb.return_value = mock_mb

        info = get_label_info("Nonexistent Label")
        assert info is None


class TestGetLabelRoster:
    """Test getting other artists on a label."""

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_gets_roster_excluding_artist(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.browse_releases.return_value = MOCK_LABEL_ROSTER
        mock_get_mb.return_value = mock_mb

        roster = get_label_roster("lab-001", exclude_artist="Vitess")

        assert len(roster) == 2
        names = {a.name for a in roster}
        assert "Otik" in names
        assert "Laksa" in names
        assert "Vitess" not in names

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_counts_releases_per_artist(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.browse_releases.return_value = MOCK_LABEL_ROSTER
        mock_get_mb.return_value = mock_mb

        roster = get_label_roster("lab-001", exclude_artist="Vitess")

        otik = next(a for a in roster if a.name == "Otik")
        assert otik.release_count == 2

        laksa = next(a for a in roster if a.name == "Laksa")
        assert laksa.release_count == 1

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_sorted_by_release_count(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.browse_releases.return_value = MOCK_LABEL_ROSTER
        mock_get_mb.return_value = mock_mb

        roster = get_label_roster("lab-001", exclude_artist="Vitess")

        assert roster[0].name == "Otik"  # 2 releases
        assert roster[1].name == "Laksa"  # 1 release

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._get_mb")
    def test_handles_api_error(self, mock_get_mb, mock_sleep):
        mock_mb = _make_mock_mb()
        mock_mb.browse_releases.side_effect = Exception("Network error")
        mock_get_mb.return_value = mock_mb

        roster = get_label_roster("lab-001")
        assert roster == []


class TestCrossReferenceLibrary:
    """Test cross-referencing roster artists with library files."""

    @patch("cratedigger.digger.label.find_audio_files")
    def test_finds_matching_files(self, mock_find):
        mock_find.return_value = [
            Path("/music/Otik - Dawn Chorus.mp3"),
            Path("/music/Otik - Night Run.flac"),
            Path("/music/Disclosure - Latch.mp3"),
        ]

        roster = [
            RosterArtist(name="Otik", mbid="art-002", release_count=2),
            RosterArtist(name="Laksa", mbid="art-003", release_count=1),
        ]

        result = cross_reference_library(roster, Path("/music"))

        otik = result[0]
        assert otik.in_library is True
        assert len(otik.library_files) == 2

        laksa = result[1]
        assert laksa.in_library is False
        assert laksa.library_files == []

    @patch("cratedigger.digger.label.find_audio_files")
    def test_case_insensitive_match(self, mock_find):
        mock_find.return_value = [
            Path("/music/OTIK - Dawn Chorus.mp3"),
        ]

        roster = [
            RosterArtist(name="Otik", mbid="art-002", release_count=1),
        ]

        result = cross_reference_library(roster, Path("/music"))
        assert result[0].in_library is True

    @patch("cratedigger.digger.label.find_audio_files")
    def test_empty_library(self, mock_find):
        mock_find.return_value = []

        roster = [
            RosterArtist(name="Otik", mbid="art-002", release_count=1),
        ]

        result = cross_reference_library(roster, Path("/music"))
        assert result[0].in_library is False


class TestDisplayLabelReport:
    """Test rich output rendering."""

    def test_display_does_not_crash(self, capsys):
        """Display function should run without errors for any valid report."""
        report = LabelReport(
            artist=ArtistInfo(name="Vitess", mbid="abc-123", country="DE"),
            releases=[
                Release(
                    title="Desire Path",
                    label="Afulab",
                    date="2023-06-15",
                    catalog_number="AFUL001",
                    format="Digital Media",
                ),
            ],
            labels=[
                LabelInfo(
                    name="Afulab",
                    mbid="lab-001",
                    country="DE",
                    label_type="Original Production",
                    urls=[{"type": "bandcamp", "url": "https://afulab.bandcamp.com"}],
                ),
            ],
            roster={
                "Afulab": [
                    RosterArtist(name="Otik", mbid="art-002", release_count=2, in_library=True,
                                 library_files=["/music/Otik - Track.mp3"]),
                    RosterArtist(name="Laksa", mbid="art-003", release_count=1),
                ],
            },
        )

        # Should not raise
        display_label_report(report)

    def test_display_empty_report(self):
        """Display should handle a report with no releases or labels."""
        report = LabelReport(
            artist=ArtistInfo(name="Unknown", mbid="000"),
            releases=[],
            labels=[],
            roster={},
        )
        display_label_report(report)


class TestResearchLabel:
    """Test the full research pipeline."""

    @patch("cratedigger.digger.label.get_label_roster")
    @patch("cratedigger.digger.label.get_label_info")
    @patch("cratedigger.digger.label.get_artist_releases")
    @patch("cratedigger.digger.label.search_artist")
    def test_full_pipeline(self, mock_search, mock_releases, mock_label_info, mock_roster):
        mock_search.return_value = ArtistInfo(name="Vitess", mbid="abc-123", country="DE")
        mock_releases.return_value = [
            Release(title="Desire Path", label="Afulab"),
        ]
        mock_label_info.return_value = LabelInfo(name="Afulab", mbid="lab-001", country="DE")
        mock_roster.return_value = [
            RosterArtist(name="Otik", mbid="art-002", release_count=2),
        ]

        report = research_label("Vitess", web_search=False)

        assert report is not None
        assert report.artist.name == "Vitess"
        assert len(report.labels) == 1
        assert report.labels[0].name == "Afulab"
        assert "Afulab" in report.roster
        assert report.roster["Afulab"][0].name == "Otik"

    @patch("cratedigger.digger.label.search_artist")
    def test_returns_none_when_artist_not_found(self, mock_search):
        mock_search.return_value = None
        report = research_label("NonexistentArtist")

        assert report is None

    @patch("cratedigger.digger.label.cross_reference_library")
    @patch("cratedigger.digger.label.get_label_roster")
    @patch("cratedigger.digger.label.get_label_info")
    @patch("cratedigger.digger.label.get_artist_releases")
    @patch("cratedigger.digger.label.search_artist")
    def test_pipeline_with_library(self, mock_search, mock_releases, mock_label_info,
                                    mock_roster, mock_xref):
        mock_search.return_value = ArtistInfo(name="Vitess", mbid="abc-123")
        mock_releases.return_value = [Release(title="A", label="TestLabel")]
        mock_label_info.return_value = LabelInfo(name="TestLabel", mbid="lab-x")
        roster = [RosterArtist(name="SomeArtist", mbid="art-x", release_count=1)]
        mock_roster.return_value = roster
        mock_xref.return_value = roster

        report = research_label("Vitess", library_path=Path("/music"), web_search=False)

        mock_xref.assert_called_once()
        assert report is not None


class TestDigLabelCLI:
    """Test the dig label CLI command."""

    @patch("cratedigger.digger.label.research_label")
    def test_dig_label_command(self, mock_research):
        mock_research.return_value = LabelReport(
            artist=ArtistInfo(name="Vitess", mbid="abc-123"),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["dig", "label", "Vitess"])

        assert result.exit_code == 0
        mock_research.assert_called_once_with("Vitess", library_path=None, web_search=True)

    @patch("cratedigger.digger.label.research_label")
    def test_dig_label_not_found(self, mock_research):
        mock_research.return_value = None

        runner = CliRunner()
        result = runner.invoke(cli, ["dig", "label", "NonexistentArtist"])

        assert result.exit_code == 0

    @patch("cratedigger.digger.label.research_label")
    def test_dig_label_no_web_flag(self, mock_research):
        mock_research.return_value = LabelReport(
            artist=ArtistInfo(name="Vitess", mbid="abc-123"),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["dig", "label", "--no-web", "Vitess"])

        assert result.exit_code == 0
        mock_research.assert_called_once_with("Vitess", library_path=None, web_search=False)

    @patch("cratedigger.digger.label.research_label")
    def test_dig_label_without_no_web_flag(self, mock_research):
        mock_research.return_value = LabelReport(
            artist=ArtistInfo(name="Vitess", mbid="abc-123"),
        )

        runner = CliRunner()
        result = runner.invoke(cli, ["dig", "label", "Vitess"])

        assert result.exit_code == 0
        mock_research.assert_called_once_with("Vitess", library_path=None, web_search=True)


class TestWebSearchParsing:
    """Test web scraping extraction functions."""

    def test_extract_labels_from_beatport(self):
        html = '''
        <a href="/label/chevry-agency/12345">Chevry Agency</a>
        <a href="/label/running-hot/67890">Running Hot</a>
        <a href="/label/ab/1">Ab</a>
        '''
        labels = _extract_labels_from_beatport(html)
        assert "Chevry Agency" in labels
        assert "Running Hot" in labels
        # Short names (<=2 chars) should be filtered
        assert "Ab" not in labels

    def test_extract_labels_from_ra(self):
        html = '''
        <a href="/record-labels/chevry-agency">Chevry Agency</a>
        <a href="/labels/12345" class="lnk">Afulab</a>
        '''
        labels = _extract_labels_from_ra(html)
        assert "Chevry Agency" in labels

    def test_extract_labels_from_ra_labels_link(self):
        html = '<a href="/labels/12345">Some Label</a>'
        labels = _extract_labels_from_ra(html)
        assert "Some Label" in labels

    def test_extract_labels_from_snippets_text_patterns(self):
        html = '''
        <html><body>
        <div>Vitess released on Chevry Agency. She has also released on Running Hot Records.</div>
        <div>Check out <a href="https://afulab.bandcamp.com">Afulab</a></div>
        </body></html>
        '''
        labels = _extract_labels_from_snippets(html)
        assert "Chevry Agency" in labels
        assert "Afulab" in labels

    def test_extract_labels_from_snippets_bandcamp_urls(self):
        html = '<a href="https://deeptrax.bandcamp.com/album/test">link</a>'
        labels = _extract_labels_from_snippets(html)
        assert "Deeptrax" in labels

    def test_extract_labels_from_snippets_filters_common_bandcamp(self):
        html = '<a href="https://daily.bandcamp.com">daily</a>'
        labels = _extract_labels_from_snippets(html)
        assert "Daily" not in labels

    def test_extract_labels_from_snippets_beatport_in_results(self):
        html = '<a href="https://beatport.com/label/chevry-agency/99999">link</a>'
        labels = _extract_labels_from_snippets(html)
        assert "Chevry Agency" in labels

    def test_extract_aliases_basic(self):
        text = "Vitess aka DJ Vita is a Berlin-based producer."
        aliases = _extract_aliases_from_text(text, "Vitess")
        assert "DJ Vita" in aliases

    def test_extract_aliases_also_known_as(self):
        text = "Vitess also known as Vita produces minimal techno."
        aliases = _extract_aliases_from_text(text, "Vitess")
        assert "Vita" in aliases

    def test_extract_aliases_no_self_match(self):
        text = "Vitess aka Vitess is great."
        aliases = _extract_aliases_from_text(text, "Vitess")
        assert len(aliases) == 0

    def test_extract_aliases_empty_when_no_pattern(self):
        text = "Vitess is a DJ from Berlin."
        aliases = _extract_aliases_from_text(text, "Vitess")
        assert aliases == []


class TestEnrichWithWebSearch:
    """Test the web enrichment merge logic."""

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._fetch_google_search")
    @patch("cratedigger.digger.label._fetch_beatport_search")
    @patch("cratedigger.digger.label._fetch_ra_page")
    @patch("cratedigger.digger.label.get_label_info")
    def test_merges_new_labels(self, mock_label_info, mock_ra, mock_bp, mock_google, mock_sleep):
        """New labels from web should be added to the report."""
        mock_ra.return_value = (["Chevry Agency"], [])
        mock_bp.return_value = ["Running Hot"]
        mock_google.return_value = ([], [])
        # First call returns structured data, second returns None
        mock_label_info.side_effect = [
            LabelInfo(name="Chevry Agency", mbid="lab-chevry", source="musicbrainz"),
            None,
        ]

        report = LabelReport(
            artist=ArtistInfo(name="Vitess", mbid="abc-123"),
            labels=[LabelInfo(name="Afulab", mbid="lab-001")],
        )

        result = enrich_with_web_search("Vitess", report)

        assert len(result.labels) == 3
        label_names = [l.name for l in result.labels]
        assert "Afulab" in label_names
        assert "Chevry Agency" in label_names
        assert "Running Hot" in label_names

        # Chevry Agency found on MB should have web+musicbrainz source
        chevry = next(l for l in result.labels if l.name == "Chevry Agency")
        assert chevry.source == "web+musicbrainz"
        assert chevry.mbid == "lab-chevry"

        # Running Hot not on MB should have web source
        rh = next(l for l in result.labels if l.name == "Running Hot")
        assert rh.source == "web"
        assert rh.mbid == ""

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._fetch_google_search")
    @patch("cratedigger.digger.label._fetch_beatport_search")
    @patch("cratedigger.digger.label._fetch_ra_page")
    @patch("cratedigger.digger.label.get_label_info")
    def test_does_not_duplicate_existing_labels(self, mock_label_info, mock_ra, mock_bp,
                                                  mock_google, mock_sleep):
        """Labels already in the report should not be added again."""
        mock_ra.return_value = (["Afulab"], [])
        mock_bp.return_value = ["Afulab"]
        mock_google.return_value = ([], [])

        report = LabelReport(
            artist=ArtistInfo(name="Vitess", mbid="abc-123"),
            labels=[LabelInfo(name="Afulab", mbid="lab-001")],
        )

        result = enrich_with_web_search("Vitess", report)

        assert len(result.labels) == 1
        mock_label_info.assert_not_called()

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._fetch_google_search")
    @patch("cratedigger.digger.label._fetch_beatport_search")
    @patch("cratedigger.digger.label._fetch_ra_page")
    def test_adds_aliases(self, mock_ra, mock_bp, mock_google, mock_sleep):
        """Aliases found on the web should be added to ArtistInfo."""
        mock_ra.return_value = ([], ["DJ Vita"])
        mock_bp.return_value = []
        mock_google.return_value = ([], ["V-Tess"])

        report = LabelReport(
            artist=ArtistInfo(name="Vitess", mbid="abc-123"),
        )

        result = enrich_with_web_search("Vitess", report)

        assert "DJ Vita" in result.artist.aliases
        assert "V-Tess" in result.artist.aliases

    @patch("cratedigger.digger.label.time.sleep")
    @patch("cratedigger.digger.label._fetch_google_search")
    @patch("cratedigger.digger.label._fetch_beatport_search")
    @patch("cratedigger.digger.label._fetch_ra_page")
    def test_handles_fetch_errors_gracefully(self, mock_ra, mock_bp, mock_google, mock_sleep):
        """Web fetch errors should not crash the enrichment."""
        mock_ra.side_effect = Exception("Connection refused")
        mock_bp.side_effect = Exception("Timeout")
        mock_google.side_effect = Exception("DNS error")

        report = LabelReport(
            artist=ArtistInfo(name="Vitess", mbid="abc-123"),
            labels=[LabelInfo(name="Afulab", mbid="lab-001")],
        )

        result = enrich_with_web_search("Vitess", report)

        # Should return unchanged report without crashing
        assert len(result.labels) == 1
        assert result.labels[0].name == "Afulab"


class TestResearchLabelWebSearch:
    """Test research_label with web_search parameter."""

    @patch("cratedigger.digger.label.enrich_with_web_search")
    @patch("cratedigger.digger.label.get_label_roster")
    @patch("cratedigger.digger.label.get_label_info")
    @patch("cratedigger.digger.label.get_artist_releases")
    @patch("cratedigger.digger.label.search_artist")
    def test_web_search_called_by_default(self, mock_search, mock_releases,
                                           mock_label_info, mock_roster, mock_enrich):
        mock_search.return_value = ArtistInfo(name="Vitess", mbid="abc-123")
        mock_releases.return_value = []
        mock_enrich.side_effect = lambda name, report: report

        report = research_label("Vitess")

        assert report is not None
        mock_enrich.assert_called_once()

    @patch("cratedigger.digger.label.enrich_with_web_search")
    @patch("cratedigger.digger.label.get_label_roster")
    @patch("cratedigger.digger.label.get_label_info")
    @patch("cratedigger.digger.label.get_artist_releases")
    @patch("cratedigger.digger.label.search_artist")
    def test_web_search_disabled(self, mock_search, mock_releases,
                                  mock_label_info, mock_roster, mock_enrich):
        mock_search.return_value = ArtistInfo(name="Vitess", mbid="abc-123")
        mock_releases.return_value = []

        report = research_label("Vitess", web_search=False)

        assert report is not None
        mock_enrich.assert_not_called()


class TestLabelInfoSource:
    """Test the source field on LabelInfo."""

    def test_default_source_is_musicbrainz(self):
        info = LabelInfo(name="Test", mbid="123")
        assert info.source == "musicbrainz"

    def test_web_source(self):
        info = LabelInfo(name="Test", mbid="", source="web")
        assert info.source == "web"

    def test_web_musicbrainz_source(self):
        info = LabelInfo(name="Test", mbid="123", source="web+musicbrainz")
        assert info.source == "web+musicbrainz"


class TestArtistInfoAliases:
    """Test the aliases field on ArtistInfo."""

    def test_default_aliases_empty(self):
        artist = ArtistInfo(name="Test", mbid="123")
        assert artist.aliases == []

    def test_aliases_set(self):
        artist = ArtistInfo(name="Test", mbid="123", aliases=["Alias1", "Alias2"])
        assert artist.aliases == ["Alias1", "Alias2"]
