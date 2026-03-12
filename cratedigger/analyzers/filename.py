"""Analyze filenames for DJ library quality issues."""

import re
from pathlib import Path

from ..models import HealthScore

# Junk patterns commonly found in downloaded DJ tracks
JUNK_PATTERNS = [
    (r"\(\d{1,2}\)", "numbered copy suffix like (1)"),  # skip 4-digit years
    (r"_copy\b", "copy suffix"),
    (r"\[www\..+?\]", "website watermark in brackets"),
    (r"\(www\..+?\)", "website watermark in parens"),
    (r"www\.\S+", "website URL in filename"),
    (r"https?://\S+", "URL in filename"),
    (r"__+", "multiple underscores"),
    (r"\s{2,}", "multiple spaces"),
    (r"[\x00-\x1f]", "control characters"),
    (r"\ufffd", "unicode replacement character"),
]

# Patterns suggesting ripped/numbered playlists
NUMBERED_PREFIX_PATTERNS = [
    (r"^\d{1,3}\s*[-._]\s*", "numbered track prefix"),
    (r"^Track\s*\d+", "generic track numbering"),
]

# The ideal DJ filename pattern: Artist - Title
ARTIST_TITLE_PATTERN = re.compile(r"^.+\s+-\s+.+$")


def analyze_filename(file_path: Path) -> tuple[HealthScore, list[str]]:
    """
    Analyze a filename for DJ library quality issues.

    Returns:
        (score, list of issue descriptions)
    """
    stem = file_path.stem  # filename without extension
    issues: list[str] = []

    # Check for junk patterns
    for pattern, description in JUNK_PATTERNS:
        if re.search(pattern, stem, re.IGNORECASE):
            issues.append(f"Junk in filename: {description}")

    # Check for numbered prefixes
    for pattern, description in NUMBERED_PREFIX_PATTERNS:
        if re.search(pattern, stem, re.IGNORECASE):
            issues.append(f"Playlist rip: {description}")

    # Check for Artist - Title pattern
    if not ARTIST_TITLE_PATTERN.match(stem):
        issues.append("Missing 'Artist - Title' format")

    # Check for very short filenames (likely incomplete)
    if len(stem) < 5:
        issues.append("Filename too short")

    # Check for very long filenames
    if len(stem) > 200:
        issues.append("Filename excessively long")

    # Score based on issues
    if not issues:
        return HealthScore.CLEAN, issues
    elif len(issues) == 1 and issues[0] == "Missing 'Artist - Title' format":
        # Only missing the pattern is "needs attention", not messy
        return HealthScore.NEEDS_ATTENTION, issues
    elif len(issues) <= 2:
        return HealthScore.NEEDS_ATTENTION, issues
    else:
        return HealthScore.MESSY, issues
