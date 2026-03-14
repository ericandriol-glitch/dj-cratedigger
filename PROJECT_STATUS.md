# DJ CrateDigger AI — Project Knowledge Base

## Project Overview

A Python CLI tool for DJs to scan, diagnose, clean, and enrich their music libraries. Built modularly — each module builds on the previous. The tool is designed to be safe (read-only scanning, confirmation before any writes) and DJ-workflow-aware.

**Location:** `C:\Users\eandrio\dj-cratedigger\`
**Target library:** `C:\Users\eandrio\Downloads\Music` (687 audio files, 8.8 GB)
**Tech stack:** Python 3.12 | Essentia | mutagen | click | rich | spotipy | requests | PyYAML
**Runs via WSL** (Python 3.12 + Essentia) — venv at `.venv/` in project root

---

## Architecture

```
dj-cratedigger/
├── requirements.txt
├── cratedigger/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py                    # Click CLI — all commands (~1,200 lines)
│   ├── models.py                 # Data models: TrackMetadata, TrackAnalysis, etc.
│   ├── scanner.py                # Walk folder tree, find audio files
│   ├── metadata.py               # Read tags via mutagen + tinytag fallback
│   ├── report.py                 # Rich terminal output + markdown export
│   ├── analyzers/
│   │   ├── filename.py           # Detect bad filenames
│   │   ├── tags.py               # Detect missing/incomplete tags
│   │   └── duplicates.py         # Hash + fuzzy duplicate detection
│   ├── fixers/
│   │   ├── parse_filename.py     # Parse "Artist - Title [320].mp3"
│   │   ├── tags.py               # Write tags to files
│   │   ├── duplicates.py         # Smart keep/remove logic
│   │   └── filename.py           # Strip junk from filenames
│   ├── core/
│   │   └── essentia_analyzer.py  # Essentia audio analysis (BPM, key, energy, etc.)
│   ├── utils/
│   │   ├── db.py                 # SQLite DB management + schema
│   │   └── config.py             # YAML config loader (~/.cratedigger/config.yaml)
│   ├── harmonic/
│   │   ├── camelot.py            # Camelot wheel + harmonic mixing logic
│   │   └── mix_advisor.py        # Track-to-track mix compatibility
│   ├── gig/
│   │   ├── rekordbox_parser.py   # Rekordbox XML/TXT playlist parser
│   │   ├── preflight.py          # Pre-gig checklist (missing tags, key conflicts)
│   │   ├── structure.py          # Track structure detection (drops, breakdowns)
│   │   ├── cue_points.py         # Cue point suggestions
│   │   └── playlist_writer.py    # Export playlists (M3U/Rekordbox XML)
│   ├── digger/
│   │   ├── profile.py            # DJ profile builder
│   │   └── sleeping.py           # "What Am I Sleeping On?" cross-reference
│   └── enrichment/
│       ├── musicbrainz.py        # Genre lookup via MusicBrainz
│       ├── enrich.py             # AcoustID fingerprint enrichment
│       ├── spotify.py            # Spotify streaming profile (spotipy + OAuth)
│       └── youtube.py            # YouTube Music profile (Data API v3)
└── tests/                        # 266 tests (265 passing)
```

---

## Sprint Status (as of 2026-03-13)

### Sprint 1: Essentia Audio Analysis — COMPLETE ✓
Tasks 1.1-1.5. BPM, key, energy, danceability via Essentia. SQLite storage.

### Sprint 2: DJ Profile + Streaming — COMPLETE ✓
- 2.1 DJ Profile builder — analyzes library for genre/BPM/key preferences
- 2.2 Spotify connector — OAuth via spotipy, `user-top-read` scope
- 2.3 YouTube Music connector — YouTube Data API v3 (not ytmusicapi)
- 2.4 "Sleeping On" skill — cross-references streaming with USB library

### Sprint 3: Gig Preparation — COMPLETE ✓
Tasks 3.1-3.5. Rekordbox parser, pre-gig preflight, structure detection, cue points, playlist writer.

### Sprint 4: Discovery — MOSTLY DONE
- 4.1-4.3 done (MusicBrainz, AcoustID, watcher)
- 4.4 Label deep-dive — needs Discogs token
- 4.5 Artist research — needs Discogs + MusicBrainz

### Sprint 5: Automation — PARTIAL
- 5.1 Watcher + 5.2 Fingerprint done
- 5.3 Weekly dig — needs Beatport scraping
- 5.4 Festival scanner — needs EDMTrain API key

**All 22 core tasks complete. Remaining features are extensions.**

---

## CLI Commands

```bash
# Run from WSL: source .venv/bin/activate

