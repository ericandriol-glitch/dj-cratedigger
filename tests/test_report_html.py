"""Tests for HTML library insights report."""

from pathlib import Path

from cratedigger.report_html import _query_analysis_stats, generate_html_report


class TestQueryAnalysisStats:
    def test_empty_db(self, tmp_path: Path):
        """Stats from empty database return zero counts."""
        from cratedigger.utils.db import get_connection
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        conn.close()

        stats = _query_analysis_stats(db_path)
        assert stats["total_tracks"] == 0

    def test_with_data(self, tmp_path: Path):
        """Stats include BPM, key, energy from populated DB."""
        from cratedigger.utils.db import get_connection
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        conn.execute(
            "INSERT INTO audio_analysis (filepath, bpm, key_camelot, energy, danceability, genre) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("/test/track1.mp3", 125.0, "8A", 0.7, 0.8, "Tech House"),
        )
        conn.execute(
            "INSERT INTO audio_analysis (filepath, bpm, key_camelot, energy, danceability, genre) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("/test/track2.mp3", 130.0, "11B", 0.85, 0.9, "Deep House"),
        )
        conn.commit()
        conn.close()

        stats = _query_analysis_stats(db_path)
        assert stats["total_tracks"] == 2
        assert stats["analyzed_count"] == 2
        assert stats["bpm_min"] == 125.0
        assert stats["bpm_max"] == 130.0
        assert len(stats["keys"]) == 2
        assert len(stats["genres"]) == 2


class TestGenerateHtmlReport:
    def test_creates_html_file(self, tmp_path: Path):
        """Report generates a valid HTML file."""
        from cratedigger.utils.db import get_connection
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        conn.execute(
            "INSERT INTO audio_analysis (filepath, bpm, key_camelot, energy, danceability, genre) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("/test/track.mp3", 128.0, "8A", 0.75, 0.85, "House"),
        )
        conn.commit()
        conn.close()

        out = tmp_path / "report.html"
        result = generate_html_report(db_path=db_path, output_path=out)

        assert result == out
        assert out.exists()
        content = out.read_text()
        assert "DJ CrateDigger" in content
        assert "chart.js" in content.lower() or "Chart" in content
        assert "128" in content  # BPM should appear

    def test_creates_report_with_empty_db(self, tmp_path: Path):
        """Report handles empty database gracefully."""
        from cratedigger.utils.db import get_connection
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        conn.close()

        out = tmp_path / "report.html"
        generate_html_report(db_path=db_path, output_path=out)

        assert out.exists()
        content = out.read_text()
        assert "DJ CrateDigger" in content
        assert "0" in content  # Zero tracks

    def test_default_output_path(self, tmp_path: Path, monkeypatch):
        """Default output is library_report.html in current directory."""
        from cratedigger.utils.db import get_connection
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        conn.close()

        monkeypatch.chdir(tmp_path)
        result = generate_html_report(db_path=db_path)
        assert result.name == "library_report.html"
        assert result.exists()

    def test_html_contains_charts(self, tmp_path: Path):
        """HTML includes Chart.js canvas elements."""
        from cratedigger.utils.db import get_connection
        db_path = tmp_path / "test.db"
        conn = get_connection(db_path)
        conn.execute(
            "INSERT INTO audio_analysis (filepath, bpm, key_camelot, energy, genre) "
            "VALUES (?, ?, ?, ?, ?)",
            ("/test/t.mp3", 125.0, "8A", 0.7, "House"),
        )
        conn.commit()
        conn.close()

        out = tmp_path / "report.html"
        generate_html_report(db_path=db_path, output_path=out)
        content = out.read_text()

        assert "bpmChart" in content
        assert "keyChart" in content
        assert "genreChart" in content
