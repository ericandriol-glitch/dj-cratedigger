import { usePlayer } from "../hooks/usePlayer";
import { P, F } from "../theme";
import { Waveform } from "./ui";
import { Play, Pause, Volume2, VolumeX } from "lucide-react";

function fmt(s) {
  if (!s || !isFinite(s)) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export default function PlayerBar() {
  const { track, playing, currentTime, duration, volume, togglePlay, seek, setVol } = usePlayer();

  if (!track) return null;

  const pct = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="player-bar" style={{
      position: "fixed", bottom: 0, left: 0, right: 0, zIndex: 200,
      background: `linear-gradient(180deg, ${P.bgElevated}F0 0%, ${P.bgElevated} 40%)`,
      backdropFilter: "blur(24px)", WebkitBackdropFilter: "blur(24px)",
      borderTop: `1px solid ${P.border}`,
    }}>
      {/* Progress bar — clickable */}
      <div
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const ratio = (e.clientX - rect.left) / rect.width;
          seek(ratio * duration);
        }}
        style={{
          height: 3, background: P.bgSurface, cursor: "pointer",
          position: "relative", marginTop: -1,
        }}
      >
        <div style={{
          height: "100%", width: `${pct}%`,
          background: `linear-gradient(90deg, ${P.terracotta}80, ${P.terracotta})`,
          borderRadius: "0 2px 2px 0",
          transition: "width 0.3s linear",
        }} />
        {/* Scrub handle */}
        <div style={{
          position: "absolute", top: -4, left: `${pct}%`, transform: "translateX(-50%)",
          width: 10, height: 10, borderRadius: "50%",
          background: P.terracotta, border: `2px solid ${P.cream}`,
          opacity: 0, transition: "opacity 0.15s",
        }} className="scrub-handle" />
      </div>

      <div style={{
        display: "flex", alignItems: "center", gap: 14,
        padding: "10px 20px 14px",
      }}>
        {/* Play/Pause */}
        <button onClick={togglePlay} style={{
          width: 40, height: 40, borderRadius: 10,
          background: P.terracotta, border: "none", cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: `0 4px 16px ${P.terracotta}30`,
          flexShrink: 0, transition: "transform 0.1s",
        }}
          onMouseDown={(e) => e.currentTarget.style.transform = "scale(0.93)"}
          onMouseUp={(e) => e.currentTarget.style.transform = "scale(1)"}
        >
          {playing
            ? <Pause size={18} color="#fff" fill="#fff" strokeWidth={0} />
            : <Play size={18} color="#fff" fill="#fff" strokeWidth={0} style={{ marginLeft: 2 }} />
          }
        </button>

        {/* Track info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 13, fontFamily: F.b, fontWeight: 600, color: P.cream,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>{track.title}</div>
          <div style={{
            fontSize: 11, fontFamily: F.b, color: P.textSec,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>{track.artist}</div>
        </div>

        {/* BPM + Key badges */}
        <div className="player-badges" style={{ display: "flex", gap: 6, flexShrink: 0 }}>
          {track.bpm && <span className="badge-bpm">{track.bpm}</span>}
          {track.key && <span className="badge-key">{track.key}</span>}
        </div>

        {/* Waveform viz */}
        <div className="player-waveform" style={{ flexShrink: 0 }}>
          {playing ? <Waveform count={8} style={{ opacity: 0.5 }} /> : null}
        </div>

        {/* Time */}
        <div style={{ flexShrink: 0, textAlign: "right", minWidth: 70 }}>
          <span style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>
            {fmt(currentTime)}
          </span>
          <span style={{ fontSize: 11, fontFamily: F.m, color: P.textMut }}> / {fmt(duration)}</span>
        </div>

        {/* Volume */}
        <div className="player-volume" style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
          <button onClick={() => setVol(volume > 0 ? 0 : 0.8)} style={{
            background: "none", border: "none", cursor: "pointer", padding: 0,
            display: "flex", alignItems: "center",
          }}>
            {volume > 0
              ? <Volume2 size={14} color={P.textMut} />
              : <VolumeX size={14} color={P.critical} />
            }
          </button>
          <input
            type="range" min={0} max={1} step={0.01} value={volume}
            onChange={(e) => setVol(parseFloat(e.target.value))}
            className="vol-slider"
            style={{ width: 60, accentColor: P.terracotta }}
          />
        </div>
      </div>
    </div>
  );
}
