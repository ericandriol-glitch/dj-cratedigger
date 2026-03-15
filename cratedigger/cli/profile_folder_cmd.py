"""CLI command for folder profiling."""

from pathlib import Path

import click
from rich.console import Console

from . import cli


@cli.command("profile-folder")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
def profile_folder_cmd(path: str) -> None:
    """Quick profile of any folder -- BPM, genres, keys, duration.

    Scans a folder of audio files and shows BPM distribution,
    genre breakdown, key coverage, and file stats.

    Example: cratedigger profile-folder /mnt/usb/DJ-Music
    """
    from ..discovery.profile_folder import print_folder_profile, profile_folder

    console = Console(force_terminal=True, force_jupyter=False)
    folder = Path(path)

    console.print(
        f"\n  [bold magenta]DJ CrateDigger[/bold magenta]"
        f" -- Profiling [bold]{folder.name}[/bold]...\n"
    )

    prof = profile_folder(folder)
    print_folder_profile(prof, folder, console=console)
