"""Detect exact and near-duplicate audio files."""

import hashlib
from collections import defaultdict

from ..models import TrackAnalysis


def _partial_hash(track: TrackAnalysis, chunk_size: int = 8192) -> str:
    """Hash the first and last chunks of a file for fast exact-match detection."""
    path = track.file_path
    size = path.stat().st_size
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read(chunk_size))
        if size > chunk_size * 2:
            f.seek(-chunk_size, 2)
            h.update(f.read(chunk_size))
    return h.hexdigest()


def find_duplicates(tracks: list[TrackAnalysis]) -> list[list[TrackAnalysis]]:
    """
    Find duplicate groups among tracks.

    Strategy:
    1. Exact duplicates: same file size AND same partial file hash
    2. Near duplicates: same normalized artist + title across different files

    Returns:
        List of duplicate groups (each group is a list of 2+ tracks)
    """
    groups: list[list[TrackAnalysis]] = []
    seen_indices: set[int] = set()

    # --- Pass 1: Exact duplicates (same size, then verify with partial hash) ---
    size_map: dict[int, list[int]] = defaultdict(list)
    for i, track in enumerate(tracks):
        byte_size = track.file_path.stat().st_size
        size_map[byte_size].append(i)

    for byte_size, indices in size_map.items():
        if len(indices) < 2:
            continue
        # Within same-size files, group by partial hash
        hash_map: dict[str, list[int]] = defaultdict(list)
        for i in indices:
            h = _partial_hash(tracks[i])
            hash_map[h].append(i)

        for h, hash_indices in hash_map.items():
            if len(hash_indices) >= 2:
                group = [tracks[i] for i in hash_indices]
                groups.append(group)
                seen_indices.update(hash_indices)

    # --- Pass 2: Near duplicates (same artist + title, different files) ---
    artist_title_map: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, track in enumerate(tracks):
        if i in seen_indices:
            continue
        artist = (track.metadata.artist or "").strip().lower()
        title = (track.metadata.title or "").strip().lower()
        if artist and title:
            artist_title_map[(artist, title)].append(i)

    for key, indices in artist_title_map.items():
        if len(indices) >= 2:
            group = [tracks[i] for i in indices]
            groups.append(group)

    return groups
