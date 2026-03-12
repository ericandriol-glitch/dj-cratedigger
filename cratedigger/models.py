"""Data models for DJ CrateDigger."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class HealthScore(Enum):
    CLEAN = "clean"
    NEEDS_ATTENTION = "needs_attention"
    MESSY = "messy"


@dataclass
class TrackMetadata:
    artist: Optional[str] = None
    title: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    bpm: Optional[float] = None
    key: Optional[str] = None
    comment: Optional[str] = None
    duration_seconds: Optional[float] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None


@dataclass
class TrackAnalysis:
    file_path: Path
    file_size_mb: float
    audio_format: str
    metadata: TrackMetadata
    filename_score: HealthScore = HealthScore.CLEAN
    filename_issues: list[str] = field(default_factory=list)
    metadata_score: HealthScore = HealthScore.CLEAN
    metadata_issues: list[str] = field(default_factory=list)
    duplicate_group: Optional[int] = None


@dataclass
class LibraryReport:
    scan_path: str
    total_files: int
    audio_files: int
    total_size_gb: float
    scan_duration_seconds: float
    tracks: list[TrackAnalysis] = field(default_factory=list)
    health_score: float = 0.0
    duplicate_groups: list[list[TrackAnalysis]] = field(default_factory=list)
