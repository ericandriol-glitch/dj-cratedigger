import { useState } from "react";
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

export default function AppV2() {
  const [screen, setScreen] = useState("home");
  const nav = (s) => setScreen(s);

  return (
    <div
      style={{
        width: "100%",
        maxWidth: 420,
        margin: "0 auto",
        minHeight: "100vh",
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

      {/* Screen content */}
      <div style={{ overflowY: "auto", height: "100vh" }}>
        {screen === "home" && <HomePage nav={nav} />}
        {screen === "dig" && <DigScreen nav={nav} />}
        {screen === "prep" && <PrepScreen nav={nav} />}
        {screen === "practice" && <PracticeScreen nav={nav} />}
        {screen === "gig" && <GigScreen nav={nav} />}
      </div>

      {/* Bottom navigation — frosted glass */}
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
    </div>
  );
}
