"""Fix missing metadata tags by extracting info from filenames."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mutagen.flac import FLAC
from mutagen.id3 import ID3, TBPM, TCON, TDRC, TIT2, TKEY, TPE1, ID3NoHeaderError

# TCON = Content type (genre)
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis

from ..metadata import read_metadata
from .parse_filename import parse_filename


@dataclass
class TagFix:
    file_path: Path
    field: str
    old_value: Optional[str]
    new_value: str


def plan_tag_fixes(audio_files: list[Path]) -> list[TagFix]:
    """
    Plan tag fixes by comparing existing tags to what we can extract from filenames.
    Does NOT modify any files — just returns a list of proposed changes.
    """
    fixes: list[TagFix] = []

    for path in audio_files:
        meta = read_metadata(path)
        parsed = parse_filename(path)

        # Fix missing artist
        if not meta.artist or meta.artist.strip().lower() in (
            "unknown", "unknown artist", ""
        ):
            if parsed.artist:
                fixes.append(TagFix(
                    file_path=path,
                    field="artist",
                    old_value=meta.artist,
                    new_value=parsed.artist,
                ))

        # Fix missing title
        if not meta.title or meta.title.strip().lower() in (
            "unknown", "unknown title", "untitled", "track", "audio track", ""
        ):
            if parsed.title:
                fixes.append(TagFix(
                    file_path=path,
                    field="title",
                    old_value=meta.title,
                    new_value=parsed.title,
                ))

        # Fix missing year
        if meta.year is None and parsed.year:
            fixes.append(TagFix(
                file_path=path,
                field="year",
                old_value=None,
                new_value=str(parsed.year),
            ))

    return fixes


def apply_tag_fixes(fixes: list[TagFix]) -> tuple[int, list[str]]:
    """
    Apply tag fixes to files.

    Returns:
        (success_count, list of error messages)
    """
    success = 0
    errors: list[str] = []

    # Group fixes by file
    fixes_by_file: dict[Path, list[TagFix]] = {}
    for fix in fixes:
        fixes_by_file.setdefault(fix.file_path, []).append(fix)

    for path, file_fixes in fixes_by_file.items():
        try:
            _apply_fixes_to_file(path, file_fixes)
            success += 1
        except Exception as e:
            errors.append(f"{path.name}: {e}")

    return success, errors


def _apply_fixes_to_file(path: Path, fixes: list[TagFix]) -> None:
    """Apply a list of tag fixes to a single file."""
    ext = path.suffix.lower()

    if ext == ".mp3":
        _apply_mp3(path, fixes)
    elif ext in (".m4a", ".aac"):
        _apply_mp4(path, fixes)
    elif ext == ".flac":
        _apply_flac(path, fixes)
    elif ext == ".ogg":
        _apply_ogg(path, fixes)
    else:
        raise ValueError(f"Tag writing not supported for {ext}")


# Field mappings for each format
_MP3_FIELDS = {
    "artist": lambda v: TPE1(encoding=3, text=[v]),
    "title": lambda v: TIT2(encoding=3, text=[v]),
    "year": lambda v: TDRC(encoding=3, text=[v]),
    "bpm": lambda v: TBPM(encoding=3, text=[v]),
    "key": lambda v: TKEY(encoding=3, text=[v]),
    "genre": lambda v: TCON(encoding=3, text=[v]),
}

_MP4_FIELDS = {
    "artist": "\xa9ART",
    "title": "\xa9nam",
    "year": "\xa9day",
    "bpm": "tmpo",
    "genre": "\xa9gen",
}

_VORBIS_FIELDS = {
    "artist": "artist",
    "title": "title",
    "year": "date",
    "bpm": "bpm",
    "key": "initialkey",
    "genre": "genre",
}


def _apply_mp3(path: Path, fixes: list[TagFix]) -> None:
    try:
        tags = ID3(path)
    except ID3NoHeaderError:
        tags = ID3()

    for fix in fixes:
        factory = _MP3_FIELDS.get(fix.field)
        if factory:
            tags.add(factory(fix.new_value))

    tags.save(path)


def _apply_mp4(path: Path, fixes: list[TagFix]) -> None:
    audio = MP4(path)
    if audio.tags is None:
        audio.add_tags()

    for fix in fixes:
        key = _MP4_FIELDS.get(fix.field)
        if key:
            audio.tags[key] = [fix.new_value]

    audio.save()


def _apply_flac(path: Path, fixes: list[TagFix]) -> None:
    audio = FLAC(path)

    for fix in fixes:
        key = _VORBIS_FIELDS.get(fix.field)
        if key:
            audio[key] = fix.new_value

    audio.save()


def _apply_ogg(path: Path, fixes: list[TagFix]) -> None:
    audio = OggVorbis(path)

    for fix in fixes:
        key = _VORBIS_FIELDS.get(fix.field)
        if key:
            audio[key] = fix.new_value

    audio.save()
