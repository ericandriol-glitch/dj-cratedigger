import { useState, useEffect, useRef, useCallback } from "react";
import { P, F } from "./theme";
import { PlayerProvider } from "./hooks/usePlayer";
import { fetchApi } from "./hooks/useApi";
import PlayerBar from "./components/Player";
import Home from "./pages/Home";
import Dig from "./pages/Dig";
import Library from "./pages/Library";
import Enrich from "./pages/Enrich";
import {
  LayoutGrid, Disc3, Compass, Sparkles, Search, Command,
  AudioLines, Hash, Tag, ArrowRight,
} from "lucide-react";

const TABS = [
  { id: "home", Icon: LayoutGrid, label: "Home" },
  { id: "library", Icon: Disc3, label: "Library" },
  { id: "discover", Icon: Compass, label: "Dig" },
  { id: "enrich", Icon: Sparkles, label: "Enrich" },
];

/* ─── Sidebar (desktop) ─── */
function Sidebar({ tab, setTab }) {
  return (
    <div style={{
      width: 220, minHeight: "100vh",
      background: `linear-gradient(180deg, ${P.bgElevated} 0%, #0E0D15 100%)`,
      borderRight: `1px solid ${P.border}`, padding: "24px 12px",
      display: "flex", flexDirection: "column", flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 10px", marginBottom: 32 }}>
        <div style={{ width: 30, height: 30, position: "relative", flexShrink: 0 }}>
          <div style={{ position: "absolute", width: 16, height: 16, background: P.terracotta, top: 0, left: 0, borderRadius: 3.5 }} />
          <div style={{ position: "absolute", width: 16, height: 16, background: P.lime, bottom: 0, right: 0, borderRadius: 3.5, opacity: 0.85 }} />
          <div style={{ position: "absolute", width: 10, height: 10, background: P.azure, top: 10, left: 10, borderRadius: 2.5 }} />
        </div>
        <div style={{ lineHeight: 1 }}>
          <span style={{ fontSize: 15, fontWeight: 800, fontFamily: F.d, color: P.cream, letterSpacing: 1.5 }}>CRATE</span>
          <span style={{ fontSize: 15, fontWeight: 800, fontFamily: F.d, color: P.terracotta, letterSpacing: 1.5 }}>DIGGER</span>
        </div>
      </div>

      {/* Nav section label */}
      <div style={{
        fontSize: 9, fontFamily: F.m, color: P.textMut, letterSpacing: 2,
        textTransform: "uppercase", padding: "0 12px", marginBottom: 8,
      }}>
        Navigate
      </div>

      {/* Nav items */}
      <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
        {TABS.map(({ id, Icon, label }) => {
          const active = tab === id;
          return (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`sidebar-nav-item${active ? " active" : ""}`}
              style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "11px 12px", borderRadius: 9,
                background: active ? `${P.terracotta}10` : "transparent",
                border: "none",
                cursor: "pointer", width: "100%",
              }}
            >
              <Icon size={17} strokeWidth={active ? 2.2 : 1.5}
                color={active ? P.terracotta : P.textMut} />
              <span style={{
                fontSize: 13, fontFamily: F.b, fontWeight: active ? 600 : 400,
                color: active ? P.cream : P.textSec,
                letterSpacing: active ? 0.2 : 0,
              }}>{label}</span>
            </button>
          );
        })}
      </div>

      {/* Divider */}
      <div style={{
        height: 1, margin: "20px 12px",
        background: `linear-gradient(90deg, ${P.border}, transparent)`,
      }} />

      {/* Library pulse */}
      <div style={{ padding: "0 12px", marginBottom: 12 }}>
        <div style={{
          fontSize: 9, fontFamily: F.m, color: P.textMut, letterSpacing: 2,
          textTransform: "uppercase", marginBottom: 10,
        }}>
          Library
        </div>
        <div style={{
          display: "flex", alignItems: "center", gap: 6, marginBottom: 6,
        }}>
          <div style={{
            width: 6, height: 6, borderRadius: "50%", background: P.healthy,
            boxShadow: `0 0 6px ${P.healthy}40`, animation: "pulseGlow 2.5s infinite",
          }} />
          <span style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>Connected</span>
        </div>
      </div>

      {/* Bottom version */}
      <div style={{ marginTop: "auto", padding: "12px 12px" }}>
        <div style={{ display: "flex", gap: 5, marginBottom: 8 }}>
          {[P.terracotta, P.lime, P.azure, P.mauve].map((c, i) => (
            <div key={i} style={{ width: 4, height: 4, background: c, borderRadius: 1, opacity: 0.5 }} />
          ))}
        </div>
        <span style={{ fontSize: 9, fontFamily: F.m, color: P.textMut, letterSpacing: 1.5 }}>v0.1.0 BETA</span>
      </div>
    </div>
  );
}

