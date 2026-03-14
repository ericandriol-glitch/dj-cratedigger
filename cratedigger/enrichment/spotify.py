"""Spotify connector — sync streaming profile for cross-referencing."""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cratedigger.utils.db import get_connection

logger = logging.getLogger(__name__)
console = Console()

SCOPES = "user-top-read"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
CACHE_PATH = Path.home() / ".cratedigger" / ".spotify_cache"


@dataclass
class SpotifyProfile:
    """Aggregated Spotify streaming profile."""

    top_artists_short: list[dict] = field(default_factory=list)
    top_artists_medium: list[dict] = field(default_factory=list)
    top_artists_long: list[dict] = field(default_factory=list)
    top_tracks: list[dict] = field(default_factory=list)
    saved_tracks: list[dict] = field(default_factory=list)
    followed_artists: list[dict] = field(default_factory=list)
    synced_at: str = ""


def sync_spotify(client_id: str, client_secret: str) -> SpotifyProfile:
    """Run OAuth flow and pull streaming data from Spotify.

    Opens a browser for OAuth consent on first run. Token is cached
    at ~/.cratedigger/.spotify_cache for subsequent calls.
    """
    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        cache_path=str(CACHE_PATH),
    )
    sp = spotipy.Spotify(auth_manager=auth)

    profile = SpotifyProfile(synced_at=datetime.now(timezone.utc).isoformat())

    # Top artists by time range
    for time_range, attr in [
        ("short_term", "top_artists_short"),
        ("medium_term", "top_artists_medium"),
        ("long_term", "top_artists_long"),
    ]:
        results = sp.current_user_top_artists(limit=50, time_range=time_range)
        items = [
            {"name": a["name"], "genres": a.get("genres", []),
             "popularity": a.get("popularity", 0)}
            for a in results.get("items", [])
        ]
        setattr(profile, attr, items)

    # Top tracks (medium term)
    results = sp.current_user_top_tracks(limit=50, time_range="medium_term")
    profile.top_tracks = [
        {"title": t["name"], "artist": t["artists"][0]["name"],
         "album": t["album"]["name"]}
        for t in results.get("items", [])
    ]

    # Saved / liked tracks (requires user-library-read scope, may not be available)
    saved = []
    try:
        offset = 0
        while offset < 500:
            results = sp.current_user_saved_tracks(limit=50, offset=offset)
            items = results.get("items", [])
            if not items:
                break
            for item in items:
                t = item["track"]
                saved.append({
                    "title": t["name"],
                    "artist": t["artists"][0]["name"],
                    "album": t["album"]["name"],
                })
            offset += 50
    except Exception as e:
        logger.warning("Could not fetch saved tracks: %s", e)
    profile.saved_tracks = saved

    # Followed artists (requires user-follow-read scope, may not be available)
    followed = []
    try:
        after = None
        while True:
            results = sp.current_user_followed_artists(limit=50, after=after)
            artists_data = results.get("artists", {})
            items = artists_data.get("items", [])
            if not items:
                break
            for a in items:
                followed.append({
                    "name": a["name"],
                    "genres": a.get("genres", []),
                })
            after = items[-1]["id"]
            if not artists_data.get("next"):
                break
    except Exception as e:
        logger.warning("Could not fetch followed artists: %s", e)
    profile.followed_artists = followed

    return profile


def save_spotify_profile(profile: SpotifyProfile, db_path: Path | None = None) -> None:
    """Store Spotify profile as JSON in the database."""
    conn = get_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    profile_json = json.dumps(asdict(profile), indent=2)
    conn.execute(
        "INSERT OR REPLACE INTO spotify_profile (id, profile_json, updated_at) VALUES (1, ?, ?)",
        (profile_json, now),
    )
    conn.commit()
    conn.close()


def load_spotify_profile(db_path: Path | None = None) -> SpotifyProfile | None:
    """Load Spotify profile from the database."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT profile_json FROM spotify_profile WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return None
    data = json.loads(row[0])
    return SpotifyProfile(**data)


def display_spotify_profile(profile: SpotifyProfile) -> None:
    """Render Spotify profile with Rich terminal output."""
    console.print()
    console.print(Panel.fit(
        "[bold green]Spotify[/bold green] — Streaming Profile",
        border_style="green",
    ))

    console.print(f"\n  [bold]Synced:[/bold] {profile.synced_at}")
    console.print(f"  [bold]Saved tracks:[/bold] {len(profile.saved_tracks)}")
    console.print(f"  [bold]Followed artists:[/bold] {len(profile.followed_artists)}")

    # Top artists (medium term)
    if profile.top_artists_medium:
        console.print("\n  [bold]Top Artists (last 6 months):[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("#", style="dim", justify="right")
        table.add_column("Artist", style="cyan")
        table.add_column("Genres", style="dim", max_width=40)
        for i, a in enumerate(profile.top_artists_medium[:15], 1):
            genres = ", ".join(a.get("genres", [])[:3])
            table.add_row(str(i), a["name"], genres)
        console.print(table)

    # Top tracks
    if profile.top_tracks:
        console.print("\n  [bold]Top Tracks (last 6 months):[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("#", style="dim", justify="right")
        table.add_column("Track", style="cyan")
        table.add_column("Artist", style="green")
        for i, t in enumerate(profile.top_tracks[:15], 1):
            table.add_row(str(i), t["title"], t["artist"])
        console.print(table)

    console.print()
