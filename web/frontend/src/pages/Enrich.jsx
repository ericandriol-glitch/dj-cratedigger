import { useState } from "react";
import { P, F } from "../theme";
import { useApi, fetchApi } from "../hooks/useApi";
import { Sec, Ring, CBar, Loader } from "../components/ui";
import {
  Sparkles, AudioLines, Hash, Tag,
  Music, Wand2, Play, CheckCircle, AlertTriangle, Loader2,
} from "lucide-react";

function ActionCard({ title, desc, count, color, icon: Icon, onRun, running, result }) {
  return (
    <div style={{
      background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 12,
      padding: "16px", marginBottom: 10,
    }}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: `${color}10`, border: `1px solid ${color}18`,
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
        }}>
          <Icon size={18} color={color} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 15, fontFamily: F.b, fontWeight: 600, color: P.text, marginBottom: 3 }}>
            {title}
          </div>
          <div style={{ fontSize: 12, fontFamily: F.b, color: P.textSec, marginBottom: 10, lineHeight: 1.5 }}>
            {desc}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{
              fontSize: 11, fontFamily: F.m, padding: "3px 10px", borderRadius: 5,
              background: `${color}10`, color, fontWeight: 600,
            }}>
              {count} tracks
            </span>
            <button
              onClick={onRun}
              disabled={running || count === 0}
              style={{
                padding: "7px 16px", borderRadius: 8, border: "none",
                background: (running || count === 0) ? P.bgSurface : color,
                color: (running || count === 0) ? P.textMut : "#fff",
                fontFamily: F.d, fontSize: 12, fontWeight: 700,
                cursor: (running || count === 0) ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", gap: 5,
                transition: "all 0.2s ease",
                opacity: count === 0 ? 0.4 : 1,
              }}
            >
              {running ? <><Loader2 size={12} className="spin" /> Running...</>
                : count === 0 ? <><CheckCircle size={12} /> All done</>
                : <><Play size={12} fill="currentColor" /> Run</>
              }
            </button>
          </div>
        </div>
      </div>

      {/* Result feedback */}
      {result && (
        <div style={{
          marginTop: 10, padding: "8px 12px", borderRadius: 8,
          background: result.error ? `${P.critical}10` : result.info ? `${P.azure}10` : `${P.healthy}10`,
          border: `1px solid ${result.error ? P.critical : result.info ? P.azure : P.healthy}20`,
          fontSize: 12, fontFamily: F.m,
          color: result.error ? P.critical : result.info ? P.azure : P.healthy,
        }}>
          {result.error || result.info || `Enriched ${result.enriched} tracks. ${result.total_missing} still remaining.`}
        </div>
      )}
    </div>
  );
}

