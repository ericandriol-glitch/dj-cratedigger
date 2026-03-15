"""Data models for the intake pipeline."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IntakeTrack:
    """A single track moving through the intake pipeline."""

    filepath: Path
    original_filename: str
    # Identification
    identified_via: str = "none"  # "acoustid", "metadata", "filename", "manual", "none"
    identification_confidence: float = 0.0
    # Metadata (enriched)
    artist: str | None = None
    title: str | None = None
    album: str | None = None
    genre: str | None = None
    year: str | None = None
    # Analysis
    bpm: float | None = None
    bpm_source: str = "none"  # "essentia", "librosa", "tag", "none"
    key_camelot: str | None = None
    key_source: str = "none"  # "essentia", "librosa", "tag", "none"
    energy: float | None = None
    # Review
    suggested_filename: str | None = None
    destination_folder: str | None = None
    status: str = "pending"  # "pending", "approved", "edited", "skipped"
    # Applied
    new_filepath: Path | None = None


@dataclass
class IntakeResult:
    """Summary of a completed intake run."""

    tracks: list[IntakeTrack] = field(default_factory=list)
    total_processed: int = 0
    identified_count: int = 0
    unidentified_count: int = 0
    skipped_count: int = 0
    destination_folders: dict[str, int] = field(default_factory=dict)
    rekordbox_xml_path: Path | None = None
