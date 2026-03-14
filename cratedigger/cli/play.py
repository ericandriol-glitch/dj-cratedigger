"""Play command for DJ CrateDigger — preview tracks from your library."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import cli


@cli.command("play")
@click.argument("target", required=False, type=click.Path(resolve_path=True))
@click.option("--search", "-s", default=None, help="Search library by artist/title")
@click.option("--volume", "-v", default=80, type=click.IntRange(0, 100), help="Volume 0-100 (default: 80)")
def play(target: str | None, search: str | None, volume: int) -> None:
    """Play a track from your library.

    Play by file path:
        cratedigger play /path/to/track.mp3

    Play by search:
        cratedigger play --search "Bicep Glue"

    Controls during playback:
        [space] pause/resume  [q] quit  [+/-] volume
    """
    try:
        import pygame  # noqa: F401
    except ImportError:
        click.echo("pygame not installed. Run: pip install pygame")
        return

    from ..player import (
        format_time,
        is_playable,
        pause_track,
        play_track,
        search_library,
        search_library_db,
        stop_track,
        unpause_track,
    )

    console = Console(force_terminal=True, force_jupyter=False)
    vol = volume / 100.0

    # Resolve what to play
    filepath = None

    if target:
        filepath = Path(target)
        if not filepath.exists():
            console.print(f"  [red]File not found:[/red] {target}")
            return
        if not is_playable(filepath):
            console.print(f"  [red]Unsupported format:[/red] {filepath.suffix}")
            console.print("  Supported: .mp3, .flac, .wav, .ogg")
            return

    elif search:
        # Search DB first for richer results
        db_results = search_library_db(search)
        if db_results:
            filepath = _pick_from_db_results(db_results, search, console)
        else:
            # Fall back to filesystem search
            from ..utils.config import load_config
            config = load_config()
            lib_path = config.get("library_path")
            if lib_path:
                fs_results = search_library(search, Path(lib_path))
                if fs_results:
                    filepath = _pick_from_fs_results(fs_results, search, console)
                else:
                    console.print(f"  [yellow]No tracks found for:[/yellow] {search}")
                    return
            else:
                console.print("  [yellow]No library path configured and no tracks in DB.[/yellow]")
                console.print("  Scan your library first: cratedigger scan /path/to/music")
                return

        if filepath is None:
            return
    else:
        console.print("  [yellow]Provide a file path or use --search[/yellow]")
        console.print("  Example: cratedigger play track.mp3")
        console.print("  Example: cratedigger play --search \"Bicep\"")
        return

    # Play it
    console.print()
    console.print("  [bold magenta]DJ CrateDigger[/bold magenta] — Now Playing\n")

    state = play_track(filepath, volume=vol)
    if state is None:
        console.print("  [red]Could not play file.[/red]")
        return

    # Display track info
    meta = state.metadata
    artist = meta.artist or "Unknown Artist"
    title = meta.title or filepath.stem
    console.print(f"  [bold white]{artist}[/bold white] — [cyan]{title}[/cyan]")
    if meta.bpm:
        console.print(f"  BPM: [yellow]{meta.bpm:.0f}[/yellow]", end="")
    if meta.key:
        console.print(f"  Key: [green]{meta.key}[/green]", end="")
    if meta.genre:
        console.print(f"  Genre: [blue]{meta.genre}[/blue]", end="")
    console.print()
    console.print(f"  Duration: {format_time(state.duration)}")
    console.print(f"  Volume: {volume}%\n")
    console.print("  [dim]Controls: [space] pause/resume  [q] quit  [+/-] volume[/dim]\n")

    # Interactive control loop
    _interactive_loop(state, console)


def _pick_from_db_results(results: list[dict], query: str, console: Console) -> Path | None:
    """Let user pick from DB search results."""
    if len(results) == 1:
        return Path(results[0]["filepath"])

    # Show selection table
    console.print(f"\n  [bold]Found {len(results)} tracks matching \"{query}\":[/bold]\n")
    table = Table(show_header=True, padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Track", min_width=40)
    table.add_column("BPM", width=6)
    table.add_column("Key", width=5)
    table.add_column("Energy", width=7)

    display_results = results[:20]  # Cap at 20
    for i, r in enumerate(display_results, 1):
        name = Path(r["filepath"]).stem
        bpm = f"{r['bpm']:.0f}" if r.get("bpm") else "-"
        key = r.get("key") or "-"
        energy = f"{r['energy']:.0%}" if r.get("energy") else "-"
        table.add_row(str(i), name, bpm, key, energy)

    console.print(table)
    if len(results) > 20:
        console.print(f"  [dim]...and {len(results) - 20} more[/dim]")

    try:
        choice = click.prompt("\n  Pick a track", type=click.IntRange(1, len(display_results)))
        return Path(display_results[choice - 1]["filepath"])
    except (click.Abort, EOFError):
        return None


def _pick_from_fs_results(results: list[Path], query: str, console: Console) -> Path | None:
    """Let user pick from filesystem search results."""
    if len(results) == 1:
        return results[0]

    console.print(f"\n  [bold]Found {len(results)} tracks matching \"{query}\":[/bold]\n")
    display_results = results[:20]
    for i, f in enumerate(display_results, 1):
        console.print(f"  [dim]{i:>3}[/dim]  {f.stem}")

    if len(results) > 20:
        console.print(f"  [dim]...and {len(results) - 20} more[/dim]")

    try:
        choice = click.prompt("\n  Pick a track", type=click.IntRange(1, len(display_results)))
        return display_results[choice - 1]
    except (click.Abort, EOFError):
        return None


def _interactive_loop(state, console: Console) -> None:
    """Handle keyboard input during playback."""
    from ..player import format_time, pause_track, stop_track, unpause_track

    try:
        if sys.platform == "win32":
            import msvcrt

            while not state.stopped:
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b"q" or key == b"Q":
                        stop_track()
                        state.stopped = True
                        break
                    elif key == b" ":
                        state.paused = not state.paused
                        if state.paused:
                            pause_track()
                        else:
                            unpause_track()
                    elif key == b"+":
                        state.volume = min(1.0, state.volume + 0.1)
                    elif key == b"-":
                        state.volume = max(0.0, state.volume - 0.1)

                # Update position display
                status = "Paused" if state.paused else "Playing"
                sys.stdout.write(
                    f"\r  {status}: {format_time(state.position)} / "
                    f"{format_time(state.duration)}  Vol: {int(state.volume * 100)}%  "
                )
                sys.stdout.flush()
                import time
                time.sleep(0.2)
        else:
            # Unix: use termios for raw input
            import select
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                while not state.stopped:
                    if select.select([sys.stdin], [], [], 0.2)[0]:
                        key = sys.stdin.read(1)
                        if key in ("q", "Q", "\x03"):  # q or Ctrl+C
                            stop_track()
                            state.stopped = True
                            break
                        elif key == " ":
                            state.paused = not state.paused
                            if state.paused:
                                pause_track()
                            else:
                                unpause_track()
                        elif key == "+":
                            state.volume = min(1.0, state.volume + 0.1)
                        elif key == "-":
                            state.volume = max(0.0, state.volume - 0.1)

                    # Update display
                    status = "Paused" if state.paused else "Playing"
                    sys.stdout.write(
                        f"\r  {status}: {format_time(state.position)} / "
                        f"{format_time(state.duration)}  Vol: {int(state.volume * 100)}%  "
                    )
                    sys.stdout.flush()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    except KeyboardInterrupt:
        stop_track()
        state.stopped = True

    console.print("\n\n  [dim]Playback ended.[/dim]\n")
