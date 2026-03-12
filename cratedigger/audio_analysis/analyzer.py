"""Combined audio analyzer — runs BPM and key detection."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .bpm import detect_bpm
from .key import detect_key


@dataclass
class AudioAnalysisResult:
    file_path: Path
    bpm: Optional[float] = None
    key: Optional[str] = None
    error: Optional[str] = None


def analyze_track(file_path: Path) -> AudioAnalysisResult:
    """Run BPM and key detection on a single track."""
    result = AudioAnalysisResult(file_path=file_path)

    try:
        result.bpm = detect_bpm(file_path)
        result.key = detect_key(file_path)
    except Exception as e:
        result.error = str(e)

    return result
