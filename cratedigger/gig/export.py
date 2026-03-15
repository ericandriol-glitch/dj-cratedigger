"""Export a saved crate to USB drive for gig use."""

import logging
import shutil
from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from .crate import export_crate, load_crate
from .rekordbox_parser import parse_rekordbox_xml
from .preflight import display_preflight, run_preflight

logger = logging.getLogger(__name__)
console = Console()


def export_crate_to_usb(
    crate_name: str,
    usb_path: Path,
    generate_xml: bool = True,
    run_preflight_check: bool = True,
    db_path: Path | None = None,
) -> dict:
    """Export a saved crate to USB: copy tracks + Rekordbox XML + preflight.

    Steps:
        1. Load crate from database by name.
        2. Copy audio files to USB (skip existing/same-size files).
        3. Generate Rekordbox XML pointing to USB paths.
        4. Optionally run preflight readiness check on the XML.

    Args:
        crate_name: Name of a previously saved crate.
        usb_path: Root path of the USB drive.
        generate_xml: Whether to write a Rekordbox XML file.
        run_preflight_check: Whether to run preflight after export.
        db_path: Optional custom database path.

    Returns:
        Dict with keys: tracks_copied, tracks_skipped, total_bytes,
        xml_path (or None), preflight_report (or None).

    Raises:
        FileNotFoundError: If usb_path does not exist.
        ValueError: If the crate is not found.
    """
    usb_path = Path(usb_path).resolve()
    if not usb_path.exists():
        raise FileNotFoundError(f"USB path does not exist: {usb_path}")

    # 1. Load crate
    crate = load_crate(crate_name, db_path=db_path)
    if crate is None:
        raise ValueError(f"Crate '{crate_name}' not found. Use gig-crate --list to see saved crates.")

    if not crate.tracks:
        return {
            "tracks_copied": 0,
            "tracks_skipped": 0,
            "total_bytes": 0,
            "xml_path": None,
            "preflight_report": None,
        }

    # 2. Copy tracks to USB
    music_dir = usb_path / "Music" / crate_name
    music_dir.mkdir(parents=True, exist_ok=True)

    tracks_copied = 0
    tracks_skipped = 0
    total_bytes = 0
    # Map track index -> USB destination path (only for tracks that made it)
    usb_path_map: dict[int, Path] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task("Copying tracks to USB...", total=len(crate.tracks))

        for idx, track in enumerate(crate.tracks):
            src = Path(track.filepath)
            dst = music_dir / src.name

            if not src.exists():
                logger.warning("Source file missing, skipping: %s", src)
                tracks_skipped += 1
                progress.advance(task)
                continue

            src_size = src.stat().st_size

            # Skip if destination exists and is the same size
            if dst.exists() and dst.stat().st_size == src_size:
                tracks_skipped += 1
                usb_path_map[idx] = dst
                progress.advance(task)
                continue

            shutil.copy2(str(src), str(dst))
            tracks_copied += 1
            total_bytes += src_size
            usb_path_map[idx] = dst
            progress.advance(task)

    # 3. Generate Rekordbox XML
    xml_path: Path | None = None
    if generate_xml and usb_path_map:
        # Temporarily patch filepaths to USB locations
        original_paths = {i: crate.tracks[i].filepath for i in usb_path_map}
        for idx, usb_fp in usb_path_map.items():
            crate.tracks[idx].filepath = str(usb_fp)

        xml_out = usb_path / f"{crate_name}.xml"
        xml_path = export_crate(crate, xml_out)

        # Restore original paths
        for idx, orig in original_paths.items():
            crate.tracks[idx].filepath = orig

    # 4. Run preflight
    preflight_report = None
    if run_preflight_check and xml_path and xml_path.exists():
        try:
            library = parse_rekordbox_xml(xml_path)
            playlists = library.playlists
            if playlists:
                first_playlist = next(iter(playlists.keys()))
                preflight_report = run_preflight(library, first_playlist)
        except Exception as exc:
            logger.warning("Preflight check failed: %s", exc)

    return {
        "tracks_copied": tracks_copied,
        "tracks_skipped": tracks_skipped,
        "total_bytes": total_bytes,
        "xml_path": xml_path,
        "preflight_report": preflight_report,
    }
