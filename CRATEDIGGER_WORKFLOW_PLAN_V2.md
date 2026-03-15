# CrateDigger — Workflow Improvement Plan

**Date:** 2026-03-15
**Author:** Rico + Claude (co-founder session)
**Goal:** Make CrateDigger solve real DJ workflows end-to-end, not just expose commands.

---

## Rico's DJ Preferences (reference for all sessions)

| Preference | Value | Impact on design |
|-----------|-------|-----------------|
| **Filename decisions** | Per-track (not batch) | Intake uses a review queue, not auto-rename |
| **Set planning** | Vibe/energy first, keys later | Gig crate organized by energy zones, Camelot as metadata |
| **Set size** | Big crate (80-100 tracks), decide on the fly | Build pools, not setlists |
| **Track sources** | SoundCloud, artist-direct, YouTube/Spotify rips | AcoustID fingerprinting is PRIMARY (garbage metadata) |
| **Discovery focus** | Follow artists > follow labels | `dig artist` is the primary discovery command |
| **Duplicate handling** | Original + Extended = flag, let me decide | Not auto-resolved, DJ chooses |
| **Artwork** | Don't care | Completely removed from all checks |
| **YouTube** | Watches Boiler Room, Cercle regularly | Valid 3rd source for DJ profile |
| **Rekordbox** | Version 7 | XML schema differs from v6 |
| **API keys** | Spotify configured, Discogs not yet | Enrichment degrades gracefully without Discogs |
| **Style categories** | DJ-defined, not auto-assigned | Interactive sorting in intake, not genre-tag mapping |

---

## Philosophy

CrateDigger has 30+ commands and 443 tests. What it doesn't have is workflows — connected sequences that take a working DJ from a real-world trigger ("I just bought new tracks") to a real-world outcome ("they're on my USB, analyzed, and I trust them"). This plan fixes that.

Each workflow is designed around **one moment in a DJ's week**, broken into sessions sized for Claude Code remote execution (30-90 min each).

---

## Workflow 1: New Track Intake (Priority: NOW)

### The real moment
You've got 15-30 new tracks from various sources — SoundCloud free downloads, direct links from artists, Spotify/YouTube rips, maybe some Beatport purchases. Files land in your Downloads folder with wildly inconsistent quality: SoundCloud filenames are often random strings, YouTube rips have garbage tags or none at all, artist-direct files might just be `final_master_v3.wav`. You need these metadata-complete and ready to import into Rekordbox — where you'll analyze beatgrids, set cue points, and export to USB.

### The pain today
Manual sort by style → manual import to Rekordbox → manual playlist organization → Analyze → wait → export to USB → show up at the gig hoping everything is there.

### Critical design note: track sources have terrible metadata
Rico's primary sources (SoundCloud, artist-direct, YouTube/Spotify rips) produce the *worst* metadata in the DJ world. This means:
- **AcoustID fingerprinting is not a fallback — it's a primary identification tool.** Many tracks can't be matched by metadata alone.
- **The review queue UX is essential.** Auto-renaming will get things wrong. Every track needs DJ approval.
- **Enrichment from MusicBrainz/Spotify is the main way these tracks get proper tags.**

### What CrateDigger should do
Handle everything BEFORE Rekordbox (intake) and validate everything AFTER Rekordbox (preflight). Rekordbox stays in the middle — its beatgrid/waveform analysis can't be replaced.

```
Downloads folder (SoundCloud, artist-direct, rips, purchases)
    ↓
cratedigger intake  ← NEW: single command, review queue
    ├── Scan files, read existing tags
    ├── Fingerprint via AcoustID (primary ID for messy files)
    ├── Detect BPM / key / energy (Essentia or librosa fallback)
    ├── Enrich metadata (AcoustID → MusicBrainz → Spotify)
    ├── Present REVIEW QUEUE: each track with detected info
    │     DJ approves/edits: filename, artist, title, style folder
    ├── Apply approved changes (rename, tag, move to dest)
    ├── Generate Rekordbox 7 XML import
    └── Print summary report
    ↓
Open Rekordbox → import XML → tracks are in the right crates → Analyze → Export USB
    ↓
cratedigger preflight /usb  ← NEW: validation before you leave the house
    ├── Every track present on USB?
    ├── All tracks analyzed (beatgrid exists)?
    ├── BPM/key populated?
    ├── Any corrupt or zero-byte files?
    └── Print confidence score: "47/47 tracks ready. You're good."
```

---

### Session 1: The `intake` command

**Goal:** A single CLI command that scans new tracks, identifies them (fingerprinting first), enriches metadata, then presents a review queue where the DJ approves each track's filename, tags, and destination folder.

**Command signature:**
```bash
cratedigger intake /path/to/downloads --dest /path/to/library --dry-run
cratedigger intake /path/to/downloads --dest ~/Music/DJ
cratedigger intake /path/to/downloads --dest ~/Music/DJ --auto --move
```

**Behavior:**

1. **Scan** — Find all audio files in source folder (recursive). Use existing scanner module.

2. **Identify (fingerprint first)** — For files with bad/missing metadata:
   - Run AcoustID fingerprint → match against 73M fingerprints database.
   - This is the PRIMARY identification method because Rico's sources (SoundCloud, rips, artist-direct) often have garbage filenames and no tags.
   - If AcoustID matches: pull artist, title, album, ISRC from MusicBrainz linked data.
   - If AcoustID misses: fall back to fuzzy metadata match on whatever tags exist.
   - Log match method and confidence per track.

3. **Analyze** — Run BPM/key/energy detection.
   - If Essentia is available (WSL): use it (higher accuracy).
   - If not: fall back to librosa for BPM, use existing tag if key is already present.
   - Log which engine was used per track so the DJ knows confidence level.

