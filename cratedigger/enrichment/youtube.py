"""YouTube Music connector — sync streaming profile for cross-referencing.

Uses the YouTube Data API v3 directly (not ytmusicapi's internal API)
for reliable OAuth-authenticated access.
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from cratedigger.utils.db import get_connection

logger = logging.getLogger(__name__)
console = Console()

YT_API_BASE = "https://www.googleapis.com/youtube/v3"


@dataclass
class YouTubeProfile:
    """Aggregated YouTube Music streaming profile."""

    liked_songs: list[dict] = field(default_factory=list)
    playlists: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    synced_at: str = ""


def _get_token(auth_json_path: str, client_id: str | None, client_secret: str | None) -> str:
    """Load and refresh the OAuth token if needed."""
    path = Path(auth_json_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(
            f"YouTube auth file not found: {path}\n"
            f"Run the ytmusicapi oauth flow first (see README)."
        )
    data = json.loads(path.read_text())
    token = data["access_token"]

    # Check if expired and refresh
    import time
    if data.get("expires_at", 0) < time.time() and data.get("refresh_token") and client_id and client_secret:
        resp = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": data["refresh_token"],
            "grant_type": "refresh_token",
        }).json()
        if "access_token" in resp:
            token = resp["access_token"]
            data["access_token"] = token
            data["expires_at"] = int(time.time()) + resp.get("expires_in", 3600)
            path.write_text(json.dumps(data, indent=2))
            logger.info("Refreshed YouTube OAuth token")
        else:
            logger.warning("Token refresh failed: %s", resp)

    return token


def _yt_get(token: str, endpoint: str, params: dict) -> dict:
    """Make an authenticated GET to YouTube Data API v3."""
    resp = requests.get(
        f"{YT_API_BASE}/{endpoint}",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_artist_title(snippet: dict) -> tuple[str, str]:
    """Best-effort extraction of artist and title from a YouTube video snippet."""
    title = snippet.get("title", "")
    channel = snippet.get("videoOwnerChannelTitle", snippet.get("channelTitle", ""))
    # Strip " - Topic" suffix from auto-generated music channels
    channel = channel.removesuffix(" - Topic")

    # Try to split "Artist - Title" format
    if " - " in title:
        parts = title.split(" - ", 1)
        return parts[0].strip(), parts[1].strip()

    return channel, title


def sync_youtube(
    auth_json_path: str,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> YouTubeProfile:
    """Pull data from YouTube via the Data API v3.

    Fetches liked videos (filtered for music) and playlists.
    """
    token = _get_token(auth_json_path, client_id, client_secret)
    profile = YouTubeProfile(synced_at=datetime.now(timezone.utc).isoformat())

    # Liked videos (up to 200)
    try:
        liked = []
        page_token = None
        while len(liked) < 200:
            params = {"part": "snippet", "myRating": "like", "maxResults": 50,
                      "videoCategoryId": "10"}  # category 10 = Music
            if page_token:
                params["pageToken"] = page_token
            data = _yt_get(token, "videos", params)
            for item in data.get("items", []):
                snippet = item["snippet"]
                artist, title = _extract_artist_title(snippet)
                liked.append({
                    "title": title,
                    "artist": artist,
                    "album": "",
                })
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        profile.liked_songs = liked
    except Exception as e:
        logger.warning("Failed to fetch liked videos: %s", e)

    # Playlists
    try:
        params = {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}
        data = _yt_get(token, "playlists", params)
        profile.playlists = [
            {
                "name": item["snippet"]["title"],
                "track_count": item["contentDetails"].get("itemCount", 0),
            }
            for item in data.get("items", [])
        ]
    except Exception as e:
        logger.warning("Failed to fetch playlists: %s", e)

    # Recent activity / history — use playlistItems from "Liked Music" auto-playlist
    # (YouTube Data API doesn't expose watch history, but liked music is the best proxy)

    return profile


def save_youtube_profile(profile: YouTubeProfile, db_path: Path | None = None) -> None:
    """Store YouTube profile as JSON in the database."""
    conn = get_connection(db_path)
    now = datetime.now(timezone.utc).isoformat()
    profile_json = json.dumps(asdict(profile), indent=2)
    conn.execute(
        "INSERT OR REPLACE INTO youtube_profile (id, profile_json, updated_at) VALUES (1, ?, ?)",
        (profile_json, now),
    )
    conn.commit()
    conn.close()


def load_youtube_profile(db_path: Path | None = None) -> YouTubeProfile | None:
    """Load YouTube profile from the database."""
    conn = get_connection(db_path)
    row = conn.execute("SELECT profile_json FROM youtube_profile WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return None
    data = json.loads(row[0])
    return YouTubeProfile(**data)


def display_youtube_profile(profile: YouTubeProfile) -> None:
    """Render YouTube Music profile with Rich terminal output."""
    console.print()
    console.print(Panel.fit(
        "[bold red]YouTube Music[/bold red] — Streaming Profile",
        border_style="red",
    ))

    console.print(f"\n  [bold]Synced:[/bold] {profile.synced_at}")
    console.print(f"  [bold]Liked songs:[/bold] {len(profile.liked_songs)}")
    console.print(f"  [bold]Playlists:[/bold] {len(profile.playlists)}")
    console.print(f"  [bold]History entries:[/bold] {len(profile.history)}")

    # Liked songs sample
    if profile.liked_songs:
        console.print("\n  [bold]Recent Liked Songs:[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("#", style="dim", justify="right")
        table.add_column("Track", style="cyan")
        table.add_column("Artist", style="green")
        for i, t in enumerate(profile.liked_songs[:15], 1):
            table.add_row(str(i), t["title"], t["artist"])
        console.print(table)

    # Playlists
    if profile.playlists:
        console.print("\n  [bold]Playlists:[/bold]")
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Name", style="cyan")
        table.add_column("Tracks", justify="right", style="green")
        for p in profile.playlists[:10]:
            table.add_row(p["name"], str(p.get("track_count", "?")))
        console.print(table)

    console.print()
