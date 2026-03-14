# CrateDigger

A local-first Python CLI tool for DJs to manage music libraries, prep for gigs, and discover new music. Built for the terminal. No cloud. No subscriptions.

---

## What It Does

CrateDigger connects the dots between library management, audio analysis, and gig preparation in a single workflow. It treats your music collection as a first-class database and gives you programmatic control over every aspect of preparation.

**Library Management** — Scan files, analyse audio (BPM, key, energy, danceability), fix tags, find duplicates, watch download folders for new tracks.

**Gig Prep** — Build harmonically-optimised playlists, detect track structure (intros, breakdowns, drops, outros), generate cue points, check Rekordbox readiness, prioritise which transitions to practice.

**Music Discovery** — Cross-reference Spotify and YouTube Music streaming history with your USB library to find gaps ("What Am I Sleeping On?"). Weekly new release scanning, label deep-dives, artist research. *(Discogs connector coming.)*

---

## Why It Exists

Rekordbox does beatgrids and cue points, but won't build you a harmonically-optimised setlist. Mixed In Key detects keys, but won't tell you which transitions need practice. Spotify knows what you listen to, but doesn't know what's on your USB stick.

CrateDigger does all of it, locally, with no vendor lock-in. It's built around the actual Friday-night workflow:

1. Download tracks
2. Analyse (BPM, key, energy, structure)
3. Build set (harmonic + energy + BPM flow)
4. Check readiness (preflight audit)
5. Practice transitions (difficulty scoring + advice)
6. Export to Rekordbox XML with auto-generated cue points
7. Play the gig

---

## Quick Start

```bash
# Install (WSL/Linux required for Essentia)
python -m pip install -e ".[dev]"

# Scan and analyse your library
cratedigger scan-essentia /path/to/music

# Build your DJ profile
cratedigger profile build /path/to/music
cratedigger profile show

# Build a playlist for a warmup set
cratedigger gig build --genre "deep house" --duration 120 --slot warmup --bpm-start 118

# Check if your set is ready
cratedigger gig preflight "Saturday Set" --rekordbox ~/rekordbox.xml

# See which transitions need practice
cratedigger gig practice "Saturday Set" --rekordbox ~/rekordbox.xml

# Detect structure and generate cue points
cratedigger gig structure /path/to/music
cratedigger cues generate "Saturday Set" --rekordbox ~/rekordbox.xml

# Export with cues back to Rekordbox
cratedigger gig export "Saturday Set" --rekordbox ~/rekordbox.xml -o ~/saturday_cues.xml --include-cues

# Watch downloads folder for new tracks
cratedigger watch ~/Downloads/Music/ --target ~/Music/DJ/

# Identify unknown tracks via AcoustID
cratedigger identify /path/to/unknown.mp3 --api-key YOUR_KEY
```

---

## Streaming Integration Setup (Spotify + YouTube Music)

These connectors let you cross-reference what you **stream** with what's on your **USB stick**, powering the "What Am I Sleeping On?" gap analysis.

### Step 0: Create the config file

```bash
mkdir -p ~/.cratedigger
nano ~/.cratedigger/config.yaml
```

Paste this template (fill in values as you complete the steps below):

```yaml
spotify:
  client_id: "paste-your-spotify-client-id"
  client_secret: "paste-your-spotify-client-secret"

youtube:
  client_id: "paste-your-google-client-id"
  client_secret: "paste-your-google-client-secret"
  auth_json: "~/.cratedigger/youtube_oauth.json"
```

---

### Spotify Setup

#### 1. Create a Spotify Developer App

1. Go to **https://developer.spotify.com/dashboard** and log in.
   - **You need Spotify Premium** on the account that owns the app (as of Feb 2026).
2. Click **"Create App"**.
3. Fill in:
   - **App Name**: `CrateDigger` (or whatever you like -- users see this on the consent screen)
   - **App Description**: `DJ library gap analysis`
4. Accept the Terms of Service and click **Create**.

#### 2. Copy your Client ID and Client Secret

On the app overview page:
- **Client ID** is shown directly. Copy it.
- Click **"Show client secret"** to reveal the secret. Copy it.

Paste both into `~/.cratedigger/config.yaml`.

#### 3. Set the Redirect URI (this is where most people get stuck)

1. Click **"Edit Settings"** on your app page.
2. Under **Redirect URIs**, add exactly:
   ```
   http://127.0.0.1:8888/callback
   ```
3. Click **Save**.

> **CRITICAL**: Do NOT use `http://localhost:8888/callback` -- Spotify **banned `localhost`** in redirect URIs in April 2025. You must use the IP address `127.0.0.1`. If you used `localhost`, you'll get a redirect error during OAuth.

