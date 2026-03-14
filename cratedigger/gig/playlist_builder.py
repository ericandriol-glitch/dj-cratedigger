"""Smart playlist builder with harmonic + energy + BPM flow."""

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from cratedigger.harmonic.camelot import compatibility_score

console = Console()


@dataclass
class PlaylistTrack:
    """A track candidate for playlist building."""

    filepath: str
    name: str
    artist: str
    genre: str
    bpm: float
    key: str  # Camelot notation
    energy: float
    danceability: float = 0.0


@dataclass
class PlaylistTransition:
    """Metadata about the transition between two adjacent tracks."""

    camelot_score: float
    bpm_score: float
    energy_score: float
    combined_score: float
    notes: str


@dataclass
class BuiltPlaylist:
    """Result of the playlist builder."""

    tracks: list[PlaylistTrack]
    transitions: list[PlaylistTransition]
    slot: str
    target_duration_min: float
    estimated_duration_min: float = 0.0


# Average track duration assumption (minutes) when we don't have actual duration
AVG_TRACK_DURATION_MIN = 5.5


def _bpm_range_for_slot(start_bpm: float, slot: str) -> tuple[float, float]:
    """Return (min_bpm, max_bpm) appropriate for the slot type."""
    if slot == "warmup":
        return start_bpm - 8, start_bpm + 16  # Allow gradual increase
    elif slot == "peak":
        return start_bpm - 4, start_bpm + 4
    elif slot == "closing":
        return start_bpm - 16, start_bpm + 8  # Allow gradual decrease
    else:
        return start_bpm - 8, start_bpm + 8


def filter_candidates(
    tracks: list[PlaylistTrack],
    genre: str | None,
    start_bpm: float,
    slot: str,
) -> list[PlaylistTrack]:
    """Filter tracks by genre and slot-appropriate BPM range."""
    bpm_min, bpm_max = _bpm_range_for_slot(start_bpm, slot)

    candidates = []
    for t in tracks:
        # Genre filter (case-insensitive substring match)
        if genre and genre.lower() not in t.genre.lower():
            continue
        # BPM filter
        if not (bpm_min <= t.bpm <= bpm_max):
            continue
        candidates.append(t)

    return candidates


def score_pair(
    current: PlaylistTrack,
    candidate: PlaylistTrack,
    slot: str,
    position_ratio: float,
) -> PlaylistTransition:
    """Score a track pair for playlist sequencing.

    Args:
        current: The track currently at end of playlist.
        candidate: The track being considered as next.
        slot: Slot type for energy flow direction.
        position_ratio: 0.0 (start) to 1.0 (end) — affects energy preference.

    Returns:
        PlaylistTransition with individual and combined scores.
    """
    # Camelot compatibility (0.0-1.0, already scaled)
    try:
        camelot = compatibility_score(current.key, candidate.key)
    except ValueError:
        camelot = 0.2

    # BPM proximity (0.0-1.0, closer = higher)
    bpm_diff = abs(current.bpm - candidate.bpm)
    if bpm_diff <= 2:
        bpm_score = 1.0
    elif bpm_diff <= 4:
        bpm_score = 0.8
    elif bpm_diff <= 8:
        bpm_score = 0.5
    else:
        bpm_score = 0.2

    # Energy flow (depends on slot and position)
    energy_diff = candidate.energy - current.energy
    if slot == "warmup":
        # Prefer gradual energy increase
        if energy_diff >= 0:
            energy_score = 1.0 - min(abs(energy_diff), 0.3) / 0.3 * 0.3
        else:
            energy_score = max(0.2, 1.0 - abs(energy_diff) * 3)
    elif slot == "closing":
        # Prefer gradual energy decrease
        if energy_diff <= 0:
            energy_score = 1.0 - min(abs(energy_diff), 0.3) / 0.3 * 0.3
        else:
            energy_score = max(0.2, 1.0 - abs(energy_diff) * 3)
    else:
        # Peak: keep energy steady and high
        energy_score = max(0.2, 1.0 - abs(energy_diff) * 2)

    # Combined: Camelot × 0.4 + BPM × 0.3 + Energy × 0.3
    combined = round(camelot * 0.4 + bpm_score * 0.3 + energy_score * 0.3, 3)

    # Build transition notes
    notes_parts = []
    if camelot >= 0.95:
        notes_parts.append("perfect key match")
    elif camelot >= 0.9:
        notes_parts.append("key swap OK")
    elif camelot < 0.5:
        notes_parts.append("key clash!")

    if bpm_diff > 4:
        notes_parts.append(f"BPM jump {bpm_diff:.0f}")
    if abs(energy_diff) > 0.3:
        direction = "up" if energy_diff > 0 else "down"
        notes_parts.append(f"energy {direction} {abs(energy_diff):.2f}")

    notes = "; ".join(notes_parts) if notes_parts else "smooth"

    return PlaylistTransition(
        camelot_score=camelot,
        bpm_score=bpm_score,
        energy_score=energy_score,
        combined_score=combined,
        notes=notes,
    )


def _find_starter(
    candidates: list[PlaylistTrack],
    start_bpm: float,
    start_key: str | None,
    slot: str,
) -> PlaylistTrack:
    """Find the best starting track."""
    best = None
    best_score = -1.0

    for t in candidates:
        bpm_diff = abs(t.bpm - start_bpm)
        bpm_score = max(0.0, 1.0 - bpm_diff / 10)

        key_score = 0.5  # Default if no start key given
        if start_key:
            try:
                key_score = compatibility_score(start_key, t.key)
            except ValueError:
                key_score = 0.2

        # For warmup, prefer lower energy; for peak, higher; for closing, medium
        if slot == "warmup":
            energy_score = 1.0 - t.energy
        elif slot == "closing":
            energy_score = 1.0 - abs(t.energy - 0.6)
        else:
            energy_score = t.energy

        score = bpm_score * 0.4 + key_score * 0.3 + energy_score * 0.3
        if score > best_score:
            best_score = score
            best = t

    assert best is not None  # candidates is non-empty
    return best


