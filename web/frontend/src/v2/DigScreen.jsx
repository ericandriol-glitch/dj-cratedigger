import { useState } from "react";
import {
  Search, Users, Globe, MapPin, Tag, Play,
  Heart, Star, Calendar, Disc3, Download,
  CircleCheck, CircleX, AlertTriangle, ListMusic,
  ChevronRight, User, Loader,
} from "lucide-react";
import { P, F } from "./theme";
import { Badge, SourceDot, ThemeHeader } from "./components";

export default function DigScreen({ nav, isDesktop }) {
  const [tab, setTab] = useState("discover");
  const pad = isDesktop ? "32px 32px 48px" : "20px 18px 100px";

  return (
    <div style={{ padding: pad }}>
      <ThemeHeader
        nav={nav}
        icon={Search}
        label="Dig"
        sub="Find new music"
        color={P.azure}
        isDesktop={isDesktop}
      />
      <div
        style={{
          display: "flex",
          gap: 0,
          marginBottom: 18,
          borderBottom: `1px solid ${P.border}`,
          overflowX: "auto",
        }}
      >
        {[
          { id: "discover", l: "Discover" },
          { id: "wishlist", l: "Wishlist (23)" },
          { id: "tracklist", l: "Tracklist" },
        ].map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              background: "none",
              border: "none",
              borderBottom: `2px solid ${tab === t.id ? P.azure : "transparent"}`,
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
      {tab === "discover" && <DiscoverContent isDesktop={isDesktop} />}
      {tab === "wishlist" && <WishlistContent isDesktop={isDesktop} />}
      {tab === "tracklist" && <TracklistContent isDesktop={isDesktop} />}
    </div>
  );
}

function DiscoverContent({ isDesktop }) {
  const [sessionActive, setSessionActive] = useState(false);
  const [sessionStep, setSessionStep] = useState(0);

  const startSession = () => {
    setSessionActive(true);
    setSessionStep(0);
    const steps = [1, 2, 3, 4, 5];
    steps.forEach((s, i) => {
      setTimeout(() => setSessionStep(s), (i + 1) * 900);
    });
  };

  return (
    <>
      {/* Profile-powered indicator (Gap 7) */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginBottom: 12,
          padding: "6px 10px",
          background: P.bgSurface,
          borderRadius: 8,
          width: "fit-content",
        }}
      >
        <User size={10} color={P.text3} />
        <span style={{ fontSize: 10, fontFamily: F.b, color: P.text3 }}>
          Showing artists in your styles
        </span>
        <span style={{ fontSize: 9, fontFamily: F.m, color: P.text3, opacity: 0.6 }}>
          (from your profile)
        </span>
        <button
          style={{
            background: "none",
            border: "none",
            color: P.azure,
            fontSize: 10,
            fontFamily: F.b,
            cursor: "pointer",
            padding: 0,
            textDecoration: "underline",
          }}
        >
          Change
        </button>
      </div>

      {/* Search bar + quick filter pills — row on desktop, stacked on mobile */}
      <div
        style={
          isDesktop
            ? { display: "flex", gap: 12, marginBottom: 18, alignItems: "center" }
            : {}
        }
      >
        <div
          style={{
            background: P.bgSurface,
            borderRadius: 12,
            padding: "12px 16px",
            marginBottom: isDesktop ? 0 : 16,
            border: `1px solid ${P.border}`,
            display: "flex",
            alignItems: "center",
            gap: 10,
            ...(isDesktop ? { flex: 1 } : {}),
          }}
        >
          <Search size={14} color={P.text3} />
          <span style={{ fontSize: 13, fontFamily: F.b, color: P.text3 }}>
            Artist, festival, club, or label...
          </span>
        </div>

        <div
          style={{
            display: "flex",
            gap: 6,
            marginBottom: isDesktop ? 0 : 18,
            overflowX: "auto",
            paddingBottom: isDesktop ? 0 : 4,
            flexShrink: 0,
          }}
        >
          {[
            { i: Users, l: "Artist" },
            { i: Globe, l: "Festival" },
            { i: MapPin, l: "Club" },
            { i: Tag, l: "Label" },
            { i: Play, l: "Boiler Room" },
          ].map((q, idx) => (
            <button
              key={idx}
              style={{
                background: P.bgCard,
                border: `1px solid ${P.border}`,
                borderRadius: 20,
                padding: "7px 14px",
                fontSize: 11,
                fontFamily: F.b,
                color: P.cream,
                cursor: "pointer",
                whiteSpace: "nowrap",
                display: "flex",
                alignItems: "center",
                gap: 5,
              }}
            >
              <q.i size={12} color={P.text2} />
              {q.l}
            </button>
          ))}
        </div>
      </div>

      {/* Artist card + Weekly dig — side by side on desktop */}
      <div
        style={
          isDesktop
            ? { display: "flex", gap: 16, alignItems: "flex-start" }
            : {}
        }
      >
        {/* Artist card */}
        <div
          style={{
            background: P.bgCard,
            borderRadius: 14,
            overflow: "hidden",
            border: `1px solid ${P.border}`,
            ...(isDesktop ? { flex: 3 } : {}),
          }}
        >
          <div
            style={{
              background: `linear-gradient(135deg,${P.azure}18,${P.mauve}12)`,
              padding: isDesktop ? "20px 22px" : "16px 18px",
              position: "relative",
            }}
          >
            <div
              style={{
                position: "absolute",
                top: -6,
                right: -6,
                width: 28,
                height: 28,
                border: `1px solid ${P.azure}15`,
                borderRadius: 4,
                transform: "rotate(15deg)",
              }}
            />
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div>
                <div
                  style={{
                    fontSize: isDesktop ? 26 : 22,
                    fontWeight: 800,
                    fontFamily: F.d,
                    color: P.cream,
                  }}
                >
                  Innellea
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    marginTop: 3,
                  }}
                >
                  <span
                    style={{ fontSize: 11, fontFamily: F.b, color: P.text2 }}
                  >
                    Melodic techno -- Munich
                  </span>
                  <SourceDot src="ra" />
                </div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div
                  style={{
                    fontSize: 16,
                    fontWeight: 800,
                    fontFamily: F.d,
                    color: P.azure,
                  }}
                >
                  42.1K
                </div>
                <div
                  style={{ fontSize: 8, fontFamily: F.m, color: P.text3 }}
                >
                  RA
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 5, marginTop: 10 }}>
              <Badge color={P.green}>2 owned</Badge>
              <Badge color={P.warn}>1 wishlist</Badge>
            </div>
          </div>
          <div style={{ padding: isDesktop ? "18px 22px" : "14px 18px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                marginBottom: 6,
              }}
            >
              <MapPin size={10} color={P.text3} />
              <span
                style={{
                  fontSize: 10,
                  fontFamily: F.m,
                  color: P.text3,
                  letterSpacing: 1,
                }}
              >
                PLAYS AT
              </span>
            </div>
            <div style={{ fontSize: 12, fontFamily: F.b, color: P.cream }}>
              Pacha Ibiza -- Printworks -- Watergate{" "}
              <SourceDot src="ra" />
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                marginTop: 12,
                marginBottom: 6,
              }}
            >
              <Disc3 size={10} color={P.text3} />
              <span
                style={{
                  fontSize: 10,
                  fontFamily: F.m,
                  color: P.text3,
                  letterSpacing: 1,
                }}
              >
                RELEASES
              </span>
            </div>
            {[
              { y: "2025", t: "The Belonging", s: "mb" },
              { y: "2024", t: "Vigilance", s: "mb" },
              { y: "2023", t: "Transhumanism", s: "web" },
            ].map((r, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  marginBottom: 4,
                }}
              >
                <span
                  style={{
                    fontSize: 10,
                    fontFamily: F.m,
                    color: P.text3,
                    width: 32,
                  }}
                >
                  {r.y}
                </span>
                <span
                  style={{
                    fontSize: 12,
                    fontFamily: F.b,
                    color: P.cream,
                    flex: 1,
                  }}
                >
                  {r.t}
                </span>
                <SourceDot src={r.s} />
              </div>
            ))}
            <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
              <button
                style={{
                  flex: 1,
                  background: P.azure + "18",
                  border: `1px solid ${P.azure}30`,
                  borderRadius: 8,
                  padding: "10px",
                  color: P.azure,
                  fontSize: 11,
                  fontFamily: F.d,
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 4,
                }}
              >
                <Heart size={12} />
                Follow
              </button>
              <button
                style={{
                  flex: 1,
                  background: P.lime + "18",
                  border: `1px solid ${P.lime}30`,
                  borderRadius: 8,
                  padding: "10px",
                  color: P.lime,
                  fontSize: 11,
                  fontFamily: F.d,
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 4,
                }}
              >
                <Star size={12} />
                Wishlist
              </button>
            </div>
          </div>
        </div>

        {/* Weekly dig card + Session stepper */}
        <div
          style={{
            background: P.bgCard,
            borderRadius: 14,
            padding: isDesktop ? "20px" : "16px",
            marginTop: isDesktop ? 0 : 12,
            border: `1px solid ${sessionActive ? P.azure + "40" : P.border}`,
            ...(isDesktop ? { flex: 2 } : {}),
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              marginBottom: 4,
            }}
          >
            <Calendar size={10} color={P.azure} />
            <span
              style={{
                fontSize: 10,
                fontFamily: F.m,
                color: P.azure,
                letterSpacing: 1,
              }}
            >
              WEEKLY DIG
            </span>
          </div>

          {!sessionActive ? (
            <>
              <div
                style={{
                  fontSize: 14,
                  fontWeight: 600,
                  fontFamily: F.d,
                  color: P.cream,
                  marginTop: 4,
                }}
              >
                8 new finds from followed artists
              </div>
              <button
                onClick={startSession}
                style={{
                  width: "100%",
                  background: P.azure + "15",
                  border: `1px solid ${P.azure}30`,
                  borderRadius: 10,
                  padding: "10px",
                  marginTop: 12,
                  color: P.azure,
                  fontSize: 12,
                  fontFamily: F.d,
                  fontWeight: 600,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 6,
                }}
              >
                <Search size={14} />
                Start dig session
              </button>
            </>
          ) : (
            <div style={{ marginTop: 8 }}>
              {[
                { label: "Scanning followed artists...", result: "14 found" },
                { label: "Checking new releases...", result: "8 found" },
                { label: "Sleeping on analysis...", result: "5 found" },
                { label: "Deduplicating...", result: "20 unique (7 removed)" },
                { label: "Library cross-reference...", result: "11 new to you" },
              ].map((step, i) => {
                const done = sessionStep > i;
                const active = sessionStep === i;
                return (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 6,
                      opacity: done || active ? 1 : 0.3,
                    }}
                  >
                    <div style={{ width: 20, display: "flex", justifyContent: "center" }}>
                      {done ? (
                        <CircleCheck size={14} color={P.azure} />
                      ) : active ? (
                        <Loader size={14} color={P.azure} style={{ animation: "spin 1s linear infinite" }} />
                      ) : (
                        <div
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            border: `1px solid ${P.text3}`,
                          }}
                        />
                      )}
                    </div>
                    <span style={{ fontSize: 11, fontFamily: F.b, color: done ? P.cream : P.text3, flex: 1 }}>
                      Step {i + 1}: {step.label}
                    </span>
                    {done && (
                      <span style={{ fontSize: 10, fontFamily: F.m, color: P.azure }}>
                        {step.result}
                      </span>
                    )}
                  </div>
                );
              })}
              <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>

              {sessionStep >= 5 && (
                <div style={{ marginTop: 12 }}>
                  <div
                    style={{
                      fontSize: 16,
                      fontWeight: 800,
                      fontFamily: F.d,
                      color: P.azure,
                      marginBottom: 8,
                    }}
                  >
                    Results: 11 new discoveries
                  </div>
                  <button
                    style={{
                      width: "100%",
                      background: P.azure,
                      border: "none",
                      borderRadius: 10,
                      padding: "10px",
                      color: P.cream,
                      fontSize: 12,
                      fontFamily: F.d,
                      fontWeight: 700,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 6,
                    }}
                  >
                    <Star size={14} />
                    Preview & Save to Wishlist
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function WishlistContent({ isDesktop }) {
  const [downloaded, setDownloaded] = useState({});
  const [toast, setToast] = useState(null);

  const items = [
    { a: "Innellea", t: "Vigilance (Extended)", p: "high", s: "dig-artist" },
    { a: "Adriatique", t: "Nude", p: "medium", s: "tracklist" },
    { a: "Recondite", t: "Phalanx", p: "medium", s: "tracklist" },
    { a: "Ame", t: "Rej (DJ Koze Remix)", p: "low", s: "dig-weekly" },
  ];

  const markDownloaded = (idx) => {
    setDownloaded((prev) => ({ ...prev, [idx]: true }));
    setToast("Track moved to Intake queue \u2014 switch to Prep to process");
    setTimeout(() => setToast(null), 3500);
  };

  return (
    <>
      {toast && (
        <div
          style={{
            background: P.green + "18",
            border: `1px solid ${P.green}30`,
            borderRadius: 10,
            padding: "10px 14px",
            marginBottom: 12,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <CircleCheck size={14} color={P.green} />
          <span style={{ fontSize: 12, fontFamily: F.b, color: P.cream }}>{toast}</span>
        </div>
      )}
      <div
        style={
          isDesktop
            ? { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }
            : {}
        }
      >
        {items.map((t, i) => {
          const isDl = downloaded[i];
          return (
            <div
              key={i}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: isDesktop ? "14px 18px" : "12px 14px",
                background: P.bgCard,
                borderRadius: 10,
                border: `1px solid ${isDl ? P.green + "25" : P.border}`,
                marginBottom: isDesktop ? 0 : 6,
              }}
            >
              <div style={{ flex: 1 }}>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    fontFamily: F.b,
                    color: P.cream,
                  }}
                >
                  {t.a} -- {t.t}
                </div>
                <div style={{ display: "flex", gap: 5, marginTop: 4 }}>
                  {isDl ? (
                    <Badge color={P.green}>downloaded</Badge>
                  ) : (
                    <Badge
                      color={
                        t.p === "high"
                          ? P.terra
                          : t.p === "medium"
                            ? P.warn
                            : P.text3
                      }
                    >
                      {t.p}
                    </Badge>
                  )}
                  <Badge color={P.text3}>{t.s}</Badge>
                </div>
              </div>
              <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                {!isDl && (
                  <button
                    onClick={() => markDownloaded(i)}
                    style={{
                      background: P.green + "15",
                      border: `1px solid ${P.green}25`,
                      borderRadius: 6,
                      padding: "5px 8px",
                      color: P.green,
                      fontSize: 10,
                      fontFamily: F.m,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      gap: 3,
                    }}
                  >
                    <CircleCheck size={10} />
                    Got it
                  </button>
                )}
                <button
                  style={{
                    background: P.azure + "18",
                    border: `1px solid ${P.azure}30`,
                    borderRadius: 6,
                    padding: "5px 10px",
                    color: P.azure,
                    fontSize: 10,
                    fontFamily: F.m,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 3,
                  }}
                >
                  <Download size={10} />
                  Find
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

function TracklistContent({ isDesktop }) {
  const tracks = [
    { t: "Innellea - Vigilance", o: true, s: "acoustid" },
    { t: "Stephan Bodzin - Zulu", o: true, s: "mb" },
    { t: "Adriatique - Nude", o: false, s: "1001" },
    { t: "Mind Against - Atlant", o: true, s: "spotify" },
    { t: "Recondite - Phalanx", o: false, s: "1001" },
    { t: "ID - ID", o: false, s: null },
    { t: "Solomun - After Rain", o: true, s: "acoustid" },
  ];
  const owned = tracks.filter((t) => t.o).length;
  return (
    <>
      <div
        style={{
          background: P.bgSurface,
          borderRadius: 12,
          padding: isDesktop ? "14px 18px" : "12px 14px",
          marginBottom: 14,
          border: `1px solid ${P.azure}25`,
          ...(isDesktop ? { maxWidth: 600 } : {}),
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
            marginBottom: 6,
          }}
        >
          <ListMusic size={10} color={P.text3} />
          <span
            style={{ fontSize: 10, fontFamily: F.m, color: P.text3 }}
          >
            PASTE A SET URL OR SEARCH
          </span>
        </div>
        <div style={{ fontSize: 12, fontFamily: F.m, color: P.azure }}>
          Solomun Boiler Room Tulum 2025
        </div>
      </div>
      <div style={{ display: "flex", gap: 12, marginBottom: 14 }}>
        <div>
          <span
            style={{
              fontSize: 22,
              fontWeight: 800,
              fontFamily: F.d,
              color: P.green,
            }}
          >
            {owned}
          </span>
          <span
            style={{ fontSize: 11, fontFamily: F.b, color: P.text2 }}
          >
            {" "}
            owned
          </span>
        </div>
        <div>
          <span
            style={{
              fontSize: 22,
              fontWeight: 800,
              fontFamily: F.d,
              color: P.terra,
            }}
          >
            {tracks.length - owned}
          </span>
          <span
            style={{ fontSize: 11, fontFamily: F.b, color: P.text2 }}
          >
            {" "}
            missing
          </span>
        </div>
      </div>
      {/* Desktop: show as wider table-like rows */}
      {tracks.map((t, i) => (
        <div
          key={i}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: isDesktop ? "10px 16px" : "9px 12px",
            background: P.bgCard,
            borderRadius: 8,
            border: `1px solid ${t.o ? P.green + "18" : P.border}`,
            marginBottom: 3,
          }}
        >
          {t.o ? (
            <CircleCheck size={14} color={P.green} />
          ) : t.s ? (
            <CircleX size={14} color={P.terra} />
          ) : (
            <AlertTriangle size={12} color={P.warn} />
          )}
          <span
            style={{
              flex: 1,
              fontSize: isDesktop ? 13 : 12,
              fontFamily: F.b,
              color: t.o ? P.cream : P.text2,
            }}
          >
            {t.t}
          </span>
          {t.s && <SourceDot src={t.s} />}
          {!t.o && t.s && (
            <button
              style={{
                background: P.azure + "15",
                border: `1px solid ${P.azure}25`,
                borderRadius: 5,
                padding: "3px 8px",
                color: P.azure,
                fontSize: 9,
                fontFamily: F.m,
                cursor: "pointer",
              }}
            >
              +wish
            </button>
          )}
        </div>
      ))}
      <button
        style={{
          width: isDesktop ? "auto" : "100%",
          background: P.azure,
          border: "none",
          borderRadius: 10,
          padding: isDesktop ? "12px 32px" : "12px",
          marginTop: 12,
          color: P.cream,
          fontSize: 12,
          fontFamily: F.d,
          fontWeight: 700,
          cursor: "pointer",
        }}
      >
        Add {tracks.length - owned - 1} missing to wishlist
      </button>
    </>
  );
}
