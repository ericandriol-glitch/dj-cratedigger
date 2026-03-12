# DJ CrateDigger AI — Project Knowledge Base

## Project Overview

A Python CLI tool for DJs to scan, diagnose, clean, and enrich their music libraries. Built modularly — each module builds on the previous. The tool is designed to be safe (read-only scanning, confirmation before any writes) and DJ-workflow-aware.

**Location:** `C:\Users\eandrio\dj-cratedigger\`
**Target library:** `C:\Users\eandrio\Downloads\Music` (687 audio files, 8.8 GB)
**Tech stack:** Python 3.13 | mutagen | click | rich | tinytag | librosa | musicbrainzngs

---

## Architecture

```
dj-cratedigger/
├── requirements.txt              # mutagen, click, rich, tinytag, librosa, musicbrainzngs
├── cratedigger/
│   ├── __init__.py               # Package init, version 0.1.0
│   ├── __main__.py               # python -m cratedigger entry point
│   ├── cli.py                    # Click CLI — all commands defined here
│   ├── models.py                 # Data models: TrackMetadata, TrackAnalysis, LibraryReport, HealthScore
│   ├── scanner.py                # Walk folder tree, find audio files, build TrackAnalysis list
│   ├── metadata.py               # Read tags via mutagen (MP3/FLAC/MP4/OGG/AIFF) + tinytag fallback
│   ├── report.py                 # Rich terminal output + markdown file export
│   ├── analyzers/
│   │   ├── filename.py           # Detect bad filenames (junk chars, missing Artist-Title pattern)
│   │   ├── tags.py               # Detect missing/incomplete metadata tags
│   │   └── duplicates.py         # Hash-based exact dupes + artist-title near-dupes
│   ├── fixers/
│   │   ├── parse_filename.py     # Parse "Artist - Title [320].mp3" into structured components
│   │   ├── tags.py               # Write tags to files (MP3/MP4/FLAC/OGG) — supports all fields
│   │   ├── duplicates.py         # Smart keep/remove logic, optional trash folder
│   │   └── filename.py           # Strip junk from filenames (watermarks, copy suffixes)
│   ├── audio_analysis/
│   │   ├── bpm.py                # BPM detection via librosa beat_track (120s from middle of track)
│   │   ├── key.py                # Key detection via chroma CQT + Krumhansl-Schmuckler algorithm
│   │   └── analyzer.py           # Combined analyzer — runs BPM + key on a single track
│   └── enrichment/
│       └── musicbrainz.py        # Genre lookup via MusicBrainz (artist-level then recording-level)
├── tests/
│   ├── test_scanner.py           # 3 tests — find audio, return paths, skip non-audio
│   ├── test_metadata.py          # 4 tests — tagged MP3, untagged MP3, WAV, missing file
│   ├── test_analyzers.py         # 9 tests — filename, tags, duplicates
│   ├── create_fixtures.py        # Script to generate test fixture audio files
│   └── fixtures/                 # Small test MP3s and WAV (auto-generated)
├── sample_output/
│   └── example_report.md         # Example report from test fixtures
├── music_report.md               # First scan report (before fixes)
├── music_report_after.md         # Report after Module 2 fixes
└── music_report_final.md         # Report after Module 3 analysis
```

---

## CLI Commands

```bash
cd C:\Users\eandrio\dj-cratedigger

# Module 1 — Scan & Report
python -m cratedigger scan <path> [-o report.md] [-v]

# Module 2 — Cleanup
python -m cratedigger fix-tags <path> [--dry-run] [-y]        # Fill artist/title/year from filenames
python -m cratedigger fix-dupes <path> [--dry-run] [-y] [--trash-dir <dir>]  # Remove duplicates
python -m cratedigger fix-filenames <path> [--dry-run] [-y]   # Strip junk from filenames
python -m cratedigger fix-all <path> [--dry-run] [--trash-dir <dir>]  # Run all Module 2 fixes

# Module 3 — Audio Analysis
python -m cratedigger analyze <path> [--dry-run] [-y] [-w 4]  # BPM & key detection

