# CrateDigger — What's Next

Updated: 2026-03-13

---

## DONE: Phase 1 — Spotify + YouTube (Tasks 2.2, 2.3, 2.4) ✓

Completed 2026-03-13. All three tasks implemented and working:
- `cratedigger spotify sync/show` — pulls top artists (3 time ranges) + top tracks via spotipy
- `cratedigger youtube sync/show` — pulls liked videos + playlists via YouTube Data API v3
- `cratedigger dig-sleeping` — cross-references streaming with USB library, shows gaps
- 34 new tests, all passing. 265/266 total tests passing.
- Config stored in `~/.cratedigger/config.yaml`

**Session learnings documented in `STREAMING_SETUP_LEARNINGS.md`**

---

## Next Up: Phase 2 — Discogs + MusicBrainz Research (Tasks 4.4, 4.5)

**Setup needed:**
- Discogs: Create app at https://www.discogs.com/settings/developers, get personal access token. Free, 60 req/min.
- MusicBrainz: No key needed (1 req/sec rate limit). Set user-agent string.
- Install: `pip install python3-discogs-client musicbrainzngs`

**What we'll build:**

### 4.4 — Label Deep-Dive
- Search Discogs for a label (e.g., "Afterlife", "Drumcode")
- Get all releases + artists on that label
- Cross-reference with your USB library — what do you own?
- Find gaps: artists/releases you're missing
- Get MusicBrainz cross-platform links (Bandcamp, Beatport, SoundCloud URLs)
- CLI: `cratedigger dig label "Afterlife"`

### 4.5 — Artist Research
- MusicBrainz artist search → get MBID → get URL relations (Bandcamp, SoundCloud, etc.)
- Discogs discography + labels
- Spotify follow/play status (if connected)
- USB library track count for this artist
- Output: your relationship with this artist, what you're missing, related artists
- CLI: `cratedigger dig artist "Solomun"`

**Estimated effort:** 1-2 sessions.

---

## Phase 3: Weekly Workflow Automation (Tasks 5.3, 5.4)

**Setup needed:**
- Beatport: No API key needed (HTML scraping). Install `beautifulsoup4` + `requests`.
- EDMTrain: Free API key at https://edmtrain.com/api. Structured JSON, no scraping.

### 5.3 — Weekly Dig (Beatport)
- Load your DJ profile (top genres, BPM range, known labels)
- Scrape Beatport new releases pages for your genres
- Filter by your profile's BPM range + known labels/artists
- Exclude tracks already in your library DB
- Flag tracks by Spotify top artists (if connected)
- CLI: `cratedigger dig weekly`

### 5.4 — Festival Lineup Scanner
- Two input modes: festival name (EDMTrain API) or pasted lineup text
- For each artist: check USB library, check Spotify history
- Categorise: already-own / stream-but-don't-own / unknown
- CLI: `cratedigger dig festival "Sonar 2026"`

**Estimated effort:** 1-2 sessions.

---

## Phase 4: Polish + Integration

### Split cli.py
- Currently ~1,200 lines. Split into `cli/scan.py`, `cli/gig.py`, `cli/dig.py`, `cli/streaming.py`.

### Genre in playlist builder
- Add genre column to `audio_analysis` or join with metadata at query time
- Unblocks `cratedigger gig build --genre "deep house"` working from DB alone

### Structure detection tuning
- Run on 10+ real tracks, compare with actual drop/breakdown positions
- May need per-genre presets (house vs techno vs DnB)

### Merge branches to master
- Currently 5+ feature branches, none merged to master yet

### Fix test_reads_tagged_mp3
- Pre-existing fixture issue in WSL — recreate the MP3 fixture

---

## Credential Checklist

```
[x] Spotify Developer App     → DONE (Dev mode, user-top-read scope)
[x] YouTube Music OAuth        → DONE (Data API v3, device code flow)
[x] Config file                → ~/.cratedigger/config.yaml
[ ] Discogs Personal Token     → https://www.discogs.com/settings/developers
[ ] EDMTrain API Key           → https://edmtrain.com/api
[x] AcoustID API Key           → Already set up
[x] Install fpcalc             → Already installed
```

---

## Suggested Order

1. ~~Spotify + YouTube~~ **DONE**
2. **Discogs label dive** (directly useful for crate digging) ← NEXT
3. **Artist research** (builds on Discogs + MusicBrainz)
4. **Weekly dig** (Beatport scraping, automates Monday routine)
5. **Festival scanner** (seasonal use, lower priority)
6. **Polish** (branch merge, cli split, genre fix)

*Each phase is 1-2 sessions. Total remaining: ~4-6 sessions.*
