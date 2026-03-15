import { useState, useEffect } from "react";
import {
  Wrench, Fingerprint, HardDrive, Activity, Radio, Hash,
  CircleCheck, CircleX, AlertTriangle, Tag, Clock,
  AudioLines, SkipForward, ChevronRight,
} from "lucide-react";
import { P, F } from "./theme";
import { Badge, EnergyBar, Ring, ThemeHeader, camelotColor } from "./components";
import { fetchStats } from "./api";

export default function PrepScreen({ nav }) {
  const [tab, setTab] = useState("intake");
  return (
    <div style={{ padding: "20px 18px 100px" }}>
      <ThemeHeader
        nav={nav}
        icon={Wrench}
        label="Prep"
        sub="Get it ready"
        color={P.lime}
      />
      <div
        style={{
          display: "flex",
          gap: 0,
          marginBottom: 18,
          borderBottom: `1px solid ${P.border}`,
        }}
      >
        {[
          { id: "intake", l: "Intake (14)" },
          { id: "library", l: "Library" },
          { id: "profile", l: "My Sound" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              background: "none",
              border: "none",
              borderBottom: `2px solid ${tab === t.id ? P.lime : "transparent"}`,
              padding: "10px 14px",
              color: tab === t.id ? P.cream : P.text3,
              fontSize: 12,
              fontFamily: F.d,
              fontWeight: 600,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            {t.l}
          </button>
        ))}
      </div>
      {tab === "intake" && <IntakeContent />}
      {tab === "library" && <LibraryContent />}
      {tab === "profile" && <ProfileContent />}
    </div>
  );
}