#### 4. Add yourself as a test user

Since your app starts in **Development Mode**, you must whitelist every user:

1. Go to your app's **"Users and Access"** section in the Dashboard.
2. Click **"Add new user"**.
3. Enter your **name** and the **email address tied to your Spotify account**.

Without this step, you'll get a **403 Forbidden** error when the app tries to read your data.

#### 5. Sync

```bash
cratedigger spotify sync
```

A browser tab opens for Spotify OAuth consent. Grant permission, and the terminal pulls your streaming data. Token is cached at `~/.cratedigger/.spotify_cache` so subsequent syncs don't require the browser.

#### Spotify gotchas

| Issue | Fix |
|-------|-----|
| `INVALID_CLIENT: Invalid redirect URI` | Use `127.0.0.1` not `localhost` in the Dashboard redirect URI |
| `403 Forbidden` | Add yourself under "Users and Access" in the Dashboard |
| `Premium required` error | The app **owner** needs Premium; test users don't |
| Dev mode limits | 5 test users max, 1 app per developer. Fine for personal use |

---

### YouTube Music Setup

YouTube Music requires a Google Cloud project with OAuth credentials. This is more steps than Spotify, but it's a one-time setup.

#### 1. Create a Google Cloud project

1. Go to **https://console.cloud.google.com/**
2. Click the project dropdown at the top, then **"New Project"**.
3. Name it `CrateDigger` and click **Create**.
4. Make sure the new project is selected in the dropdown.

#### 2. Enable the YouTube Data API

1. Go to **APIs & Services > Library** (or search "YouTube Data API v3").
2. Click **YouTube Data API v3**, then click **Enable**.

#### 3. Configure the OAuth consent screen

1. Go to **APIs & Services > OAuth consent screen**.
2. Select **External** as user type.
3. Fill in:
   - **App name**: `CrateDigger`
   - **User support email**: your email
   - **Developer contact email**: your email
4. On the **Scopes** page, skip (ytmusicapi handles this).
5. On the **Test Users** page, **add your own Google email**.
6. Click **Save and Continue**.

> **Tip**: By default, Google puts your consent screen in "Testing" mode, which means **tokens expire after 7 days**. To avoid re-authorizing weekly, click **"Publish App"** on the consent screen page. For personal use this is fine -- users just see an "unverified app" warning you can click through.

#### 4. Create OAuth credentials

1. Go to **APIs & Services > Credentials**.
2. Click **"+ CREATE CREDENTIALS" > "OAuth client ID"**.
3. **Application type**: Select **"TVs and Limited Input devices"**.
   > This is critical -- other types (Web, Desktop) will NOT work with ytmusicapi's device code flow.
4. Name it `ytmusicapi`.
5. Click **Create**.
6. Copy the **Client ID** and **Client Secret** immediately.

Paste both into `~/.cratedigger/config.yaml` under the `youtube:` section.

#### 5. Run the ytmusicapi OAuth flow

```bash
# Make sure you're in the CrateDigger venv
source .venv/bin/activate

ytmusicapi oauth \
  --client-id "YOUR_GOOGLE_CLIENT_ID" \
  --client-secret "YOUR_GOOGLE_CLIENT_SECRET" \
  --file ~/.cratedigger/youtube_oauth.json
```

This will:
1. Print a URL and a **user code** in the terminal.
2. Open the URL in your browser (or go to `https://www.google.com/device`).
3. Sign in with your Google account.
4. Enter the user code.
5. Grant permission.
6. Save credentials to `~/.cratedigger/youtube_oauth.json`.

#### 6. Sync

```bash
cratedigger youtube sync
```

#### YouTube gotchas

| Issue | Fix |
|-------|-----|
| `Error 401: access_denied` | Add your Google email as a test user on the consent screen |
| `Token has been expired or revoked` | Consent screen in "Testing" mode -- tokens expire after 7 days. Publish the app or re-run `ytmusicapi oauth` |
| OAuth client type error | Must be **"TVs and Limited Input devices"**, not "Web" or "Desktop" |
| `oauth.json` not found | Check the `auth_json` path in config.yaml matches where you saved it |
| Can't refresh token | You must pass the **same** client_id/secret that created the token. If you regenerated credentials in Google Cloud, re-run the oauth flow |

---

### Using the Gap Analysis

Once you have at least one streaming profile synced (Spotify, YouTube, or both):

```bash
# Make sure your DJ profile is up to date
cratedigger profile build /path/to/music

# Run the cross-reference
cratedigger dig-sleeping
```

