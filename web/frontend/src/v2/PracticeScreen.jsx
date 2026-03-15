import { useState } from "react";
import {
  Headphones, Zap, Search, Disc3, Target, ChevronRight, Clock,
  TrendingUp, TrendingDown,
} from "lucide-react";
import { P, F } from "./theme";
import { Badge, EnergyBar, ThemeHeader, camelotColor } from "./components";

export default function PracticeScreen({ nav, isDesktop }) {
  const [mode, setMode] = useState("hard");

  const mixes = [
    {
      a: "Tale Of Us - Astral",
      b: "Stephan Bodzin - Zulu",
      bA: 126, bB: 124, kA: "8A", kB: "5A",
      eA: 0.92, eB: 0.74, diff: "hard",
      tip: "Big energy drop. Use a long breakdown to transition.",
    },
    {
      a: "Mind Against - Atlant",
      b: "Dixon - Transmoderna",
      bA: 128, bB: 122, kA: "11B", kB: "2A",
      eA: 0.88, eB: 0.62, diff: "expert",
      tip: "6 BPM gap + key clash. Loop down or use an acapella bridge.",
    },
    {
      a: "Solomun - After Rain",
      b: "Tale Of Us - Astral",
      bA: 118, bB: 126, kA: "8A", kB: "8A",
      eA: 0.35, eB: 0.92, diff: "hard",
      tip: "Same key but massive energy jump. Build over 32 bars.",
    },
  ];

  const dc = (d) =>
    d === "expert" ? P.terra : d === "hard" ? P.warn : d === "medium" ? P.azure : P.green;

  const pad = isDesktop ? "32px 32px 48px" : "20px 18px 100px";

  return (
    <div style={{ padding: pad }}>
      <ThemeHeader
        nav={nav}
        icon={Headphones}
        label="Practice"
        sub="Know your tracks"
        color={P.purple}
        isDesktop={isDesktop}
      />
      <div style={{ display: "flex", gap: 6, marginBottom: 18, ...(isDesktop ? { maxWidth: 600 } : {}), overflowX: "auto" }}>
        {[
          { id: "hard", l: "Hard transitions", I: Zap },
          { id: "free", l: "Pick any two", I: Search },
          { id: "history", l: "History", I: Clock },
        ].map((m) => (
          <button
            key={m.id}
            onClick={() => setMode(m.id)}
            style={{
              flex: 1,
              background: mode === m.id ? P.purple + "18" : "transparent",
              border: `1px solid ${mode === m.id ? P.purple + "40" : P.border}`,
              borderRadius: 10,
              padding: "10px",
              color: mode === m.id ? P.purple : P.text3,
              fontSize: 12,
              fontFamily: F.d,
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 5,
            }}
          >
            <m.I size={13} />
            {m.l}
          </button>
        ))}
      </div>

      {mode === "hard" && (
        <>
          <div
            style={{
              fontSize: 11,
              fontFamily: F.b,
              color: P.text2,
              marginBottom: 14,
            }}
          >
            Hardest transitions in your Saturday crate
          </div>
          {/* Desktop: 2-column grid of transition cards */}
          <div
            style={
              isDesktop
                ? { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }
                : {}
            }
          >
            {mixes.map((m, i) => (
              <div
                key={i}
                style={{
                  background: P.bgCard,
                  borderRadius: 14,
                  padding: isDesktop ? "20px" : "16px",
                  border: `1px solid ${P.border}`,
                  marginBottom: isDesktop ? 0 : 10,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    marginBottom: 12,
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        fontFamily: F.b,
                        color: P.cream,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {m.a}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        marginTop: 2,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 10,
                          fontFamily: F.m,
                          color: P.text2,
                        }}
                      >
                        {m.bA}
                      </span>
                      <span
                        style={{
                          fontSize: 10,
                          fontFamily: F.m,
                          color: camelotColor(m.kA),
                        }}
                      >
                        {m.kA}
                      </span>
                      <EnergyBar energy={m.eA} w={24} />
                    </div>
                  </div>
                  <ChevronRight size={14} color={P.text3} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        fontFamily: F.b,
                        color: P.cream,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {m.b}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        marginTop: 2,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 10,
                          fontFamily: F.m,
                          color: P.text2,
                        }}
                      >
                        {m.bB}
                      </span>
                      <span
                        style={{
                          fontSize: 10,
                          fontFamily: F.m,
                          color: camelotColor(m.kB),
                        }}
                      >
                        {m.kB}
                      </span>
                      <EnergyBar energy={m.eB} w={24} />
                    </div>
                  </div>
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    alignItems: "center",
                    marginBottom: 8,
                  }}
                >
                  <Badge color={dc(m.diff)}>{m.diff}</Badge>
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: F.m,
                      color: P.text2,
                    }}
                  >
                    BPM {m.bA > m.bB ? "-" : "+"}
                    {Math.abs(m.bA - m.bB)} -- Energy{" "}
                    {m.eA > m.eB ? "drop" : "jump"}{" "}
                    {Math.abs(m.eA - m.eB).toFixed(2)}
                  </span>
                </div>
                <div
                  style={{
                    fontSize: 11,
                    fontFamily: F.b,
                    color: P.text2,
                    lineHeight: 1.5,
                    background: P.bgSurface,
                    borderRadius: 8,
                    padding: isDesktop ? "12px 14px" : "10px 12px",
                    display: "flex",
                    gap: 6,
                    alignItems: "flex-start",
                  }}
                >
                  <Target
                    size={12}
                    color={P.purple}
                    style={{ flexShrink: 0, marginTop: 2 }}
                  />
                  {m.tip}
                </div>
                <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
                  {[
                    ["Low", P.terra],
                    ["Medium", P.warn],
                    ["High", P.green],
                  ].map(([c, col], j) => (
                    <button
                      key={j}
                      style={{
                        flex: 1,
                        background: P.bgHover,
                        border: `1px solid ${P.border}`,
                        borderRadius: 8,
                        padding: "8px",
                        color: P.cream,
                        fontSize: 10,
                        fontFamily: F.d,
                        fontWeight: 600,
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: 4,
                      }}
                    >
                      <div
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: "50%",
                          background: col,
                        }}
                      />
                      {c}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {mode === "free" && (
        <div
          style={{
            background: P.bgCard,
            borderRadius: 14,
            padding: isDesktop ? "32px" : "20px",
            border: `1px solid ${P.border}`,
            textAlign: "center",
            ...(isDesktop ? { maxWidth: 600 } : {}),
          }}
        >
          <Disc3
            size={28}
            color={P.purple}
            style={{ margin: "0 auto 12px" }}
          />
          <div
            style={{
              fontSize: 14,
              fontFamily: F.d,
              fontWeight: 600,
              color: P.cream,
              marginBottom: 8,
            }}
          >
            Pick two tracks from your library
          </div>
          <div
            style={{
              fontSize: 12,
              fontFamily: F.b,
              color: P.text2,
              marginBottom: 16,
            }}
          >
            Search by name, BPM, or key to explore any transition
          </div>
          <div
            style={{
              background: P.bgSurface,
              borderRadius: 10,
              padding: isDesktop ? "14px 20px" : "12px 16px",
              border: `1px solid ${P.border}`,
              display: "flex",
              alignItems: "center",
              gap: 8,
              textAlign: "left",
            }}
          >
            <Search size={14} color={P.text3} />
            <span
              style={{ fontSize: 13, fontFamily: F.b, color: P.text3 }}
            >
              Search your tracks...
            </span>
          </div>
        </div>
      )}

      {mode === "history" && (
        <div style={isDesktop ? { maxWidth: 800 } : {}}>
          {/* Summary header */}
          <div
            style={{
              display: isDesktop ? "flex" : "block",
              gap: 12,
              marginBottom: 18,
            }}
          >
            <div
              style={{
                background: P.bgCard,
                borderRadius: 14,
                padding: isDesktop ? "20px" : "16px",
                border: `1px solid ${P.purple}20`,
                marginBottom: isDesktop ? 0 : 10,
                flex: 1,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <Clock size={14} color={P.purple} />
                <span style={{ fontSize: 11, fontFamily: F.m, color: P.purple, letterSpacing: 1 }}>
                  PRACTICE HISTORY
                </span>
              </div>
              <div style={{ display: "flex", gap: 16 }}>
                <div>
                  <div style={{ fontSize: 28, fontWeight: 800, fontFamily: F.d, color: P.purple }}>12</div>
                  <div style={{ fontSize: 10, fontFamily: F.m, color: P.text2 }}>sessions</div>
                </div>
                <div>
                  <div style={{ fontSize: 28, fontWeight: 800, fontFamily: F.d, color: P.cream }}>28</div>
                  <div style={{ fontSize: 10, fontFamily: F.m, color: P.text2 }}>transitions drilled</div>
                </div>
              </div>
            </div>
            <div
              style={{
                background: P.bgCard,
                borderRadius: 14,
                padding: isDesktop ? "20px" : "16px",
                border: `1px solid ${P.border}`,
                marginBottom: isDesktop ? 0 : 10,
                flex: 1,
              }}
            >
              <div style={{ fontSize: 10, fontFamily: F.m, color: P.text3, letterSpacing: 1, marginBottom: 10 }}>
                THIS MONTH
              </div>
              <div style={{ display: "flex", gap: 14 }}>
                {[
                  { n: 8, l: "improved", color: P.green, I: TrendingUp },
                  { n: 3, l: "new", color: P.azure, I: Disc3 },
                  { n: 1, l: "regressed", color: P.terra, I: TrendingDown },
                ].map((s, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <s.I size={12} color={s.color} />
                    <div>
                      <span style={{ fontSize: 16, fontWeight: 800, fontFamily: F.d, color: s.color }}>{s.n}</span>
                      <span style={{ fontSize: 10, fontFamily: F.b, color: P.text2, marginLeft: 4 }}>{s.l}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Recent sessions */}
          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 10, fontFamily: F.m, color: P.text3, letterSpacing: 1, marginBottom: 8 }}>
              RECENT SESSIONS
            </div>
            {[
              { date: "Mar 14", crate: "Saturday crate", transitions: 5, confidence: "Medium" },
              { date: "Mar 12", crate: "Saturday crate", transitions: 3, confidence: "High" },
              { date: "Mar 10", crate: "Festival prep", transitions: 4, confidence: "Low" },
            ].map((s, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: isDesktop ? "12px 16px" : "10px 12px",
                  background: P.bgCard,
                  borderRadius: 10,
                  border: `1px solid ${P.border}`,
                  marginBottom: 4,
                }}
              >
                <span style={{ fontSize: 11, fontFamily: F.m, color: P.text3, width: 50, flexShrink: 0 }}>
                  {s.date}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, fontFamily: F.b, color: P.cream }}>
                    {s.crate}
                  </div>
                  <div style={{ fontSize: 10, fontFamily: F.m, color: P.text2, marginTop: 1 }}>
                    {s.transitions} transitions
                  </div>
                </div>
                <Badge
                  color={
                    s.confidence === "High" ? P.green : s.confidence === "Medium" ? P.warn : P.terra
                  }
                >
                  avg: {s.confidence}
                </Badge>
              </div>
            ))}
          </div>

          {/* Most practiced */}
          <div>
            <div style={{ fontSize: 10, fontFamily: F.m, color: P.text3, letterSpacing: 1, marginBottom: 8 }}>
              MOST PRACTICED
            </div>
            {[
              { a: "Tale Of Us", b: "Stephan Bodzin", times: 5, from: "High", to: "High" },
              { a: "Mind Against", b: "Dixon", times: 3, from: "Low", to: "Medium" },
            ].map((p, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: isDesktop ? "12px 16px" : "10px 12px",
                  background: P.bgCard,
                  borderRadius: 10,
                  border: `1px solid ${P.border}`,
                  marginBottom: 4,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      fontFamily: F.b,
                      color: P.cream,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {p.a} {"\u2192"} {p.b}
                  </div>
                  <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 3 }}>
                    <span style={{ fontSize: 10, fontFamily: F.m, color: P.text2 }}>
                      {p.times} times
                    </span>
                    <span style={{ fontSize: 10, fontFamily: F.m, color: P.text3 }}>
                      confidence:
                    </span>
                    <Badge color={p.from === "High" ? P.green : p.from === "Medium" ? P.warn : P.terra}>
                      {p.from}
                    </Badge>
                    <ChevronRight size={10} color={P.text3} />
                    <Badge color={p.to === "High" ? P.green : p.to === "Medium" ? P.warn : P.terra}>
                      {p.to}
                    </Badge>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
