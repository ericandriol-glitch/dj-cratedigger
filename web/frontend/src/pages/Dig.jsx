import { useState } from "react";
import { P, F, genreColor } from "../theme";
import { Sec, Loader, Pill } from "../components/ui";
import { fetchApi } from "../hooks/useApi";
import {
  Compass, Search, Disc3, Users, Globe, Music,
  MapPin, ExternalLink, ChevronDown, ChevronUp,
  CircleCheck, AlertTriangle, CircleX, Ticket,
} from "lucide-react";

/* ─── Label Research View ─── */
function LabelResearch() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState(null);
  const [error, setError] = useState(null);
  const [expandedLabel, setExpandedLabel] = useState(null);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const data = await fetchApi(`/api/dig/label?artist=${encodeURIComponent(query.trim())}`);
      setReport(data.report);
      if (!data.report) setError("No results found");
    } catch (e) {
      setError("Search failed — is the API running?");
    }
    setLoading(false);
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
        <button onClick={search} disabled={loading} style={{
          padding: "10px 18px", borderRadius: 10, border: "none",
          background: P.terracotta, color: "#fff", fontFamily: F.d,
          fontSize: 12, fontWeight: 700, cursor: "pointer",
          opacity: loading ? 0.6 : 1, display: "flex", alignItems: "center", gap: 5,
        }}>
          <Search size={14} strokeWidth={2.5} />
          Dig
        </button>
      </div>

      {loading && <Loader text="Researching labels..." />}
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

  const scan = async () => {
    if (!lineup.trim()) return;
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const params = new URLSearchParams({
        lineup: lineup.trim(),
        name: name.trim() || "Festival",
      });
      const data = await fetchApi(`/api/dig/festival?${params}`);
      setReport(data.report);
      if (!data.report) setError("No results");
    } catch (e) {
      setError("Scan failed — is the API running?");
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
      <button onClick={scan} disabled={loading} style={{
        width: "100%", padding: "12px", borderRadius: 10, border: "none",
        background: P.terracotta, color: "#fff", fontFamily: F.d,
        fontSize: 13, fontWeight: 700, cursor: "pointer",
        opacity: loading ? 0.6 : 1, display: "flex", alignItems: "center",
        justifyContent: "center", gap: 6, marginBottom: 20,
      }}>
        <Ticket size={15} strokeWidth={2.5} />
        Scan Lineup
      </button>

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


/* ─── Main Dig Page ─── */
export default function Dig() {
  const [mode, setMode] = useState("label");

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
          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: F.d, color: P.cream }}>Dig Deeper</div>
          <div style={{ fontSize: 11, fontFamily: F.m, color: P.textMut }}>Research artists, labels & festivals</div>
        </div>
      </div>

      {/* Mode tabs */}
      <div style={{
        display: "flex", gap: 0, marginBottom: 20,
        background: P.bgCard, borderRadius: 10, border: `1px solid ${P.border}`,
        overflow: "hidden",
      }}>
        {[
          { id: "label", label: "Label Research", icon: Disc3 },
          { id: "festival", label: "Festival Scanner", icon: Ticket },
        ].map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setMode(id)} style={{
            flex: 1, padding: "10px 12px", border: "none",
            background: mode === id ? `${P.terracotta}15` : "transparent",
            color: mode === id ? P.terracotta : P.textMut,
            fontFamily: F.m, fontSize: 11, letterSpacing: 0.3,
            cursor: "pointer", display: "flex", alignItems: "center",
            justifyContent: "center", gap: 6,
            borderBottom: mode === id ? `2px solid ${P.terracotta}` : "2px solid transparent",
            transition: "all 0.2s ease",
          }}>
            <Icon size={13} strokeWidth={2} />
            {label}
          </button>
        ))}
      </div>

      {mode === "label" ? <LabelResearch /> : <FestivalScanner />}
    </div>
  );
}
