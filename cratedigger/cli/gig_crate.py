"""CLI command for gig crate builder."""

from pathlib import Path

import click
from rich.console import Console

from . import cli


@cli.command("gig-crate")
@click.option("--name", default="", help="Gig name")
@click.option("--vibe", default=None, help="Comma-separated genre filter")
@click.option("--bpm", default=None, help="BPM range, e.g., '122-130'")
@click.option("--energy-range", default=None, help="Energy range, e.g., '0.3-0.9'")
@click.option("--size", default=80, type=int, help="Target crate size")
@click.option("--export", "export_path", type=click.Path(), default=None,
              help="Export as Rekordbox XML")
@click.option("--list", "list_crates_flag", is_flag=True, help="List saved crates")
@click.option("--db-path", default=None, type=click.Path(resolve_path=True),
              help="Custom database path")
def gig_crate(
    name: str,
    vibe: str | None,
    bpm: str | None,
    energy_range: str | None,
    size: int,
    export_path: str | None,
    list_crates_flag: bool,
    db_path: str | None,
) -> None:
    """Build a curated track crate for a gig."""
    from ..gig.crate import (
        build_crate,
        export_crate,
        list_crates,
        load_crate,
        save_crate,
    )
    from ..gig.crate_report import print_crate_report

    console = Console()
    db = Path(db_path) if db_path else None

    # List mode
    if list_crates_flag:
        crates = list_crates(db_path=db)
        if not crates:
            console.print("\n  [yellow]No saved crates.[/yellow]\n")
            return
        console.print("\n  [bold magenta]Saved Crates:[/bold magenta]\n")
        for c in crates:
            console.print(f"  {c['name']} — {c['track_count']} tracks (updated {c['updated_at']})")
        console.print()
        return

    if not name:
        console.print("\n  [red]--name is required (unless using --list).[/red]\n")
        return

    # Parse filters
    vibe_list = [v.strip() for v in vibe.split(",")] if vibe else None

    bpm_range = None
    if bpm:
        parts = bpm.split("-")
        if len(parts) == 2:
            bpm_range = (float(parts[0]), float(parts[1]))

    energy_tuple = None
    if energy_range:
        parts = energy_range.split("-")
        if len(parts) == 2:
            energy_tuple = (float(parts[0]), float(parts[1]))

    # Build or load
    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Crate Builder\n")

    crate = build_crate(
        name=name,
        vibe=vibe_list,
        bpm_range=bpm_range,
        energy_range=energy_tuple,
        size=size,
        db_path=db,
    )

    if not crate.tracks:
        console.print("  [yellow]No tracks matched your filters.[/yellow]\n")
        return

    # Save the crate
    save_crate(crate, db_path=db)

    # Print report
    print_crate_report(crate, console)

    # Export if requested
    if export_path:
        out = Path(export_path)
        export_crate(crate, out)
        console.print(f"  [green]Exported to {out}[/green]\n")
