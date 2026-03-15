"""Pretty-print pre-flight check results using Rich."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .checks import PreflightResult


def _format_duration(seconds: float) -> str:
    """Format seconds as 'Xh Ym'.

    Args:
        seconds: Total duration in seconds.

    Returns:
        Human-readable duration string.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable size string (e.g. '4.2 GB').
    """
    if size_bytes >= 1_073_741_824:  # 1 GB
        return f"{size_bytes / 1_073_741_824:.1f} GB"
    if size_bytes >= 1_048_576:  # 1 MB
        return f"{size_bytes / 1_048_576:.1f} MB"
    return f"{size_bytes / 1024:.1f} KB"


def _check_line(label: str, passed: bool, detail: str) -> Text:
    """Build a single check result line.

    Args:
        label: Check name.
        passed: Whether the check passed.
        detail: Detail text.

    Returns:
        Rich Text object with color coding.
    """
    mark = "[green]\u2713[/green]" if passed else "[red]\u2717[/red]"
    return Text.from_markup(f"  {mark} {label:<20s} {detail}")


def _top_genres(genre_dist: dict[str, int], limit: int = 3) -> str:
    """Format top genres as percentages.

    Args:
        genre_dist: Genre name to count mapping.
        limit: Maximum genres to show.

    Returns:
        Formatted string like 'melodic-techno 48%, deep-house 29%'.
    """
    if not genre_dist:
        return "None"
    total = sum(genre_dist.values())
    parts = []
    for genre, count in list(genre_dist.items())[:limit]:
        pct = count / total * 100
        parts.append(f"{genre} {pct:.0f}%")
    return ", ".join(parts)


def print_preflight_report(
    result: PreflightResult,
    console: Console,
    list_all: bool = False,
) -> None:
    """Print a formatted pre-flight report to the console.

    Args:
        result: The PreflightResult to display.
        console: Rich Console instance.
        list_all: If True, list all issues individually.
    """
    # Header
    console.print()
    header = f"USB PREFLIGHT: {result.path}"
    console.print(Panel(header, style="bold magenta", expand=False))

    if result.total_tracks == 0:
        console.print("  [yellow]No audio files found.[/yellow]\n")
        return

    # Filesystem info
    if result.filesystem_type:
        console.print(f"  Filesystem:        {result.filesystem_type}")

    # Summary checks
    console.print(f"  Tracks on USB:     {result.total_tracks}")

    # Corrupt / zero-byte
    corrupt_count = len(result.corrupt_files) + len(result.zero_byte_files)
    passed = corrupt_count == 0
    detail = (
        f"({len(result.corrupt_files)} corrupt, {len(result.zero_byte_files)} zero-byte)"
        if not passed
        else f"(0 corrupt, 0 zero-byte)"
    )
    console.print(_check_line("All files readable:", passed, detail))

    # BPM
    bpm_ok = len(result.missing_bpm) == 0
    bpm_have = result.total_tracks - len(result.missing_bpm) - corrupt_count
    bpm_detail = (
        f"({bpm_have}/{result.total_tracks})"
        if bpm_ok
        else f"({bpm_have}/{result.total_tracks} \u2014 {len(result.missing_bpm)} missing)"
    )
    console.print(_check_line("BPM populated:", bpm_ok, bpm_detail))

    # Key
    key_ok = len(result.missing_key) == 0
    key_have = result.total_tracks - len(result.missing_key) - corrupt_count
    key_detail = (
        f"({key_have}/{result.total_tracks})"
        if key_ok
        else f"({key_have}/{result.total_tracks} \u2014 {len(result.missing_key)} missing)"
    )
    console.print(_check_line("Key populated:", key_ok, key_detail))

    # Genre
    genre_ok = len(result.missing_genre) == 0
    genre_have = result.total_tracks - len(result.missing_genre) - corrupt_count
    genre_detail = (
        f"({genre_have}/{result.total_tracks})"
        if genre_ok
        else f"({genre_have}/{result.total_tracks} \u2014 {len(result.missing_genre)} missing)"
    )
    console.print(_check_line("Genre populated:", genre_ok, genre_detail))

    # Duplicates
    dup_ok = len(result.duplicate_filenames) == 0
    dup_detail = "None" if dup_ok else f"{len(result.duplicate_filenames)} groups"
    console.print(_check_line("Duplicate names:", dup_ok, dup_detail))

    # USB Profile
    console.print()
    console.print("  [bold]USB PROFILE:[/bold]")

    if result.bpm_range:
        bpm_lo, bpm_hi = result.bpm_range
        median_str = f" (median: {result.bpm_median:.0f})" if result.bpm_median else ""
        console.print(f"    BPM range:       {bpm_lo:.0f}-{bpm_hi:.0f}{median_str}")

    console.print(f"    Top genres:      {_top_genres(result.genre_distribution)}")
    console.print(f"    Total duration:  {_format_duration(result.total_duration_seconds)}")
    console.print(f"    Total size:      {_format_size(result.total_size_bytes)}")

    if result.key_distribution:
        console.print(f"    Key coverage:    {len(result.key_distribution)}/24 Camelot keys")

    # Rekordbox section
    if result.rekordbox_analyzed is not None:
        console.print()
        console.print("  [bold]REKORDBOX:[/bold]")
        rb_total = result.rekordbox_analyzed + (
            len(result.rekordbox_not_analyzed) if result.rekordbox_not_analyzed else 0
        )
        console.print(f"    Analyzed:        {result.rekordbox_analyzed}/{rb_total}")
        if result.tracks_with_cues is not None:
            console.print(f"    With cue points: {result.tracks_with_cues}/{rb_total}")

        if list_all and result.rekordbox_not_analyzed:
            console.print("    [yellow]Not analyzed:[/yellow]")
            for name in result.rekordbox_not_analyzed:
                console.print(f"      - {name}")

        if list_all and result.tracks_without_cues:
            console.print("    [yellow]Without cues:[/yellow]")
            for name in result.tracks_without_cues:
                console.print(f"      - {name}")

    # Issues list
    if not result.is_clean:
        console.print()
        console.print("  [bold]ISSUES:[/bold]")
        _print_issue_list(
            console, "Missing BPM", result.missing_bpm, list_all
        )
        _print_issue_list(
            console, "Missing key", result.missing_key, list_all
        )
        _print_issue_list(
            console, "Missing genre", result.missing_genre, list_all
        )
        _print_issue_list(
            console, "Corrupt file", result.corrupt_files, list_all
        )
        _print_issue_list(
            console, "Zero-byte file", result.zero_byte_files, list_all
        )
        if result.duplicate_filenames:
            for group in result.duplicate_filenames:
                names = ", ".join(str(p) for p in group)
                console.print(f"    [red]\u2717[/red] Duplicate name: {names}")

    # Verdict
    console.print()
    if result.is_clean:
        console.print(
            "  [bold green]VERDICT: All checks passed. USB is gig-ready.[/bold green]"
        )
    else:
        issues = result.issue_count
        label = "issue" if issues == 1 else "issues"
        console.print(
            f"  [bold red]VERDICT: {issues} {label} found. "
            f"Review before the gig.[/bold red]"
        )
    console.print()


def _print_issue_list(
    console: Console,
    label: str,
    paths: list,
    list_all: bool,
    max_shown: int = 5,
) -> None:
    """Print a list of issue paths, truncated unless list_all is True.

    Args:
        console: Rich Console instance.
        label: Issue category label.
        paths: List of Paths with this issue.
        list_all: Show all entries if True.
        max_shown: Max entries when list_all is False.
    """
    if not paths:
        return
    show = paths if list_all else paths[:max_shown]
    for p in show:
        console.print(f"    [red]\u2717[/red] {label}:   {p.name}")
    remaining = len(paths) - len(show)
    if remaining > 0:
        console.print(f"    ... ({remaining} more)")
