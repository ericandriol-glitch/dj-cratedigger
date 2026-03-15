import { useState, useRef, useEffect } from "react";
import { P, F, genreColor } from "../theme";
import { Sec, Loader, Pill } from "../components/ui";
import { fetchApi, API } from "../hooks/useApi";
import {
  Compass, Search, Disc3, Users, Globe, Music,
  MapPin, ExternalLink, ChevronDown, ChevronUp,
  CircleCheck, AlertTriangle, CircleX, Ticket, X,
  User, Flame, TrendingUp, Play, Pause,
} from "lucide-react";
import { usePlayer } from "../hooks/usePlayer";

/* ─── Label Research View ─── */
function LabelResearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [expandedLabel, setExpandedLabel] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const abortRef = useRef(null);
  const timerRef = useRef(null);

  // Cleanup timer on unmount (but don't abort — request survives tab switches)
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const cancel = () => {
    if (abortRef.current) abortRef.current.abort();
    if (timerRef.current) clearInterval(timerRef.current);
    setLoading(false);
    setElapsed(0);
  };

  const search = async () => {
    if (!query.trim() || loading) return;
    // Cancel any previous request
    if (abortRef.current) abortRef.current.abort();
    if (timerRef.current) clearInterval(timerRef.current);

    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setReport(null);
    setElapsed(0);

    // Elapsed timer
    const start = Date.now();
    timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);

    try {
      // Uses API from useApi hook
      const r = await fetch(`${API}/api/dig/label?artist=${encodeURIComponent(query.trim())}`, {
        signal: controller.signal,
      });
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      setReport(data.report);
      if (!data.report) setError("No results found for this artist");
    } catch (e) {
      if (e.name === "AbortError") {
        // User cancelled — don't show error
      } else {
        setError(`Search failed: ${e.message}`);
      }
    }
    clearInterval(timerRef.current);
    timerRef.current = null;
    setLoading(false);
    setElapsed(0);
  };

  return (
    <div>
      {/* Search bar */}
      <div style={{
        display: "flex", gap: 8, marginBottom: 20,
      }}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="Artist name..."
          style={{
            flex: 1, padding: "10px 14px", borderRadius: 10,
            background: P.bgCard, border: `1px solid ${P.border}`,
            color: P.text, fontFamily: F.b, fontSize: 14,
            outline: "none",
          }}
        />
        <button
          onClick={search}
          disabled={loading || !query.trim()}
          style={{
            padding: "10px 18px", borderRadius: 10, border: "none",
            background: (!query.trim() || loading) ? P.bgSurface : P.terracotta,
            color: (!query.trim() || loading) ? P.textMut : "#fff",
            fontFamily: F.d, fontSize: 12, fontWeight: 700,
            cursor: (!query.trim() || loading) ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", gap: 5,
            transition: "all 0.2s ease",
          }}
        >
          <Search size={14} strokeWidth={2.5} />
          {loading ? "Searching..." : "Dig"}
        </button>
      </div>

      {!loading && !report && !error && (
        <div style={{ textAlign: "center", padding: "8px 0 16px", fontSize: 11, fontFamily: F.m, color: P.textMut }}>
          Label research takes ~60-90s due to MusicBrainz rate limits
        </div>
      )}

      {loading && (
        <div style={{ textAlign: "center", padding: "30px 0" }}>
          <Loader text={`Researching labels... ${elapsed}s`} />
          <button onClick={cancel} style={{
            marginTop: 12, padding: "6px 16px", borderRadius: 8, border: `1px solid ${P.border}`,
            background: P.bgCard, color: P.textSec, fontFamily: F.m, fontSize: 11,
            cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 5,
          }}>
            <X size={12} /> Cancel
          </button>
        </div>
      )}
      {error && (
        <div style={{ textAlign: "center", padding: 30, color: P.warning, fontFamily: F.m, fontSize: 12 }}>
          {error}
        </div>
      )}

      {report && (
        <>
          {/* Artist header */}
          <div style={{
            background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14,
            padding: "16px 16px", marginBottom: 16,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <div style={{
                width: 40, height: 40, borderRadius: 10,
                background: `${P.terracotta}15`, border: `1px solid ${P.terracotta}25`,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Users size={18} color={P.terracotta} />
              </div>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700, fontFamily: F.d, color: P.cream }}>
                  {report.artist.name}
                </div>
                {report.artist.disambiguation && (
                  <div style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>
                    {report.artist.disambiguation}
                  </div>
                )}
              </div>
            </div>
            {report.artist.aliases?.length > 0 && (
              <div style={{ fontSize: 11, fontFamily: F.m, color: P.textMut }}>
                aka {report.artist.aliases.join(", ")}
              </div>
            )}
          </div>

          {/* Releases */}
          <Sec label={`Releases (${report.releases.length})`} icon={Disc3} />
          <div style={{
            background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14,
            padding: "12px 14px", marginBottom: 8,
          }}>
            {report.releases.slice(0, 12).map((r, i) => (
              <div key={i} style={{
                display: "flex", gap: 10, padding: "10px 0",
                borderBottom: i < 11 ? `1px solid ${P.borderSub}` : "none",
                alignItems: "center",
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{
                    fontSize: 13, fontFamily: F.b, fontWeight: 600, color: P.text,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>{r.title}</div>
                  <div style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>
                    {r.label || "Self-released"} {r.catalog && `· ${r.catalog}`}
                  </div>
                </div>
                <div style={{ textAlign: "right", flexShrink: 0 }}>
                  <div style={{ fontSize: 10, fontFamily: F.m, color: P.textMut }}>{r.date || "—"}</div>
                  {r.format && (
                    <span style={{
                      fontSize: 9, fontFamily: F.m, color: P.azure, padding: "1px 6px",
                      background: `${P.azure}10`, borderRadius: 4,
                    }}>{r.format}</span>
                  )}
                </div>
              </div>
            ))}
            {report.releases.length > 12 && (
              <div style={{ textAlign: "center", padding: "10px 0", fontSize: 11, fontFamily: F.m, color: P.textMut }}>
                + {report.releases.length - 12} more
              </div>
            )}
          </div>

          {/* Labels */}
          <Sec label={`Labels (${report.labels.length})`} icon={Globe} />
          {report.labels.map((label, i) => {
            const isExpanded = expandedLabel === label.name;
            const roster = report.roster[label.name] || [];
            const sourceTag = label.source && label.source !== "musicbrainz"
              ? ` [${label.source}]` : "";

            return (
              <div key={i} style={{
                background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 12,
                marginBottom: 8, overflow: "hidden",
              }}>
                <button onClick={() => setExpandedLabel(isExpanded ? null : label.name)} style={{
                  width: "100%", display: "flex", alignItems: "center", gap: 10,
                  padding: "12px 14px", background: "none", border: "none",
                  cursor: "pointer", textAlign: "left",
                }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: `${genreColor(i)}12`, border: `1px solid ${genreColor(i)}20`,
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                  }}>
                    <Music size={14} color={genreColor(i)} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 14, fontFamily: F.b, fontWeight: 600, color: P.text,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      {label.name}
                      {sourceTag && (
                        <span style={{ fontSize: 9, fontFamily: F.m, color: P.textMut, marginLeft: 6 }}>
                          {sourceTag}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>
                      {label.country || ""} {label.type ? `· ${label.type}` : ""}
                      {roster.length > 0 && ` · ${roster.length} artists`}
                    </div>
                  </div>
                  {isExpanded
                    ? <ChevronUp size={16} color={P.textMut} />
                    : <ChevronDown size={16} color={P.textMut} />
                  }
                </button>

                {isExpanded && (
                  <div style={{ padding: "0 14px 12px" }}>
                    {/* URLs */}
                    {label.urls?.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
                        {label.urls.map((u, j) => (
                          <a key={j} href={u.url} target="_blank" rel="noopener noreferrer" style={{
                            fontSize: 10, fontFamily: F.m, color: P.azure,
                            padding: "3px 8px", borderRadius: 5,
                            background: `${P.azure}08`, border: `1px solid ${P.azure}15`,
                            textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 3,
                          }}>
                            <ExternalLink size={8} /> {u.type || "link"}
                          </a>
                        ))}
                      </div>
                    )}

                    {/* Roster */}
                    {roster.length > 0 && (
                      <>
                        <div style={{ fontSize: 10, fontFamily: F.m, color: P.textMut, letterSpacing: 1, marginBottom: 6, textTransform: "uppercase" }}>
                          You might also like
                        </div>
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                          {roster.slice(0, 12).map((a, k) => (
                            <span key={k} style={{
                              fontSize: 11, fontFamily: F.b, color: a.in_library ? P.healthy : P.textSec,
                              padding: "3px 8px", borderRadius: 6,
                              background: a.in_library ? `${P.healthy}10` : P.bgSurface,
                              border: `1px solid ${a.in_library ? P.healthy + "20" : P.borderSub}`,
                            }}>
                              {a.name} <span style={{ fontSize: 9, color: P.textMut }}>{a.release_count}</span>
                            </span>
                          ))}
                          {roster.length > 12 && (
                            <span style={{ fontSize: 10, fontFamily: F.m, color: P.textMut, padding: "4px 6px" }}>
                              +{roster.length - 12} more
                            </span>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}


/* ─── Festival Scanner View ─── */
function FestivalScanner() {
  const [name, setName] = useState("");
  const [lineup, setLineup] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("all");
  const abortRef = useRef(null);

  // No cleanup abort — request survives tab switches

  const scan = async () => {
    if (!lineup.trim() || loading) return;
    if (abortRef.current) abortRef.current.abort();

    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const params = new URLSearchParams({
        lineup: lineup.trim(),
        name: name.trim() || "Festival",
      });
      // Uses API from useApi hook
      const r = await fetch(`${API}/api/dig/festival?${params}`, { signal: controller.signal });
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      setReport(data.report);
      if (!data.report) setError("No results");
    } catch (e) {
      if (e.name !== "AbortError") {
        setError("Scan failed — check the API is running on port 8000");
      }
    }
    setLoading(false);
  };

  const catIcon = { "already-own": CircleCheck, "stream-but-dont-own": AlertTriangle, "unknown": CircleX };
  const catColor = { "already-own": P.healthy, "stream-but-dont-own": P.warning, "unknown": P.critical };

  const filtered = report?.artists?.filter(a => {
    if (tab === "all") return true;
    if (tab === "own") return a.category === "already-own";
    if (tab === "stream") return a.category === "stream-but-dont-own";
    if (tab === "unknown") return a.category === "unknown";
    if (tab === "match") return a.genre_match;
    return true;
  }) || [];

  return (
    <div>
      {/* Inputs */}
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Festival name (optional)..."
        style={{
          width: "100%", padding: "10px 14px", borderRadius: 10, marginBottom: 8,
          background: P.bgCard, border: `1px solid ${P.border}`,
          color: P.text, fontFamily: F.b, fontSize: 14, outline: "none",
        }}
      />
      <textarea
        value={lineup}
        onChange={(e) => setLineup(e.target.value)}
        placeholder="Paste lineup here (comma or newline separated)..."
        rows={4}
        style={{
          width: "100%", padding: "10px 14px", borderRadius: 10, marginBottom: 10,
          background: P.bgCard, border: `1px solid ${P.border}`,
          color: P.text, fontFamily: F.b, fontSize: 13, outline: "none",
          resize: "vertical",
        }}
      />
      <button
        onClick={scan}
        disabled={loading || !lineup.trim()}
        style={{
          width: "100%", padding: "12px", borderRadius: 10, border: "none",
          background: (!lineup.trim() || loading) ? P.bgSurface : P.terracotta,
          color: (!lineup.trim() || loading) ? P.textMut : "#fff",
          fontFamily: F.d, fontSize: 13, fontWeight: 700,
          cursor: (!lineup.trim() || loading) ? "not-allowed" : "pointer",
          display: "flex", alignItems: "center",
          justifyContent: "center", gap: 6, marginBottom: 6,
          transition: "all 0.2s ease",
        }}
      >
        <Ticket size={15} strokeWidth={2.5} />
        {loading ? "Scanning..." : "Scan Lineup"}
      </button>
      {!lineup.trim() && !report && !loading && (
        <div style={{ textAlign: "center", marginBottom: 16, fontSize: 11, fontFamily: F.m, color: P.textMut }}>
          Paste artist names above to get started
        </div>
      )}

      {loading && <Loader text="Scanning lineup (genre lookups may take a moment)..." />}
      {error && (
        <div style={{ textAlign: "center", padding: 30, color: P.warning, fontFamily: F.m, fontSize: 12 }}>
          {error}
        </div>
      )}

      {report && (
        <>
          {/* Summary */}
          <div style={{
            background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14,
            padding: "16px", marginBottom: 16,
          }}>
            <div style={{ fontSize: 16, fontWeight: 700, fontFamily: F.d, color: P.cream, marginBottom: 10 }}>
              {report.festival_name}
            </div>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              {[
                { n: report.total, label: "Artists", c: P.cream },
                { n: report.already_own, label: "Own", c: P.healthy },
                { n: report.stream_only, label: "Stream", c: P.warning },
                { n: report.unknown, label: "Unknown", c: P.critical },
                { n: report.genre_matches, label: "Genre Match", c: P.azure },
              ].map((s, i) => (
                <div key={i} style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 20, fontWeight: 800, fontFamily: F.d, color: s.c, lineHeight: 1 }}>{s.n}</div>
                  <div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 0.8, marginTop: 3 }}>{s.label}</div>
                </div>
              ))}
            </div>
            {/* Prep score bar */}
            {report.total > 0 && (() => {
              const pct = Math.round((report.already_own + report.stream_only) / report.total * 100);
              return (
                <div style={{ marginTop: 14 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                    <span style={{ fontSize: 10, fontFamily: F.m, color: P.textMut }}>PREP SCORE</span>
                    <span style={{ fontSize: 12, fontFamily: F.d, fontWeight: 700, color: pct > 60 ? P.healthy : pct > 30 ? P.warning : P.critical }}>{pct}%</span>
                  </div>
                  <div style={{ height: 4, background: P.bgSurface, borderRadius: 2, overflow: "hidden" }}>
                    <div style={{
                      width: `${pct}%`, height: "100%", borderRadius: 2,
                      background: `linear-gradient(90deg, ${P.terracotta}, ${P.lime})`,
                      transition: "width 1s ease",
                    }} />
                  </div>
                </div>
              );
            })()}
          </div>

          {/* Filter pills */}
          <div style={{ display: "flex", gap: 6, overflowX: "auto", marginBottom: 14 }}>
            {[
              { label: "All", key: "all", count: report.total },
              { label: "Own", key: "own", count: report.already_own },
              { label: "Stream", key: "stream", count: report.stream_only },
              { label: "Unknown", key: "unknown", count: report.unknown },
              { label: "Genre Match", key: "match", count: report.genre_matches },
            ].map(f => (
              <Pill key={f.key} label={f.label} count={f.count} active={tab === f.key} onClick={() => setTab(f.key)} />
            ))}
          </div>

          {/* Artist list */}
          <div style={{
            background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14,
            padding: "10px 14px",
          }}>
            {filtered.map((a, i) => {
              const Icon = catIcon[a.category] || CircleX;
              const color = catColor[a.category] || P.textMut;
              return (
                <div key={i} style={{
                  display: "flex", gap: 10, padding: "11px 0",
                  borderBottom: i < filtered.length - 1 ? `1px solid ${P.borderSub}` : "none",
                  alignItems: "center",
                }}>
                  <div style={{
                    width: 28, height: 28, borderRadius: 7,
                    background: `${color}10`, border: `1px solid ${color}18`,
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                  }}>
                    <Icon size={12} color={color} strokeWidth={2.5} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 13, fontFamily: F.b, fontWeight: 600, color: P.text,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>{a.name}</div>
                    <div style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>
                      {a.category === "already-own" && `${a.library_tracks} tracks in library`}
                      {a.category === "stream-but-dont-own" && `Stream score: ${a.stream_score}`}
                      {a.category === "unknown" && (a.genres?.length > 0 ? a.genres.slice(0, 3).join(", ") : "no genre info")}
                    </div>
                  </div>
                  {a.genre_match && (
                    <span style={{
                      fontSize: 8, fontFamily: F.m, color: P.azure, padding: "2px 6px",
                      background: `${P.azure}12`, border: `1px solid ${P.azure}20`,
                      borderRadius: 4, letterSpacing: 0.5, flexShrink: 0,
                    }}>MATCH</span>
                  )}
                </div>
              );
            })}
            {filtered.length === 0 && (
              <div style={{ textAlign: "center", padding: 20, color: P.textMut, fontFamily: F.m, fontSize: 12 }}>
                No artists in this category
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}


/* ─── Artist Research View ─── */
function ArtistResearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  const search = async () => {
    if (!query.trim() || loading) return;
    if (timerRef.current) clearInterval(timerRef.current);
    setLoading(true); setError(null); setReport(null); setElapsed(0);
    const start = Date.now();
    timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    try {
      const r = await fetch(`${API}/api/dig/artist?name=${encodeURIComponent(query.trim())}`);
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      setReport(data.report);
      if (!data.report) setError("No results found");
    } catch (e) {
      setError("Search failed — check the API is running");
    }
    clearInterval(timerRef.current); timerRef.current = null;
    setLoading(false); setElapsed(0);
  };

  const sp = report?.spotify_status;

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input value={query} onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          placeholder="Artist name..."
          style={{ flex: 1, padding: "10px 14px", borderRadius: 10, background: P.bgCard, border: `1px solid ${P.border}`, color: P.text, fontFamily: F.b, fontSize: 14, outline: "none" }}
        />
        <button onClick={search} disabled={loading || !query.trim()} style={{
          padding: "10px 18px", borderRadius: 10, border: "none",
          background: (!query.trim() || loading) ? P.bgSurface : P.terracotta,
          color: (!query.trim() || loading) ? P.textMut : "#fff",
          fontFamily: F.d, fontSize: 12, fontWeight: 700,
          cursor: (!query.trim() || loading) ? "not-allowed" : "pointer",
          display: "flex", alignItems: "center", gap: 5, transition: "all 0.2s ease",
        }}>
          <Search size={14} strokeWidth={2.5} />
          {loading ? "Searching..." : "Research"}
        </button>
      </div>

      {loading && <Loader text={`Researching artist... ${elapsed}s`} />}
      {error && <div style={{ textAlign: "center", padding: 30, color: P.warning, fontFamily: F.m, fontSize: 12 }}>{error}</div>}

      {report && (
        <>
          {/* Artist header */}
          <div style={{ background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14, padding: 16, marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: `${P.azure}15`, border: `1px solid ${P.azure}25`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <User size={18} color={P.azure} />
              </div>
              <div>
                <div style={{ fontSize: 18, fontWeight: 700, fontFamily: F.d, color: P.cream }}>
                  {report.name}
                  {report.country && <span style={{ fontSize: 12, color: P.textMut, marginLeft: 8 }}>({report.country})</span>}
                </div>
                {report.disambiguation && <div style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>{report.disambiguation}</div>}
              </div>
            </div>
            {report.aliases?.length > 0 && <div style={{ fontSize: 11, fontFamily: F.m, color: P.textMut }}>aka {report.aliases.slice(0, 4).join(", ")}</div>}
            {report.genres?.length > 0 && (
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 8 }}>
                {report.genres.map((g, i) => (
                  <span key={i} style={{ fontSize: 10, fontFamily: F.m, padding: "2px 8px", borderRadius: 5, background: `${genreColor(i)}12`, border: `1px solid ${genreColor(i)}20`, color: genreColor(i) }}>{g}</span>
                ))}
              </div>
            )}
          </div>

          {/* Sound profile (BPM/Key from library) */}
          {(report.bpm_profile || report.key_profile) && (
            <>
              <Sec label="Sound Profile (from your library)" icon={Music} />
              <div style={{ background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14, padding: 16, marginBottom: 16 }}>
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                  {report.bpm_profile && (
                    <>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 20, fontWeight: 800, fontFamily: F.d, color: P.lime, lineHeight: 1 }}>{report.bpm_profile.min}-{report.bpm_profile.max}</div>
                        <div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 0.8, marginTop: 3 }}>BPM RANGE</div>
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 20, fontWeight: 800, fontFamily: F.d, color: P.azure, lineHeight: 1 }}>{report.bpm_profile.avg}</div>
                        <div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 0.8, marginTop: 3 }}>AVG BPM</div>
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <div style={{ fontSize: 20, fontWeight: 800, fontFamily: F.d, color: P.cream, lineHeight: 1 }}>{report.bpm_profile.count}</div>
                        <div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 0.8, marginTop: 3 }}>TRACKS</div>
                      </div>
                    </>
                  )}
                </div>
                {report.key_profile?.top_keys && (
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 10 }}>
                    {report.key_profile.top_keys.map((k, i) => (
                      <span key={i} style={{ fontSize: 11, fontFamily: F.m, padding: "3px 8px", borderRadius: 5, background: `${P.mauve}12`, border: `1px solid ${P.mauve}20`, color: P.mauve }}>
                        {k.key} <span style={{ fontSize: 9, color: P.textMut }}>({k.count})</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}

          {/* Your relationship */}
          <Sec label="Your Relationship" icon={Users} />
          <div style={{ background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14, padding: 16, marginBottom: 16 }}>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 24, fontWeight: 800, fontFamily: F.d, color: report.library_tracks?.length > 0 ? P.healthy : P.critical, lineHeight: 1 }}>{report.library_tracks?.length || 0}</div>
                <div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 0.8, marginTop: 3 }}>IN LIBRARY</div>
              </div>
              {sp && sp.connected && (
                <>
                  {sp.in_top_short && <div style={{ textAlign: "center" }}><div style={{ fontSize: 16, color: P.healthy, fontWeight: 700, fontFamily: F.d }}>Top</div><div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut }}>4 WEEKS</div></div>}
                  {sp.followed && <div style={{ textAlign: "center" }}><div style={{ fontSize: 16, color: P.healthy, fontWeight: 700, fontFamily: F.d }}>Yes</div><div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut }}>FOLLOWING</div></div>}
                  {sp.saved_track_count > 0 && <div style={{ textAlign: "center" }}><div style={{ fontSize: 16, color: P.lime, fontWeight: 700, fontFamily: F.d }}>{sp.saved_track_count}</div><div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut }}>SAVED</div></div>}
                </>
              )}
            </div>
            {report.library_tracks?.length > 0 && (
              <div style={{ marginTop: 10 }}>
                {report.library_tracks.slice(0, 5).map((t, i) => (
                  <div key={i} style={{ fontSize: 11, fontFamily: F.m, color: P.textSec, padding: "2px 0" }}>{t}</div>
                ))}
                {report.library_tracks.length > 5 && <div style={{ fontSize: 10, fontFamily: F.m, color: P.textMut }}>+ {report.library_tracks.length - 5} more</div>}
              </div>
            )}
          </div>

          {/* Labels */}
          {report.labels?.length > 0 && (
            <>
              <Sec label={`Labels (${report.labels.length})`} icon={Globe} />
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
                {report.labels.map((lb, i) => (
                  <span key={i} style={{ fontSize: 11, fontFamily: F.b, color: P.text, padding: "4px 10px", borderRadius: 6, background: P.bgCard, border: `1px solid ${P.border}` }}>{lb}</span>
                ))}
              </div>
            </>
          )}

          {/* Discography */}
          {report.releases?.length > 0 && (
            <>
              <Sec label={`Discography (${report.releases.length})`} icon={Disc3} />
              <div style={{ background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14, padding: "12px 14px", marginBottom: 16 }}>
                {report.releases.slice(0, 12).map((r, i) => (
                  <div key={i} style={{ display: "flex", gap: 10, padding: "8px 0", borderBottom: i < 11 ? `1px solid ${P.borderSub}` : "none", alignItems: "center" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontFamily: F.b, fontWeight: 600, color: P.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.title}</div>
                    </div>
                    <div style={{ textAlign: "right", flexShrink: 0 }}>
                      <div style={{ fontSize: 10, fontFamily: F.m, color: P.textMut }}>{r.date || "?"}</div>
                      <span style={{ fontSize: 9, fontFamily: F.m, color: P.azure, padding: "1px 6px", background: `${P.azure}10`, borderRadius: 4 }}>{r.type}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Links */}
          {report.urls?.length > 0 && (
            <>
              <Sec label="Links" icon={ExternalLink} />
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 16 }}>
                {report.urls.slice(0, 8).map((u, i) => (
                  <a key={i} href={u.url} target="_blank" rel="noopener noreferrer" style={{
                    fontSize: 10, fontFamily: F.m, color: P.azure, padding: "3px 8px", borderRadius: 5,
                    background: `${P.azure}08`, border: `1px solid ${P.azure}15`, textDecoration: "none",
                    display: "inline-flex", alignItems: "center", gap: 3,
                  }}>
                    <ExternalLink size={8} /> {u.type}
                  </a>
                ))}
              </div>
            </>
          )}

          {/* Related */}
          {report.related_artists?.length > 0 && (
            <>
              <Sec label="Related Artists" icon={Users} />
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 16 }}>
                {report.related_artists.slice(0, 12).map((a, i) => (
                  <span key={i} style={{ fontSize: 11, fontFamily: F.b, color: P.textSec, padding: "3px 8px", borderRadius: 6, background: P.bgSurface, border: `1px solid ${P.borderSub}` }}>
                    {a.name} <span style={{ fontSize: 9, color: P.textMut }}>{a.relationship}</span>
                  </span>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}


/* ─── Weekly Dig View ─── */
function WeeklyDigView() {
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [genres, setGenres] = useState("");
  const player = usePlayer();

  const scan = async () => {
    setLoading(true); setError(null); setReport(null);
    try {
      const params = genres.trim() ? `?genres=${encodeURIComponent(genres.trim())}` : "";
      const r = await fetch(`${API}/api/dig/weekly${params}`);
      if (!r.ok) throw new Error(`${r.status}`);
      const data = await r.json();
      setReport(data.report);
    } catch (e) {
      setError("Scan failed — check the API is running");
    }
    setLoading(false);
  };

  const hot = report?.releases?.filter(r => r.relevance_score > 0.3) || [];
  const others = report?.releases?.filter(r => r.relevance_score <= 0.3) || [];

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input value={genres} onChange={(e) => setGenres(e.target.value)}
          placeholder="Genres (optional, e.g. Tech House, Deep House)..."
          style={{ flex: 1, padding: "10px 14px", borderRadius: 10, background: P.bgCard, border: `1px solid ${P.border}`, color: P.text, fontFamily: F.b, fontSize: 14, outline: "none" }}
        />
        <button onClick={scan} disabled={loading} style={{
          padding: "10px 18px", borderRadius: 10, border: "none",
          background: loading ? P.bgSurface : P.lime, color: loading ? P.textMut : P.bg,
          fontFamily: F.d, fontSize: 12, fontWeight: 700,
          cursor: loading ? "not-allowed" : "pointer",
          display: "flex", alignItems: "center", gap: 5, transition: "all 0.2s ease",
        }}>
          <TrendingUp size={14} strokeWidth={2.5} />
          {loading ? "Scanning..." : "Dig"}
        </button>
      </div>

      {!loading && !report && !error && (
        <div style={{ textAlign: "center", padding: "8px 0 16px", fontSize: 11, fontFamily: F.m, color: P.textMut }}>
          Leave genres blank to use your DJ profile. Scans Traxsource + Spotify for new releases with 30s preview clips.
        </div>
      )}

      {loading && <Loader text="Scanning new releases..." />}
      {error && <div style={{ textAlign: "center", padding: 30, color: P.warning, fontFamily: F.m, fontSize: 12 }}>{error}</div>}

      {report && (
        <>
          {/* Summary */}
          <div style={{ background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14, padding: 16, marginBottom: 16 }}>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 8 }}>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 800, fontFamily: F.d, color: P.cream, lineHeight: 1 }}>{report.total_found}</div>
                <div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 0.8, marginTop: 3 }}>FOUND</div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 800, fontFamily: F.d, color: P.lime, lineHeight: 1 }}>{report.after_filter}</div>
                <div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 0.8, marginTop: 3 }}>NEW</div>
              </div>
              <div style={{ textAlign: "center" }}>
                <div style={{ fontSize: 20, fontWeight: 800, fontFamily: F.d, color: P.terracotta, lineHeight: 1 }}>{hot.length}</div>
                <div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 0.8, marginTop: 3 }}>HOT</div>
              </div>
            </div>
            {report.genres_scanned?.length > 0 && (
              <div style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>
                Scanned: {report.genres_scanned.join(", ")}
              </div>
            )}
          </div>

          {/* Hot picks */}
          {hot.length > 0 && (
            <>
              <Sec label={`Hot Picks (${hot.length})`} icon={Flame} />
              <div style={{ background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14, padding: "10px 14px", marginBottom: 16 }}>
                {hot.slice(0, 15).map((r, i) => {
                  const isPlaying = player.playing && player.track?.directUrl === r.preview_url;
                  return (
                    <div key={i} style={{ display: "flex", gap: 10, padding: "10px 0", borderBottom: i < hot.length - 1 ? `1px solid ${P.borderSub}` : "none", alignItems: "center" }}>
                      {r.preview_url ? (
                        <button onClick={() => isPlaying ? player.pause() : player.play({ directUrl: r.preview_url, title: r.title, artist: r.artist, genre: r.genre })}
                          style={{ width: 32, height: 32, borderRadius: "50%", border: "none", background: isPlaying ? P.lime : P.bgSurface, color: isPlaying ? P.bg : P.lime, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "all 0.2s ease" }}>
                          {isPlaying ? <Pause size={14} /> : <Play size={14} style={{ marginLeft: 2 }} />}
                        </button>
                      ) : (
                        <div style={{ width: 32, textAlign: "center", fontSize: 12, fontWeight: 700, fontFamily: F.d, color: P.terracotta }}>{r.relevance_score.toFixed(1)}</div>
                      )}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontFamily: F.b, fontWeight: 600, color: P.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.artist || "?"} — {r.title}</div>
                        <div style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>
                          {r.genre}{r.label ? ` · ${r.label}` : ""}{r.release_date ? ` · ${r.release_date}` : ""}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 3, flexShrink: 0, alignItems: "center" }}>
                        {r.artist_in_library && <span style={{ fontSize: 8, fontFamily: F.m, color: P.healthy, padding: "1px 5px", background: `${P.healthy}10`, borderRadius: 3 }}>LIB</span>}
                        {r.artist_in_streaming && <span style={{ fontSize: 8, fontFamily: F.m, color: P.azure, padding: "1px 5px", background: `${P.azure}10`, borderRadius: 3 }}>STREAM</span>}
                        {r.url && <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: P.textMut, marginLeft: 4 }}><ExternalLink size={12} /></a>}
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {/* Others */}
          {others.length > 0 && (
            <>
              <Sec label={`Other Releases (${others.length})`} icon={Music} />
              <div style={{ background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14, padding: "10px 14px" }}>
                {others.slice(0, 15).map((r, i) => {
                  const isPlaying = player.playing && player.track?.directUrl === r.preview_url;
                  return (
                    <div key={i} style={{ display: "flex", gap: 10, padding: "8px 0", borderBottom: i < Math.min(others.length, 15) - 1 ? `1px solid ${P.borderSub}` : "none", alignItems: "center" }}>
                      {r.preview_url ? (
                        <button onClick={() => isPlaying ? player.pause() : player.play({ directUrl: r.preview_url, title: r.title, artist: r.artist, genre: r.genre })}
                          style={{ width: 28, height: 28, borderRadius: "50%", border: "none", background: isPlaying ? P.lime : P.bgSurface, color: isPlaying ? P.bg : P.textSec, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "all 0.2s ease" }}>
                          {isPlaying ? <Pause size={12} /> : <Play size={12} style={{ marginLeft: 1 }} />}
                        </button>
                      ) : (
                        <div style={{ width: 28 }} />
                      )}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 12, fontFamily: F.b, color: P.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.artist || "?"} — {r.title}</div>
                        <div style={{ fontSize: 10, fontFamily: F.m, color: P.textMut }}>{r.genre}{r.release_date ? ` · ${r.release_date}` : ""}</div>
                      </div>
                      {r.url && <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: P.textMut, flexShrink: 0 }}><ExternalLink size={12} /></a>}
                    </div>
                  );
                })}
                {others.length > 15 && <div style={{ textAlign: "center", padding: "8px 0", fontSize: 10, fontFamily: F.m, color: P.textMut }}>+ {others.length - 15} more</div>}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}