# Module 4 — Genre Enrichment
python -m cratedigger enrich <path> [--dry-run] [-y] [--rate-limit 1.1]  # MusicBrainz genre lookup
```

All write commands support `--dry-run` (preview only) and `-y` (skip confirmation).

---

## Module Status

### Module 1: Library Scanner & Health Report — COMPLETE ✓
- Scans all common DJ audio formats (MP3, FLAC, WAV, AIFF, M4A, AAC, OGG, WMA)
- Skips hidden files and system folders (.Spotlight, .Trashes, System Volume Information)
- Reads metadata via mutagen with tinytag fallback — never crashes on corrupt files
- Filename analysis: detects junk, missing Artist-Title format, playlist rip prefixes, URL watermarks
- Tag analysis: flags missing critical (artist/title) and useful (genre/BPM/key/year) tags
- Duplicate detection: partial file hash for exact matches, normalized artist+title for near-dupes
- Health score formula: filename (40%) + metadata (50%) + not-duplicate (10%)
- Output: rich terminal table + markdown file

### Module 2: Library Cleanup — COMPLETE ✓
- Filename parser: extracts artist, title, bitrate `[320]`, year `(1995)` from DJ filenames
- Tag fixer: writes extracted artist/title/year to file tags
- Duplicate cleaner: scores by bitrate tag, metadata completeness, Artist-Title format; optional trash folder
- Filename cleaner: strips URL watermarks, copy suffixes, multiple underscores
- All operations are safe: dry-run preview, confirmation prompt, trash folder option

### Module 3: Audio Analysis (BPM & Key) — COMPLETE ✓
- BPM via librosa beat_track — loads 120s from 30s offset (skips intros)
- Key via chroma CQT + Krumhansl-Schmuckler correlation against major/minor profiles
- Multi-threaded with ThreadPoolExecutor (ProcessPool crashes on Windows with librosa)
- Validated: Dancing Queen = 99.4 BPM (real: 100), A major (correct); 0832am = 123 BPM (tagged: 124)

### Module 4: Genre Enrichment — CODE COMPLETE, NOT YET RUN ON LIBRARY
- MusicBrainz integration (free, no API key needed)
- Two-pass: artist-level tags (best coverage) → recording-level tags (fallback)
- Artist caching reduces API calls (many tracks share same artist)
- 80+ genre mappings normalized to DJ-friendly names (e.g., "house" → "House", "nu-disco" → "Nu-Disco")
- Priority system: prefers specific genres (Deep House, Tech House) over generic (Electronic, Dance)
- Rate-limited at 1.1s per request (MusicBrainz requires ≥1s)
- **To run:** `python -m cratedigger enrich "C:\Users\eandrio\Downloads\Music" -y`
- **Expected:** ~6 min for ~300 unique artists, ~60-70% coverage based on testing

### Module 5: Smart Playlists — NOT STARTED
- Generate playlists by key/BPM/energy for harmonic mixing
- Camelot wheel integration for key compatibility
- BPM range filtering for smooth transitions

### Module 6: Web UI — NOT STARTED
- Streamlit or Gradio interface for non-CLI users

---

## Library Health Progress

| Metric              | Initial (scan) | After Module 2 | After Module 3 | After Module 4 (est) |
|---------------------|---------------|-----------------|-----------------|----------------------|
| **Health Score**    | 68/100        | 78/100          | 78/100          | ~85/100              |
| Missing artist/title| 226           | 15              | 15              | 15                   |
| Missing BPM         | 186           | 186             | 81              | 81                   |
| Missing key         | 195           | 195             | 115             | 115                  |
| Missing genre       | 663           | 663             | 663             | ~200                 |
| Duplicates          | 30 groups     | 25 removed      | —               | —                    |
| Space recovered     | —             | 339 MB          | —               | —                    |

**Duplicate trash location:** `C:\Users\eandrio\Downloads\Music\_duplicates_trash` (can delete once verified)

---

## Key Design Decisions

1. **Read-only by default** — scan never modifies files; all writes require explicit commands
2. **Dry-run + confirmation** — every write command previews changes and asks before proceeding
3. **Trash folder for dupes** — duplicates moved, not deleted, so user can restore if needed
4. **Hash-based dupe detection** — MD5 of first+last 8KB chunks, not just file size (avoids false positives)
5. **ThreadPoolExecutor over ProcessPool** — ProcessPool crashes on Windows with librosa's native libs
6. **Artist-level genre lookup** — MusicBrainz recording tags are sparse; artist tags have much better coverage
7. **DJ-relevant genre priority** — specific subgenres (Deep House, Tech House) preferred over generic (Electronic)
8. **Filename pattern: `Artist - Title [bitrate].mp3`** — detected as the library's standard naming convention

---

## Known Limitations & Future Improvements

### BPM/Key Detection
- 81 files still missing BPM — mostly ambient/beatless tracks where librosa can't lock a beat
- 115 files missing key — tracks with flat chroma distributions (heavily processed electronic)
- Could try: `madmom` library (better for electronic music BPM), longer analysis windows, confidence thresholds

### Genre Enrichment
- MusicBrainz has poor coverage for underground/niche artists (e.g., Abdul Raeva, Kolter)
- Could add: Discogs API (strong for electronic music), Last.fm API, Spotify API (requires OAuth)

### Remaining Gaps
- 15 files missing artist/title — no Artist-Title in filename to extract; would need manual tagging or audio fingerprinting (e.g., Shazam/AcoustID)
- WAV files can't have tags written (format limitation) — 2-3 WAV files in library
- Year tag is only extracted when present as `(YYYY)` in filename

---

## Dependencies

```
mutagen>=1.47.0        # Audio metadata read/write (MP3, FLAC, WAV, AIFF, AAC, M4A)
click>=8.1.0           # CLI framework
rich>=13.0.0           # Terminal output (tables, colors, progress)
tinytag>=1.9.0         # Fallback metadata reader
librosa>=0.11.0        # Audio analysis (BPM, chroma/key detection)
musicbrainzngs>=0.7.1  # MusicBrainz API client
pytest>=9.0.0          # Testing (dev dependency)
```

---

## Test Suite

16 tests, all passing: `python -m pytest tests/ -v`

- `test_scanner.py` — file discovery, path types, non-audio filtering
- `test_metadata.py` — tagged MP3, untagged MP3, WAV, missing file handling
- `test_analyzers.py` — clean/messy filenames, numbered prefixes, complete/missing tags, generic values, near-dupes, no-dupes

---

## Quick Start for Next Session

```bash
cd C:\Users\eandrio\dj-cratedigger

# 1. Run the genre enrichment (was interrupted)
python -m cratedigger enrich "C:\Users\eandrio\Downloads\Music" -y

# 2. Re-scan to see updated health score
python -m cratedigger scan "C:\Users\eandrio\Downloads\Music" -o music_report_enriched.md

# 3. Then move on to Module 5 (Smart Playlists) or Module 6 (Web UI)
```
