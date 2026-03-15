"""Rich terminal output for library audit results."""

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .scanner import AuditResult

console = Console()

# Severity display config
SEVERITY_CONFIG = {
    "critical": {"label": "CRITICAL", "color": "red", "icon": "X"},
    "high": {"label": "HIGH", "color": "dark_orange", "icon": "!"},
    "medium": {"label": "MEDIUM", "color": "yellow", "icon": "~"},
    "low": {"label": "LOW", "color": "dim", "icon": "-"},
}


def _health_score_style(score: int) -> str:
    """Return rich style based on health score."""
    if score >= 80:
        return "bold green"
    if score >= 60:
        return "bold yellow"
    if score >= 40:
        return "bold dark_orange"
    return "bold red"


def _health_verdict(score: int) -> str:
    """Return a DJ-friendly verdict based on health score."""
    if score >= 90:
        return "Gig-ready. Your library is clean."
    if score >= 70:
        return "Mostly clean. Fix the high-priority issues before your next gig."
    if score >= 50:
        return "Needs attention. Several issues could cause problems in the booth."
    if score >= 30:
        return "Messy. Significant cleanup needed before this is reliable."
    return "Critical state. Major issues that will cause problems during a set."


def _issue_table(issues: list[dict], severity: str, max_rows: int = 25) -> Table:
    """Build a rich table for a severity category."""
    cfg = SEVERITY_CONFIG[severity]
    table = Table(
        title=f"{cfg['label']} ({len(issues)} issues)",
        title_style=cfg["color"],
        show_lines=False,
        expand=False,
    )
    table.add_column("#", style="dim", justify="right", width=4)
    table.add_column("File", style="cyan", max_width=50)
    table.add_column("Issue", style=cfg["color"], max_width=45)

    for i, issue in enumerate(issues[:max_rows], 1):
        filepath = Path(issue["path"]).name
        table.add_row(str(i), filepath, issue["issue"])

    if len(issues) > max_rows:
        table.add_row("", f"... and {len(issues) - max_rows} more", "")

    return table


def display_audit(result: AuditResult, category: str | None = None) -> None:
    """Display audit results with rich terminal formatting.

    Args:
        result: The AuditResult from the scanner.
        category: If set, only show issues for this severity level.
    """
    # Header
    console.print()
    header = Text()
    header.append("LIBRARY AUDIT", style="bold magenta")
    header.append(f"  {result.path}", style="dim")
    console.print(Panel(header, border_style="magenta", expand=False))

    # Health score
    score_style = _health_score_style(result.health_score)
    console.print()
    console.print(f"  [{score_style}]Health Score: {result.health_score}/100[/{score_style}]")
    console.print(f"  Tracks scanned: {result.total_tracks}")
    console.print()

    # Summary counts
    counts = {
        "critical": len(result.critical),
        "high": len(result.high),
        "medium": len(result.medium),
        "low": len(result.low),
    }
    total_issues = sum(counts.values())
    console.print(f"  Total issues: {total_issues}")
    for sev, count in counts.items():
        cfg = SEVERITY_CONFIG[sev]
        if count > 0:
            console.print(f"    [{cfg['color']}]{cfg['icon']} {cfg['label']}: {count}[/{cfg['color']}]")
        else:
            console.print(f"    [dim]{cfg['icon']} {cfg['label']}: 0[/dim]")

    # Detail tables
    severity_map = {
        "critical": result.critical,
        "high": result.high,
        "medium": result.medium,
        "low": result.low,
    }

    if category:
        issues = severity_map.get(category, [])
        if issues:
            console.print()
            console.print(_issue_table(issues, category))
        else:
            console.print(f"\n  [dim]No {category} issues found.[/dim]")
    else:
        for sev in ["critical", "high", "medium", "low"]:
            issues = severity_map[sev]
            if issues:
                console.print()
                console.print(_issue_table(issues, sev))

    # Verdict
    console.print()
    verdict = _health_verdict(result.health_score)
    console.print(f"  [bold]{verdict}[/bold]")
    console.print()


def export_audit_json(result: AuditResult) -> str:
    """Export audit result as JSON string.

    Args:
        result: The AuditResult to export.

    Returns:
        JSON string representation of the audit.
    """
    data = {
        "path": str(result.path),
        "total_tracks": result.total_tracks,
        "health_score": result.health_score,
        "summary": {
            "critical": len(result.critical),
            "high": len(result.high),
            "medium": len(result.medium),
            "low": len(result.low),
        },
        "critical": result.critical,
        "high": result.high,
        "medium": result.medium,
        "low": result.low,
    }
    return json.dumps(data, indent=2)