This shows three categories:
- **Stream but don't own** -- artists you listen to but have zero tracks for on USB
- **Underrepresented** -- artists you stream heavily but only have 1-2 tracks
- **Own but don't stream** -- tracks in your library you never listen to (maybe outdated?)

---

## Architecture

```
cratedigger/
├── cli.py                        # Click CLI — 26 commands
├── scanner.py                    # Audio file discovery
├── metadata.py                   # Format-specific tag readers (MP3, FLAC, M4A, OGG, AIFF)
├── core/
│   ├── analyzer.py               # Essentia audio analysis (BPM, key, energy, danceability)
│   ├── batch_analyzer.py         # Batch processing with progress + resume
│   ├── enrich.py                 # Write-back BPM/key to file tags (backup first)
│   ├── fingerprint.py            # AcoustID fingerprint → MusicBrainz metadata
│   └── watcher.py                # Download folder monitor (auto-tag, analyse, sort)
├── digger/
│   ├── profile.py                # DJ profile builder (genres, BPM range, key distribution)
│   └── sleeping.py               # "What Am I Sleeping On?" cross-reference skill
├── gig/
│   ├── rekordbox_parser.py       # Parse Rekordbox XML exports
│   ├── rekordbox_writer.py       # Write Rekordbox-compatible XML
│   ├── preflight.py              # Playlist readiness check
│   ├── structure_analyzer.py     # Detect intros, breakdowns, drops, outros (Essentia)
│   ├── cue_generator.py          # Auto cue points from structure + YAML templates
│   ├── cue_templates/default.yaml
│   ├── playlist_builder.py       # Smart playlist (harmonic + energy + BPM flow)
│   └── practice.py               # Transition difficulty scoring + mixing advice
├── harmonic/
│   └── camelot.py                # Camelot wheel compatibility engine
├── utils/
│   ├── db.py                     # SQLite with WAL mode
│   └── config.py                 # YAML config loader (~/.cratedigger/config.yaml)
├── analyzers/                    # Filename, tag, and duplicate quality scoring
├── fixers/                       # Auto-fix tags, filenames, duplicates
└── enrichment/
    ├── musicbrainz.py            # MusicBrainz genre lookups
    ├── spotify.py                # Spotify streaming profile sync (spotipy + OAuth)
    └── youtube.py                # YouTube Music streaming profile sync (ytmusicapi)
```

---

## Key Features in Detail

### Essentia Audio Analysis

Uses Essentia's EDM-optimised algorithms:
- **BPM**: `RhythmExtractor2013` with multifeature method
- **Key**: `KeyExtractor` with `edma` profile (EDM-optimised, not generic classical)
- **Energy**: RMS → dB normalised to 0-1
- **Danceability**: Essentia DFA normalised to 0-1

Batch processing with Rich progress bars, SQLite storage, and resume-on-interruption. Analyses ~10 tracks/90 seconds.

### Camelot Harmonic Engine

Full 24-key compatibility scoring, not just "same key = good":

| Relationship | Score | Example |
|---|---|---|
| Same key | 1.0 | 8A → 8A |
| Adjacent (+-1) | 0.95 | 8A → 9A |
| Major/minor swap | 0.9 | 8A → 8B |
| Adjacent + swap | 0.85 | 8A → 9B |
| Energy boost (+7) | 0.8 | 1A → 8A |
| Two steps | 0.5 | 8A → 10A |
| Clash | 0.2 | 1A → 6A |

### Smart Playlist Builder

Greedy sequencer balancing three dimensions:
- **Camelot compatibility** x 0.4
- **BPM proximity** x 0.3
- **Energy flow** x 0.3

Slot-aware energy curves: warmup sets prefer gradual energy increase, peak sets keep energy steady and high, closing sets prefer gradual decrease.

### Track Structure Detection

Energy envelope analysis to find:
- **Intro end**: first moment energy exceeds 60% of track mean
- **Breakdowns**: energy drops below 40% of mean for >8 beats
- **Drops**: energy rises above 80% of mean after a breakdown
- **Outro start**: last moment energy drops below 60% and stays low

All positions snapped to nearest 4-bar downbeat boundary.

### Cue Point Generator

YAML-template driven. Default template places 5 cues:

| Cue | Colour | Position |
|---|---|---|
| Intro | Green | End of intro |
| Breakdown | Blue | First breakdown |
| Drop | Red | First drop |
| Build | Purple | 64 beats before first drop |
| Mix Out | Orange | Start of outro |

Templates are extensible — create your own in `cue_templates/`.

### Practice Prioritiser