export default function Enrich({ onNavigate }) {
  const { data: stats, loading, error: statsError } = useApi("/api/library/stats");
  const [genreRunning, setGenreRunning] = useState(false);
  const [genreResult, setGenreResult] = useState(null);
  const [bpmResult, setBpmResult] = useState(null);
  const [writeRunning, setWriteRunning] = useState(false);
  const [writeResult, setWriteResult] = useState(null);

  const s = stats || {};
  const comp = s.completeness || {};
  const issues = s.issues || {};
  const total = s.total_tracks || 0;

  const runGenreEnrich = async () => {
    setGenreRunning(true);
    setGenreResult(null);
    try {
      const resp = await fetch(
        `${import.meta.env.VITE_API_URL || "http://127.0.0.1:8899"}/api/enrich/genres?limit=50`,
        { method: "POST" },
      );
      if (!resp.ok) throw new Error(`${resp.status}`);
      const data = await resp.json();
      setGenreResult(data);
    } catch (e) {
      setGenreResult({ error: "Enrichment failed — check the API is running" });
    }
    setGenreRunning(false);
  };

  const showBpmMessage = () => {
    setBpmResult({ info: "BPM & Key detection requires Essentia (WSL/Linux). Run from terminal: cratedigger scan-essentia" });
  };

  const runWriteTags = async () => {
    setWriteRunning(true);
    setWriteResult(null);
    try {
      const resp = await fetch(
        `${import.meta.env.VITE_API_URL || "http://127.0.0.1:8899"}/api/enrich/genres?limit=100`,
        { method: "POST" },
      );
      if (!resp.ok) throw new Error(`${resp.status}`);
      const data = await resp.json();
      setWriteResult({ enriched: data.enriched || 0, total_missing: data.total_missing || 0 });
    } catch (e) {
      setWriteResult({ error: "Tag writing failed — check the API is running" });
    }
    setWriteRunning(false);
  };

  return (
    <div style={{ padding: "20px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: `${P.mauve}12`, border: `1px solid ${P.mauve}20`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Sparkles size={20} color={P.mauve} />
        </div>
        <div>
          <div style={{ fontSize: 22, fontWeight: 700, fontFamily: F.d, color: P.cream }}>Enrich</div>
          <div style={{ fontSize: 11, fontFamily: F.m, color: P.textMut }}>Fill gaps in your library metadata</div>
        </div>
      </div>

      {statsError && (
        <div style={{
          textAlign: "center", padding: "30px 20px",
          background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14,
          marginBottom: 20,
        }}>
          <div style={{ fontSize: 14, fontFamily: F.b, color: P.warning, marginBottom: 8 }}>
            Could not connect to the API
          </div>
          <div style={{ fontSize: 12, fontFamily: F.m, color: P.textMut }}>
            Make sure the backend is running on the configured port
          </div>
        </div>
      )}
      {loading ? <Loader text="Loading library stats..." /> : (
        <>
          {/* Compact summary — one line, not duplicated dashboard */}
          <div style={{
            display: "flex", alignItems: "center", gap: 14,
            background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 12,
            padding: "14px 16px", marginBottom: 20,
          }}>
            <Ring pct={s.health_score || 0} size={56} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontFamily: F.b, fontWeight: 600, color: P.text }}>
                {total} tracks · {s.good || 0} complete · {(issues.missing_bpm || 0) + (issues.missing_key || 0) + (issues.missing_genre || 0)} gaps
              </div>
              <div style={{ display: "flex", gap: 12, marginTop: 6 }}>
                <span style={{ fontSize: 10, fontFamily: F.m, color: P.warning }}>{issues.missing_bpm || 0} no BPM</span>
                <span style={{ fontSize: 10, fontFamily: F.m, color: P.terracotta }}>{issues.missing_key || 0} no key</span>
                <span style={{ fontSize: 10, fontFamily: F.m, color: P.azure }}>{issues.missing_genre || 0} no genre</span>
              </div>
            </div>
          </div>

          {/* Actions — real buttons */}
          <Sec label="Enrichment Actions" icon={Wand2} color={P.mauve} />

          <ActionCard
            title="Enrich Genres"
            desc="Look up genres via MusicBrainz for tracks with artist + title but no genre tag. Processes 50 tracks per run."
            count={issues.missing_genre || 0}
            color={P.mauve}
            icon={Tag}
            onRun={runGenreEnrich}
            running={genreRunning}
            result={genreResult}
          />

          <ActionCard
            title="Detect BPM & Key"
            desc="Requires Essentia (WSL/Linux). Run from terminal for now."
            count={issues.missing_bpm || 0}
            color={P.lime}
            icon={AudioLines}
            onRun={showBpmMessage}
            running={false}
            result={bpmResult}
          />

          <ActionCard
            title="Write Tags to Files"
            desc="Apply detected BPM and key values back to file tags (creates backups)."
            count={issues.missing_bpm || 0}
            color={P.azure}
            icon={Wand2}
            onRun={runWriteTags}
            running={writeRunning}
            result={writeResult}
          />

          {total === 0 && (
            <div style={{ textAlign: "center", padding: "30px 0", marginTop: 10 }}>
              <div style={{ color: P.textSec, fontFamily: F.b, fontSize: 13, marginBottom: 12 }}>
                No library data yet. Scan first to find tracks that need enrichment.
              </div>
              <button onClick={() => onNavigate?.("home")} style={{
                padding: "8px 16px", borderRadius: 8, border: "none",
                background: P.terracotta, color: "#fff",
                fontFamily: F.d, fontSize: 12, fontWeight: 700, cursor: "pointer",
              }}>
                Go to Home
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
