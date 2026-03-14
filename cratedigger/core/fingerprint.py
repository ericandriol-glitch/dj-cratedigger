"""AcoustID fingerprint matching for track identification."""

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

console = Console()


@dataclass
class FingerprintResult:
    """Result of an AcoustID fingerprint lookup."""

    filepath: Path
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    musicbrainz_id: str | None = None
    confidence: float = 0.0
    error: str | None = None


def fingerprint_file(filepath: Path) -> tuple[float, str] | None:
    """Generate a Chromaprint fingerprint for an audio file.

    Requires fpcalc binary (libchromaprint-tools).

    Returns:
        Tuple of (duration_seconds, fingerprint_string), or None on failure.
    """
    try:
        import acoustid
    except ImportError:
        return None

    filepath = Path(filepath)
    if not filepath.exists():
        return None

    try:
        duration, fingerprint = acoustid.fingerprint_file(str(filepath))
        return (duration, fingerprint)
    except Exception:
        return None


def lookup_acoustid(
    filepath: Path,
    api_key: str,
) -> FingerprintResult:
    """Identify a track using AcoustID fingerprint matching.

    Args:
        filepath: Path to audio file.
        api_key: AcoustID API key (register at acoustid.org).

    Returns:
        FingerprintResult with matched metadata.
    """
    result = FingerprintResult(filepath=filepath)

    try:
        import acoustid
    except ImportError:
        result.error = "pyacoustid not installed. Run: pip install pyacoustid"
        return result

    filepath = Path(filepath)
    if not filepath.exists():
        result.error = "File not found"
        return result

    try:
        results = acoustid.match(
            api_key, str(filepath),
            meta="recordings releasegroups",
        )
    except acoustid.FingerprintGenerationError:
        result.error = "Fingerprint generation failed. Is fpcalc installed?"
        return result
    except acoustid.WebServiceError as e:
        result.error = f"AcoustID API error: {e}"
        return result
    except Exception as e:
        result.error = f"Unexpected error: {e}"
        return result

    # Parse best match
    best_score = 0.0
    for score, recording_id, title, artist in results:
        if score > best_score:
            best_score = score
            result.confidence = round(float(score), 3)
            result.musicbrainz_id = recording_id
            result.title = title
            result.artist = artist

    if best_score == 0:
        result.error = "No match found in AcoustID database"

    return result


def lookup_musicbrainz(recording_id: str) -> dict[str, str | None]:
    """Get full metadata from MusicBrainz using a recording ID.

    Returns:
        Dict with title, artist, album, isrc keys.
    """
    try:
        import musicbrainzngs
    except ImportError:
        return {}

    musicbrainzngs.set_useragent(
        "CrateDigger", "0.1", "https://github.com/cratedigger"
    )

    try:
        result = musicbrainzngs.get_recording_by_id(
            recording_id,
            includes=["artists", "releases", "isrcs"],
        )
    except Exception:
        return {}

    recording = result.get("recording", {})
    metadata: dict[str, str | None] = {
        "title": recording.get("title"),
        "artist": None,
        "album": None,
        "isrc": None,
    }

    # Extract artist
    artists = recording.get("artist-credit", [])
    if artists:
        artist_parts = []
        for credit in artists:
            if isinstance(credit, dict) and "artist" in credit:
                artist_parts.append(credit["artist"].get("name", ""))
        metadata["artist"] = " & ".join(artist_parts) if artist_parts else None

    # Extract album from first release
    releases = recording.get("release-list", [])
    if releases:
        metadata["album"] = releases[0].get("title")

    # Extract ISRC
    isrcs = recording.get("isrc-list", [])
    if isrcs:
        metadata["isrc"] = isrcs[0]

    return metadata


def identify_track(filepath: Path, api_key: str) -> FingerprintResult:
    """Full identification pipeline: fingerprint → AcoustID → MusicBrainz.

    Args:
        filepath: Path to audio file.
        api_key: AcoustID API key.

    Returns:
        FingerprintResult with the most complete metadata available.
    """
    result = lookup_acoustid(filepath, api_key)

    # Enrich with MusicBrainz if we got a recording ID
    if result.musicbrainz_id and not result.error:
        mb_data = lookup_musicbrainz(result.musicbrainz_id)
        if mb_data.get("title"):
            result.title = mb_data["title"]
        if mb_data.get("artist"):
            result.artist = mb_data["artist"]
        if mb_data.get("album"):
            result.album = mb_data["album"]

    return result


def display_result(result: FingerprintResult) -> None:
    """Display fingerprint identification result."""
    if result.error:
        console.print(f"  [red]{result.error}[/red]")
        return

    console.print(f"  [cyan]{result.filepath.name}[/cyan]")
    if result.artist and result.title:
        console.print(f"  [green]Match:[/green] {result.artist} - {result.title}")
    if result.album:
        console.print(f"  [dim]Album: {result.album}[/dim]")
    console.print(f"  [dim]Confidence: {result.confidence:.0%}[/dim]")
    if result.musicbrainz_id:
        console.print(f"  [dim]MusicBrainz: {result.musicbrainz_id}[/dim]")
