// V2 API helpers — fetch from CrateDigger backend
const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8899";

export async function fetchStats() {
  const r = await fetch(`${API}/api/library/stats`);
  if (!r.ok) throw new Error(`Stats fetch failed: ${r.status}`);
  return r.json();
}

export async function fetchTracks(params = {}) {
  const q = new URLSearchParams(params);
  const r = await fetch(`${API}/api/library/tracks?${q}`);
  if (!r.ok) throw new Error(`Tracks fetch failed: ${r.status}`);
  return r.json();
}

export async function fetchGenres() {
  const r = await fetch(`${API}/api/library/genres`);
  if (!r.ok) throw new Error(`Genres fetch failed: ${r.status}`);
  return r.json();
}
