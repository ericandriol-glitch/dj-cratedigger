"""CLI command for USB/folder pre-flight validation."""

from pathlib import Path

import click
from rich.console import Console

from . import cli


@cli.command("preflight")
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--rekordbox",
    type=click.Path(exists=True),
    default=None,
    help="Path to Rekordbox XML export for cross-referencing.",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Enable strict checks (naming consistency, etc.).",
)
@click.option(
    "--list-all",
    is_flag=True,
    default=False,
    help="List all issues individually, not just summary counts.",
)
def preflight(path: str, rekordbox: str | None, strict: bool, list_all: bool) -> None:
    """Validate a USB stick or folder before a gig.

    Scans PATH for audio files and checks for corrupt files, missing
    metadata (BPM, key, genre), duplicate filenames, and computes
    statistics. Optionally cross-references with a Rekordbox XML export.
    """
    from ..preflight.checks import run_preflight
    from ..preflight.report import print_preflight_report

    console = Console()
    scan_path = Path(path).resolve()
    rb_path = Path(rekordbox).resolve() if rekordbox else None

    result = run_preflight(
        path=scan_path,
        rekordbox_xml=rb_path,
        strict=strict,
    )

    print_preflight_report(result, console, list_all=list_all)
