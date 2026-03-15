"""CLI command for the weekly dig session."""

import click
from rich.console import Console

from . import cli


@cli.command("dig-session")
@click.option("--styles", default=None, help="Comma-separated genre filter (default: from profile).")
@click.option("--artists", default=None, help="Comma-separated artist names to research.")
@click.option("--quick", is_flag=True, help="Skip prompts, save all at medium priority.")
@click.option("--save", is_flag=True, help="Save results to wishlist after session.")
@click.option("--no-weekly", is_flag=True, help="Skip weekly new-releases scan.")
@click.option("--no-sleeping", is_flag=True, help="Skip streaming gap analysis.")
def dig_session(
    styles: str | None,
    artists: str | None,
    quick: bool,
    save: bool,
    no_weekly: bool,
    no_sleeping: bool,
) -> None:
    """Run a weekly digging session -- find new music across all sources.

    Combines weekly new releases, artist research, and streaming gap
    analysis into a single aggregated report.

    Examples:\n
      cratedigger dig-session\n
      cratedigger dig-session --styles "Tech House,Deep House"\n
      cratedigger dig-session --artists "Solomun,Adam Port" --no-sleeping\n
      cratedigger dig-session --quick --save
    """
    from ..discovery.session import run_dig_session
    from ..discovery.session_report import print_session_report

    console = Console(force_terminal=True, force_jupyter=False)
    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] -- Weekly Dig Session\n")

    style_list = [s.strip() for s in styles.split(",")] if styles else None
    artist_list = [a.strip() for a in artists.split(",")] if artists else None

    report = run_dig_session(
        styles=style_list,
        artists=artist_list,
        quick=quick,
        include_weekly=not no_weekly,
        include_sleeping=not no_sleeping,
    )

    print_session_report(report, console)

    # Save to wishlist flow
    if save or (not quick and report.new_to_you > 0):
        _save_to_wishlist(report, console, quick)


def _save_to_wishlist(report, console: Console, quick: bool) -> None:
    """Optionally save discovered tracks to the wishlist."""
    try:
        from ..discovery.wishlist import add_track
    except ImportError:
        console.print("  [yellow]Wishlist module not available yet.[/yellow]\n")
        return

    new_tracks = [
        t for t in report.tracks
        if not t.get("owned") and not t.get("on_wishlist")
    ]
    if not new_tracks:
        return

    if quick:
        # Auto-save all at medium priority
        saved = 0
        for t in new_tracks:
            try:
                add_track(
                    artist=t.get("artist", ""),
                    title=t.get("title", ""),
                    source="dig-session",
                    priority="medium",
                    style_tag=t.get("genre", ""),
                    preview_url=t.get("preview_url", ""),
                )
                saved += 1
            except Exception:
                pass
        console.print(f"  [green]Saved {saved} tracks to wishlist.[/green]\n")
    else:
        console.print("  Save to wishlist? [bold][all/none][/bold] ", end="")
        try:
            choice = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            choice = "none"

        if choice == "all":
            saved = 0
            for t in new_tracks:
                try:
                    add_track(
                        artist=t.get("artist", ""),
                        title=t.get("title", ""),
                        source="dig-session",
                        priority="medium",
                        style_tag=t.get("genre", ""),
                        preview_url=t.get("preview_url", ""),
                    )
                    saved += 1
                except Exception:
                    pass
            console.print(f"  [green]Saved {saved} tracks to wishlist.[/green]\n")
        else:
            console.print("  [dim]Skipped wishlist save.[/dim]\n")
