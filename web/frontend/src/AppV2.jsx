import { useState, useEffect } from "react";
import {
  Home, Search, Wrench, Headphones, SlidersHorizontal,
} from "lucide-react";
import { P, F } from "./v2/theme";
import HomePage from "./v2/HomePage";
import DigScreen from "./v2/DigScreen";
import PrepScreen from "./v2/PrepScreen";
import PracticeScreen from "./v2/PracticeScreen";
import GigScreen from "./v2/GigScreen";

const NAV_ITEMS = [
  { id: "home", Icon: Home, label: "Home" },
  { id: "dig", Icon: Search, label: "Dig", color: P.azure },
  { id: "prep", Icon: Wrench, label: "Prep", color: P.lime },
  { id: "practice", Icon: Headphones, label: "Practice", color: P.purple },
  { id: "gig", Icon: SlidersHorizontal, label: "Gig", color: P.terra },
];

function useResponsive() {
  const [isDesktop, setIsDesktop] = useState(
    typeof window !== "undefined" && window.innerWidth > 768
  );
  useEffect(() => {
    const handler = () => setIsDesktop(window.innerWidth > 768);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);
  return isDesktop;
}

export default function AppV2() {
  const [screen, setScreen] = useState("home");
  const nav = (s) => setScreen(s);
  const isDesktop = useResponsive();

  return (
    <div
      style={{
        width: "100%",
        ...(isDesktop
          ? { display: "flex", minHeight: "100vh" }
          : { maxWidth: 420, margin: "0 auto", minHeight: "100vh" }),
        background: P.bg,
        fontFamily: F.b,
        color: P.cream,
      }}
    >
      {/* Global styles for V2 */}
      <style>{`
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 3px; }
        ::-webkit-scrollbar-thumb { background: ${P.border}; border-radius: 3px; }
        button:active { transform: scale(0.98); }
      `}</style>

      {/* Desktop sidebar */}
      {isDesktop && (
        <div
          style={{
            width: 220,
            minWidth: 220,
            height: "100vh",
            position: "fixed",
            top: 0,
            left: 0,
            background: P.bgEl,
            borderRight: `1px solid ${P.border}`,
            display: "flex",
            flexDirection: "column",
            padding: "24px 0",
            zIndex: 100,
          }}
        >
          {/* Branding */}
          <div style={{ padding: "0 20px", marginBottom: 32 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                marginBottom: 6,
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
            </div>
            <span
              style={{
                fontSize: 11,
                fontFamily: F.m,
                color: P.text3,
                letterSpacing: 2,
              }}
            >
              CRATEDIGGER
            </span>
          </div>

          {/* Nav items */}
          <div style={{ flex: 1 }}>
            {NAV_ITEMS.map((n) => {
              const I = n.Icon;
              const active = screen === n.id;
              const activeColor = n.color || P.cream;
              return (
                <button
                  key={n.id}
                  onClick={() => nav(n.id)}
                  style={{
                    width: "100%",
                    background: active ? activeColor + "10" : "none",
                    border: "none",
                    borderLeft: `3px solid ${active ? activeColor : "transparent"}`,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "12px 20px",
                    marginBottom: 2,
                    transition: "background 0.15s",
                  }}
                >
                  <I
                    size={18}
                    color={active ? activeColor : P.text3}
                  />
                  <span
                    style={{
                      fontSize: 14,
                      fontFamily: F.b,
                      color: active ? P.cream : P.text3,
                      fontWeight: active ? 600 : 400,
                    }}
                  >
                    {n.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Screen content */}
      <div
        style={
          isDesktop
            ? {
                marginLeft: 220,
                flex: 1,
                overflowY: "auto",
                height: "100vh",
                display: "flex",
                justifyContent: "center",
              }
            : { overflowY: "auto", height: "100vh" }
        }
      >
        <div
          style={
            isDesktop
              ? { width: "100%", maxWidth: 1200, padding: "0" }
              : { width: "100%" }
          }
        >
          {screen === "home" && <HomePage nav={nav} isDesktop={isDesktop} />}
          {screen === "dig" && <DigScreen nav={nav} isDesktop={isDesktop} />}
          {screen === "prep" && <PrepScreen nav={nav} isDesktop={isDesktop} />}
          {screen === "practice" && <PracticeScreen nav={nav} isDesktop={isDesktop} />}
          {screen === "gig" && <GigScreen nav={nav} isDesktop={isDesktop} />}
        </div>
      </div>

      {/* Bottom navigation — frosted glass (mobile only) */}
      {!isDesktop && (
        <div
          style={{
            position: "fixed",
            bottom: 0,
            left: "50%",
            transform: "translateX(-50%)",
            width: "100%",
            maxWidth: 420,
            background: `${P.bg}F2`,
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            borderTop: `1px solid ${P.border}`,
            display: "flex",
            justifyContent: "space-around",
            padding: "6px 0 12px",
            zIndex: 100,
          }}
        >
          {NAV_ITEMS.map((n) => {
            const I = n.Icon;
            const active = screen === n.id;
            return (
              <button
                key={n.id}
                onClick={() => nav(n.id)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 2,
                  padding: "4px 8px",
                  opacity: active ? 1 : 0.4,
                }}
              >
                <I
                  size={18}
                  color={active ? n.color || P.cream : P.text3}
                />
                <span
                  style={{
                    fontSize: 8,
                    fontFamily: F.m,
                    color: active ? P.cream : P.text3,
                    letterSpacing: 0.5,
                    fontWeight: active ? 600 : 400,
                  }}
                >
                  {n.label}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
