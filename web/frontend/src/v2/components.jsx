import { P, F, srcColor, SRC, camelotColor } from "./theme";
import { ChevronRight } from "lucide-react";

export function SourceDot({ src }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 3,
        fontSize: 8,
        fontFamily: F.m,
        color: srcColor(src),
        opacity: 0.8,
      }}
    >
      <span
        style={{
          width: 4,
          height: 4,
          borderRadius: "50%",
          background: srcColor(src),
        }}
      />
      {SRC[src]}
    </span>
  );
}

export function Badge({ children, color = P.lime }) {
  return (
    <span
      style={{
        fontSize: 10,
        fontFamily: F.m,
        color,
        background: color + "15",
        padding: "3px 8px",
        borderRadius: 4,
        letterSpacing: 0.5,
        fontWeight: 600,
      }}
    >
      {children}
    </span>
  );
}

export function EnergyBar({ energy, w = 50 }) {
  const c =
    energy > 0.8
      ? P.terra
      : energy > 0.6
        ? P.warn
        : energy > 0.4
          ? P.azure
          : P.mauve;
  return (
    <div
      style={{
        width: w,
        height: 6,
        background: P.border,
        borderRadius: 3,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${energy * 100}%`,
          height: "100%",
          background: c,
          borderRadius: 3,
        }}
      />
    </div>
  );
}

export function Ring({ pct, size = 64, stroke = 5, color = P.lime }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={P.border}
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={c}
          strokeDashoffset={c - (pct / 100) * c}
          strokeLinecap="round"
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span
          style={{
            fontSize: 16,
            fontWeight: 800,
            fontFamily: F.d,
            color: P.cream,
          }}
        >
          {pct}
        </span>
      </div>
    </div>
  );
}

export function ThemeHeader({ nav, icon: Icon, label, sub, color }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        marginBottom: 18,
      }}
    >
      <button
        onClick={() => nav("home")}
        style={{
          background: "none",
          border: "none",
          color: P.text2,
          fontSize: 16,
          cursor: "pointer",
          padding: 4,
          display: "flex",
        }}
      >
        <ChevronRight size={18} style={{ transform: "rotate(180deg)" }} />
      </button>
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 8,
          background: color + "18",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Icon size={16} color={color} />
      </div>
      <div>
        <h2
          style={{
            fontSize: 20,
            fontWeight: 800,
            fontFamily: F.d,
            color: P.cream,
            margin: 0,
          }}
        >
          {label}
        </h2>
        <div style={{ fontSize: 10, fontFamily: F.b, color }}>{sub}</div>
      </div>
    </div>
  );
}

export { camelotColor };
