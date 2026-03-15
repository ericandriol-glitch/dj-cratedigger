"""Summary report for completed intake runs."""

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import IntakeResult


def _count_by_source(result: IntakeResult, source: str) -> int:
    """Count tracks identified by a specific source."""
    return sum(1 for t in result.tracks if t.identified_via == source)


def _count_bpm(result: IntakeResult) -> tuple[int, int]:
    """Return (detected_count, failed_count) for BPM."""
    detected = sum(1 for t in result.tracks if t.bpm is not None)
    return detected, result.total_processed - detected


def _count_key(result: IntakeResult) -> tuple[int, int]:
    """Return (detected_count, unknown_count) for key."""
    detected = sum(1 for t in result.tracks if t.key_camelot is not None)
    return detected, result.total_processed - detected


def _build_folder_counts(result: IntakeResult) -> dict[str, int]:
    """Count approved tracks per destination folder."""
    folders: dict[str, int] = {}
    for track in result.tracks:
        if track.status in ("approved", "edited") and track.destination_folder:
            folders[track.destination_folder] = folders.get(track.destination_folder, 0) + 1
    return dict(sorted(folders.items(), key=lambda x: -x[1]))


def print_intake_report(result: IntakeResult, console: Console) -> None:
    """Print a rich summary report of the intake run.

    Args:
        result: IntakeResult from the pipeline.
        console: Rich Console instance for output.
    """
    acoustid_count = _count_by_source(result, "acoustid")
    metadata_count = _count_by_source(result, "metadata")
    filename_count = _count_by_source(result, "filename")
    manual_count = _count_by_source(result, "manual")
    bpm_ok, bpm_fail = _count_bpm(result)
    key_ok, key_unknown = _count_key(result)
    folders = _build_folder_counts(result)

    lines = Text()
    lines.append("Tracks processed:  ", style="dim")
    lines.append(f"{result.total_processed}\n", style="bold")

    # Identification breakdown
    id_parts = []
    if acoustid_count:
        id_parts.append(f"AcoustID: {acoustid_count}")
    if metadata_count:
        id_parts.append(f"metadata: {metadata_count}")
    if filename_count:
        id_parts.append(f"filename: {filename_count}")
    id_detail = f" ({', '.join(id_parts)})" if id_parts else ""
    lines.append("Identified:        ", style="dim")
    lines.append(f"{result.identified_count}{id_detail}\n", style="green")

    # Unidentified breakdown
    unid_parts = []
    if manual_count:
        unid_parts.append(f"{manual_count} manual entry")
    if result.skipped_count:
        unid_parts.append(f"{result.skipped_count} skipped")
    unid_detail = f" ({', '.join(unid_parts)})" if unid_parts else ""
    lines.append("Unidentified:      ", style="dim")
    lines.append(f"{result.unidentified_count}{unid_detail}\n", style="yellow")

    # Analysis stats
    lines.append("BPM detected:      ", style="dim")
    lines.append(f"{bpm_ok}", style="green")
    if bpm_fail:
        lines.append(f" ({bpm_fail} failed)", style="yellow")
    lines.append("\n")

    lines.append("Key detected:      ", style="dim")
    lines.append(f"{key_ok}", style="green")
    if key_unknown:
        lines.append(f" ({key_unknown} unknown)", style="yellow")
    lines.append("\n")

    # Destination folders
    if folders:
        lines.append("\nDestination folders:\n", style="bold")
        for folder, count in folders.items():
            lines.append(f"  {folder + '/':<25} {count} tracks\n", style="cyan")

    # Rekordbox XML
    if result.rekordbox_xml_path:
        lines.append(f"\nRekordbox XML:  {result.rekordbox_xml_path}\n", style="bold green")
        lines.append(
            "\nNext step: Open Rekordbox -> File -> Import -> select the XML above\n",
            style="dim",
        )

    console.print(Panel(lines, title="INTAKE COMPLETE", border_style="green"))