def build_playlist(
    tracks: list[PlaylistTrack],
    genre: str | None = None,
    duration_min: float = 60,
    slot: str = "peak",
    start_bpm: float = 128,
    start_key: str | None = None,
) -> BuiltPlaylist:
    """Build a playlist with harmonic + energy + BPM flow.

    Args:
        tracks: All available tracks (from DB).
        genre: Filter by genre (case-insensitive substring match).
        duration_min: Target set duration in minutes.
        slot: One of "warmup", "peak", "closing".
        start_bpm: Starting BPM for the set.
        start_key: Optional starting Camelot key.

    Returns:
        BuiltPlaylist with ordered tracks and transition metadata.
    """
    candidates = filter_candidates(tracks, genre, start_bpm, slot)

    if not candidates:
        return BuiltPlaylist(
            tracks=[], transitions=[], slot=slot,
            target_duration_min=duration_min,
        )

    # Pick the starter
    starter = _find_starter(candidates, start_bpm, start_key, slot)
    selected = [starter]
    used = {starter.filepath}
    transitions: list[PlaylistTransition] = []

    max_tracks = int(duration_min / AVG_TRACK_DURATION_MIN) + 1
    cumulative_min = AVG_TRACK_DURATION_MIN

    while cumulative_min < duration_min and len(selected) < max_tracks:
        current = selected[-1]
        remaining = [c for c in candidates if c.filepath not in used]

        if not remaining:
            break

        position_ratio = cumulative_min / duration_min

        # Score all remaining candidates against current track
        scored = []
        for cand in remaining:
            transition = score_pair(current, cand, slot, position_ratio)
            scored.append((cand, transition))

        # Pick the best
        scored.sort(key=lambda x: -x[1].combined_score)
        best_track, best_transition = scored[0]

        selected.append(best_track)
        used.add(best_track.filepath)
        transitions.append(best_transition)
        cumulative_min += AVG_TRACK_DURATION_MIN

    return BuiltPlaylist(
        tracks=selected,
        transitions=transitions,
        slot=slot,
        target_duration_min=duration_min,
        estimated_duration_min=round(len(selected) * AVG_TRACK_DURATION_MIN, 1),
    )


def load_tracks_from_db(db_path: Path | None = None) -> list[PlaylistTrack]:
    """Load analysed tracks from the database as PlaylistTrack objects."""
    from cratedigger.utils.db import get_connection

    conn = get_connection(db_path)
    cursor = conn.execute(
        "SELECT filepath, bpm, key_camelot, energy, danceability, genre "
        "FROM audio_analysis "
        "WHERE bpm IS NOT NULL AND key_camelot IS NOT NULL"
    )
    rows = cursor.fetchall()
    conn.close()

    tracks = []
    for filepath, bpm, key, energy, danceability, genre in rows:
        p = Path(filepath)
        # Extract artist - title from filename (best effort)
        stem = p.stem
        if " - " in stem:
            artist, name = stem.split(" - ", 1)
        else:
            artist, name = "", stem

        tracks.append(PlaylistTrack(
            filepath=filepath,
            name=name.strip(),
            artist=artist.strip(),
            genre=genre or "",
            bpm=bpm,
            key=key,
            energy=energy or 0.5,
            danceability=danceability or 0.5,
        ))

    return tracks


def display_playlist(playlist: BuiltPlaylist) -> None:
    """Display the built playlist with rich output."""
    if not playlist.tracks:
        console.print("\n  [yellow]No tracks matched your criteria.[/yellow]\n")
        return

    console.print(f"\n  [bold magenta]Built Playlist[/bold magenta] ({playlist.slot} set)")
    console.print(
        f"  {len(playlist.tracks)} tracks, "
        f"~{playlist.estimated_duration_min:.0f} min "
        f"(target: {playlist.target_duration_min:.0f} min)\n"
    )

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Artist", style="cyan", max_width=20)
    table.add_column("Track", style="white", max_width=25)
    table.add_column("BPM", justify="center", width=5)
    table.add_column("Key", justify="center", width=4)
    table.add_column("Energy", justify="center", width=6)
    table.add_column("Score", justify="right", width=5)
    table.add_column("Transition", style="yellow", max_width=30)

    for i, track in enumerate(playlist.tracks):
        score_str = ""
        transition_str = ""
        if i > 0 and i - 1 < len(playlist.transitions):
            t = playlist.transitions[i - 1]
            score_str = f"{t.combined_score:.2f}"
            transition_str = t.notes

        table.add_row(
            str(i + 1),
            track.artist[:20] or "?",
            track.name[:25],
            f"{track.bpm:.0f}",
            track.key,
            f"{track.energy:.2f}",
            score_str,
            transition_str,
        )

    console.print(table)

    # Summary stats
    if playlist.transitions:
        avg_score = sum(t.combined_score for t in playlist.transitions) / len(playlist.transitions)
        min_score = min(t.combined_score for t in playlist.transitions)
        console.print(f"\n  Avg transition score: {avg_score:.2f} | Weakest: {min_score:.2f}")

    console.print()
