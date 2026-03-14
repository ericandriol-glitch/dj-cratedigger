import { useState, useEffect } from "react";
import { P, F } from "./theme";
import Home from "./pages/Home";
import Dig from "./pages/Dig";
import Library from "./pages/Library";
import Enrich from "./pages/Enrich";
import {
  LayoutGrid, Disc3, Compass, Sparkles, Zap,
} from "lucide-react";

const TABS = [
  { id: "home", Icon: LayoutGrid, label: "Home" },
  { id: "library", Icon: Disc3, label: "Library" },
  { id: "discover", Icon: Compass, label: "Dig" },
  { id: "enrich", Icon: Sparkles, label: "Enrich" },
  { id: "agents", Icon: Zap, label: "Agents" },
];

function Placeholder({ name }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", height: "60vh", gap: 12,
    }}>
      <span style={{ fontSize: 32 }}>
        {name === "Library" ? "\uD83D\uDCBF" : name === "Dig" ? "\uD83D\uDD0D" : name === "Enrich" ? "\u2728" : "\u26A1"}
      </span>
      <span style={{ fontSize: 16, fontFamily: F.d, fontWeight: 700, color: P.cream }}>{name}</span>
      <span style={{ fontSize: 12, fontFamily: F.m, color: P.textMut }}>Coming soon</span>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("home");
  const [ready, setReady] = useState(false);
  useEffect(() => { requestAnimationFrame(() => setReady(true)); }, []);

  const renderPage = () => {
    switch (tab) {
      case "home": return <Home />;
      case "library": return <Library />;
      case "discover": return <Dig />;
      case "enrich": return <Enrich />;
      case "agents": return <Placeholder name="Agents" />;
      default: return <Home />;
    }
  };

  return (
    <div style={{
      minHeight: "100vh", maxWidth: 480, margin: "0 auto",
      background: P.bg, color: P.text, fontFamily: F.b,
      position: "relative", paddingBottom: 82, overflow: "hidden",
    }}>
      {/* BG decorations */}
      <div style={{ position: "fixed", inset: 0, pointerEvents: "none", zIndex: 0 }}>
        <div style={{
          position: "absolute", inset: 0, opacity: 0.018,
          backgroundImage: `radial-gradient(circle, ${P.cream} 0.8px, transparent 0.8px)`,
          backgroundSize: "24px 24px",
        }} />
        <div style={{ position: "absolute", top: -30, right: -40, width: 140, height: 140, background: P.terracotta, opacity: 0.025, transform: "rotate(15deg)" }} />
        <div style={{ position: "absolute", top: 350, left: -30, width: 80, height: 80, background: P.azure, opacity: 0.02, transform: "rotate(-12deg)" }} />
        <div style={{ position: "absolute", bottom: 180, right: -10, width: 60, height: 60, background: P.lime, opacity: 0.015, transform: "rotate(30deg)" }} />
      </div>

      {/* Page content */}
      <div style={{
        position: "relative", zIndex: 5,
        opacity: ready ? 1 : 0, transform: ready ? "translateY(0)" : "translateY(14px)",
        transition: "all 0.5s cubic-bezier(0.16,1,0.3,1)",
      }}>
        {renderPage()}
      </div>

      {/* TAB BAR */}
      <div style={{
        position: "fixed", bottom: 0, left: "50%", transform: "translateX(-50%)",
        width: "100%", maxWidth: 480,
        background: `linear-gradient(180deg, ${P.bgElevated}00 0%, ${P.bgElevated}F5 20%, ${P.bgElevated}FC 100%)`,
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
    </div>
  );
}
