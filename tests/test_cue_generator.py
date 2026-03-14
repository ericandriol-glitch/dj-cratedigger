"""Tests for cue point generator."""

import pytest
from pathlib import Path

from cratedigger.gig.cue_generator import (
    CueTemplate,
    GeneratedCue,
    generate_cues,
    load_template,
    store_cues,
    _resolve_position,
)
from cratedigger.gig.structure_analyzer import TrackStructure


class TestLoadTemplate:
    def test_loads_default_template(self):
        templates = load_template("default")
        assert len(templates) > 0

    def test_template_has_names(self):
        templates = load_template("default")
        names = [t.name for t in templates]
        assert "Intro" in names
        assert "Drop" in names
        assert "Mix Out" in names

    def test_template_has_colors(self):
        templates = load_template("default")
        for t in templates:
            assert 0 <= t.red <= 255
            assert 0 <= t.green <= 255
            assert 0 <= t.blue <= 255

    def test_missing_template_raises(self):
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent_template_xyz")


class TestResolvePosition:
    def test_direct_landmark(self):
        s = TrackStructure(intro_end=32.0, first_drop=96.0)
        assert _resolve_position("intro_end", s, 128.0) == 32.0
        assert _resolve_position("first_drop", s, 128.0) == 96.0

    def test_none_landmark(self):
        s = TrackStructure()
        assert _resolve_position("first_breakdown", s, 128.0) is None

    def test_beats_before(self):
        s = TrackStructure(first_drop=96.0)
        # 64 beats at 128 BPM = 30 seconds
        result = _resolve_position("64_beats_before_first_drop", s, 128.0)
        assert result is not None
        assert abs(result - 66.0) < 0.1  # 96 - 30 = 66

    def test_beats_before_missing_landmark(self):
        s = TrackStructure()
        result = _resolve_position("64_beats_before_first_drop", s, 128.0)
        assert result is None

    def test_beats_before_clamps_to_zero(self):
        s = TrackStructure(first_drop=10.0)
        # 128 beats at 128 BPM = 60 seconds, would go negative
        result = _resolve_position("128_beats_before_first_drop", s, 128.0)
        assert result == 0.0

    def test_unknown_field_returns_none(self):
        s = TrackStructure()
        result = _resolve_position("nonexistent_field", s, 128.0)
        assert result is None


class TestGenerateCues:
    def test_generates_cues_from_structure(self):
        s = TrackStructure(
            intro_end=16.0,
            first_breakdown=64.0,
            first_drop=96.0,
            outro_start=240.0,
            confidence=1.0,
        )
        cues = generate_cues(s, bpm=128.0)
        assert len(cues) >= 3  # At least Intro, Drop, Mix Out

    def test_cue_slots_sequential(self):
        s = TrackStructure(
            intro_end=16.0,
            first_breakdown=64.0,
            first_drop=96.0,
            outro_start=240.0,
        )
        cues = generate_cues(s, bpm=128.0)
        for i, cue in enumerate(cues):
            assert cue.num == i

    def test_skips_missing_landmarks(self):
        s = TrackStructure(intro_end=16.0)  # Only intro detected
        cues = generate_cues(s, bpm=128.0)
        assert len(cues) == 1
        assert cues[0].name == "Intro"

    def test_empty_structure_no_cues(self):
        s = TrackStructure()
        cues = generate_cues(s, bpm=128.0)
        assert len(cues) == 0

    def test_cue_has_color(self):
        s = TrackStructure(intro_end=16.0)
        cues = generate_cues(s, bpm=128.0)
        assert cues[0].red == 40
        assert cues[0].green == 226
        assert cues[0].blue == 160

    def test_build_cue_position(self):
        # Build = 64 beats before first drop
        s = TrackStructure(first_drop=96.0)
        cues = generate_cues(s, bpm=128.0)
        build_cues = [c for c in cues if c.name == "Build"]
        assert len(build_cues) == 1
        # 64 beats at 128 BPM = 30 seconds. 96 - 30 = 66
        assert abs(build_cues[0].position_seconds - 66.0) < 0.1


class TestStoreCues:
    def test_stores_and_retrieves(self, tmp_path):
        db_path = tmp_path / "test.db"
        cues = [
            GeneratedCue(name="Drop", position_seconds=96.0, num=0,
                         red=255, green=90, blue=126),
        ]
        store_cues("/music/track.mp3", cues, db_path=db_path)

        # Verify stored
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT * FROM generated_cues").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][1] == "Drop"  # cue_name
        assert rows[0][2] == 96.0    # position_seconds

    def test_replaces_old_cues(self, tmp_path):
        db_path = tmp_path / "test.db"
        cues1 = [GeneratedCue("Old", 10.0, 0, 255, 0, 0)]
        cues2 = [GeneratedCue("New", 20.0, 0, 0, 255, 0)]

        store_cues("/music/track.mp3", cues1, db_path=db_path)
        store_cues("/music/track.mp3", cues2, db_path=db_path)

        import sqlite3
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT cue_name FROM generated_cues").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == "New"