Scores each transition by difficulty (0.0-1.0):
- BPM delta: >4 = 0.5, >8 = 1.0
- Key clash: non-adjacent = 0.5, >3 steps = 1.0
- Energy jump: >0.3 = 0.5, >0.5 = 1.0

Splits output into **MUST NAIL** (top transitions) and **SAFE** (smooth mixes). Suggests approach for tricky transitions:
- Big BPM gap → "Use filter/loop transition"
- Key clash → "Short mix, bass swap"
- Energy jump → "Use breakdown moment"

### Rekordbox Round-Trip

Full parse → analyse → write cycle:
1. Export XML from Rekordbox
2. Parse tracks, cues, playlists (handles URL-encoded paths, nested folders)
3. Run preflight, generate cues, build playlists
4. Write back as importable XML with cue points (Type=0 hot cues, RGB colours)
5. Import into Rekordbox

### Download Watcher

Monitors a folder using `watchdog`. When a new audio file appears:
1. Waits for download to complete (size stability check)
2. Reads tags with mutagen
3. Runs Essentia analysis
4. Renames to `{artist} - {title}.{ext}`
5. Moves to genre subfolder under target directory
6. Stores in library database

---

## Tech Stack

| Role | Tool |
|------|------|
| CLI | click |
| Audio tags | mutagen |
| Audio analysis | essentia (WSL/Linux) |
| Fingerprinting | pyacoustid + chromaprint |
| Spotify API | spotipy (OAuth) |
| YouTube Music API | ytmusicapi (OAuth) |
| Config | PyYAML |
| Terminal output | rich |
| Database | SQLite (WAL mode) |
| File watching | watchdog |
| Testing | pytest |
| Lint/format | ruff |

---

## Project Stats

| Metric | Value |
|---|---|
| Production code | ~8,700 lines across 48 files |
| Test code | ~4,900 lines across 30 files |
| Tests | 321 total, 318 passing |
| Tasks complete | 19 of 22 (remaining deferred to post-launch) |
| CLI commands | 31+ |

### Sprint Status

| Sprint | Tasks | Status |
|---|---|---|
| 1 — Essentia Audio Analysis | 1.1-1.5 | Complete |
| 2 — DJ Profile + Discovery | 2.1-2.4 | Complete |
| 3 — Gig Prep Core | 3.1-3.5 | Complete |
| 4 — Smart Playlists + Research | 4.1-4.4 done | Complete (4.5 deferred) |
| 5 — Weekly Workflow | 5.1, 5.2, 5.4 done | Complete (5.3 deferred) |

### Deferred to Post-Launch

| Task | Reason |
|---|---|
| 4.5 Artist research | Needs Discogs API token for full discography |
| 5.3 Weekly dig | Needs Beatport scraping infrastructure |

### Known Issues

| Issue | Severity | Notes |
|---|---|---|
| `test_reads_tagged_mp3` fixture failure | Low | Cross-filesystem mutagen tag issue (Windows fixtures read from WSL) |
| 2 YouTube mock test failures | Low | Mocks reference old ytmusicapi patterns; YouTube connector works correctly with live API |
| Structure detection thresholds hardcoded | Medium | Energy thresholds tuned on synthetic data; needs real-track testing for production use |
| Festival scanner shows "unknown" on Windows | Low | Library DB lives in WSL; festival scanner cross-references against it. Use WSL for full results |
| `musicbrainzngs` not in WSL venv | Low | WSL has no internet; label research + festival scanner run on Windows Python |

---

## Design Principles

1. **Local-first** — Everything runs on the DJ's machine. No cloud.
2. **Non-destructive** — Never modify original files without explicit `--apply` flag. Backup first.
3. **DJ-native language** — Camelot notation (8A, 11B), BPM, not raw pitch class or tempo.
4. **Confidence scoring** — All suggestions include 0-1 confidence. 0.85 threshold for auto-apply.
5. **Resume-safe** — Batch analysis saves progress. Interruption is not data loss.
6. **Terminal-native** — Rich tables, colour coding, progress bars. No GUI needed.

---

## Testing

```bash
# Run all tests (WSL)
source .venv/bin/activate && python -m pytest tests/ -v

# Run specific module tests
python -m pytest tests/test_camelot.py -v
python -m pytest tests/test_playlist_builder.py -v
```

Tests use `tmp_path` fixtures and database path patching for full isolation. No external dependencies required for testing (Essentia calls are mocked where needed).

---

## Requirements

- **Python 3.12+**
- **WSL/Linux** for Essentia (no Windows pip wheels available)
- **fpcalc** for AcoustID fingerprinting: `apt install libchromaprint-tools`

---

*Built by Rico. A personal tool for a working DJ. Ships things that save real hours.*
