"""CLI command for library audit."""

from pathlib import Path

import click
from rich.console import Console

from . import cli


@cli.command("audit")
@click.argument("path", type=click.Path(exists=True))
@click.option("--report", is_flag=True, help="Export results as JSON")
@click.option(
    "--category",
    type=click.Choice(["critical", "high", "medium", "low"]),
    default=None,
    help="Show only issues of this severity",
)
@click.option("--db-path", default=None, type=click.Path(resolve_path=True),
              help="Custom database path")
def audit(path: str, report: bool, category: str | None,
          db_path: str | None) -> None:
    """Run a comprehensive health audit on your music library.

    Scans all audio files for missing metadata, corrupt files, duplicates,
    and filename inconsistencies. Assigns a health score from 0-100.
    """
    from ..audit.scanner import run_audit
    from ..audit.report import display_audit, export_audit_json

    console = Console()
    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Library Audit\n")

    db = Path(db_path) if db_path else None
    scan_path = Path(path)

    try:
        result = run_audit(scan_path, db_path=db)
    except ValueError as exc:
        console.print(f"  [red]{exc}[/red]\n")
        return

    if report:
        json_output = export_audit_json(result)
        output_file = scan_path / "audit_report.json"
        output_file.write_text(json_output, encoding="utf-8")
        console.print(f"  [green]Report saved to {output_file}[/green]\n")
        return

    display_audit(result, category=category)