/* ─── Bottom Tab Bar (mobile) ─── */
function BottomTabs({ tab, setTab }) {
  return (
    <div className="mobile-tabs" style={{
      position: "fixed", bottom: 0, left: 0, right: 0,
      background: `linear-gradient(180deg, ${P.bgElevated}00 0%, ${P.bgElevated}F8 25%, ${P.bgElevated} 100%)`,
      backdropFilter: "blur(24px)", WebkitBackdropFilter: "blur(24px)",
      borderTop: `1px solid ${P.border}`,
      display: "flex", justifyContent: "space-around", alignItems: "center",
      padding: "6px 0 14px", zIndex: 100,
    }}>
      {TABS.map(({ id, Icon, label }) => {
        const active = tab === id;
        return (
          <button key={id} onClick={() => setTab(id)} style={{
            display: "flex", flexDirection: "column", alignItems: "center", gap: 4,
            background: "none", border: "none", cursor: "pointer",
            padding: "6px 14px", borderRadius: 10,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10,
              background: active ? `${P.terracotta}15` : "transparent",
              border: active ? `1px solid ${P.terracotta}20` : "1px solid transparent",
              display: "flex", alignItems: "center", justifyContent: "center",
              transition: "all 0.2s ease",
            }}>
              <Icon size={18} strokeWidth={active ? 2.2 : 1.6}
                color={active ? P.terracotta : P.textMut}
                style={{ transition: "color 0.2s ease" }}
              />
            </div>
            <span style={{
              fontSize: 9, fontFamily: F.m, letterSpacing: 0.8,
              color: active ? P.terracotta : P.textMut,
              fontWeight: active ? 600 : 400,
            }}>{label}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ─── Command Palette (Cmd+K) ─── */
function CommandPalette({ open, onClose, onNavigate }) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(0);
  const inputRef = useRef(null);
  const timerRef = useRef(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setResults([]);
      setSelected(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Debounced search
  useEffect(() => {
    if (!query.trim()) { setResults([]); return; }
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await fetchApi(`/api/library/tracks?search=${encodeURIComponent(query)}&limit=8`);
        const tracks = (data.tracks || []).map(t => ({
          type: "track",
          title: t.title,
          subtitle: `${t.artist || "?"} ${t.bpm ? `· ${t.bpm} BPM` : ""} ${t.key || ""}`,
          action: () => { onNavigate("library", { search: query }); onClose(); },
        }));
        // Add navigation shortcuts
        const nav = [
          query.toLowerCase().includes("libr") && { type: "nav", title: "Go to Library", subtitle: "Browse all tracks", action: () => { onNavigate("library"); onClose(); } },
          query.toLowerCase().includes("dig") && { type: "nav", title: "Go to Dig", subtitle: "Research artists & labels", action: () => { onNavigate("discover"); onClose(); } },
          query.toLowerCase().includes("enrich") && { type: "nav", title: "Go to Enrich", subtitle: "Fix missing metadata", action: () => { onNavigate("enrich"); onClose(); } },
          query.toLowerCase().includes("home") && { type: "nav", title: "Go to Home", subtitle: "Dashboard overview", action: () => { onNavigate("home"); onClose(); } },
        ].filter(Boolean);
        setResults([...nav, ...tracks]);
      } catch { setResults([]); }
      setLoading(false);
    }, 200);
  }, [query]);

  const handleKey = (e) => {
    if (e.key === "Escape") { onClose(); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); setSelected(s => Math.min(s + 1, results.length - 1)); }
    if (e.key === "ArrowUp") { e.preventDefault(); setSelected(s => Math.max(s - 1, 0)); }
    if (e.key === "Enter" && results[selected]) { results[selected].action(); }
  };

  if (!open) return null;

  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 200,
      background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)",
      display: "flex", justifyContent: "center", paddingTop: "15vh",
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width: "100%", maxWidth: 520, maxHeight: "60vh",
        background: P.bgElevated, border: `1px solid ${P.border}`,
        borderRadius: 16, overflow: "hidden",
        boxShadow: `0 24px 80px rgba(0,0,0,0.5)`,
      }}>
        {/* Input */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "14px 16px", borderBottom: `1px solid ${P.border}`,
        }}>
          <Search size={16} color={P.textMut} />
          <input
            ref={inputRef}
            value={query}
            onChange={e => { setQuery(e.target.value); setSelected(0); }}
            onKeyDown={handleKey}
            placeholder="Search tracks, navigate..."
            style={{
              flex: 1, background: "none", border: "none", outline: "none",
              color: P.text, fontFamily: F.b, fontSize: 15,
            }}
          />
          <span style={{
            fontSize: 9, fontFamily: F.m, color: P.textMut,
            padding: "2px 6px", borderRadius: 4, border: `1px solid ${P.border}`,
          }}>ESC</span>
        </div>

        {/* Results */}
        <div style={{ maxHeight: "45vh", overflowY: "auto", padding: "6px 0" }}>
          {!query && (
            <div style={{ padding: "20px 16px", textAlign: "center", color: P.textMut, fontFamily: F.m, fontSize: 11 }}>
              Type to search tracks, or try "library", "dig", "enrich"
            </div>
          )}
          {loading && query && (
            <div style={{ padding: "12px 16px", color: P.textMut, fontFamily: F.m, fontSize: 11 }}>Searching...</div>
          )}
          {results.map((r, i) => (
            <button
              key={i}
              onClick={r.action}
              style={{
                width: "100%", display: "flex", alignItems: "center", gap: 10,
                padding: "10px 16px", border: "none", cursor: "pointer",
                background: i === selected ? `${P.terracotta}10` : "transparent",
                textAlign: "left", transition: "background 0.1s ease",
              }}
              onMouseEnter={() => setSelected(i)}
            >
              <div style={{
                width: 28, height: 28, borderRadius: 7, flexShrink: 0,
                background: r.type === "nav" ? `${P.azure}12` : P.bgSurface,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                {r.type === "nav"
                  ? <ArrowRight size={12} color={P.azure} />
                  : <Disc3 size={12} color={P.textMut} />
                }
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 13, fontFamily: F.b, fontWeight: 500, color: P.text,
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                }}>{r.title}</div>
                <div style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>{r.subtitle}</div>
              </div>
            </button>
          ))}
          {query && !loading && results.length === 0 && (
            <div style={{ padding: "20px 16px", textAlign: "center", color: P.textMut, fontFamily: F.m, fontSize: 11 }}>
              No results
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


export default function App() {
  const [tab, setTab] = useState("home");
  const [ready, setReady] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [navParams, setNavParams] = useState({});  // params to pass to pages on navigation
  // Track which pages have been visited — mount on first visit, keep alive after
  const [visited, setVisited] = useState(new Set(["home"]));
  useEffect(() => { requestAnimationFrame(() => setReady(true)); }, []);
  useEffect(() => {
    setVisited(prev => {
      if (prev.has(tab)) return prev;
      return new Set([...prev, tab]);
    });
  }, [tab]);

  // Cmd+K / Ctrl+K to open command palette
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdOpen(o => !o);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // Enhanced navigation — accepts optional params (e.g. { filter: "missing", search: "bicep" })
  const navigate = useCallback((targetTab, params = {}) => {
    setNavParams(params);
    setTab(targetTab);
  }, []);

  const PAGE_MAP = {
    home: Home,
    library: Library,
    discover: Dig,
    enrich: Enrich,
  };

  return (
    <PlayerProvider>
      <div className="noise-bg" style={{
        minHeight: "100vh", background: P.bg, color: P.text, fontFamily: F.b,
      }}>
        {/* BG decorations — deeper, more atmospheric */}
        <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0 }}>
          <div style={{
            position: "absolute", inset: 0, opacity: 0.015,
            backgroundImage: `radial-gradient(circle, ${P.cream} 0.6px, transparent 0.6px)`,
            backgroundSize: "28px 28px",
          }} />
          {/* Ambient color washes */}
          <div style={{
            position: "absolute", top: -100, right: -100, width: 400, height: 400,
            background: `radial-gradient(circle, ${P.terracotta}08 0%, transparent 70%)`,
          }} />
          <div style={{
            position: "absolute", bottom: -50, left: -80, width: 300, height: 300,
            background: `radial-gradient(circle, ${P.azure}06 0%, transparent 70%)`,
          }} />
          <div style={{
            position: "absolute", top: "40%", right: "10%", width: 200, height: 200,
            background: `radial-gradient(circle, ${P.lime}04 0%, transparent 70%)`,
          }} />
        </div>

        {/* Desktop layout: sidebar + content */}
        <div className="app-layout" style={{
          display: "flex", position: "relative", zIndex: 5, minHeight: "100vh",
        }}>
          <div className="desktop-sidebar">
            <Sidebar tab={tab} setTab={setTab} />
          </div>

          <div className="main-content" style={{
            flex: 1, minWidth: 0, overflowY: "auto", maxHeight: "100vh",
            opacity: ready ? 1 : 0, transform: ready ? "translateY(0)" : "translateY(10px)",
            transition: "all 0.6s cubic-bezier(0.16,1,0.3,1)",
          }}>
            <div className="content-inner">
              {Object.entries(PAGE_MAP).map(([id, Page]) => (
                visited.has(id) ? (
                  <div key={id} style={{ display: tab === id ? "block" : "none" }}>
                    <Page onNavigate={navigate} navParams={tab === id ? navParams : {}} />
                  </div>
                ) : null
              ))}
            </div>
          </div>
        </div>

        <div className="mobile-only">
          <BottomTabs tab={tab} setTab={setTab} />
        </div>

        {/* Persistent audio player bar */}
        <PlayerBar />

        {/* Command palette */}
        <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} onNavigate={navigate} />
      </div>
    </PlayerProvider>
  );
}
