"""Streaming integration commands (Spotify, YouTube) and dig-sleeping for DJ CrateDigger."""

import click
from rich.console import Console

# Import cli group to register commands
from . import cli


@cli.group()
def spotify():
    """Spotify integration commands."""
    pass


@spotify.command("sync")
def spotify_sync() -> None:
    """Sync your Spotify streaming profile (opens browser for OAuth)."""
    from ..utils.config import get_config
    from ..enrichment.spotify import (
        display_spotify_profile, save_spotify_profile, sync_spotify,
    )

    console = Console()
    console.print("\n  [bold green]DJ CrateDigger[/bold green] — Spotify Sync\n")

    try:
        config = get_config()
    except FileNotFoundError as e:
        console.print(f"  [red]{e}[/red]")
        return

    sp_config = config.get("spotify", {})
    client_id = sp_config.get("client_id")
    client_secret = sp_config.get("client_secret")

    if not client_id or not client_secret:
        console.print("  [red]Missing spotify.client_id or spotify.client_secret in config.yaml[/red]\n")
        return

    console.print("  Connecting to Spotify (browser may open for OAuth)...\n")
    profile = sync_spotify(client_id, client_secret)
    save_spotify_profile(profile)
    display_spotify_profile(profile)
    console.print("  [green]Spotify profile saved.[/green]\n")


@spotify.command("show")
def spotify_show() -> None:
    """Display your synced Spotify profile."""
    from ..enrichment.spotify import display_spotify_profile, load_spotify_profile

    console = Console()
    profile = load_spotify_profile()
    if not profile:
        console.print("\n  [yellow]No Spotify profile found. Run 'cratedigger spotify sync' first.[/yellow]\n")
        return

    display_spotify_profile(profile)


@cli.group()
def youtube():
    """YouTube Music integration commands."""
    pass


@youtube.command("sync")
def youtube_sync() -> None:
    """Sync your YouTube Music streaming profile."""
    from ..utils.config import get_config
    from ..enrichment.youtube import (
        display_youtube_profile, save_youtube_profile, sync_youtube,
    )

    console = Console()
    console.print("\n  [bold red]DJ CrateDigger[/bold red] — YouTube Music Sync\n")

    try:
        config = get_config()
    except FileNotFoundError as e:
        console.print(f"  [red]{e}[/red]")
        return

    yt_config = config.get("youtube", {})
    auth_json = yt_config.get("auth_json")
    client_id = yt_config.get("client_id")
    client_secret = yt_config.get("client_secret")

    if not auth_json:
        console.print("  [red]Missing youtube.auth_json in config.yaml[/red]\n")
        return

    console.print("  Connecting to YouTube Music...\n")
    try:
        profile = sync_youtube(auth_json, client_id=client_id, client_secret=client_secret)
    except FileNotFoundError as e:
        console.print(f"  [red]{e}[/red]")
        return

    save_youtube_profile(profile)
    display_youtube_profile(profile)
    console.print("  [green]YouTube Music profile saved.[/green]\n")


@youtube.command("show")
def youtube_show() -> None:
    """Display your synced YouTube Music profile."""
    from ..enrichment.youtube import display_youtube_profile, load_youtube_profile

    console = Console()
    profile = load_youtube_profile()
    if not profile:
        console.print("\n  [yellow]No YouTube profile found. Run 'cratedigger youtube sync' first.[/yellow]\n")
        return

    display_youtube_profile(profile)


@cli.command("dig-sleeping")
def dig_sleeping() -> None:
    """Cross-reference streaming history with your USB library to find gaps."""
    from ..digger.profile import load_profile
    from ..enrichment.spotify import load_spotify_profile
    from ..enrichment.youtube import load_youtube_profile
    from ..digger.sleeping import display_sleeping_on, find_sleeping_on

    console = Console()
    console.print("\n  [bold yellow]DJ CrateDigger[/bold yellow] — What Am I Sleeping On?\n")

    dj_profile = load_profile()
    if not dj_profile:
        console.print("  [red]No DJ profile found. Run 'cratedigger profile build <path>' first.[/red]\n")
        return

    spotify_profile = load_spotify_profile()
    youtube_profile = load_youtube_profile()

    if not spotify_profile and not youtube_profile:
        console.print("  [red]No streaming profiles found.[/red]")
        console.print("  Run 'cratedigger spotify sync' or 'cratedigger youtube sync' first.\n")
        return

    sources = []
    if spotify_profile:
        sources.append("Spotify")
    if youtube_profile:
        sources.append("YouTube Music")
    console.print(f"  Comparing library with: {', '.join(sources)}\n")

    report = find_sleeping_on(dj_profile, spotify_profile, youtube_profile)
    display_sleeping_on(report)
