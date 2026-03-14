import { P, F } from "../theme";
import { usePlayer } from "../hooks/usePlayer";
import {
  CircleCheck, AlertTriangle, CircleX, ChevronRight, Play,
} from "lucide-react";

/* ─── Waveform ─── */
export function Waveform({ count = 16, color = P.textMut, style = {} }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 1.5, ...style }}>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="wv-bar" style={{
          width: 2, borderRadius: 1,
          background: i % 5 === 0 ? P.terracotta : i % 3 === 0 ? P.lime : color,
          animationDuration: `${0.4 + Math.sin(i * 0.7) * 0.3}s`,
          animationDelay: `${i * 0.04}s`, minHeight: 2,
        }} />
      ))}
    </div>
  );
}

/* ─── Health Ring ─── */
export function Ring({ pct, size = 108 }) {
  const sw = 7, r = (size - sw) / 2, c = 2 * Math.PI * r;
  const color = pct >= 80 ? P.healthy : pct >= 60 ? P.lime : pct >= 40 ? P.warning : P.critical;
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={P.border} strokeWidth={sw} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={sw}
          strokeDasharray={c} strokeDashoffset={c - (pct / 100) * c} strokeLinecap="round"
          style={{ transition: "stroke-dashoffset 1.8s cubic-bezier(0.16, 1, 0.3, 1)" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
        <span style={{ fontSize: size > 90 ? 28 : 22, fontWeight: 800, fontFamily: F.d, color: P.cream, lineHeight: 1, letterSpacing: -1.5 }}>{pct}</span>
        <span style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 2.5, marginTop: 3 }}>SCORE</span>
      </div>
    </div>
  );
}

/* ─── Completeness Bar ─── */
export function CBar({ label, value, max, color, icon: Icon }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
          <Icon size={13} color={color} strokeWidth={2} style={{ opacity: 0.8 }} />
          <span style={{ fontSize: 12, fontFamily: F.b, color: P.textSec, fontWeight: 500 }}>{label}</span>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
          <span style={{ fontSize: 13, fontFamily: F.m, fontWeight: 600, color: pct > 85 ? P.healthy : color }}>{pct}%</span>
          <span style={{ fontSize: 9, fontFamily: F.m, color: P.textMut }}>{value}/{max}</span>
        </div>
      </div>
      <div style={{ height: 4, background: P.bgSurface, borderRadius: 2, overflow: "hidden" }}>
        <div className="bar-fill" style={{
          width: `${pct}%`, height: "100%", borderRadius: 2,
          background: `linear-gradient(90deg, ${color}70, ${color})`,
        }} />
      </div>
    </div>
  );
}

/* ─── Issue Row ─── */
export function IssueRow({ icon: Icon, label, value, color }) {
  return (
    <div className="issue-row" style={{
      display: "flex", alignItems: "center", gap: 10,
      background: P.bgCard, border: `1px solid ${P.borderSub}`,
      borderRadius: 10, padding: "10px 12px",
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: `${color}10`, border: `1px solid ${color}18`,
        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      }}>
        <Icon size={14} color={color} strokeWidth={2.2} />
      </div>
      <span style={{ flex: 1, fontSize: 12, fontFamily: F.b, color: P.textSec }}>{label}</span>
      <span style={{ fontSize: 18, fontWeight: 800, fontFamily: F.d, color, letterSpacing: -0.5 }}>{value}</span>
    </div>
  );
}