/* Intake — mock data (demonstrates the review queue pattern) */
function IntakeContent() {
  const t = {
    file: "SC_download_x7r9k2.mp3",
    artist: "Solomun",
    title: "After Rain (Original Mix)",
    bpm: 122,
    key: "8A",
    energy: 0.72,
  };
  return (
    <>
      <div style={{ display: "flex", gap: 3, marginBottom: 14 }}>
        {Array(14)
          .fill(0)
          .map((_, i) => (
            <div
              key={i}
              style={{
                flex: 1,
                height: 3,
                borderRadius: 2,
                background:
                  i < 1 ? P.lime : i === 1 ? P.cream : P.border,
              }}
            />
          ))}
      </div>
      <div
        style={{
          background: P.lime + "12",
          borderRadius: 10,
          padding: "10px 14px",
          marginBottom: 12,
          border: `1px solid ${P.lime}25`,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div
          style={{ display: "flex", alignItems: "center", gap: 8 }}
        >
          <Fingerprint size={14} color={P.lime} />
          <div>
            <div
              style={{ fontSize: 10, fontFamily: F.m, color: P.lime }}
            >
              IDENTIFIED -- TRACK 2 OF 14
            </div>
            <div
              style={{
                fontSize: 12,
                fontFamily: F.b,
                color: P.cream,
                marginTop: 2,
              }}
            >
              AcoustID fingerprint -- 94% match
            </div>
          </div>
        </div>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          marginBottom: 10,
        }}
      >
        <HardDrive size={10} color={P.text3} />
        <span style={{ fontSize: 10, fontFamily: F.m, color: P.text3 }}>
          {t.file}
        </span>
      </div>
      <div
        style={{
          background: P.bgCard,
          borderRadius: 14,
          padding: "16px",
          marginBottom: 12,
          border: `1px solid ${P.border}`,
        }}
      >
        <div
          style={{
            fontSize: 18,
            fontWeight: 700,
            fontFamily: F.d,
            color: P.cream,
          }}
        >
          {t.artist}
        </div>
        <div
          style={{
            fontSize: 15,
            fontFamily: F.d,
            color: P.text2,
            marginTop: 2,
          }}
        >
          {t.title}
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 10,
            marginTop: 14,
          }}
        >
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 3,
              }}
            >
              <Radio size={9} color={P.text3} />
              <span
                style={{
                  fontSize: 9,
                  fontFamily: F.m,
                  color: P.text3,
                }}
              >
                BPM
              </span>
            </div>
            <div
              style={{
                fontSize: 20,
                fontWeight: 800,
                fontFamily: F.d,
                color: P.cream,
                marginTop: 2,
              }}
            >
              {t.bpm}
            </div>
          </div>
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 3,
              }}
            >
              <Hash size={9} color={P.text3} />
              <span
                style={{
                  fontSize: 9,
                  fontFamily: F.m,
                  color: P.text3,
                }}
              >
                KEY
              </span>
            </div>
            <div
              style={{
                fontSize: 20,
                fontWeight: 800,
                fontFamily: F.d,
                color: camelotColor(t.key),
                marginTop: 2,
              }}
            >
              {t.key}
            </div>
          </div>
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 3,
              }}
            >
              <Activity size={9} color={P.text3} />
              <span
                style={{
                  fontSize: 9,
                  fontFamily: F.m,
                  color: P.text3,
                }}
              >
                ENERGY
              </span>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                marginTop: 4,
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
                {t.energy}
              </span>
              <EnergyBar energy={t.energy} w={30} />
            </div>
          </div>
        </div>
      </div>
      <div
        style={{
          background: P.bgSurface,
          borderRadius: 8,
          padding: "10px 12px",
          marginBottom: 12,
        }}
      >
        <div
          style={{ fontSize: 9, fontFamily: F.m, color: P.text3 }}
        >
          FILENAME
        </div>
        <div
          style={{
            fontSize: 11,
            fontFamily: F.m,
            color: P.lime,
            marginTop: 2,
          }}
        >
          Solomun - After Rain (Original Mix).mp3
        </div>
      </div>
      <div
        style={{
          display: "flex",
          gap: 6,
          flexWrap: "wrap",
          marginBottom: 16,
        }}
      >
        {["melodic-techno", "deep-house", "afro-house", "breaks", "+ new"].map(
          (f, i) => (
            <button
              key={i}
              style={{
                background: i === 0 ? P.terra + "18" : P.bgCard,
                border: `1px solid ${i === 0 ? P.terra : P.border}`,
                borderRadius: 8,
                padding: "7px 12px",
                color: i === 0 ? P.terra : P.cream,
                fontSize: 11,
                fontFamily: F.b,
                cursor: "pointer",
                fontWeight: i === 0 ? 700 : 400,
              }}
            >
              {f}
            </button>
          ),
        )}
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          style={{
            flex: 1,
            background: P.bgCard,
            border: `1px solid ${P.border}`,
            borderRadius: 10,
            padding: "12px",
            color: P.text2,
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
          <SkipForward size={14} />
          Skip
        </button>
        <button
          style={{
            flex: 2,
            background: P.lime,
            border: "none",
            borderRadius: 10,
            padding: "12px",
            color: P.bg,
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
          <CircleCheck size={14} />
          Approve
        </button>
      </div>
    </>
  );
}

/* Library — wired to real /api/library/stats */
function LibraryContent() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetchStats()
      .then(setStats)
      .catch(() => setError(true));
  }, []);

  const totalTracks = stats?.total_tracks || 0;
  const healthScore = stats?.health_score ?? 72;
  const missingBpm = stats?.missing_bpm || 0;
  const missingKey = stats?.missing_key || 0;
  const missingGenre = stats?.missing_genre || 0;
  const highCount = missingBpm + missingKey;

  const tiers = [
    {
      sev: "CRITICAL",
      n: 0,
      d: "Corrupt & zero-byte files",
      c: P.terra,
      I: CircleX,
    },
    {
      sev: "HIGH",
      n: highCount,
      d: `Missing BPM (${missingBpm}) or key (${missingKey})`,
      c: P.warn,
      I: AlertTriangle,
    },
    {
      sev: "MEDIUM",
      n: missingGenre,
      d: "Missing genre tags",
      c: P.azure,
      I: Tag,
    },
    {
      sev: "LOW",
      n: 0,
      d: "Missing year, album tags",
      c: P.text3,
      I: Clock,
    },
  ];

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          background: P.bgCard,
          borderRadius: 14,
          padding: "18px",
          marginBottom: 16,
          border: `1px solid ${P.border}`,
        }}
      >
        <Ring pct={healthScore} size={70} stroke={5} color={P.mauve} />
        <div>
          <div
            style={{
              fontSize: 16,
              fontWeight: 700,
              fontFamily: F.d,
              color: P.cream,
            }}
          >
            {error ? "Offline" : `${totalTracks.toLocaleString()} tracks`}
          </div>
          <div
            style={{
              fontSize: 11,
              fontFamily: F.b,
              color: P.text2,
              marginTop: 2,
            }}
          >
            {error ? "Could not connect" : "Library health score"}
          </div>
          {!error && (
            <div style={{ display: "flex", gap: 5, marginTop: 6 }}>
              {highCount > 0 && (
                <Badge color={P.warn}>{highCount} high</Badge>
              )}
              {missingGenre > 0 && (
                <Badge color={P.azure}>{missingGenre} medium</Badge>
              )}
            </div>
          )}
        </div>
      </div>
      {tiers.map((r, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "12px 14px",
            background: P.bgCard,
            borderRadius: 10,
            border: `1px solid ${P.border}`,
            marginBottom: 6,
          }}
        >
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 6,
              background: r.c + "15",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <r.I size={14} color={r.c} />
          </div>
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontSize: 9,
                fontFamily: F.m,
                color: r.c,
                letterSpacing: 1,
              }}
            >
              {r.sev}
            </div>
            <div
              style={{
                fontSize: 12,
                fontFamily: F.b,
                color: P.cream,
              }}
            >
              {r.d}
            </div>
          </div>
          <span
            style={{
              fontSize: 14,
              fontWeight: 800,
              fontFamily: F.d,
              color: r.c,
            }}
          >
            {r.n}
          </span>
          <ChevronRight size={14} color={P.text3} />
        </div>
      ))}
      <button
        style={{
          width: "100%",
          background: P.mauve,
          border: "none",
          borderRadius: 10,
          padding: "14px",
          marginTop: 8,
          color: P.cream,
          fontSize: 13,
          fontFamily: F.d,
          fontWeight: 700,
          cursor: "pointer",
        }}
      >
        Start fixing
      </button>
    </>
  );
}

