# Streaming API Setup Learnings (2026-03-13)

Hard-won knowledge from setting up Spotify and YouTube Music OAuth.

---

## Spotify

### What worked
- **Scope**: `user-top-read` only. Single scope, no issues.
- **Redirect URI**: `http://127.0.0.1:8888/callback` — must be exact match in Dashboard.
- **spotipy 2.26.0** handles OAuth flow + token caching automatically.
- Token cached at `~/.cratedigger/.spotify_cache`.

### What broke
- **`localhost` is banned** (since April 2025). Must use `127.0.0.1`. Error: `INVALID_CLIENT: Invalid redirect URI`.
- **Multiple scopes cause "illegal scope" error** in Development Mode. `user-top-read` alone works fine. `user-top-read user-library-read` → "illegal scope". Tried space-separated, comma-separated, both failed. Root cause unclear — may be a Dev Mode restriction in the Feb/March 2026 API changes.
- **Must add yourself as test user** under "Users and Access" in Dashboard, or you get 403.
- **Premium required** on the app owner's account (since Feb 2026). Test users don't need Premium.
- **Dev mode limit**: 5 test users max, 1 app per developer.

### What we get with user-top-read only
- Top artists: short term (4 weeks), medium term (6 months), long term (all time) — up to 50 each
- Top tracks: medium term — up to 50
- Saved tracks: NOT available (needs user-library-read)
- Followed artists: NOT available (needs user-follow-read)

### Conclusion
Top artists + top tracks is plenty for the "sleeping on" analysis. The missing scopes are nice-to-have, not essential.

---

## YouTube Music

### What worked
- **YouTube Data API v3** (official REST API) works perfectly with OAuth token.
- **Device code flow** for OAuth (TV/Limited Input device type in Google Cloud Console).
- Gets liked videos (filtered by Music category), playlists with track counts.
- Token refresh works with client_id + client_secret.

### What broke
- **ytmusicapi's internal API is broken with OAuth** (as of v1.11.5, March 2026). All calls to `music.youtube.com/youtubei/v1/*` return 400 "Request contains an invalid argument" when an OAuth Authorization header is present. Unauthenticated calls work fine. This appears to be a YouTube Music internal API change, not a ytmusicapi bug per se.
- **Google Cloud OAuth consent screen "Testing" mode**: tokens expire after 7 days. Must either publish the app or re-run OAuth weekly.
- **Must add yourself as test user** on the OAuth consent screen, or you get "Access blocked: has not completed the Google verification process" (403).
- **OAuth client type MUST be "TVs and Limited Input devices"**. Other types (Web, Desktop) don't support the device code flow that ytmusicapi uses.
- **Raw Google token response has `refresh_token_expires_in` field** that ytmusicapi's RefreshingToken doesn't accept. Must strip it and add `expires_at` field.

### Solution: Bypass ytmusicapi, use Data API v3 directly
We rewrote `sync_youtube()` to use `requests` + YouTube Data API v3 endpoints:
- `GET /youtube/v3/videos?myRating=like&videoCategoryId=10` — liked music videos
- `GET /youtube/v3/playlists?mine=true` — user's playlists
- Artist/title extraction from video snippets: split on " - " or use channel name (strip " - Topic")
- Token refresh handled manually via `https://oauth2.googleapis.com/token`

### Data quality notes
- YouTube liked videos include non-music content (finance videos, documentaries). Category filter helps but isn't perfect.
- Artist names from YouTube are noisier than Spotify (channel names vs proper artist metadata).
- The `dig-sleeping` cross-reference handles this gracefully — non-music artists simply don't match library artists.

---

## Config File

Location: `~/.cratedigger/config.yaml`

```yaml
spotify:
  client_id: "..."
  client_secret: "..."

youtube:
  client_id: "..."      # Google Cloud OAuth client ID
  client_secret: "..."  # Google Cloud OAuth client secret
  auth_json: "~/.cratedigger/youtube_oauth.json"
```

---

## Key Takeaways

1. **Both APIs have gotten significantly harder to use** since mid-2025. Spotify's Dev Mode restrictions and YouTube Music's internal API breakage make personal projects painful.
2. **Start with the minimal scope** and add more only if needed. Multi-scope auth is fragile.
3. **Always have a fallback**. ytmusicapi broke → we used the Data API v3 directly.
4. **Test user whitelisting is required on both platforms** and is the #1 cause of 403 errors.
5. **WSL can't open browsers** — the `gio` error is harmless. Just copy the URL manually.
