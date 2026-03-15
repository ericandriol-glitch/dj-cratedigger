"""CLI command for exporting a crate to USB."""

from pathlib import Path

import click
from rich.console import Console

from . import cli


@cli.command("gig-export")
@click.option("--crate", required=True, help="Name of the saved crate to export")
@click.option("--usb", required=True, type=click.Path(), help="Path to USB drive root")
@click.option("--no-preflight", is_flag=True, help="Skip preflight readiness check")
@click.option("--no-xml", is_flag=True, help="Skip Rekordbox XML generation")
@click.option("--db-path", default=None, type=click.Path(resolve_path=True),
              help="Custom database path")
def gig_export(crate: str, usb: str, no_preflight: bool, no_xml: bool,
               db_path: str | None) -> None:
    """Export a saved crate to USB drive for a gig.

    Copies audio files, generates Rekordbox XML, and runs preflight checks.
    """
    from ..gig.export import export_crate_to_usb
    from ..gig.preflight import display_preflight

    console = Console()
    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Gig Export\n")

    db = Path(db_path) if db_path else None
    usb_path = Path(usb)

    try:
        result = export_crate_to_usb(
            crate_name=crate,
            usb_path=usb_path,
            generate_xml=not no_xml,
            run_preflight_check=not no_preflight,
            db_path=db,
        )
    except FileNotFoundError as exc:
        console.print(f"  [red]{exc}[/red]\n")
        return
    except ValueError as exc:
        console.print(f"  [red]{exc}[/red]\n")
        return

    # Display results
    total_mb = result["total_bytes"] / (1024 * 1024)
    console.print(f"  [green]Copied:[/green]  {result['tracks_copied']} tracks ({total_mb:.1f} MB)")
    console.print(f"  [yellow]Skipped:[/yellow] {result['tracks_skipped']} tracks (already on USB)")

    if result["xml_path"]:
        console.print(f"  [green]XML:[/green]     {result['xml_path']}")

    if result["preflight_report"]:
        console.print()
        display_preflight(result["preflight_report"])

    console.print("  [bold green]Export complete.[/bold green]\n")
