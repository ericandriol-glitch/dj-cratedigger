"""Rich terminal display for deep artist profiles."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .artist_profile import ArtistProfile

# Social link display names
_SOCIAL_LABELS = {
    "spotify": "Spotify",
    "soundcloud": "SoundCloud",
    "bandcamp": "Bandcamp",
    "instagram": "Instagram",
    "youtube": "YouTube",
}


def print_artist_profile(profile: ArtistProfile, console: Console | None = None) -> None:
    """Render a deep artist profile to the terminal.

    Args:
        profile: The ArtistProfile to display.
        console: Rich Console instance. Creates one if not provided.
    """
    if console is None:
        console = Console(force_terminal=True, force_jupyter=False)

    console.print()

    # Header
    header = f"[bold cyan]{profile.name}[/bold cyan]"
    console.print(Panel.fit(header, border_style="magenta", title="ARTIST PROFILE"))

    # Bio
    if profile.bio:
        console.print(f"  [dim]Bio:[/dim] {profile.bio}")

    # Genres
    if profile.genres:
        console.print(f"  [dim]Genres:[/dim] [yellow]{', '.join(profile.genres[:5])}[/yellow]")

    # Popularity
    if profile.popularity is not None:
        console.print(f"  [dim]Popularity:[/dim] {profile.popularity}/100")

    console.print()

    # Labels
    if profile.labels:
        labels_str = ", ".join(profile.labels[:8])
        extra = f" (+{len(profile.labels) - 8} more)" if len(profile.labels) > 8 else ""
        console.print(f"  [bold]Labels:[/bold] [cyan]{labels_str}[/cyan]{extra}")
        console.print()

    # Discography
    if profile.releases:
        table = Table(
            title=f"Discography ({len(profile.releases)} releases)",
            show_header=True,
            box=None,
            padding=(0, 2),
        )
        table.add_column("Year", style="dim", width=6)
        table.add_column("Title", style="cyan")
        table.add_column("Type", style="yellow", width=10)

        for r in profile.releases[:15]:
            table.add_row(
                r.get("year", "") or "?",
                r.get("title", ""),
                r.get("type", ""),
            )
        console.print(table)
        if len(profile.releases) > 15:
            console.print(f"  [dim]... and {len(profile.releases) - 15} more releases[/dim]")
        console.print()

    # Top tracks (from Spotify)
    if profile.top_tracks:
        console.print("  [bold]Top Tracks:[/bold]")
        for i, t in enumerate(profile.top_tracks[:5], 1):
            album = f"  [dim]({t['album']})[/dim]" if t.get("album") else ""
            console.print(f"    {i}. [cyan]{t['title']}[/cyan]{album}")
        console.print()

    # Related artists
    if profile.related_artists:
        artists_str = ", ".join(profile.related_artists[:8])
        extra = f" (+{len(profile.related_artists) - 8} more)" if len(profile.related_artists) > 8 else ""
        console.print(f"  [bold]Related artists:[/bold]")
        console.print(f"    {artists_str}{extra}")
        console.print()

    # Social links
    console.print("  [bold]Social:[/bold]")
    for key, label in _SOCIAL_LABELS.items():
        if key in profile.social_links and profile.social_links[key]:
            console.print(f"    {label + ':':<14} [green]yes[/green]")
        else:
            console.print(f"    {label + ':':<14} [dim]--[/dim]")
    console.print()

    # Library cross-reference
    owned_style = "green" if profile.tracks_owned > 0 else "red"
    console.print(f"  [bold]In your library:[/bold] [{owned_style}]{profile.tracks_owned} tracks[/{owned_style}]")
    if profile.tracks_on_wishlist > 0:
        console.print(f"  [bold]On your wishlist:[/bold] [yellow]{profile.tracks_on_wishlist} tracks[/yellow]")

    # Sources
    if profile.sources_queried:
        console.print(f"\n  [dim]Sources: {', '.join(profile.sources_queried)}[/dim]")

    console.print()
