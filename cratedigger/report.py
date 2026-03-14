"""Generate health reports — terminal (rich) and markdown file."""

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import HealthScore, LibraryReport, TrackAnalysis


def _count_by_score(tracks: list[TrackAnalysis], attr: str) -> dict[HealthScore, int]:
    counts = {HealthScore.CLEAN: 0, HealthScore.NEEDS_ATTENTION: 0, HealthScore.MESSY: 0}
    for t in tracks:
        score = getattr(t, attr)
        counts[score] += 1
    return counts


def _health_color(score: float) -> str:
    if score >= 80:
        return "green"
    elif score >= 50:
        return "yellow"
    return "red"


def print_terminal_report(report: LibraryReport, verbose: bool = False) -> None:
    """Print a rich terminal report."""
    console = Console()
    console.print()

    # Header
    header = Text("DJ CrateDigger — Library Health Report", style="bold magenta")
    console.print(Panel(header, border_style="magenta"))

    # Overview
    console.print(f"\n  [bold]Scanned:[/bold] {report.scan_path}")
    console.print(
        f"  {report.audio_files:,} audio files | "
        f"{report.total_size_gb:.1f} GB | "
        f"Scanned in {report.scan_duration_seconds:.1f}s"
    )

    # Health score
    color = _health_color(report.health_score)
    console.print(f"\n  [bold]Overall Health Score:[/bold] [{color}]{report.health_score:.0f}/100[/{color}]")

    # Summary table
    fn_counts = _count_by_score(report.tracks, "filename_score")
    tag_counts = _count_by_score(report.tracks, "metadata_score")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Category", style="bold")
    table.add_column("Clean", justify="right", style="green")
    table.add_column("Needs Fix", justify="right", style="yellow")
    table.add_column("Messy", justify="right", style="red")

    table.add_row(
        "Filenames",
        str(fn_counts[HealthScore.CLEAN]),
        str(fn_counts[HealthScore.NEEDS_ATTENTION]),
        str(fn_counts[HealthScore.MESSY]),
    )
    table.add_row(
        "Metadata Tags",
        str(tag_counts[HealthScore.CLEAN]),
        str(tag_counts[HealthScore.NEEDS_ATTENTION]),
        str(tag_counts[HealthScore.MESSY]),
    )

    table.add_row(
        "Duplicates",
        "--",
        f"{len(report.duplicate_groups)} groups" if report.duplicate_groups else "0",
        "--",
    )

    console.print()
    console.print(table)

    # Top issues
    issues = _compile_top_issues(report)
    if issues:
        console.print("\n  [bold red]Top Issues:[/bold red]")
        for issue in issues:
            console.print(f"    [red]•[/red] {issue}")

    # Verbose: per-file details
    if verbose:
        console.print("\n  [bold]Per-File Details:[/bold]")
        for track in report.tracks:
            all_issues = track.filename_issues + track.metadata_issues
            if all_issues:
                console.print(f"\n    [bold]{track.file_path.name}[/bold]")
                for issue in all_issues:
                    console.print(f"      - {issue}")

    console.print()


def _compile_top_issues(report: LibraryReport) -> list[str]:
    """Compile the most important issues into summary lines."""
    issues = []

    tag_counts = _count_by_score(report.tracks, "metadata_score")
    fn_counts = _count_by_score(report.tracks, "filename_score")

    messy_tags = tag_counts[HealthScore.MESSY]
    if messy_tags:
        issues.append(f"{messy_tags} files missing artist or title tags")

    messy_fn = fn_counts[HealthScore.MESSY]
    if messy_fn:
        issues.append(f"{messy_fn} files with messy filenames (junk characters, no artist-title format)")

    if report.duplicate_groups:
        dup_files = sum(len(g) for g in report.duplicate_groups)
        issues.append(f"{len(report.duplicate_groups)} potential duplicate groups ({dup_files} files)")

    # Count specific missing tags
    missing_bpm = sum(1 for t in report.tracks if t.metadata.bpm is None)
    if missing_bpm:
        issues.append(f"{missing_bpm} files missing BPM tag")

    missing_genre = sum(1 for t in report.tracks if not t.metadata.genre)
    if missing_genre:
        issues.append(f"{missing_genre} files missing genre tag")

    missing_key = sum(1 for t in report.tracks if not t.metadata.key)
    if missing_key:
        issues.append(f"{missing_key} files missing key tag")

    return issues


def save_markdown_report(report: LibraryReport, output_path: Path) -> None:
    """Save a detailed markdown report to disk."""
    lines = [
        "# DJ CrateDigger — Library Health Report",
        "",
        "## Library Overview",
        "",
        f"- **Scanned:** `{report.scan_path}`",
        f"- **Audio files:** {report.audio_files:,}",
        f"- **Total size:** {report.total_size_gb:.1f} GB",
        f"- **Scan duration:** {report.scan_duration_seconds:.1f}s",
        f"- **Health score:** {report.health_score:.0f}/100",
        "",
    ]

    # Format breakdown
    format_counts: dict[str, int] = {}
    for t in report.tracks:
        fmt = t.audio_format
        format_counts[fmt] = format_counts.get(fmt, 0) + 1
    if format_counts:
        lines.append("### File Formats")
        lines.append("")
        for fmt, count in sorted(format_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- {fmt}: {count}")
        lines.append("")

    # Filename issues
    fn_issues = [t for t in report.tracks if t.filename_issues]
    if fn_issues:
        lines.append(f"## Filename Issues ({len(fn_issues)} files)")
        lines.append("")
        for t in fn_issues:
            lines.append(f"### `{t.file_path.name}`")
            for issue in t.filename_issues:
                lines.append(f"- {issue}")
            lines.append("")

    # Metadata gaps
    tag_issues = [t for t in report.tracks if t.metadata_issues]
    if tag_issues:
        lines.append(f"## Metadata Gaps ({len(tag_issues)} files)")
        lines.append("")
        for t in tag_issues:
            lines.append(f"### `{t.file_path.name}`")
            for issue in t.metadata_issues:
                lines.append(f"- {issue}")
            lines.append("")

    # Duplicates
    if report.duplicate_groups:
        lines.append(f"## Duplicates Found ({len(report.duplicate_groups)} groups)")
        lines.append("")
        for i, group in enumerate(report.duplicate_groups, 1):
            lines.append(f"### Group {i}")
            for t in group:
                lines.append(
                    f"- `{t.file_path.name}` "
                    f"({t.file_size_mb:.1f} MB, {t.audio_format})"
                )
            lines.append("")

    # Recommendations
    top_issues = _compile_top_issues(report)
    if top_issues:
        lines.append("## Recommendations")
        lines.append("")
        for issue in top_issues:
            lines.append(f"- {issue}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by DJ CrateDigger AI*")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