3. **Enrich** — For each track, attempt metadata completion in order:
   - Read existing tags first (don't overwrite good data).
   - AcoustID match results (from step 2) — often the best source for SoundCloud/rip files.
   - MusicBrainz lookup (free, no key needed).
   - Spotify lookup (configured — good for genre and popularity data).
   - Discogs lookup for genre (NOT YET CONFIGURED — skip gracefully, flag for future).
   - Each source gets a confidence score. Only write data above threshold (0.85).

4. **REVIEW QUEUE** — The core UX. Present each track for DJ approval:
   ```
   TRACK 1 of 27
   ───────────────────────────────────
   Source file:    downloaded_track_392847.mp3
   Identified via: AcoustID (confidence: 0.94)
   
   Artist:     Solomun                    [edit? ___]
   Title:      After Rain (Original Mix)  [edit? ___]
   BPM:        122 (Essentia)
   Key:        8A (Essentia, high confidence)
   Genre:      Melodic House & Techno (Spotify)
   
   Suggested filename: Solomun - After Rain (Original Mix).mp3
   Accept filename? [yes / edit / skip]
   
   Destination folder? [type folder name or pick from existing]
   > melodic-techno
   
   ✓ Queued: melodic-techno/Solomun - After Rain (Original Mix).mp3
   
   [next / back / skip-all-remaining / batch-assign-genre]
   ```
   - **Per-track decisions:** DJ approves or edits artist, title, filename, and destination folder.
   - **Batch mode:** "Assign all 8 tracks tagged 'deep house' to deep-house/" — for when enrichment got the genre right.
   - **Skip option:** Leave track in place, don't process.
   - **Unidentified tracks:** If AcoustID + enrichment failed, show what's known and prompt for manual entry:
     ```
     TRACK 14 of 27  ⚠️ UNIDENTIFIED
     ───────────────────────────────────
     Source file:    SC_download_x7r9k2.wav
     Identified via: NONE (AcoustID no match, no tags)
     BPM:        126 (Essentia)
     Key:        5A (Essentia, medium confidence)
     
     This track couldn't be identified. Enter details manually:
     Artist: ___
     Title:  ___
     ```

5. **Apply changes** — After the review queue is complete:
   - Rename files per DJ approval.
   - Write approved tags to files (with backup of originals).
   - Copy (default) or move (`--move` flag) to destination folders.
   - All changes logged for rollback.

6. **Generate Rekordbox 7 XML** — Create an XML import file that:
   - Targets Rekordbox 7 schema specifically (not v6).
   - Includes all processed tracks with their new file paths.
   - Organizes tracks into playlists matching the destination folders.
   - Includes BPM and key data so Rekordbox shows it immediately.
   - Does NOT include beatgrid/waveform (Rekordbox must generate these).

7. **Report** — Print a summary:
   ```
   INTAKE COMPLETE
   ───────────────────────────────────
   Tracks processed:  27
   Identified:        23 (AcoustID: 18, metadata: 5)
   Unidentified:       4 (2 manual entry, 2 skipped)
   BPM detected:      25 (2 failed — listed below)
   Key detected:      23 (4 unknown)
   
   Destination folders:
     melodic-techno/   12 tracks
     deep-house/        8 tracks
     afro-house/        4 tracks
     skipped/           3 tracks
   
   Rekordbox XML:  ~/Music/DJ/intake-2026-03-15.xml
   
   Next step: Open Rekordbox → File → Import → select the XML above
   ```

**Flags:**
- `--dry-run` — Show what would happen without moving/modifying anything.
- `--dest` — Destination library folder (required).
- `--auto` — Skip review queue: auto-accept all enrichment results, use suggested filenames, sort by detected genre. For when you trust the pipeline or just want speed.
- `--detect-folders` — Skip sorting; detect where DJ already placed files manually.
- `--no-enrich` — Skip external API lookups (offline mode).
- `--no-analyze` — Skip BPM/key detection (use existing tags only).
- `--no-fingerprint` — Skip AcoustID fingerprinting (faster, but less accurate for messy files).
- `--force` — Skip confirmation prompts.
- `--move` — Move files instead of copying (default: copy, preserving originals).

**Rekordbox 7 note:**
Rekordbox 7 changed the XML import/export format from v6. The `gig export` module must target the v7 schema specifically. Key differences: new XML namespace, different playlist node structure, updated attribute names for BPM/key fields. Session 2 should verify against the actual Rekordbox 7 XML spec.

**Technical constraints:**
- Must reuse existing modules: scanner, audio_analysis, enrichment, fixers, gig/rekordbox.
- Non-destructive: original files are COPIED to dest, not moved (unless `--move` flag).
- All writes require confirmation unless `--force`.
- Must work without any API keys configured (graceful degradation).
- Should complete 30 tracks in under 5 minutes (excluding network lookups).

**Tests to write:**
- End-to-end: fixture folder with mixed formats → verify organized output.
- Dry-run produces report but no file changes.
- AcoustID fingerprinting: mock match → correct metadata populated in review queue.
- Unidentified track: no AcoustID match + no tags → prompts for manual entry.
- Review queue: DJ edits a filename → edit is applied correctly.
- Review queue batch mode: assign genre group to folder → all tracks moved.
- Missing API keys: enrichment skips gracefully, other steps still work.
- Duplicate detection: same track in downloads and dest library.
- Rekordbox 7 XML: validate against Rekordbox 7 expected schema.
- Edge cases: WAV with no tags (common from artist-direct), SoundCloud random filename, zero-byte file.
- Auto mode: `--auto` skips review queue and applies all suggestions.

**Definition of done:**
Rico can run `cratedigger intake ~/Downloads/new-tracks --dest ~/Music/DJ` against a batch of SoundCloud downloads and YouTube rips, review each track in the queue, approve/edit metadata and filenames, assign to style folders, and get a working Rekordbox 7 XML import.

---

### Session 2: Rekordbox 7 XML import quality

**Goal:** Ensure the generated XML actually imports cleanly into Rekordbox 7.

**Tasks:**
- Research Rekordbox 7 XML import schema specifically (v7 changed format from v6).
- Ensure file paths in XML use the correct format for the user's OS.
- Test: generate XML → import into Rekordbox 7 → verify tracks appear in correct playlists.
- Handle the case where tracks already exist in Rekordbox (don't create duplicates).
- Include hot cue color mapping if cue data exists from analysis.

**Definition of done:**
Import the XML into Rekordbox 7 and see all tracks in the correct crates with BPM/key pre-populated.

---

### Session 3: USB preflight validation

**Goal:** A command that checks a USB stick before you leave for a gig.

**Command signature:**
```bash
cratedigger preflight /Volumes/DJ-USB
cratedigger preflight /media/rico/DJ-USB --strict
```

**Checks:**
- All tracks in Rekordbox export DB are physically present on USB.
- No corrupt or zero-byte audio files.
- All tracks have been analyzed by Rekordbox (beatgrid exists in DB).
- BPM and key populated for every track.
- Hot cues set for every track (reads from Rekordbox DB/XML).
- No duplicate filenames that could confuse CDJs.
- USB filesystem is FAT32 or exFAT (CDJ compatible).
- Total size vs USB capacity.
- Optional `--strict`: warn about inconsistent naming, tracks without genre tags, BPM/key mismatches between CrateDigger analysis and Rekordbox analysis.

**Output:**
```
USB PREFLIGHT: /Volumes/DJ-USB
───────────────────────────────────
Tracks on USB:     156
All analyzed:      ✓ (156/156)
BPM populated:     ✓ (156/156)
Key populated:     ✗ (149/156 — 7 missing, listed below)
Hot cues set:      ✗ (132/156 — 24 tracks have no cue points)
Corrupt files:     ✗ 1 found (see below)
Filesystem:        FAT32 ✓
Free space:        2.1 GB

USB PROFILE:
  BPM range:       118-132 (median: 124)
  Styles:          melodic-techno 48%, deep-house 29%, afro-house 15%, other 8%
  Total duration:  11h 23m
  Avg track length: 5:38

ISSUES:
  ✗ Missing key:   Artist A - Track B (Original Mix).mp3
  ✗ Missing key:   Artist C - Track D (Extended).wav
  ... (5 more)
  ✗ No hot cues:   24 tracks (run with --list-no-cues to see full list)
  ✗ Corrupt:       Artist E - Track F.mp3 (0 bytes)

VERDICT: 1 critical issue (corrupt file). 24 tracks without cue points.
```

**Definition of done:**
Run against a real USB export and get an accurate, trustworthy report.

---

### Session 4: Real library stress test

**Goal:** Run the full intake → Rekordbox → preflight flow against Rico's actual library.

**Tasks:**
- Run `intake` against a batch of 30+ real tracks from recent purchases.
- Document every failure, wrong detection, bad filename cleanup.
- Fix the top 5 most common issues found.
- Run `preflight` against an actual USB stick used for a gig.
- Tune confidence thresholds based on real results.
- Update the style mapping YAML based on Rico's actual genre categories.

**Definition of done:**
Rico uses intake + preflight for his next gig and trusts the output.

---

## Workflow 2: Gig Prep (Priority: HIGH)

### The real moment
You have a gig on Saturday at a specific venue. You know the vibe — maybe it's a deep house night, maybe it's a festival mainstage slot. You don't plan a rigid setlist — you bring a **big crate of 80-100 tracks** and decide on the fly based on the room. What you need is: the right tracks selected, organized by vibe and energy so you can browse easily on CDJs, and a USB you trust.

### What exists
`gig preflight`, `gig export`, `gig cues`, `gig practice` — individual commands that aren't connected.

### What's missing
A guided flow that starts from "I have a gig" and ends at "USB is ready." The key insight: Rico doesn't build setlists — he builds **curated crates**. The tool should help select and organize tracks, not sequence them.

### Design principle: vibe and energy first, harmonic compatibility second
Rico picks tracks by feel and energy, then worries about keys during the performance. CrateDigger should organize the crate by energy zones so he can easily grab the right track for the moment. Camelot compatibility becomes a **browsing aid** (shown as metadata on each track) rather than a sequencing algorithm.

### The target flow
```
"I have a gig Saturday"
    ↓
cratedigger gig crate  ← build the crate (NOT a setlist)
    ├── Filter library by style/energy/BPM range
    ├── Organize into energy zones (warm-up / build / peak / cool-down)
    ├── Show Camelot keys as browsing metadata (not sequencing)
    ├── DJ reviews: add/remove tracks, adjust the crate
    └── Save as named gig crate
    ↓
cratedigger gig practice  ← optional: drill tricky transitions
    ├── Pick any two tracks from the crate
    ├── Show BPM delta, key relationship, energy gap
    ├── Score difficulty, suggest approach
    └── Log practice for confidence tracking
    ↓
cratedigger gig export  ← package for USB
    ├── Copy crate tracks to USB
    ├── Generate Rekordbox 7 XML with crate as playlist
    ├── Auto-run preflight validation
    └── Print "you're ready" or "fix these issues"
```

---

### Session 5: The `gig crate` command

**Goal:** A crate builder that helps the DJ select 80-100 tracks organized by energy zone, with Camelot keys shown as metadata for on-the-fly mixing decisions.

**Command signature:**
```bash
cratedigger gig crate --name "Saturday at Warehouse" --vibe "deep-house,melodic-techno"
cratedigger gig crate --name "Festival Slot" --bpm 122-130 --energy-range 0.6-0.9
cratedigger gig crate --name "Warm Up" --vibe "deep-house" --energy-range 0.3-0.6 --size 40
```

**Behavior:**

1. **Filter candidates** — Pull tracks from the library matching criteria:
   - Style/genre filter (from `--vibe`).
   - BPM range (from `--bpm`, default: no filter).
   - Energy range (from `--energy-range`, default: full range).
   - Already-on-USB filter: if `--usb /path` is given, only include tracks already exported.
   - Show candidate count: "Found 284 tracks matching your criteria."

2. **Smart selection** — Narrow from candidates to a crate of ~80-100 tracks (configurable with `--size`):
   - Ensure energy coverage: include tracks across the full energy spectrum so Rico can play any moment.
   - Ensure BPM variety within the range: don't cluster at one tempo.
   - Ensure key diversity: spread across the Camelot wheel so harmonic options exist.
   - Favor recently added tracks (fresh material) while keeping proven favorites.
   - Flag if the selection is thin in any zone: "Warning: only 3 tracks in the cool-down zone (energy < 0.4)."

3. **Organize by energy zone** — Group the crate into browsable sections:
   ```
   GIG CRATE: Saturday at Warehouse (87 tracks)
   ────────────────────────────────────────
   
   CRATE PROFILE:
     BPM range:     118-130 (median: 124)
     Styles:        melodic-techno (52%), deep-house (31%), afro-house (17%)
     Avg length:    5:42 (shortest: 3:18, longest: 8:45)
     Total duration: 8h 17m (plenty of headroom for a 2h set)
     Key coverage:  18/24 Camelot keys ✓
     Hot cues:      71/87 tracks have cues set ✓ (16 need cue points)
   
   🔥 PEAK (energy 0.8-1.0) — 18 tracks
     Artist A - Track B        128 BPM  8A   energy: 0.92  🎯 cues
     Artist C - Track D        126 BPM  11B  energy: 0.88  🎯 cues
     ...
   
   ⚡ BUILD (energy 0.6-0.8) — 31 tracks
     Artist E - Track F        124 BPM  5A   energy: 0.74  🎯 cues
     ...
   
   🌊 GROOVE (energy 0.4-0.6) — 24 tracks
     Artist G - Track H        122 BPM  2A   energy: 0.52  ⚠️ no cues
     ...
   
   🌙 WARM-UP (energy 0.2-0.4) — 14 tracks
     Artist I - Track J        118 BPM  7A   energy: 0.35  🎯 cues
     ...
   
   WARNINGS:
     ⚠️ 16 tracks have no hot cues — set them in Rekordbox before the gig
     ⚠️ No tracks below 118 BPM — warm-up flexibility limited
   ```
   
   The 🎯/⚠️ hot cue indicator reads from Rekordbox 7's XML export or database. Tracks without cues are flagged so Rico knows what still needs prep work in Rekordbox.

4. **Interactive editing** — After presenting the crate:
   - `add "search term"` — search library for a track to add.
   - `remove 5` — drop a track from the crate.
   - `swap 5` — replace a track with an alternative at similar energy/BPM.
   - `more peak` — add more tracks to the peak zone.
   - `less warmup` — trim the warm-up zone.
   - `done` — save the crate.

5. **Save** — Store crate in SQLite with metadata (gig name, date, venue). Export as:
   - M3U playlist file.
   - Rekordbox 7 XML playlist (organized by energy zone as sub-playlists).
   - Summary text.

**Flags:**
- `--name` — Gig name for reference.
- `--vibe` — Comma-separated style filter.
- `--bpm` — BPM range (e.g., "122-130").
- `--energy-range` — Energy range (e.g., "0.3-0.9").
- `--size` — Target crate size (default: 80).
- `--usb` — Only use tracks already on this USB.
- `--from-playlist` — Start from an existing playlist instead of filtering.
- `--auto` — Skip interactive editing, output best auto-generated crate.
- `--rekordbox` — Path to Rekordbox XML export (for hot cue data). Auto-detected if default export path exists.

**Also: standalone folder/USB profile command:**
```bash
cratedigger profile-folder /Volumes/DJ-USB
cratedigger profile-folder ~/Music/DJ/melodic-techno
```
Works on any folder — not just crates. Shows BPM histogram, style breakdown, length distribution, key coverage, hot cue status, total duration. Useful for getting a quick read on what's on your USB or in any subfolder of your library.

**Tests to write:**
- Energy zone coverage: crate has tracks in all 4 energy zones.
- BPM variety: no single BPM represents > 40% of the crate.
- Key diversity: at least 12 of 24 Camelot keys represented.
- Size targeting: `--size 80` produces ~80 tracks (±10%).
- Thin zone warning: if only 2 peak tracks exist → warning shown.
- Crate profile: BPM median, style %, avg length calculated correctly.
- Hot cue detection: reads Rekordbox XML → correct cue/no-cue indicator per track.
- Tracks without cues flagged in warnings section.
- Interactive add/remove: changes persist in the crate.
- Rekordbox 7 XML: energy zones become sub-playlists.
- profile-folder: works on arbitrary folder, not just crates.

**Definition of done:**
Rico can run `gig crate --name "Saturday" --vibe "melodic-techno,deep-house"`, get a crate of 80-100 tracks organized by energy zone with Camelot keys visible, tweak it interactively, and export to Rekordbox 7 XML.

---

### Session 6: Practice mode — explore your crate

**Goal:** Help the DJ explore transitions between tracks in their crate, focusing on combinations that need practice.

**Command signature:**
```bash
cratedigger gig practice --crate "Saturday at Warehouse"
cratedigger gig practice --crate "Saturday at Warehouse" --focus hard
cratedigger gig practice --pair "Artist A - Track B" "Artist C - Track D"
cratedigger gig practice --history
```

**Behavior:**

1. **Load crate** — Pull the saved crate from Session 5.

2. **Transition explorer** — Pick any two tracks and get a compatibility analysis:
   ```
   TRANSITION: Artist A - Track B  →  Artist C - Track D
   ────────────────────────────────────────
   BPM:      124 → 128 (+4)        Difficulty: MEDIUM
   Key:      8A → 9A (+1)          Compatible ✓ (Camelot +1)
   Energy:   0.6 → 0.85 (+0.25)   Big jump — consider a bridge track
   
   Suggestion: Loop a 16-bar section to ride the BPM up gradually.
   Key transition is smooth — focus on the energy jump.
   
   Bridge candidates from your crate:
     Artist E - Track F  (126 BPM, 8A, energy 0.72) — splits the gap
   ```

3. **Smart suggestions** — "Which transitions should I practice?"
   - Analyze all possible pairs in the crate (or a random sample if crate is large).
   - Surface the most interesting/challenging combinations:
     - Tracks you might play back-to-back based on energy adjacency but with a tricky key/BPM gap.
     - "These 5 transitions are the trickiest in your crate."

4. **Practice logging** — After drilling a transition:
   - `log --confidence high` — mark as practiced.
   - Track practice count and confidence over time.
   - "You've practiced Track A → Track B 3 times. Last confidence: medium."

5. **History** — `--history` shows all practice sessions across all crates.

**Tests to write:**
- Transition analysis: known BPM/key/energy pairs → correct difficulty score.
- Bridge track suggestion: candidate sits between the two tracks in BPM + energy.
- Practice log persists across sessions.
- Smart suggestions: hardest transitions surfaced first.

**Definition of done:**
Rico loads his gig crate, asks "what should I practice?", gets the 5 trickiest transitions with specific advice, drills them, and logs confidence.

---

### Session 7: Gig day export + checklist

**Goal:** A single command that packages the crate for USB and validates everything.

**Command signature:**
```bash
cratedigger gig export --crate "Saturday at Warehouse" --usb /Volumes/DJ-USB
cratedigger gig checklist --crate "Saturday at Warehouse"
```

**Behavior:**

1. **Export** — `gig export`:
   - Copy all crate tracks to USB (skip if already present).
   - Generate Rekordbox 7 XML with the crate organized by energy zone as sub-playlists.
   - Auto-run `preflight` on the USB after export.
   - Report: "Exported 87 tracks. USB preflight: all clear."

2. **Checklist** — `gig checklist`:
   ```
   GIG CHECKLIST: Saturday at Warehouse
   ────────────────────────────────────────
   ✓  Crate finalized (87 tracks)
   ✓  Energy zones covered (warm-up: 14, groove: 24, build: 31, peak: 18)
   ✓  All tracks on USB
   ✓  All tracks analyzed in Rekordbox
   ✓  USB preflight passed
   ✗  BPM range narrow (124-128 only) — consider adding some 118-122 for warm-up flexibility
   
   VERDICT: Ready. Crate is solid.
   ```

3. **Backup USB** — If `--backup /Volumes/BACKUP-USB` is provided, mirror the primary USB.

**Tests to write:**
- Export copies only missing tracks (doesn't duplicate).
- Preflight runs automatically after export.
- Checklist flags thin energy zones.
- Backup USB mirrors primary USB contents.
- Rekordbox 7 XML has energy zone sub-playlists.

**Definition of done:**
Rico runs `gig export`, plugs USB into CDJs, and his crate is there — organized by energy zone in Rekordbox, with every track analyzed and ready to play.

---

## Workflow 3: Discovery (Priority: MEDIUM)

### The real moment
It's your weekly digging session. You want to find new tracks you'd actually play — not random recommendations, but music that fits your sound, from labels and artists you trust or should know about.

### What exists
`dig weekly`, `dig label`, `dig artist`, `dig-sleeping` — each produces output but they don't connect back to your library or lead to action.

### What's missing
The "so what?" step. Discovery should end with an acquisition list, not just a printout. Right now you can find music but there's no pipeline from "interesting" to "purchased" to "in my library."

### The target flow
```
Weekly dig session
    ↓
cratedigger dig session  ← NEW: guided weekly routine
    ├── dig weekly (new releases in your styles)
    ├── dig artist (new from followed ARTISTS — primary)
    ├── dig sleeping (tracks you stream but don't own)
    ├── Cross-reference against library (already own it?)
    ├── Preview tracks (Spotify 30s clips)
    ├── DJ flags tracks → added to wishlist
    └── Summary: "12 new finds this week"
    ↓
cratedigger wishlist  ← NEW: acquisition pipeline
    ├── wishlist show (all flagged tracks)
    ├── wishlist links (SoundCloud / artist pages / Bandcamp links)
    └── wishlist → intake (after download, auto-flow into intake)
```

---

### Session 8: Wishlist system + discovery-to-action pipeline

**Goal:** A persistent wishlist that captures tracks from any discovery command and leads to purchase, closing the loop between "found it" and "it's in my library."

**Command signature:**
```bash
cratedigger wishlist show
cratedigger wishlist show --style "melodic-techno" --sort priority
cratedigger wishlist add "Artist - Track" --source dig-weekly --priority high
cratedigger wishlist find
cratedigger wishlist clear --downloaded
```

**Behavior:**

1. **Wishlist storage** — New SQLite table `wishlist`:
   - Fields: artist, title, source (dig-weekly/dig-artist/dig-sleeping/manual), date_added, priority (low/medium/high), style_tag, preview_url, find_urls (JSON: {soundcloud: url, bandcamp: url, artist_site: url, youtube: url}), status (new/previewed/downloaded/in-library).
   - Any `dig` command can pipe results into the wishlist with a `--save` flag.
   - Note: Rico's acquisition sources are SoundCloud (free downloads/private links), direct from artists, and YouTube/Spotify rips — NOT traditional stores. The "find" step is about locating downloadable versions, not purchasing.

2. **Integration with dig commands** — Every discovery command gets a `--save` flag:
   ```bash
   cratedigger dig weekly --styles "melodic-techno" --save
   ```
   After showing results, prompt: "Save 8 tracks to wishlist? [all/select/none]"
   - `select` mode: DJ picks which tracks to save interactively.
   - Each saved track gets source attribution and timestamp.

3. **Wishlist show** — Display saved tracks with smart grouping:
   ```
   WISHLIST (23 tracks)
   ────────────────────────────────────────
   HIGH PRIORITY (5)
     1. Solomun - After Rain (Original Mix)     [dig-label, Mar 12]
     2. Innellea - Vigilance (Extended)          [dig-weekly, Mar 10]
     ...
   
   MEDIUM PRIORITY (11)
     ...
   
   ALREADY IN LIBRARY (3) — auto-detected
     ✓ Stephan Bodzin - Zulu (you own this)
     ...
   ```

4. **Find links** — `wishlist find`:
   - For each track, search for downloadable sources:
     - SoundCloud: search for artist + title, check if free download is available.
     - Bandcamp: search for artist, check if track is available (often pay-what-you-want).
     - YouTube: search for official upload or set containing the track.
     - Artist website/social: if known from enrichment.
   - Display as clickable links (terminal hyperlinks where supported).
   - Mark tracks as "downloaded" after DJ confirms.
   - Downloaded tracks flow into intake: "Run `cratedigger intake` to process your new downloads."

5. **Library cross-reference** — Automatically check wishlist against library:
   - Fuzzy match artist + title (handle remix variants).
   - Flag tracks already owned so you don't download duplicates.
   - Update status to "in-library" when track is detected in a scan.

**Flags:**
- `--style` — Filter by style tag.
- `--source` — Filter by discovery source (dig-weekly, dig-artist, etc.).
- `--sort` — Sort by: priority, date, artist, source.
- `--downloaded` — Show/clear only downloaded tracks.
- `--export` — Export wishlist as CSV or JSON.

**Tests to write:**
- Add track to wishlist → persists in SQLite.
- Duplicate detection: same track from two dig sessions → one entry, updated source.
- Library cross-reference: track in wishlist + library → status becomes "in-library."
- Find link generation: mock SoundCloud/Bandcamp/YouTube search results.
- `--save` flag on dig commands: verify tracks pipe into wishlist correctly.
- Priority sorting: high → medium → low, then by date within each tier.

**Definition of done:**
Rico runs `dig session --save`, previews tracks, saves favorites to wishlist, runs `wishlist find` to get SoundCloud/Bandcamp/YouTube links, downloads tracks, then runs `intake` to process them into his library. Full circle.

---

### Session 9: Smart weekly routine

**Goal:** A single command that runs the entire weekly digging session — combining multiple discovery sources, cross-referencing against the library, and outputting actionable results.

**Command signature:**
```bash
cratedigger dig session
cratedigger dig session --quick
cratedigger dig session --deep --include-artists "solomun,tale-of-us,mind-against"
```

**Behavior:**

1. **Aggregate discovery** — Run multiple dig commands in sequence:
   - `dig artist` — New releases from your **followed artists** (primary discovery source).
   - `dig weekly` — New releases across your active styles.
   - `dig-sleeping` — Tracks in your streaming that aren't in your library yet.
   - Deduplicate results across all three sources.
   - Note: labels are secondary for Rico — he follows artists more than labels. Label digging is available via `dig label` separately but not part of the default session.

2. **Cross-reference** — For every discovered track:
   - Check against library (already own it → skip).
   - Check against wishlist (already saved → show status).
   - Flag genuinely new tracks.

3. **Present results** — Grouped by source, with preview capability:
   ```
   WEEKLY DIG SESSION — March 15, 2026
   ────────────────────────────────────────
   New releases (Traxsource):     14 found, 11 new to you
   Followed labels:                8 found,  6 new to you
   Sleeping on (Spotify/YouTube):  5 found,  3 new to you
   ────────────────────────────────────────
   Total new discoveries: 20
   
   Preview? [yes/no]
   ```

4. **Preview + save flow** — Step through tracks with Spotify previews:
   - Play 30s clip → "Save to wishlist? [yes/no/skip] Priority? [high/medium/low]"
   - Batch mode: preview all, then select which to save.

5. **Quick mode** — `--quick` skips preview, just shows the list and saves all to wishlist at medium priority.

**Configuration (YAML):**
```yaml
dig_session:
  followed_artists:          # PRIMARY discovery source
    - solomun
    - tale-of-us
    - mind-against
    - stephan-bodzin
    - innellea
  styles:
    - melodic-techno
    - deep-house
  sources:
    - artists                # artist releases first
    - weekly                 # then genre-wide new releases
    - sleeping               # then streaming gaps
  # Optional: add followed_labels if Rico starts tracking labels later
```

**Tests to write:**
- Deduplication: same track from weekly + artist dig → appears once.
- Library cross-reference: owned tracks excluded from "new" count.
- Quick mode: no preview prompts, all tracks saved at medium priority.
- Config loading: YAML artist list drives dig-artist queries.
- Summary stats: counts are accurate across sources.

**Definition of done:**
Rico runs `dig session` once a week, sees new releases from artists he follows + genre-wide discoveries, previews them, saves favorites, and has a clear list of what to download.

---

### Session 10: Deep artist research + Resident Advisor + profile-driven recommendations

**Goal:** Transform `dig artist` from a basic API lookup into a comprehensive artist research tool that combines APIs, Resident Advisor, and web search to build rich artist profiles — especially for underground electronic artists that APIs miss. Also surface profile-driven recommendations and gaps.

**Command signatures:**
```bash
# Deep artist research
cratedigger dig artist "Solomun" --deep
cratedigger dig artist "Solomun" --deep --save

# Start from a festival or club
cratedigger dig festival "Dekmantel 2025"
cratedigger dig club "Berghain" --recent
cratedigger dig club "Fabric" --residents

# Start from a label
cratedigger dig label "Afterlife" --artists

# Profile-driven gap detection
cratedigger dig gaps
cratedigger dig suggest --explore "breaks"
```

**Behavior:**

1. **Deep artist research** — `dig artist "Solomun" --deep`:
   Combine multiple sources into a rich artist profile:

   **Layer 1: APIs (existing)**
   - Spotify: genre tags, popularity, related artists, top tracks.
   - MusicBrainz: discography, labels, release dates, ISRCs.
   - Discogs: label associations, vinyl releases (if configured).

   **Layer 2: Resident Advisor (NEW)**
   - RA has a GraphQL API that returns: artist bio, follower count, related artists, top venues they play, cities they're active in, labels, social media links (SoundCloud, Bandcamp, Instagram).
   - Event history: where they've played, who they've shared lineups with.
   - Recursive related artists: start from one artist, discover their network.

   **Layer 3: Web search (NEW)**
   - For underground artists that APIs miss, run a targeted web search.
   - Search for: "[artist] discography", "[artist] SoundCloud", "[artist] Bandcamp", "[artist] DJ set".
   - Particularly valuable for artists with no Spotify presence (SoundCloud-only, Bandcamp-only).
   - Scrape structured data from results (release lists, social links, label pages).

   **Output: Artist Profile**
   ```
   ARTIST PROFILE: Solomun
   ────────────────────────────────────────
   Bio: Mladen Solomun, Bosnian-German DJ/producer based in Hamburg.
        Known for melodic house/techno with emotional depth.
   
   Labels: Diynamic Music (founder), 2020 Vision, Watergate
   
   Discography:
     2024  Nobody Is Not Loved (Album)     Diynamic Music
     2023  Home (Single)                    Diynamic Music
     2020  Nobody Is Not Loved (Single)     Diynamic Music
     2012  Dance Baby (EP)                  Diynamic Music
     ...
   
   Where they play:
     Pacha Ibiza (resident), Printworks London, Watergate Berlin,
     DC-10 Ibiza, Space Miami
   
   Related artists (RA):
     Tale Of Us, Mind Against, Maceo Plex, Dixon, Adriatique
   
   Social:
     SoundCloud: soundcloud.com/solomun
     Bandcamp:   —
     Instagram:  @solomun
     RA:         ra.co/dj/solomun
   
   In your library: 4 tracks owned
   On your wishlist: 1 track
   
   [Save related artists to followed list? yes/no]
   [Add top tracks to wishlist? yes/no]
   ```

2. **Start from a festival** — `dig festival "Dekmantel 2025"`:
   - Search web + RA for the festival lineup.
   - For each artist on the lineup: quick profile (genre, RA followers, social links).
   - Cross-reference against your library: "You have tracks from 8 of 47 artists."
   - Highlight unknown artists worth researching further.
   - "Deep dive" into any artist from the lineup with `--deep`.

3. **Start from a club** — `dig club "Berghain" --recent`:
   - Search RA for recent events at that venue.
   - Extract all artists from those lineups.
   - Surface artists who play there frequently (residents or regulars).
   - "Berghain's most booked artists this year: [list]"
   - Cross-reference against your library and wishlist.

4. **Start from a label** — `dig label "Afterlife" --artists`:
   - Pull the full artist roster from RA + Discogs + web search.
   - For each artist: follower count, recent releases, social links.
   - "Afterlife's most prolific artists: [list]"
   - Highlight artists you don't already follow.

5. **Profile-driven gap detection** — `dig gaps`:
   ```
   LIBRARY GAPS
   ────────────────────────────────────────
   You stream a lot of breaks but own 0 tracks.
     → Try: Overmono, SHERELLE, object blue
   
   Your melodic-techno is concentrated in 124-126 BPM.
     → Explore slower (118-122) for warm-up sets.
   
   You play 8A more than any other key but have no 8B tracks.
     → 8B is the relative minor — great for transitions.
   
   You watched 7 Cercle sets this month featuring organic house artists.
     → You might be gravitating toward this style. Explore?
   ```

6. **Explore mode** — `dig suggest --explore "breaks"`:
   - "You don't play breaks yet. Here's a starter pack: 10 accessible tracks that match your BPM range and energy preferences."
   - Bridge tracks: music that sits between your current sound and the new genre.
   - Sources: RA related artists in that genre + Spotify + web search.

**Data sources priority for artist research:**
| Source | What it provides | Reliability for underground |
|--------|-----------------|---------------------------|
| Resident Advisor | Bio, events, venues, related artists, labels | HIGH — RA is the electronic music bible |
| Spotify | Genre, popularity, related artists, top tracks | MEDIUM — misses SoundCloud-only artists |
| MusicBrainz | Discography, ISRCs, release dates | MEDIUM — good for released music |
| Discogs | Label associations, vinyl releases | HIGH for techno/house |
| Web search | Everything else — bios, social links, interviews | FILL THE GAPS — catches what APIs miss |

**Tests to write:**
- Deep artist profile: mock RA + Spotify + web search → combined profile correct.
- Festival lineup: mock RA event → artists extracted and cross-referenced.
- Club research: mock RA venue events → regular artists surfaced.
- Library cross-reference: owned tracks shown in artist profile.
- Unknown artist (no Spotify): RA + web search still produces useful profile.
- Gap detection: library with no breaks + Spotify with breaks → gap identified.
- Explore mode: results match the target genre + DJ's BPM range.

**Definition of done:**
Rico types `dig artist "Solomun" --deep` and gets a comprehensive profile page. Rico types `dig festival "Dekmantel 2025"` and discovers 10 artists he's never heard of. Rico types `dig club "Berghain" --recent` and sees who's been playing there.

---

## Workflow 4: Library Health (Priority: MEDIUM-LOW)

### The real moment
Your library has grown to 2000+ tracks over years. Some have garbage tags, some are duplicates, some are old tracks you never play. You want a clean, trustworthy library.

### What exists
`scan`, `fix-all`, `fix-dupes`, `fix-filenames`, `fix-tags`, `report` — this is actually the most complete workflow already.

### What's missing
Mainly a "library audit" mode that gives you an actionable health dashboard and guides you through fixing issues in priority order. The individual fix commands exist but there's no orchestration layer that says "here's what's wrong, here's the order to fix it, let's go."

### The target flow
```
"My library feels messy"
    ↓
cratedigger audit  ← NEW: comprehensive health scan
    ├── Scan entire library
    ├── Score overall health (0-100)
    ├── Categorize issues by severity
    ├── Generate prioritized fix plan
    └── Guided mode: walk through fixes interactively
    ↓
cratedigger audit --fix  ← guided remediation
    ├── Critical first (corrupt files, zero-byte)
    ├── Then high (missing BPM/key)
    ├── Then medium (naming inconsistencies)
    ├── Then low (missing artwork, incomplete tags)
    └── Progress: "Fixed 34/89 issues. 55 remaining."
    ↓
cratedigger stale  ← NEW: what should you archive?
    ├── Cross-reference with play history
    ├── Identify tracks never played or 12+ months stale
    └── Suggest archive/remove candidates
```

---

### Session 11: Library audit command

**Goal:** A comprehensive library health scan that diagnoses issues, prioritizes them, and guides the DJ through fixing them.

**Command signature:**
```bash
cratedigger audit ~/Music/DJ
cratedigger audit ~/Music/DJ --report
cratedigger audit ~/Music/DJ --fix
cratedigger audit ~/Music/DJ --fix --category critical
```

**Behavior:**

1. **Deep scan** — Scan the entire library and check every track for:
   - **Critical:** Corrupt files (can't read audio), zero-byte files, unreadable formats.
   - **High:** Missing BPM, missing key, no genre tag, no artist/title.
   - **Medium:** Inconsistent filename format, true duplicate tracks (same ISRC or near-identical fuzzy match), naming doesn't match tags.
   - **Medium (mix variants):** Original Mix + Extended Mix of the same track detected — flag for DJ to decide which to keep. These are NOT auto-resolved; Rico wants to choose.
   - **Low:** Missing album tag, missing year, no ISRC.
   - **NOT CHECKED:** Artwork. Rico doesn't care about cover art on CDJs — skip entirely.

2. **Health score** — Compute an overall score (0-100):
   ```
   LIBRARY AUDIT: ~/Music/DJ
   ────────────────────────────────────────
   Health Score: 72/100
   
   Tracks scanned:    2,147
   
   CRITICAL (3)
     ✗ 2 corrupt files (can't read audio data)
     ✗ 1 zero-byte file
   
   HIGH (47)
     ✗ 23 tracks missing BPM
     ✗ 18 tracks missing key
     ✗ 6 tracks with no genre tag
   
   MEDIUM (89)
     ✗ 34 inconsistent filenames
     ✗ 24 filename/tag mismatches
     ✗ 12 true duplicates (6 pairs)
     ✗ 19 mix variants to review (Original + Extended of same track)
   
   LOW (34)
     ✗ 34 missing year tag
   
   Run `cratedigger audit --fix` to start fixing issues.
   ```

3. **Report mode** — `--report` exports the full audit as a JSON or Markdown file for reference.

4. **Fix mode** — `--fix` walks through issues interactively by severity:
   - **Critical:** "Delete corrupt file `Artist - Track.mp3`? [yes/skip]"
   - **High:** "Track `Unknown - Untitled.wav` has no tags. Run enrichment? [yes/skip/manual]"
     - If `manual`: prompt for artist/title, then enrich from that.
   - **Medium:** "Fix filename `01_weird_label_Track.mp3` → `Artist - Track (Original Mix).mp3`? [yes/skip]"
   - **Medium (true dupes):** "True duplicate: `Track.mp3` (320kbps) and `Track.mp3` (128kbps). Keep which? [1/2/skip]"
   - **Medium (mix variants):** "Mix variants found:
       1. Artist - Track (Original Mix).mp3  [4:32, 124 BPM]
       2. Artist - Track (Extended Mix).wav   [7:18, 124 BPM]
     Keep which? [1/2/both/skip]"
   - Each fix is applied immediately and logged.
   - Progress bar: "Fixed 12/47 high-priority issues..."

5. **Category filter** — `--category critical` fixes only critical issues. Useful for quick passes.

6. **Progress persistence** — Store audit results and fix progress in SQLite:
   - "Last audit: March 15. Fixed 34/89 issues. 55 remaining."
   - Re-running audit skips already-fixed issues and detects new ones.

**Tests to write:**
- Health score calculation: known library state → expected score.
- Severity categorization: corrupt file → critical, missing BPM → high.
- True duplicate detection: same ISRC or identical artist+title+duration → flagged as true dupe.
- Mix variant detection: "Track (Original Mix)" + "Track (Extended Mix)" → flagged as mix variant (separate category from true dupes).
- Artwork NOT checked: tracks with missing artwork don't appear in any severity level.
- Fix mode: applying a filename fix actually renames the file.
- Mix variant fix: DJ chooses "both" → both kept, no further flagging.
- Progress persistence: fix 5 issues → re-run → 5 fewer shown.
- Report export: valid JSON/Markdown with all issues listed.

**Definition of done:**
Rico runs `audit` on his library, sees a clear health score with prioritized issues, runs `--fix`, and resolves the critical and high-priority issues in one session.

---

### Session 12: Stale track detection

**Goal:** Identify tracks the DJ never plays and suggest archiving or removing them to keep the library focused.

**Command signature:**
```bash
cratedigger stale ~/Music/DJ
cratedigger stale ~/Music/DJ --since 12months --action archive
cratedigger stale ~/Music/DJ --rekordbox ~/Music/rekordbox-export.xml
```

**Behavior:**

1. **Play history analysis** — Cross-reference library against available play data:
   - Rekordbox play count (from XML export or database — Rekordbox 7 tracks this).
   - Date added to library (from file creation date or DB record).
   - Spotify listening history (if configured — do you stream tracks you also own?).

2. **Stale classification:**
   - **Never played:** In library but zero plays in Rekordbox. "You have 340 tracks you've never played."
   - **Dormant:** Not played in 12+ months (configurable with `--since`).
   - **Superseded:** You own an Original Mix AND Extended Mix — one might be redundant.
   - **Outliers:** Tracks that don't match your profile (wrong genre, extreme BPM outlier).

3. **Review mode** — Group stale tracks by genre for easier review:
   ```
   STALE TRACKS: 340 never played, 89 dormant (12+ months)
   ────────────────────────────────────────
   melodic-techno/ (45 never played)
     Artist A - Track B (added 2024-03-12)
     Artist C - Track D (added 2023-11-05)
     ...
   
   deep-house/ (23 never played)
     ...
   
   Action: [archive/delete/keep/preview]
   ```

4. **Archive action** — Move stale tracks to an `_archive/` folder (not delete — non-destructive).

5. **Stats** — After review:
   ```
   Archived: 45 tracks (1.2 GB reclaimed)
   Kept: 12 tracks (you decided to give them another chance)
   Library size: 2,102 → 2,057 active tracks
   ```

**Tests to write:**
- Never-played detection: track with 0 plays → flagged.
- Dormant detection: last played 13 months ago + threshold 12 months → flagged.
- Archive moves files to `_archive/` subfolder, doesn't delete.
- Genre grouping: stale tracks grouped correctly by genre tag.
- Rekordbox play count parsing from XML export.

**Definition of done:**
Rico runs `stale`, sees which tracks he's neglecting, archives the ones he doesn't need, and reclaims USB space for tracks he actually plays.

---

## Workflow 5: Profile & Identity (Priority: LOW — builds on others)

### The real moment
You want to understand your own sound. What do you actually play? What are your signature genres, BPM ranges, key preferences? This powers everything else — discovery recommendations, gig prep suggestions, and eventually a public DJ profile.

### What exists
`profile build/show`, `dig-sleeping` — basic profile construction.

### What's missing
The three-source cross-reference (USB + Spotify + YouTube) and actionable insights. The profile exists as data but doesn't feed back into other workflows or tell you anything surprising about yourself.

### The target flow
```
"What's my sound?"
    ↓
cratedigger profile build  ← enhanced: three sources
    ├── Library scan (what you own)
    ├── Spotify import (what you stream)
    ├── YouTube import (sets you study)
    └── Merge into unified DJ profile
    ↓
cratedigger profile show  ← enhanced: meaningful insights
    ├── Top genres, BPM range, key preferences
    ├── Library vs streaming divergence
    ├── Favorite labels, signature artists
    ├── Temporal trends (sound evolution over time)
    └── Identity summary: "your sound in one paragraph"
    ↓
Profile feeds into other workflows:
    ├── gig plan → pre-filters tracks matching your sound
    ├── dig session → prioritizes genres you play
    ├── dig suggest → knows your gaps and comfort zone
    └── intake → suggests style categories based on your profile
```

---

### Session 13: Profile enrichment — three-source merge

**Goal:** Build a comprehensive DJ profile by merging library analysis, Spotify listening history, and YouTube watching patterns.

**Command signature:**
```bash
cratedigger profile build
cratedigger profile build --refresh
cratedigger profile show
cratedigger profile show --detailed
cratedigger profile export
```

**Behavior:**

1. **Source 1: Library (what you own)** — Already built. Scan tracks and extract:
   - Genre distribution.
   - BPM distribution (mean, median, range, clusters).
   - Key distribution (Camelot wheel heatmap).
   - Energy distribution.
   - Top artists by track count.
   - Top labels by track count.
   - Date-added timeline (when did you acquire what).

2. **Source 2: Spotify (what you stream)** — Via Spotify API (already configured):
   - Recent listening history (last 50 tracks).
   - Top artists (short/medium/long term).
   - Top tracks (short/medium/long term).
   - Saved tracks.
   - Compare: what you stream vs what you own. Divergence = opportunity.

3. **Source 3: YouTube (what you study)** — Via ytmusicapi:
   - Liked music videos.
   - Watch history (DJ sets, boiler rooms, festival recordings).
   - Extract artist/track mentions from video titles.
   - "You watch a lot of Cercle sets" → maps to genres and artists you're studying.

4. **Merge logic** — Combine into a unified profile with weighted scoring:
   - Library (weight: 3x) — what you actually play matters most.
   - Spotify (weight: 2x) — what you listen to reflects taste.
   - YouTube (weight: 1x) — what you watch reflects aspiration.
   - Conflict resolution: if library says "deep house" but Spotify says "breaks," that's a divergence insight, not an error.

5. **Profile show** — Enhanced display:
   ```
   DJ PROFILE: Rico
   ────────────────────────────────────────
   Sound Identity:
   "Melodic techno and deep house DJ with a strong lean toward
   European labels. Your BPM sweet spot is 122-126 and you favor
   minor keys (Camelot A-side). You stream more breaks and
   Afro house than you own — possible growth direction."
   
   Genre Breakdown:
     Melodic Techno    ████████████████  42%
     Deep House        ████████████      31%
     Afro House        ████              10%
     Breaks            ███                7%
     Other             ████              10%
   
   BPM Profile:        122-126 (core), 118-130 (range)
   Key Preferences:    8A, 5A, 11A (minor key bias)
   Energy Range:       0.55 - 0.82 (mid-to-high, no extremes)
   
   Top Labels:         Afterlife, Drumcode, Diynamic, Innervisions
   Top Artists:        Solomun, Tale Of Us, Stephan Bodzin, Mind Against
   
   Library ↔ Streaming Divergence:
     You stream breaks (7% of Spotify) but own 0 tracks.
     You stream Afro house (12% of Spotify) but only own 10%.
     → Consider expanding these areas.
   
   Library growth:     +127 tracks in last 3 months
   Oldest track:       2019-04-12
   ```

6. **Export** — `profile export` outputs JSON for use by other tools or for a future public profile page.

**Tests to write:**
- Library profile: known track set → expected genre/BPM/key distributions.
- Spotify merge: mocked API response → correctly weighted into profile.
- YouTube merge: video titles parsed for artist/track mentions.
- Divergence detection: library genres vs Spotify genres → gaps identified.
- Profile persistence: build once → show without re-scanning.
- Refresh: `--refresh` re-scans all sources and updates.

**Definition of done:**
Rico runs `profile show` and learns something about his sound he didn't know — particularly where his streaming diverges from his library.

---

### Session 14: Profile-powered integration

**Goal:** Feed profile data into other workflows so they get smarter over time.

**Tasks:**

1. **gig crate integration:**
   - Default `--vibe` filter to profile's top genres if not specified.
   - Default `--bpm` range to profile's BPM sweet spot.
   - "Based on your profile, filtering for melodic-techno at 122-126 BPM."

2. **dig session integration:**
   - `dig artist` defaults to profile's top artists + Spotify followed artists.
   - `dig weekly` defaults to profile's genre list.
   - `dig suggest` uses divergence data for recommendations.
   - YouTube watching patterns feed into artist discovery: "You've watched 5 Boiler Room sets featuring X — follow this artist?"

3. **intake integration:**
   - When a track has unknown genre after enrichment, suggest the DJ's most common style as the default categorization in the review queue.
   - "This track has no genre tag. Your most common style is melodic-techno — assign it there? [yes/other/skip]"

4. **Profile as config** — Store profile-derived defaults in YAML:
   ```yaml
   profile:
     primary_styles:
       - melodic-techno
       - deep-house
     bpm_range: [122, 126]
     top_artists:
       - solomun
       - tale-of-us
       - mind-against
     youtube_insights:
       frequently_watched_artists:
         - solomun
         - stephan-bodzin
       set_sources:       # Boiler Room, Cercle, etc.
         - boiler-room
         - cercle
     divergence_genres:
       - breaks
       - afro-house
   ```
   Other commands read this as intelligent defaults.

**Tests to write:**
- gig crate without `--vibe`: uses profile's top genres.
- dig session without `--artists`: uses profile's top artists + Spotify followed artists.
- intake genre suggestion: unknown genre → profile's top genre offered in review queue.
- YouTube insight: frequently watched artist → auto-added to followed artists suggestion.
- Profile config YAML: generated correctly from profile data.

**Definition of done:**
Other workflows feel personalized without the DJ having to specify preferences every time. The tool learns from the library it manages.

---

## Workflow 6: Web UI Portal (Priority: AFTER CLI workflows are solid)

### The real moment
The CLI workflows are working. Now you want a visual interface — both for yourself (some tasks are nicer with a UI) and for demo/portfolio value. But the current web UI is flat: Home, Library, Dig, Enrich. These labels don't map to how a DJ thinks about their work.

### What exists
React 19 frontend with 4 pages, FastAPI backend with 21 endpoints. Beautiful dark theme with DJ palette. But navigation doesn't reflect the workflow domains.

### What's missing
A portal that presents the 5 workflow domains as clear entry points, with progressive disclosure into each workflow. Not a redesign of the tech — a redesign of the navigation and information architecture.

### Session 15: Workflow-based portal and navigation

**Goal:** Replace the flat 4-page navigation with a portal that presents CrateDigger's capabilities as 5 workflow domains, each drilling down into the relevant features.

**Landing page layout:**
```
CRATEDIGGER
────────────────────────────────────────

┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  📥 INTAKE  │  │  🎛️ GIG     │  │  🔍 DISCOVER│
│             │  │   PREP      │  │             │
│ Process new │  │ Build crate │  │ Find new    │
│ downloads   │  │ for a gig   │  │ music       │
└─────────────┘  └─────────────┘  └─────────────┘

┌─────────────┐  ┌─────────────┐
│  🏥 LIBRARY │  │  👤 PROFILE │
│   HEALTH    │  │             │
│ Clean &     │  │ Understand  │
│ maintain    │  │ your sound  │
└─────────────┘  └─────────────┘

Recent activity:
  • Last intake: 27 tracks processed (Mar 14)
  • Next gig: Saturday at Warehouse (crate: 87 tracks)
  • Wishlist: 23 tracks to download
  • Library health: 72/100
```

**Each domain drills down into its workflow:**

- **Intake** → Scan new folder, review queue (track-by-track approval UI), enrichment status, recent intakes history.
- **Gig Prep** → Crate builder (visual energy zones), practice mode, export to USB, preflight results, folder/USB profile.
- **Discover** → Weekly dig results, artist deep-dive (rich profile cards), festival/club/label research, wishlist management.
- **Library** → Audit dashboard (health score + issue breakdown), fix mode, stale track detection, library stats.
- **Profile** → DJ identity summary, genre/BPM/key visualizations, streaming divergence, followed artists.

**Design principles:**
- Progressive disclosure: each domain shows a summary card on the portal, then drills into detail.
- The 5 domains map 1:1 to the 5 CLI workflow groups — same backend, different presentation.
- Keep the existing dark theme (terracotta/lime/azure/mauve palette) but reorganize the navigation.
- Cmd+K command palette stays — it's already great for power users.
- Artist profile cards (from deep research) should be visually rich: bio, discography timeline, social links, "in your library" count.

**Technical approach:**
- This is a navigation/layout change, NOT a rewrite. The FastAPI endpoints already exist for most features.
- New endpoints needed: intake status, crate list, wishlist, audit summary, profile summary.
- Move from flat 4-page router to nested routes: `/intake`, `/gig`, `/discover`, `/library`, `/profile`.
- The portal page is a new landing route (`/`) with summary cards.
- Consider migrating inline styles to Tailwind during this session (tech debt from REVIEW.md).

**Tests to write:**
- Portal loads with 5 domain cards.
- Each card shows correct summary data (last intake, next gig, wishlist count, health score).
- Navigation: portal → domain → feature → back to portal works cleanly.
- Artist profile card: renders bio, discography, social links from deep research data.
- Responsive: portal works on mobile (stacked cards).

**Definition of done:**
Open the web UI and immediately understand what CrateDigger can do. Click into any workflow domain and find the relevant features. Artist deep-dive renders as a rich, browsable profile card. This is the "show someone at a gig" version.

---

## Implementation Order

| Priority | Workflow | Sessions | Complexity | Unlocks |
|----------|----------|----------|------------|---------|
| 1 | **New Track Intake** | 1-4 | Medium — mostly wiring existing modules | Daily use, Rekordbox integration, the "I trust this tool" moment |
| 2 | **Gig Prep** | 5-7 | Medium-High — crate builder + energy zone logic is new | Pre-gig confidence, curated crates, USB profile, hot cue awareness |
| 3 | **Discovery** | 8-10 | Medium-High — wishlist is new, RA integration + web search + deep artist profiles are new | Weekly routine, acquisition pipeline, festival/club/label research |
| 4 | **Library Health** | 11-12 | Low-Medium — mostly orchestrating existing fixers | Clean library, ongoing maintenance, space reclaim |
| 5 | **Profile & Identity** | 13-14 | Medium — three-source merge is new, integration is wiring | Personalization across all workflows, self-knowledge |
| 6 | **Web UI Portal** | 15 | Medium — navigation restructure, not a rewrite | Demo quality, portfolio piece, workflow-based UX |

**Total: 15 sessions.** At 1-2 Claude Code sessions per day (30-90 min each), that's roughly 1.5-2 weeks of focused work.

### Dependencies between workflows
- Workflow 1 (Intake) is standalone — start here.
- Workflow 2 (Gig Prep) benefits from intake being done (clean library to plan from).
- Workflow 3 (Discovery) benefits from intake (downloaded tracks flow into it) but can be built in parallel. RA integration makes this the most ambitious workflow.
- Workflow 4 (Library Health) is standalone — can be built anytime.
- Workflow 5 (Profile) should come after at least Workflows 1-3 are working — it enhances them but isn't needed for them to function.
- Workflow 6 (Web UI Portal) should come LAST — build all CLI workflows first, then put the visual layer on top. No point in building a portal for features that don't work yet.

---

## Open Questions Before Starting

1. ~~**What are your style categories?**~~ — Rico categorizes manually. Intake command defaults to interactive sorting.

2. ~~**Rekordbox version?**~~ — Rekordbox 7. XML export module must target v7 schema.

3. **ACTION NEEDED: File paths and storage strategy.** Currently tracks land in Downloads folder then get moved to USB. Rico is considering a Google Drive/cloud storage setup instead. Need to confirm:
   - Source path (where new tracks land after purchase)
   - Destination path (where the organized library lives)
   - Whether to support a cloud sync workflow (Google Drive ↔ local ↔ USB)
   - This does NOT block Session 1 — paths can be passed as arguments. But a sensible default config should be set once the storage decision is made.

4. ~~**API keys status:**~~ — Spotify configured. Discogs not yet (not a blocker — enrichment degrades gracefully).

---

*This plan prioritizes workflows Rico uses every week over features that look impressive in a demo. Build for the working DJ first, portfolio second.*