/* ─── Main Dig Page ─── */
export default function Dig() {
  const [mode, setMode] = useState("label");

  const MODES = [
    { id: "label", label: "Labels", icon: Disc3 },
    { id: "artist", label: "Artist", icon: User },
    { id: "festival", label: "Festival", icon: Ticket },
    { id: "weekly", label: "New Releases", icon: TrendingUp },
  ];

  const pages = {
    label: <LabelResearch />,
    artist: <ArtistResearch />,
    festival: <FestivalScanner />,
    weekly: <WeeklyDigView />,
  };

  return (
    <div style={{ padding: "20px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: `${P.terracotta}12`, border: `1px solid ${P.terracotta}20`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Compass size={18} color={P.terracotta} />
        </div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, fontFamily: F.d, color: P.cream }}>Dig Deeper</div>
          <div style={{ fontSize: 11, fontFamily: F.m, color: P.textMut }}>Research artists, labels, festivals & new releases</div>
        </div>
      </div>

      {/* Mode tabs */}
      <div style={{
        display: "flex", gap: 0, marginBottom: 20,
        background: P.bgCard, borderRadius: 10, border: `1px solid ${P.border}`,
        overflow: "hidden",
      }}>
        {MODES.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setMode(id)} style={{
            flex: 1, padding: "10px 8px", border: "none",
            background: mode === id ? `${P.terracotta}15` : "transparent",
            color: mode === id ? P.terracotta : P.textMut,
            fontFamily: F.m, fontSize: 10, letterSpacing: 0.3,
            cursor: "pointer", display: "flex", alignItems: "center",
            justifyContent: "center", gap: 5,
            borderBottom: mode === id ? `2px solid ${P.terracotta}` : "2px solid transparent",
            transition: "all 0.2s ease",
          }}>
            <Icon size={13} strokeWidth={2} />
            {label}
          </button>
        ))}
      </div>

      {pages[mode]}
    </div>
  );
}