# Scanning & Reports
cratedigger scan <path> [-o report.md] [-v]

# Cleanup
cratedigger fix-tags <path> [--dry-run] [-y]
cratedigger fix-dupes <path> [--dry-run] [-y] [--trash-dir <dir>]
cratedigger fix-filenames <path> [--dry-run] [-y]
cratedigger fix-all <path> [--dry-run] [--trash-dir <dir>]

# Audio Analysis
cratedigger analyze <path> [--dry-run] [-y] [-w 4]

# Enrichment
cratedigger enrich <path> [--dry-run] [-y] [--rate-limit 1.1]

# Harmonic Mixing
cratedigger harmonic <track-path>
cratedigger mix-check <track1> <track2>

# Gig Preparation
cratedigger gig parse <playlist-file>
cratedigger gig preflight <playlist-file>
cratedigger gig structure <track-path>
cratedigger gig cues <track-path>
cratedigger gig build [--genre] [--bpm-range] [--key] [-o output.m3u]

# DJ Profile
cratedigger profile show
cratedigger profile build

# Streaming
cratedigger spotify sync
cratedigger spotify show
cratedigger youtube sync
cratedigger youtube show
cratedigger dig-sleeping
```

---

## Streaming Integration (2026-03-13)

### Spotify
- OAuth via spotipy, `user-top-read` scope only (multi-scope broken in Dev Mode)
- Redirect URI: `http://127.0.0.1:8888/callback` (localhost banned since April 2025)
- Token cached at `~/.cratedigger/.spotify_cache`
- Gets: top artists (3 time ranges, 50 each) + top tracks (50)

### YouTube Music
- YouTube Data API v3 via `requests` (ytmusicapi's internal API broken with OAuth)
- Device code flow for OAuth (TV/Limited Input device type)
- Gets: liked videos (music category, up to 200) + playlists
- Token at `~/.cratedigger/youtube_oauth.json` with auto-refresh

### Config
Location: `~/.cratedigger/config.yaml`
```yaml
spotify:
  client_id: "..."
  client_secret: "..."
youtube:
  client_id: "..."
  client_secret: "..."
  auth_json: "~/.cratedigger/youtube_oauth.json"
```

**Full setup learnings: `STREAMING_SETUP_LEARNINGS.md`**

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

---

## What's Next

See `CRATEDIGGER_NEXT_STEPS.md` for the full roadmap. In order:

1. **Discogs label dive** (Task 4.4) — needs personal access token
2. **Artist research** (Task 4.5) — builds on Discogs + MusicBrainz
3. **Weekly dig** (Task 5.3) — Beatport scraping
4. **Festival scanner** (Task 5.4) — EDMTrain API
5. **Polish** — cli.py split, genre fix, branch merge

---

## Test Suite

266 tests, 265 passing, 1 pre-existing failure (test_reads_tagged_mp3 — WSL fixture issue).

```bash
source .venv/bin/activate && python -m pytest tests/ -v
```

---

## Key Design Decisions

1. **Read-only by default** — scan never modifies files; all writes require explicit commands
2. **Dry-run + confirmation** — every write command previews changes and asks before proceeding
3. **Trash folder for dupes** — duplicates moved, not deleted, so user can restore if needed
4. **SQLite for everything** — audio analysis, profiles, streaming data all in one DB
5. **YAML config for credentials** — `~/.cratedigger/config.yaml` for all API keys
6. **YouTube Data API v3 over ytmusicapi** — internal API broke with OAuth in March 2026
7. **Single Spotify scope** — multi-scope auth broken in Dev Mode as of 2026
8. **Artist name normalization** — strips "the", punctuation, collapses whitespace for fuzzy matching

---

## Known Issues

- `cli.py` is ~1,200 lines — should be split into command groups
- Genre field not in `audio_analysis` DB table — playlist builder genre filter limited
- Structure detection thresholds hardcoded — need tuning on real tracks
- YouTube test mocks still reference ytmusicapi (tests pass but mock patterns outdated)
- Google OAuth consent screen in "Testing" mode — tokens expire after 7 days