/* ─── Track Card — DJ-first layout: BPM and Key are prominent ─── */
export function Track({ t, i }) {
  const sc = { complete: P.healthy, partial: P.warning, missing: P.critical };
  const si = { complete: CircleCheck, partial: AlertTriangle, missing: CircleX };
  const StatusIcon = si[t.status] || CircleX;
  return (
    <div className="track-row" style={{
      display: "flex", gap: 12, padding: "13px 0",
      borderBottom: `1px solid ${P.borderSub}`,
      alignItems: "center",
    }}>
      {/* Track number */}
      <div style={{
        width: 28, height: 28, borderRadius: 7, background: P.bgSurface,
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0,
      }}>
        <span style={{ fontSize: 10, fontFamily: F.m, color: P.textMut, fontWeight: 500 }}>
          {String(i + 1).padStart(2, "0")}
        </span>
      </div>

      {/* Title + Artist */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 14, fontFamily: F.b, fontWeight: 600, color: P.text,
          marginBottom: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>{t.title}</div>
        <div style={{ fontSize: 12, fontFamily: F.b, color: P.textSec }}>{t.artist}</div>
      </div>

      {/* BPM — large and prominent like Rekordbox */}
      {t.bpm && (
        <span className="badge-bpm">{t.bpm}</span>
      )}

      {/* Key — Camelot notation prominent */}
      {t.key && (
        <span className="badge-key">{t.key}</span>
      )}

      {/* Status indicator */}
      <StatusIcon size={14} strokeWidth={2.5} color={sc[t.status] || P.textMut} style={{ flexShrink: 0 }} />
    </div>
  );
}

/* ─── Genre Row ─── */
export function Genre({ name, pct, color }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
      <div style={{ width: 3, height: 28, background: color, borderRadius: 2, opacity: 0.9, flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
          <span style={{ fontSize: 13, fontFamily: F.b, color: P.text, fontWeight: 500 }}>{name}</span>
          <span style={{ fontSize: 12, fontFamily: F.m, fontWeight: 600, color }}>{pct}%</span>
        </div>
        <div style={{ height: 3, background: P.bgSurface, borderRadius: 2 }}>
          <div style={{
            width: `${Math.min(pct * 2, 100)}%`, height: "100%",
            background: `linear-gradient(90deg, ${color}50, ${color})`, borderRadius: 2,
            transition: "width 0.8s cubic-bezier(0.16, 1, 0.3, 1)",
          }} />
        </div>
      </div>
    </div>
  );
}

/* ─── Section Divider ─── */
export function Sec({ label, icon: Icon, color = P.terracotta }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, marginTop: 32 }}>
      {Icon && <Icon size={12} color={color} strokeWidth={2.5} />}
      <span style={{ fontSize: 10, fontFamily: F.m, color: P.textMut, letterSpacing: 2.5, textTransform: "uppercase" }}>{label}</span>
      <div style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${P.border}, transparent)` }} />
    </div>
  );
}

/* ─── Filter Pill ─── */
export function Pill({ label, active, count, onClick }) {
  return (
    <button onClick={onClick} className="pill" style={{
      padding: "7px 14px", borderRadius: 8,
      border: `1px solid ${active ? P.terracotta + "40" : P.borderSub}`,
      background: active ? `${P.terracotta}12` : "transparent",
      color: active ? P.terracotta : P.textMut,
      fontSize: 11, fontFamily: F.m, letterSpacing: 0.3,
      cursor: "pointer", whiteSpace: "nowrap",
      display: "flex", alignItems: "center", gap: 6,
    }}>
      {label}
      {count !== undefined && (
        <span style={{
          fontSize: 9, fontFamily: F.m,
          background: active ? `${P.terracotta}25` : P.bgSurface,
          padding: "1px 6px", borderRadius: 4,
          color: active ? P.terracotta : P.textMut,
          fontWeight: 600,
        }}>{count}</span>
      )}
    </button>
  );
}

/* ─── Loading Spinner ─── */
export function Loader({ text = "Loading..." }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", padding: "60px 0", gap: 14,
    }}>
      <div style={{
        width: 28, height: 28, border: `2px solid ${P.border}`,
        borderTopColor: P.terracotta, borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
      }} />
      <span style={{ fontSize: 11, fontFamily: F.m, color: P.textMut, letterSpacing: 0.5 }}>{text}</span>
    </div>
  );
}

/* ─── Card wrapper with glow effect ─── */
export function Card({ children, className = "", style = {}, hero = false }) {
  return (
    <div
      className={`card-glow ${hero ? "hero-card" : ""} ${className}`}
      style={{
        background: P.bgCard,
        border: `1px solid ${P.border}`,
        borderRadius: 14,
        padding: "18px 16px",
        position: "relative",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
