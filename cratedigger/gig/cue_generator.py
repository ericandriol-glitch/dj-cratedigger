"""Auto cue point generator from track structure + YAML templates."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from rich.console import Console
from rich.table import Table

from cratedigger.gig.structure_analyzer import TrackStructure

console = Console()

# Default template location
TEMPLATES_DIR = Path(__file__).parent / "cue_templates"


@dataclass
class GeneratedCue:
    """A generated cue point for a track."""

    name: str
    position_seconds: float
    num: int  # Hot cue slot (0-7)
    red: int
    green: int
    blue: int


@dataclass
class CueTemplate:
    """A single cue definition from a YAML template."""

    name: str
    detect: str
    red: int
    green: int
    blue: int


def load_template(template_name: str = "default") -> list[CueTemplate]:
    """Load a cue template from YAML.

    Args:
        template_name: Template name (without .yaml extension).

    Returns:
        List of CueTemplate definitions.
    """
    template_path = TEMPLATES_DIR / f"{template_name}.yaml"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path) as f:
        data = yaml.safe_load(f)

    templates = []
    for cue_def in data.get("cues", []):
        color = cue_def.get("color", {})
        templates.append(CueTemplate(
            name=cue_def["name"],
            detect=cue_def["detect"],
            red=color.get("r", 255),
            green=color.get("g", 255),
            blue=color.get("b", 255),
        ))

    return templates


def _resolve_position(
    detect: str,
    structure: TrackStructure,
    bpm: float,
) -> float | None:
    """Resolve a detect string to a position in seconds.

    Handles:
        - Direct landmark names: "intro_end", "first_breakdown", etc.
        - Relative positions: "64_beats_before_first_drop"
    """
    # Check for relative positions (e.g., "64_beats_before_first_drop")
    if "_beats_before_" in detect:
        parts = detect.split("_beats_before_")
        try:
            beat_count = int(parts[0])
        except ValueError:
            return None

        landmark_name = parts[1]
        landmark_pos = getattr(structure, landmark_name, None)

        if landmark_pos is None or bpm <= 0:
            return None

        beat_duration = 60.0 / bpm
        offset = beat_count * beat_duration
        result = landmark_pos - offset
        return max(0.0, result)

    # Direct landmark lookup
    value = getattr(structure, detect, None)
    if isinstance(value, (int, float)):
        return float(value)

    return None


def generate_cues(
    structure: TrackStructure,
    bpm: float,
    template_name: str = "default",
) -> list[GeneratedCue]:
    """Generate cue points from track structure using a template.

    Args:
        structure: Detected track structure.
        bpm: Track BPM (for relative position calculations).
        template_name: Name of the cue template to use.

    Returns:
        List of GeneratedCue objects (only for successfully resolved positions).
    """
    templates = load_template(template_name)
    cues = []
    slot = 0

    for tmpl in templates:
        position = _resolve_position(tmpl.detect, structure, bpm)
        if position is None:
            continue

        cues.append(GeneratedCue(
            name=tmpl.name,
            position_seconds=round(position, 3),
            num=slot,
            red=tmpl.red,
            green=tmpl.green,
            blue=tmpl.blue,
        ))
        slot += 1

    return cues


def store_cues(
    filepath: str,
    cues: list[GeneratedCue],
    template_name: str = "default",
    db_path: Path | None = None,
) -> None:
    """Store generated cues in the database."""
    from cratedigger.utils.db import get_connection

    conn = get_connection(db_path)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS generated_cues (
            filepath TEXT,
            cue_name TEXT,
            position_seconds REAL,
            color_r INTEGER,
            color_g INTEGER,
            color_b INTEGER,
            template_name TEXT,
            generated_at TEXT
        )
    """)

    # Remove old cues for this file+template
    conn.execute(
        "DELETE FROM generated_cues WHERE filepath = ? AND template_name = ?",
        (filepath, template_name),
    )

    now = datetime.now(timezone.utc).isoformat()
    for cue in cues:
        conn.execute(
            """INSERT INTO generated_cues
               (filepath, cue_name, position_seconds, color_r, color_g, color_b,
                template_name, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (filepath, cue.name, cue.position_seconds,
             cue.red, cue.green, cue.blue, template_name, now),
        )

    conn.commit()
    conn.close()


def display_cues(track_name: str, cues: list[GeneratedCue]) -> None:
    """Display generated cues with rich output."""
    if not cues:
        console.print(f"  [yellow]No cues generated for {track_name}[/yellow]")
        return

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=3)
    table.add_column("Cue", style="bold", width=12)
    table.add_column("Position", justify="right", width=10)
    table.add_column("Color", width=8)

    for cue in cues:
        minutes = int(cue.position_seconds // 60)
        seconds = cue.position_seconds % 60
        pos_str = f"{minutes}:{seconds:05.2f}"

        # Rich color block
        color_hex = f"#{cue.red:02x}{cue.green:02x}{cue.blue:02x}"
        color_str = f"[{color_hex}]■■[/{color_hex}]"

        table.add_row(str(cue.num), cue.name, pos_str, color_str)

    console.print(f"  [cyan]{track_name}[/cyan]")
    console.print(table)