/* My Sound profile — mock data */
function ProfileContent() {
  const genres = [
    { n: "Melodic Techno", p: 48, o: 42, c: P.terra },
    { n: "Deep House", p: 28, o: 31, c: P.azure },
    { n: "Afro House", p: 12, o: 10, c: P.lime },
    { n: "Breaks", p: 5, o: 0, c: P.purple },
    { n: "Other", p: 7, o: 17, c: P.text3 },
  ];
  return (
    <>
      <div
        style={{
          background: `linear-gradient(135deg,${P.lime}10,${P.azure}08)`,
          borderRadius: 14,
          padding: "16px",
          marginBottom: 16,
          border: `1px solid ${P.lime}15`,
        }}
      >
        <div
          style={{
            fontSize: 13,
            fontFamily: F.b,
            color: P.cream,
            lineHeight: 1.6,
          }}
        >
          Melodic techno & deep house. BPM{" "}
          <span style={{ color: P.lime, fontWeight: 700 }}>122-126</span>. Minor
          keys. You play{" "}
          <span style={{ color: P.warn, fontWeight: 700 }}>16%</span> of your
          library at gigs.
        </div>
      </div>
      <div
        style={{
          background: P.bgCard,
          borderRadius: 14,
          padding: "14px 16px",
          marginBottom: 14,
          border: `1px solid ${P.border}`,
        }}
      >
        <div
          style={{ display: "flex", alignItems: "center", gap: 14 }}
        >
          <Ring pct={16} size={56} stroke={4} color={P.warn} />
          <div>
            <div
              style={{
                fontSize: 13,
                fontWeight: 600,
                fontFamily: F.b,
                color: P.cream,
              }}
            >
              340 of 2,147 played
            </div>
            <div
              style={{
                fontSize: 11,
                fontFamily: F.b,
                color: P.text2,
              }}
            >
              84% of gigs from 20% of library
            </div>
          </div>
        </div>
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          marginBottom: 8,
        }}
      >
        <AudioLines size={10} color={P.text3} />
        <span
          style={{
            fontSize: 9,
            fontFamily: F.m,
            color: P.text3,
            letterSpacing: 1,
          }}
        >
          WHAT YOU PLAY vs WHAT YOU OWN
        </span>
      </div>
      {genres.map((g, i) => (
        <div key={i} style={{ marginBottom: 10 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginBottom: 3,
            }}
          >
            <span
              style={{ fontSize: 11, fontFamily: F.b, color: P.cream }}
            >
              {g.n}
            </span>
            <span
              style={{
                fontSize: 9,
                fontFamily: F.m,
                color: P.text2,
              }}
            >
              {g.p}% played -- {g.o}% owned
            </span>
          </div>
          <div
            style={{
              position: "relative",
              height: 12,
              background: P.border,
              borderRadius: 3,
            }}
          >
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                height: 12,
                width: `${g.o}%`,
                background: g.c + "25",
                borderRadius: 3,
              }}
            />
            <div
              style={{
                position: "absolute",
                top: 2,
                left: 0,
                height: 8,
                width: `${g.p}%`,
                background: g.c,
                borderRadius: 2,
              }}
            />
          </div>
          {g.p > 0 && g.o === 0 && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 3,
                marginTop: 2,
              }}
            >
              <AlertTriangle size={9} color={P.warn} />
              <span
                style={{
                  fontSize: 9,
                  fontFamily: F.m,
                  color: P.warn,
                }}
              >
                You play this but own 0 tracks
              </span>
            </div>
          )}
        </div>
      ))}
    </>
  );
}
