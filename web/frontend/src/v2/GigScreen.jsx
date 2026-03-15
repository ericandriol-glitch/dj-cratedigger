import { useState, useEffect } from "react";
import {
  SlidersHorizontal, Music, Zap, Activity, Volume2,
  Radio, Clock, Hash, Target, Scan, HardDrive,
  CircleCheck, AlertTriangle,
} from "lucide-react";
import { P, F } from "./theme";
import { EnergyBar, ThemeHeader, camelotColor } from "./components";
import { fetchTracks } from "./api";

export default function GigScreen({ nav, isDesktop }) {
  const [zone, setZone] = useState("all");
  const [tracks, setTracks] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchTracks({ limit: 30, sort: "energy", order: "desc" })
      .then((data) => {
        const list = (data.tracks || []).map((t) => {
          const e = t.energy != null ? t.energy : 0.5;
          let z = "groove";
          if (e >= 0.8) z = "peak";
          else if (e >= 0.6) z = "build";
          else if (e >= 0.4) z = "groove";
          else z = "warm";
          return {
            a: t.artist || "Unknown",
            t: t.title || t.filename || "Untitled",
            bpm: t.bpm || 0,
            key: t.key || "",
            genre: t.genre || "",
            e,
            cue: true,
            z,
          };
        });
        setTracks(list);
      })
      .catch(() => {
        setError(true);
        setTracks(null);
      });
  }, []);

  // Fall back to mock data if API unavailable
  const mockTracks = [
    { a: "Tale Of Us", t: "Astral (Extended)", bpm: 126, key: "8A", genre: "Melodic Techno", e: 0.92, cue: true, z: "peak" },
    { a: "Mind Against", t: "Atlant", bpm: 128, key: "11B", genre: "Melodic Techno", e: 0.88, cue: true, z: "peak" },
    { a: "Stephan Bodzin", t: "Zulu", bpm: 124, key: "5A", genre: "Melodic Techno", e: 0.74, cue: true, z: "build" },
    { a: "Dixon", t: "Transmoderna", bpm: 122, key: "2A", genre: "Deep House", e: 0.62, cue: false, z: "groove" },
    { a: "Ame", t: "Rej (DJ Koze Remix)", bpm: 120, key: "7A", genre: "Deep House", e: 0.45, cue: true, z: "warm" },
    { a: "Solomun", t: "After Rain", bpm: 118, key: "8A", genre: "Deep House", e: 0.35, cue: false, z: "warm" },
  ];

  const displayTracks = tracks || mockTracks;

  // Calculate zone counts
  const zoneCounts = { all: displayTracks.length };
  for (const t of displayTracks) {
    zoneCounts[t.z] = (zoneCounts[t.z] || 0) + 1;
  }

  const zones = [
    { id: "all", l: "All", n: zoneCounts.all || 0, c: P.cream, I: Music },
    { id: "peak", l: "Peak", n: zoneCounts.peak || 0, c: P.terra, I: Zap },
    { id: "build", l: "Build", n: zoneCounts.build || 0, c: P.warn, I: Activity },
    { id: "groove", l: "Groove", n: zoneCounts.groove || 0, c: P.azure, I: Volume2 },
    { id: "warm", l: "Warm", n: zoneCounts.warm || 0, c: P.mauve, I: Music },
  ];

  const filtered =
    zone === "all" ? displayTracks : displayTracks.filter((t) => t.z === zone);

  // Calculate stats from real data
  const bpms = displayTracks.map((t) => t.bpm).filter(Boolean);
  const minBpm = bpms.length ? Math.min(...bpms) : 0;
  const maxBpm = bpms.length ? Math.max(...bpms) : 0;
  const keysSet = new Set(displayTracks.map((t) => t.key).filter(Boolean));
  const cueCount = displayTracks.filter((t) => t.cue).length;

  const pad = isDesktop ? "32px 32px 48px" : "20px 18px 100px";

  return (
    <div style={{ padding: pad }}>
      {/* Desktop: ThemeHeader + action buttons in one row */}
      {isDesktop ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 18,
          }}
        >
          <ThemeHeader
            nav={nav}
            icon={SlidersHorizontal}
            label="Gig"
            sub="Play out"
            color={P.terra}
            isDesktop={isDesktop}
            noMargin
          />
          <div style={{ display: "flex", gap: 8 }}>
            <button
              style={{
                background: P.bgCard,
                border: `1px solid ${P.border}`,
                borderRadius: 10,
                padding: "10px 20px",
                color: P.cream,
                fontSize: 12,
                fontFamily: F.d,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <Scan size={14} />
              Preflight
            </button>
            <button
              style={{
                background: P.terra,
                border: "none",
                borderRadius: 10,
                padding: "10px 20px",
                color: P.cream,
                fontSize: 12,
                fontFamily: F.d,
                fontWeight: 700,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 4,
              }}
            >
              <HardDrive size={14} />
              Export USB
            </button>
          </div>
        </div>
      ) : (
        <ThemeHeader
          nav={nav}
          icon={SlidersHorizontal}
          label="Gig"
          sub="Play out"
          color={P.terra}
          isDesktop={isDesktop}
        />
      )}

      {/* Desktop: crate header + stats in a row */}
      <div
        style={
          isDesktop
            ? { display: "flex", gap: 16, marginBottom: 18, alignItems: "stretch" }
            : {}
        }
      >
        {/* Crate header */}
        <div
          style={{
            background: P.bgCard,
            borderRadius: 14,
            padding: isDesktop ? "18px 20px" : "14px 16px",
            marginBottom: isDesktop ? 0 : 14,
            border: `1px solid ${P.terra}20`,
            position: "relative",
            overflow: "hidden",
            ...(isDesktop ? { flex: 1 } : {}),
          }}
        >
          <div
            style={{
              position: "absolute",
              top: -8,
              right: -8,
              width: 24,
              height: 24,
              border: `1px solid ${P.terra}15`,
              borderRadius: 3,
              transform: "rotate(15deg)",
            }}
          />
          <div
            style={{
              fontSize: isDesktop ? 20 : 16,
              fontWeight: 700,
              fontFamily: F.d,
              color: P.cream,
            }}
          >
            Saturday at Warehouse
          </div>
          <div
            style={{
              fontSize: 11,
              fontFamily: F.b,
              color: P.text2,
              marginTop: 2,
            }}
          >
            Deep House Night
          </div>
        </div>

        {/* Stats row */}
        <div
          style={{
            display: "flex",
            gap: 6,
            marginBottom: isDesktop ? 0 : 14,
            overflowX: "auto",
            ...(isDesktop ? { flexShrink: 0 } : {}),
          }}
        >
          {[
            { l: "BPM", v: bpms.length ? `${minBpm}-${maxBpm}` : "--", I: Radio },
            { l: "Tracks", v: String(displayTracks.length), I: Clock },
            { l: "Keys", v: `${keysSet.size}/24`, I: Hash },
            {
              l: "Cues",
              v: `${cueCount}/${displayTracks.length}`,
              I: Target,
              w: cueCount < displayTracks.length,
            },
          ].map((s, i) => (
            <div
              key={i}
              style={{
                background: P.bgCard,
                borderRadius: 8,
                padding: isDesktop ? "10px 16px" : "8px 12px",
                border: `1px solid ${P.border}`,
                whiteSpace: "nowrap",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 3,
                }}
              >
                <s.I size={8} color={P.text3} />
                <span
                  style={{
                    fontSize: 8,
                    fontFamily: F.m,
                    color: P.text3,
                  }}
                >
                  {s.l}
                </span>
              </div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  fontFamily: F.d,
                  color: s.w ? P.warn : P.cream,
                  marginTop: 2,
                }}
              >
                {s.v}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Energy zone tabs */}
      <div
        style={{
          display: "flex",
          gap: 5,
          marginBottom: 14,
          overflowX: "auto",
        }}
      >
        {zones.map((z) => (
          <button
            key={z.id}
            onClick={() => setZone(z.id)}
            style={{
              background: zone === z.id ? z.c + "15" : "transparent",
              border: `1px solid ${zone === z.id ? z.c + "40" : P.border}`,
              borderRadius: 16,
              padding: "5px 12px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 4,
              whiteSpace: "nowrap",
            }}
          >
            <z.I size={10} color={zone === z.id ? z.c : P.text3} />
            <span
              style={{
                fontSize: 11,
                fontFamily: F.b,
                color: zone === z.id ? z.c : P.text3,
                fontWeight: zone === z.id ? 700 : 400,
              }}
            >
              {z.l}
            </span>
            <span
              style={{
                fontSize: 9,
                fontFamily: F.m,
                color: P.text3,
              }}
            >
              {z.n}
            </span>
          </button>
        ))}
      </div>

      {/* Desktop: table-like header row */}
      {isDesktop && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "6px 16px",
            marginBottom: 2,
          }}
        >
          <div style={{ width: 4 }} />
          <span
            style={{
              flex: 2,
              fontSize: 9,
              fontFamily: F.m,
              color: P.text3,
              letterSpacing: 1,
            }}
          >
            TRACK
          </span>
          <span
            style={{
              width: 50,
              fontSize: 9,
              fontFamily: F.m,
              color: P.text3,
              letterSpacing: 1,
            }}
          >
            BPM
          </span>
          <span
            style={{
              width: 40,
              fontSize: 9,
              fontFamily: F.m,
              color: P.text3,
              letterSpacing: 1,
            }}
          >
            KEY
          </span>
          <span
            style={{
              width: 120,
              fontSize: 9,
              fontFamily: F.m,
              color: P.text3,
              letterSpacing: 1,
            }}
          >
            GENRE
          </span>
          <span
            style={{
              width: 60,
              fontSize: 9,
              fontFamily: F.m,
              color: P.text3,
              letterSpacing: 1,
            }}
          >
            ENERGY
          </span>
          <span
            style={{
              width: 20,
              fontSize: 9,
              fontFamily: F.m,
              color: P.text3,
              letterSpacing: 1,
              textAlign: "center",
            }}
          >
            CUE
          </span>
        </div>
      )}

      {/* Track list */}
      {filtered.map((t, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: isDesktop ? "10px 16px" : "10px 12px",
            background: P.bgCard,
            borderRadius: 8,
            border: `1px solid ${P.border}`,
            marginBottom: 3,
          }}
        >
          <EnergyBar energy={t.e} w={4} />
          {isDesktop ? (
            <>
              {/* Desktop: wider table layout with genre + energy bar columns */}
              <div style={{ flex: 2, minWidth: 0 }}>
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
                  {t.a} -- {t.t}
                </div>
              </div>
              <span
                style={{
                  width: 50,
                  fontSize: 11,
                  fontFamily: F.m,
                  color: P.text2,
                }}
              >
                {t.bpm || "?"}
              </span>
              <span
                style={{
                  width: 40,
                  fontSize: 11,
                  fontFamily: F.m,
                  color: camelotColor(t.key),
                }}
              >
                {t.key || "?"}
              </span>
              <span
                style={{
                  width: 120,
                  fontSize: 11,
                  fontFamily: F.b,
                  color: P.text3,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {t.genre || "--"}
              </span>
              <div style={{ width: 60 }}>
                <EnergyBar energy={t.e} w={50} />
              </div>
              <div style={{ width: 20, textAlign: "center" }}>
                {t.cue ? (
                  <CircleCheck size={12} color={P.green} />
                ) : (
                  <AlertTriangle size={12} color={P.warn} />
                )}
              </div>
            </>
          ) : (
            <>
              {/* Mobile: compact layout */}
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
                  {t.a} -- {t.t}
                </div>
                <div
                  style={{ display: "flex", gap: 8, marginTop: 2 }}
                >
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: F.m,
                      color: P.text2,
                    }}
                  >
                    {t.bpm || "?"}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      fontFamily: F.m,
                      color: camelotColor(t.key),
                    }}
                  >
                    {t.key || "?"}
                  </span>
                </div>
              </div>
              {t.cue ? (
                <CircleCheck size={12} color={P.green} />
              ) : (
                <AlertTriangle size={12} color={P.warn} />
              )}
            </>
          )}
        </div>
      ))}

      {/* Action buttons — only on mobile (desktop has them in header) */}
      {!isDesktop && (
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button
            style={{
              flex: 1,
              background: P.bgCard,
              border: `1px solid ${P.border}`,
              borderRadius: 10,
              padding: "12px",
              color: P.cream,
              fontSize: 12,
              fontFamily: F.d,
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 4,
            }}
          >
            <Scan size={14} />
            Preflight
          </button>
          <button
            style={{
              flex: 1,
              background: P.terra,
              border: "none",
              borderRadius: 10,
              padding: "12px",
              color: P.cream,
              fontSize: 12,
              fontFamily: F.d,
              fontWeight: 700,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 4,
            }}
          >
            <HardDrive size={14} />
            Export USB
          </button>
        </div>
      )}
    </div>
  );
}
