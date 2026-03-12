"""Parse DJ filenames to extract artist, title, and other info."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ParsedFilename:
    artist: Optional[str] = None
    title: Optional[str] = None
    bitrate: Optional[int] = None
    year: Optional[int] = None
    original_stem: str = ""


# Match patterns like [320], [192], [128] at end of stem
BITRATE_PATTERN = re.compile(r"\s*\[(\d{2,3})\]\s*$")

# Match year in parens like (1995), (2021)
YEAR_PATTERN = re.compile(r"\s*\((\d{4})\)\s*")

# Artist - Title separator (the DJ standard)
SEPARATOR = re.compile(r"\s+-\s+")


def parse_filename(file_path: Path) -> ParsedFilename:
    """
    Parse a DJ filename into structured components.

    Handles patterns like:
        "Disclosure - Latch (Club Mix) [320].mp3"
        "Armin - Blue Fear (Original Extended Version) (1997) [320].mp3"
        "Abba - Dancing Queen [128].mp3"
    """
    stem = file_path.stem
    result = ParsedFilename(original_stem=stem)

    working = stem

    # Extract bitrate suffix [320]
    m = BITRATE_PATTERN.search(working)
    if m:
        result.bitrate = int(m.group(1))
        working = working[:m.start()]

    # Extract year (1995) — but only if it looks like a year, not part of the title
    m = YEAR_PATTERN.search(working)
    if m:
        year_val = int(m.group(1))
        if 1950 <= year_val <= 2030:
            result.year = year_val
            working = working[:m.start()] + working[m.end():]

    # Split on " - " to get artist and title
    parts = SEPARATOR.split(working.strip(), maxsplit=1)
    if len(parts) == 2:
        result.artist = parts[0].strip()
        result.title = parts[1].strip()
    elif len(parts) == 1:
        # No separator — the whole thing is the title (artist unknown)
        result.title = parts[0].strip()

    return result
