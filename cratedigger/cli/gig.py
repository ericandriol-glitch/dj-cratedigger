"""Gig prep and cue point commands for DJ CrateDigger."""

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ..scanner import find_audio_files

# Import cli group to register commands
from . import cli


@cli.group()
def gig():
    """Gig prep commands."""
    pass


@gig.command("preflight")
@click.argument("playlist_name")
@click.option("--rekordbox", required=True, type=click.Path(exists=True, resolve_path=True),
              help="Path to Rekordbox XML export")
def gig_preflight(playlist_name: str, rekordbox: str) -> None:
    """Run pre-flight readiness check on a Rekordbox playlist."""
    from ..gig.preflight import display_preflight, run_preflight
    from ..gig.rekordbox_parser import parse_rekordbox_xml

    console = Console()
    xml_path = Path(rekordbox)

    library = parse_rekordbox_xml(xml_path)

    if playlist_name not in library.playlists:
        console.print(f"\n  [red]Playlist '{playlist_name}' not found.[/red]")
        console.print("  Available playlists:")
        for name in sorted(library.playlists.keys()):
            count = len(library.playlists[name].track_keys)
            console.print(f"    - {name} ({count} tracks)")
        console.print()
        return

    report = run_preflight(library, playlist_name)
    display_preflight(report)


@gig.command("export")
@click.argument("playlist_name")
@click.option("--rekordbox", required=True, type=click.Path(exists=True, resolve_path=True),
              help="Path to Rekordbox XML export (source)")
@click.option("--output", "-o", required=True, type=click.Path(resolve_path=True),
              help="Output XML file path")
@click.option("--include-cues", is_flag=True, default=False,
              help="Include generated cue points from database")
def gig_export(playlist_name: str, rekordbox: str, output: str, include_cues: bool) -> None:
    """Export a playlist as Rekordbox-compatible XML."""
    from ..gig.rekordbox_parser import parse_rekordbox_xml
    from ..gig.rekordbox_writer import ExportCuePoint, write_rekordbox_xml

    console = Console()
    xml_path = Path(rekordbox)

    library = parse_rekordbox_xml(xml_path)

    if playlist_name not in library.playlists:
        console.print(f"\n  [red]Playlist '{playlist_name}' not found.[/red]")
        console.print("  Available playlists:")
        for name in sorted(library.playlists.keys()):
            console.print(f"    - {name}")
        console.print()
        return

    tracks = library.get_playlist_tracks(playlist_name)
    export_tracks: list[dict] = []
    for t in tracks:
        cues: list[ExportCuePoint] = []
        if include_cues:
            for cue in t.hot_cues:
                cues.append(ExportCuePoint(
                    name=cue.name, position_seconds=cue.start, num=cue.num,
                    red=cue.red, green=cue.green, blue=cue.blue,
                ))
        export_tracks.append({
            "filepath": Path(t.location), "title": t.name, "artist": t.artist,
            "bpm": t.bpm, "key_camelot": t.key or "", "duration_seconds": t.total_time,
            "cue_points": cues, "album": "", "genre": "", "year": "",
            "bitrate": 0, "sample_rate": 0,
        })

    out_path = Path(output)
    write_rekordbox_xml(export_tracks, playlist_name, out_path)
    console.print(f"\n  [green]Exported {len(export_tracks)} tracks to {out_path}[/green]\n")


