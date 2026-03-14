"""Analyze metadata tag completeness and quality."""

from ..models import HealthScore, TrackMetadata

# Generic/placeholder values that indicate missing real data
GENERIC_VALUES = {
    "unknown", "unknown artist", "unknown title", "untitled",
    "track", "track 1", "audio track", "audio", "various",
    "various artists", "va", "n/a", "none", "null", "",
}


def _is_generic(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() in GENERIC_VALUES


def analyze_tags(metadata: TrackMetadata) -> tuple[HealthScore, list[str]]:
    """
    Analyze metadata tags for completeness and quality.

    Returns:
        (score, list of issue descriptions)
    """
    issues: list[str] = []
    critical_missing = 0

    # Critical tags — artist and title
    if _is_generic(metadata.artist):
        issues.append("Missing or generic artist tag")
        critical_missing += 1

    if _is_generic(metadata.title):
        issues.append("Missing or generic title tag")
        critical_missing += 1

    # Useful tags — not critical but valuable for DJ workflow
    if _is_generic(metadata.genre):
        issues.append("Missing genre tag")

    if metadata.bpm is None:
        issues.append("Missing BPM tag")

    if metadata.key is None:
        issues.append("Missing key tag")

    if metadata.year is None:
        issues.append("Missing year tag")

    if _is_generic(metadata.album):
        issues.append("Missing album tag")

    # Score
    if critical_missing > 0:
        return HealthScore.MESSY, issues
    elif len(issues) == 0:
        return HealthScore.CLEAN, issues
    elif len(issues) <= 2:
        return HealthScore.NEEDS_ATTENTION, issues
    else:
        return HealthScore.NEEDS_ATTENTION, issues
