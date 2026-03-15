import { useState, useEffect } from "react";
import {
  Search, Wrench, Headphones, SlidersHorizontal,
  AlertTriangle,
} from "lucide-react";
import { P, F } from "./theme";
import { fetchStats } from "./api";

export default function HomePage({ nav, isDesktop }) {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => setError(true));
  }, []);

  // Derive tile data from real stats or fall back to defaults
  const digStat = stats?.total_tracks != null ? String(stats.total_tracks) : "--";
  const digSub = stats?.total_tracks != null ? "tracks" : "loading";

  const missingBpm = stats?.missing_bpm || 0;
  const missingKey = stats?.missing_key || 0;
  const missingGenre = stats?.missing_genre || 0;
  const prepCount = missingBpm + missingKey;
  const prepStat = stats ? String(prepCount) : "--";
  const prepSub = stats ? "need attention" : "loading";

  const healthScore = stats?.health_score != null ? stats.health_score : null;
  const prepDetail = stats
    ? `Library health: ${healthScore != null ? healthScore : "?"} ${missingGenre > 0 ? `\u00B7 ${missingGenre} no genre` : ""}`
    : "Checking library...";

  const tiles = [
    {
      id: "dig",
      Icon: Search,
      color: P.azure,
      label: "Dig",
      stat: digStat,
      statSub: digSub,
      detail: stats ? `${stats.total_tracks || 0} in library` : "Connecting...",
    },
    {
      id: "prep",
      Icon: Wrench,
      color: P.lime,
      label: "Prep",
      stat: prepStat,
      statSub: prepSub,
      detail: prepDetail,
    },
    {
      id: "practice",
      Icon: Headphones,
      color: P.purple,
      label: "Practice",
      stat: "5",
      statSub: "hard mixes",
      detail: "Toughest transitions to drill",
    },
    {
      id: "gig",
      Icon: SlidersHorizontal,
      color: P.terra,
      label: "Gig",
      stat: "READY",
      statSub: "next gig",
      detail: "Energy zones \u00B7 crate browser",
    },
  ];

  // Build contextual nudge from stats
  const nudgeItems = [];
  if (stats) {
    if (missingBpm > 0) nudgeItems.push(`${missingBpm} tracks missing BPM`);
    if (missingKey > 0) nudgeItems.push(`${missingKey} missing key`);
    if (missingGenre > 0) nudgeItems.push(`${missingGenre} missing genre`);
  }
  const nudgeText = nudgeItems.length > 0
    ? nudgeItems.join(". ") + "."
    : stats
      ? "Library looking healthy. Time to dig for new music."
      : "Connecting to CrateDigger...";

  const pad = isDesktop ? "32px 32px 48px" : "20px 18px 100px";
  const tilePad = isDesktop ? "22px 20px" : "18px 16px";

  return (
    <div style={{ padding: pad }}>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: isDesktop ? 32 : 24,
        }}
      >
        <div>
          {/* Branding dots — only on mobile (desktop has sidebar branding) */}
          {!isDesktop && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                marginBottom: 4,
              }}
            >
              {[P.azure, P.lime, P.purple, P.terra].map((c, i) => (
                <div
                  key={i}
                  style={{
                    width: 6,
                    height: 6,
                    background: c,
                    borderRadius: 1.5,
                  }}
                />
              ))}
              <span
                style={{
                  fontSize: 10,
                  fontFamily: F.m,
                  color: P.text3,
                  letterSpacing: 2,
                }}
              >
                CRATEDIGGER
              </span>
            </div>
          )}
          <h1
            style={{
              fontSize: isDesktop ? 28 : 24,
              fontWeight: 800,
              fontFamily: F.d,
              color: P.cream,
              margin: 0,
            }}
          >
            Hey Rico
          </h1>
        </div>
        <div
          style={{
            fontSize: 10,
            fontFamily: F.m,
            color: P.text3,
            textAlign: "right",
          }}
        >
          <div>{new Date().toLocaleDateString("en-US", { weekday: "long" })}</div>
          <div style={{ color: P.cream }}>
            {new Date().toLocaleDateString("en-US", { month: "short", day: "numeric" })}
          </div>
        </div>
      </div>

      {/* Tiles grid — 4-column on desktop, 2x2 on mobile */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: isDesktop ? "1fr 1fr 1fr 1fr" : "1fr 1fr",
          gap: isDesktop ? 16 : 12,
          marginBottom: isDesktop ? 24 : 20,
        }}
      >
        {tiles.map((t) => {
          const I = t.Icon;
          return (
            <div
              key={t.id}
              onClick={() => nav(t.id)}
              style={{
                background: P.bgCard,
                borderRadius: 16,
                padding: tilePad,
                cursor: "pointer",
                border: `1px solid ${P.border}`,
                position: "relative",
                overflow: "hidden",
              }}
            >
              {/* Corner glow */}
              <div
                style={{
                  position: "absolute",
                  top: -20,
                  right: -20,
                  width: 60,
                  height: 60,
                  background: `radial-gradient(circle,${t.color}12,transparent)`,
                  borderRadius: "50%",
                }}
              />
              {/* Dekmantel geometric square accent */}
              <div
                style={{
                  position: "absolute",
                  top: 8,
                  right: 8,
                  width: 16,
                  height: 16,
                  border: `1px solid ${t.color}20`,
                  borderRadius: 3,
                  transform: "rotate(12deg)",
                }}
              />
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: isDesktop ? 16 : 12,
                }}
              >
                <div
                  style={{
                    width: isDesktop ? 32 : 28,
                    height: isDesktop ? 32 : 28,
                    borderRadius: 7,
                    background: t.color + "15",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <I size={isDesktop ? 16 : 14} color={t.color} />
                </div>
                <span
                  style={{
                    fontSize: isDesktop ? 18 : 16,
                    fontWeight: 700,
                    fontFamily: F.d,
                    color: P.cream,
                  }}
                >
                  {t.label}
                </span>
              </div>
              <div
                style={{
                  fontSize: isDesktop ? 32 : 28,
                  fontWeight: 800,
                  fontFamily: F.d,
                  color: t.color,
                  lineHeight: 1,
                }}
              >
                {t.stat}
              </div>
              <div
                style={{
                  fontSize: 10,
                  fontFamily: F.m,
                  color: P.text2,
                  marginTop: 2,
                  letterSpacing: 0.5,
                }}
              >
                {t.statSub}
              </div>
              <div
                style={{
                  fontSize: 11,
                  fontFamily: F.b,
                  color: P.text3,
                  marginTop: isDesktop ? 14 : 10,
                  lineHeight: 1.4,
                }}
              >
                {t.detail}
              </div>
            </div>
          );
        })}
      </div>

      {/* Contextual nudge — full width */}
      <div
        style={{
          background: P.bgEl,
          borderRadius: 14,
          padding: isDesktop ? "20px 24px" : "16px 18px",
          border: `1px solid ${P.warn}18`,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginBottom: 6,
          }}
        >
          <AlertTriangle size={12} color={P.warn} />
          <span
            style={{
              fontSize: 10,
              fontFamily: F.m,
              color: P.warn,
              letterSpacing: 1,
            }}
          >
            THIS WEEK
          </span>
        </div>
        <div
          style={{
            fontSize: 13,
            fontFamily: F.b,
            color: P.cream,
            lineHeight: 1.5,
          }}
        >
          {error ? "Could not connect to CrateDigger backend." : nudgeText}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <button
            onClick={() => nav("prep")}
            style={{
              background: P.lime + "18",
              border: `1px solid ${P.lime}30`,
              borderRadius: 8,
              padding: "8px 14px",
              color: P.lime,
              fontSize: 11,
              fontFamily: F.d,
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <Wrench size={12} />
            Process tracks
          </button>
          <button
            onClick={() => nav("practice")}
            style={{
              background: P.purple + "18",
              border: `1px solid ${P.purple}30`,
              borderRadius: 8,
              padding: "8px 14px",
              color: P.purple,
              fontSize: 11,
              fontFamily: F.d,
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <Headphones size={12} />
            Practice
          </button>
        </div>
      </div>
    </div>
  );
}
