import { P, F } from "../theme";
import {
  CircleCheck, AlertTriangle, CircleX, ChevronRight,
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
        <span style={{ fontSize: 28, fontWeight: 800, fontFamily: F.d, color: P.cream, lineHeight: 1, letterSpacing: -1.5 }}>{pct}</span>
        <span style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 2.5, marginTop: 3 }}>SCORE</span>
      </div>
    </div>
  );
}

/* ─── Completeness Bar ─── */
export function CBar({ label, value, max, color, icon: Icon }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 5 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <Icon size={12} color={color} strokeWidth={2} style={{ opacity: 0.7 }} />
          <span style={{ fontSize: 12, fontFamily: F.b, color: P.textSec }}>{label}</span>
        </div>
        <span style={{ fontSize: 11, fontFamily: F.m, color: pct > 85 ? P.healthy : color }}>{pct}%</span>
      </div>
      <div style={{ height: 3, background: P.bgSurface, borderRadius: 2, overflow: "hidden" }}>
        <div className="bar-fill" style={{
          width: `${pct}%`, height: "100%", borderRadius: 2,
          background: `linear-gradient(90deg, ${color}90, ${color})`,
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
      borderRadius: 10, padding: "10px 12px", transition: "all 0.2s ease",
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: `${color}10`, border: `1px solid ${color}18`,
        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      }}>
        <Icon size={14} color={color} strokeWidth={2.2} />
      </div>
      <span style={{ flex: 1, fontSize: 12, fontFamily: F.b, color: P.textSec }}>{label}</span>
      <span style={{ fontSize: 17, fontWeight: 800, fontFamily: F.d, color, letterSpacing: -0.5 }}>{value}</span>
    </div>
  );
}

/* ─── Track Card ─── */
export function Track({ t, i }) {
  const sc = { complete: P.healthy, partial: P.warning, missing: P.critical };
  const si = { complete: CircleCheck, partial: AlertTriangle, missing: CircleX };
  const StatusIcon = si[t.status] || CircleX;
  return (
    <div className="track-row" style={{
      display: "flex", gap: 12, padding: "13px 0",
      borderBottom: `1px solid ${P.borderSub}`,
      alignItems: "flex-start", transition: "all 0.15s ease",
    }}>
      <div style={{
        width: 30, height: 30, borderRadius: 7, background: P.bgSurface,
        display: "flex", alignItems: "center", justifyContent: "center",
        flexShrink: 0, marginTop: 1,
      }}>
        <span style={{ fontSize: 11, fontFamily: F.m, color: P.textMut, fontWeight: 500 }}>
          {String(i + 1).padStart(2, "0")}
        </span>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 14, fontFamily: F.b, fontWeight: 600, color: P.text,
          marginBottom: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>{t.title}</div>
        <div style={{ fontSize: 12, fontFamily: F.b, color: P.textSec, marginBottom: 7 }}>{t.artist}</div>
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
          {t.key && (
            <span style={{
              padding: "2px 8px", borderRadius: 5,
              background: `${P.mauve}10`, border: `1px solid ${P.mauve}20`,
              fontSize: 10, fontFamily: F.m, color: P.mauve, letterSpacing: 0.3,
            }}>{t.key}</span>
          )}
          {t.bpm && (
            <span style={{
              padding: "2px 8px", borderRadius: 5,
              background: `${P.azure}10`, border: `1px solid ${P.azure}20`,
              fontSize: 10, fontFamily: F.m, color: P.azure,
            }}>{t.bpm}</span>
          )}
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 3,
            padding: "2px 8px", borderRadius: 5,
            background: `${sc[t.status]}08`, border: `1px solid ${sc[t.status]}18`,
            fontSize: 10, fontFamily: F.m, color: sc[t.status],
            textTransform: "uppercase", letterSpacing: 0.5,
          }}>
            <StatusIcon size={9} strokeWidth={2.5} />
            {t.status}
          </span>
        </div>
      </div>
      <ChevronRight size={16} color={P.textMut} style={{ marginTop: 8, flexShrink: 0, opacity: 0.4 }} />
    </div>
  );
}

/* ─── Genre Row ─── */
export function Genre({ name, pct, color }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 11 }}>
      <div style={{ width: 3, height: 26, background: color, borderRadius: 2, opacity: 0.8, flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
          <span style={{ fontSize: 13, fontFamily: F.b, color: P.text, fontWeight: 500 }}>{name}</span>
          <span style={{ fontSize: 11, fontFamily: F.m, color }}>{pct}%</span>
        </div>
        <div style={{ height: 2, background: P.bgSurface, borderRadius: 1 }}>
          <div style={{
            width: `${Math.min(pct * 4, 100)}%`, height: "100%",
            background: `linear-gradient(90deg, ${color}60, ${color})`, borderRadius: 1,
          }} />
        </div>
      </div>
    </div>
  );
}

/* ─── Section Divider ─── */
export function Sec({ label, icon: Icon }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, marginTop: 30 }}>
      {Icon && <Icon size={12} color={P.terracotta} strokeWidth={2.5} />}
      <span style={{ fontSize: 10, fontFamily: F.m, color: P.textMut, letterSpacing: 2.5, textTransform: "uppercase" }}>{label}</span>
      <div style={{ flex: 1, height: 1, background: `linear-gradient(90deg, ${P.border}, transparent)` }} />
    </div>
  );
}

/* ─── Filter Pill ─── */
export function Pill({ label, active, count, onClick }) {
  return (
    <button onClick={onClick} className="pill" style={{
      padding: "6px 12px", borderRadius: 7,
      border: `1px solid ${active ? P.terracotta + "50" : P.borderSub}`,
      background: active ? `${P.terracotta}12` : "transparent",
      color: active ? P.terracotta : P.textMut,
      fontSize: 11, fontFamily: F.m, letterSpacing: 0.3,
      cursor: "pointer", whiteSpace: "nowrap",
      display: "flex", alignItems: "center", gap: 5,
      transition: "all 0.15s ease",
    }}>
      {label}
      {count !== undefined && (
        <span style={{
          fontSize: 9, fontFamily: F.m,
          background: active ? `${P.terracotta}25` : P.bgSurface,
          padding: "1px 5px", borderRadius: 4,
          color: active ? P.terracotta : P.textMut,
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
      justifyContent: "center", padding: "60px 0", gap: 12,
    }}>
      <div style={{
        width: 24, height: 24, border: `2px solid ${P.border}`,
        borderTopColor: P.terracotta, borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
      }} />
      <span style={{ fontSize: 11, fontFamily: F.m, color: P.textMut }}>{text}</span>
    </div>
  );
}