@gig.command("structure")
@click.argument("path", type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.option("--force", is_flag=True, default=False, help="Re-analyze files already processed")
def gig_structure(path: str, force: bool) -> None:
    """Detect track structure (intros, breakdowns, drops, outros)."""
    from ..gig.structure_analyzer import analyze_structure, store_structure
    from ..utils.db import get_connection

    console = Console()
    scan_path = Path(path)

    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Structure Analysis\n")

    audio_paths = find_audio_files(scan_path)
    if not audio_paths:
        console.print("  [yellow]No audio files found.[/yellow]\n")
        return

    # Get BPM data from Essentia DB
    conn = get_connection()
    bpm_map: dict[str, float] = {}
    for row in conn.execute("SELECT filepath, bpm FROM audio_analysis WHERE bpm IS NOT NULL"):
        bpm_map[row[0]] = row[1]
    conn.close()

    console.print(f"  Analyzing structure for {len(audio_paths)} tracks...\n")

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("Track", style="cyan", max_width=35)
    table.add_column("Intro", justify="right", width=7)
    table.add_column("Breakdown", justify="right", width=9)
    table.add_column("Drop", justify="right", width=7)
    table.add_column("Outro", justify="right", width=7)
    table.add_column("Conf", justify="right", width=5)

    analyzed = 0
    for fp in audio_paths:
        bpm = bpm_map.get(str(fp))
        structure = analyze_structure(fp, bpm=bpm)

        if structure.confidence > 0:
            store_structure(str(fp), structure)
            analyzed += 1

            def _fmt(val: float | None) -> str:
                if val is None:
                    return "-"
                m, s = int(val // 60), val % 60
                return f"{m}:{s:04.1f}"

            table.add_row(
                fp.name[:35],
                _fmt(structure.intro_end),
                _fmt(structure.first_breakdown),
                _fmt(structure.first_drop),
                _fmt(structure.outro_start),
                f"{structure.confidence:.2f}",
            )

    console.print(table)
    console.print(f"\n  [green]Analyzed {analyzed} / {len(audio_paths)} tracks[/green]\n")


@cli.group()
def cues():
    """Cue point commands."""
    pass


@cues.command("generate")
@click.argument("playlist_name")
@click.option("--rekordbox", required=True, type=click.Path(exists=True, resolve_path=True),
              help="Path to Rekordbox XML export")
@click.option("--template", default="default", help="Cue template name (default: default)")
def cues_generate(playlist_name: str, rekordbox: str, template: str) -> None:
    """Generate cue points for tracks in a playlist."""
    from ..gig.cue_generator import display_cues, generate_cues, store_cues
    from ..gig.rekordbox_parser import parse_rekordbox_xml
    from ..gig.structure_analyzer import analyze_structure, store_structure
    from ..utils.db import get_connection

    console = Console()
    xml_path = Path(rekordbox)

    console.print(f"\n  [bold magenta]DJ CrateDigger[/bold magenta] — Cue Generator ({template})\n")

    library = parse_rekordbox_xml(xml_path)

    if playlist_name not in library.playlists:
        console.print(f"  [red]Playlist '{playlist_name}' not found.[/red]")
        console.print("  Available playlists:")
        for name in sorted(library.playlists.keys()):
            console.print(f"    - {name}")
        console.print()
        return

    tracks = library.get_playlist_tracks(playlist_name)

    # Get BPM data from DB
    conn = get_connection()
    bpm_map: dict[str, float] = {}
    for row in conn.execute("SELECT filepath, bpm FROM audio_analysis WHERE bpm IS NOT NULL"):
        bpm_map[row[0]] = row[1]
    conn.close()

    total_cues = 0
    for track in tracks:
        bpm = track.bpm or bpm_map.get(track.location, 128.0)

        # Analyze structure if not already done
        structure = analyze_structure(track.location, bpm=bpm)
        if structure.confidence > 0:
            store_structure(track.location, structure)

        cue_list = generate_cues(structure, bpm=bpm, template_name=template)
        if cue_list:
            store_cues(track.location, cue_list, template_name=template)
            display_cues(f"{track.artist} - {track.name}", cue_list)
            total_cues += len(cue_list)

    console.print(f"\n  [green]Generated {total_cues} cues for {len(tracks)} tracks[/green]\n")


@gig.command("build")
@click.option("--genre", default=None, help="Filter by genre (case-insensitive substring)")
@click.option("--duration", default=60, type=int, help="Target set duration in minutes (default 60)")
@click.option("--slot", default="peak", type=click.Choice(["warmup", "peak", "closing"]),
              help="Set type: warmup, peak, or closing")
@click.option("--bpm-start", default=128, type=float, help="Starting BPM (default 128)")
@click.option("--key-start", default=None, help="Starting Camelot key (e.g. 8A)")
@click.option("--db-path", default=None, type=click.Path(resolve_path=True),
              help="Custom database path")
def gig_build(genre: str | None, duration: int, slot: str, bpm_start: float,
              key_start: str | None, db_path: str | None) -> None:
    """Build a smart playlist with harmonic + energy + BPM flow."""
    from ..gig.playlist_builder import build_playlist, display_playlist, load_tracks_from_db

    console = Console()
    console.print("\n  [bold magenta]DJ CrateDigger[/bold magenta] — Playlist Builder\n")

    db = Path(db_path) if db_path else None
    tracks = load_tracks_from_db(db)

    if not tracks:
        console.print("  [yellow]No analysed tracks in database. Run 'scan-essentia' first.[/yellow]\n")
        return

    console.print(f"  {len(tracks)} tracks in library")
    console.print(f"  Building {slot} set: ~{duration} min, starting {bpm_start:.0f} BPM")
    if genre:
        console.print(f"  Genre filter: {genre}")
    if key_start:
        console.print(f"  Starting key: {key_start}")
    console.print()

    playlist = build_playlist(
        tracks, genre=genre, duration_min=duration,
        slot=slot, start_bpm=bpm_start, start_key=key_start,
    )
    display_playlist(playlist)


@gig.command("practice")
@click.argument("playlist_name")
@click.option("--rekordbox", required=True, type=click.Path(exists=True, resolve_path=True),
              help="Path to Rekordbox XML export")
def gig_practice(playlist_name: str, rekordbox: str) -> None:
    """Score transition difficulty and prioritise practice."""
    from ..gig.practice import Transition, display_practice, prioritise_practice
    from ..gig.rekordbox_parser import parse_rekordbox_xml
    from ..utils.db import get_connection

    console = Console()
    xml_path = Path(rekordbox)
    library = parse_rekordbox_xml(xml_path)

    if playlist_name not in library.playlists:
        console.print(f"\n  [red]Playlist '{playlist_name}' not found.[/red]")
        return

    tracks = library.get_playlist_tracks(playlist_name)
    if len(tracks) < 2:
        console.print("\n  [yellow]Need at least 2 tracks for practice scoring.[/yellow]\n")
        return

    # Get energy data from Essentia DB
    conn = get_connection()
    energy_map: dict[str, float] = {}
    for row in conn.execute("SELECT filepath, energy FROM audio_analysis WHERE energy IS NOT NULL"):
        energy_map[row[0]] = row[1]
    conn.close()

    # Build transitions
    transitions = []
    for i in range(len(tracks) - 1):
        a, b = tracks[i], tracks[i + 1]
        # Use Essentia energy if available, else estimate from position
        energy_a = energy_map.get(a.location, 0.7)
        energy_b = energy_map.get(b.location, 0.7)

        if a.bpm and b.bpm and a.key and b.key:
            from ..core.analyzer import musical_key_to_camelot
            key_a = musical_key_to_camelot(a.key) or a.key
            key_b = musical_key_to_camelot(b.key) or b.key
            transitions.append(Transition(
                track_a_name=f"{a.artist} - {a.name}",
                track_b_name=f"{b.artist} - {b.name}",
                bpm_a=a.bpm, bpm_b=b.bpm,
                key_a=key_a, key_b=key_b,
                energy_a=energy_a, energy_b=energy_b,
            ))

    console.print(f"\n  [bold magenta]Practice Priority:[/bold magenta] {playlist_name}")
    scored = prioritise_practice(transitions)
    display_practice(scored)
