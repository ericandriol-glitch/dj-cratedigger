"""Read audio metadata using mutagen with tinytag fallback."""

from pathlib import Path

import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.aiff import AIFF

from .models import TrackMetadata


def _safe_first(tags: dict, key: str) -> str | None:
    """Get first value from a tag list, or None."""
    val = tags.get(key)
    if val:
        if isinstance(val, list):
            return str(val[0]).strip() or None
        return str(val).strip() or None
    return None


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(float(str(val)))
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val))
    except (ValueError, TypeError):
        return None


def _read_mp3(path: Path) -> TrackMetadata:
    audio = MP3(path)
    try:
        tags = EasyID3(path)
    except mutagen.id3.ID3NoHeaderError:
        tags = {}

    # EasyID3 doesn't map BPM/key by default — read raw ID3 for those
    bpm = _safe_float(_safe_first(tags, "bpm"))
    key = None
    try:
        raw = audio.tags
        if raw:
            if not bpm:
                tbpm = raw.get("TBPM")
                if tbpm:
                    bpm = _safe_float(str(tbpm))
            tkey = raw.get("TKEY")
            if tkey:
                key = str(tkey).strip() or None
    except Exception:
        pass

    return TrackMetadata(
        artist=_safe_first(tags, "artist"),
        title=_safe_first(tags, "title"),
        album=_safe_first(tags, "album"),
        genre=_safe_first(tags, "genre"),
        year=_safe_int(_safe_first(tags, "date")),
        bpm=bpm,
        key=key,
        comment=None,
        duration_seconds=round(audio.info.length, 2) if audio.info else None,
        bitrate=audio.info.bitrate if audio.info else None,
        sample_rate=audio.info.sample_rate if audio.info else None,
    )


def _read_mp4(path: Path) -> TrackMetadata:
    audio = MP4(path)
    tags = audio.tags or {}

    return TrackMetadata(
        artist=_safe_first(tags, "\xa9ART"),
        title=_safe_first(tags, "\xa9nam"),
        album=_safe_first(tags, "\xa9alb"),
        genre=_safe_first(tags, "\xa9gen"),
        year=_safe_int(_safe_first(tags, "\xa9day")),
        bpm=_safe_float(_safe_first(tags, "tmpo")),
        key=None,
        comment=_safe_first(tags, "\xa9cmt"),
        duration_seconds=round(audio.info.length, 2) if audio.info else None,
        bitrate=audio.info.bitrate if audio.info else None,
        sample_rate=audio.info.sample_rate if audio.info else None,
    )


def _read_flac(path: Path) -> TrackMetadata:
    audio = FLAC(path)
    tags = audio.tags or {}

    return TrackMetadata(
        artist=_safe_first(tags, "artist"),
        title=_safe_first(tags, "title"),
        album=_safe_first(tags, "album"),
        genre=_safe_first(tags, "genre"),
        year=_safe_int(_safe_first(tags, "date")),
        bpm=_safe_float(_safe_first(tags, "bpm")),
        key=_safe_first(tags, "initialkey"),
        comment=_safe_first(tags, "comment"),
        duration_seconds=round(audio.info.length, 2) if audio.info else None,
        bitrate=audio.info.bitrate if hasattr(audio.info, "bitrate") else None,
        sample_rate=audio.info.sample_rate if audio.info else None,
    )


def _read_ogg(path: Path) -> TrackMetadata:
    audio = OggVorbis(path)
    tags = audio.tags or {}

    return TrackMetadata(
        artist=_safe_first(tags, "artist"),
        title=_safe_first(tags, "title"),
        album=_safe_first(tags, "album"),
        genre=_safe_first(tags, "genre"),
        year=_safe_int(_safe_first(tags, "date")),
        bpm=_safe_float(_safe_first(tags, "bpm")),
        key=_safe_first(tags, "initialkey"),
        comment=_safe_first(tags, "comment"),
        duration_seconds=round(audio.info.length, 2) if audio.info else None,
        bitrate=audio.info.bitrate if hasattr(audio.info, "bitrate") else None,
        sample_rate=audio.info.sample_rate if audio.info else None,
    )


def _read_aiff(path: Path) -> TrackMetadata:
    audio = AIFF(path)
    tags = audio.tags or {}

    return TrackMetadata(
        artist=_safe_first(tags, "TPE1") if tags else None,
        title=_safe_first(tags, "TIT2") if tags else None,
        album=_safe_first(tags, "TALB") if tags else None,
        genre=_safe_first(tags, "TCON") if tags else None,
        year=_safe_int(_safe_first(tags, "TDRC")) if tags else None,
        bpm=_safe_float(_safe_first(tags, "TBPM")) if tags else None,
        key=_safe_first(tags, "TKEY") if tags else None,
        comment=None,
        duration_seconds=round(audio.info.length, 2) if audio.info else None,
        bitrate=audio.info.bitrate if audio.info else None,
        sample_rate=audio.info.sample_rate if audio.info else None,
    )


def _read_fallback(path: Path) -> TrackMetadata:
    """Fallback using tinytag for formats not directly handled."""
    try:
        from tinytag import TinyTag
        tag = TinyTag.get(path)
        return TrackMetadata(
            artist=tag.artist,
            title=tag.title,
            album=tag.album,
            genre=tag.genre,
            year=_safe_int(tag.year),
            bpm=None,
            key=None,
            comment=tag.comment,
            duration_seconds=round(tag.duration, 2) if tag.duration else None,
            bitrate=_safe_int(tag.bitrate),
            sample_rate=_safe_int(tag.samplerate),
        )
    except Exception:
        return TrackMetadata()


# Map extensions to reader functions
_READERS = {
    ".mp3": _read_mp3,
    ".flac": _read_flac,
    ".m4a": _read_mp4,
    ".aac": _read_mp4,
    ".ogg": _read_ogg,
    ".aiff": _read_aiff,
    ".aif": _read_aiff,
}


def read_metadata(path: Path) -> TrackMetadata:
    """Read metadata from an audio file. Never raises — returns empty metadata on failure."""
    ext = path.suffix.lower()
    reader = _READERS.get(ext, _read_fallback)
    try:
        return reader(path)
    except Exception:
        # Fallback to tinytag if primary reader fails
        try:
            return _read_fallback(path)
        except Exception:
            return TrackMetadata()
