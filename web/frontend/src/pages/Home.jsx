import { useState, useCallback } from "react";
import { P, F, genreColor } from "../theme";
import { useApi, fetchApi } from "../hooks/useApi";
import {
  Ring, CBar, IssueRow, Track, Genre, Sec, Pill, Loader, Waveform, Card,
} from "../components/ui";
import {
  Radio, SlidersHorizontal, Target, Disc3,
  AudioLines, Hash, Tag, Image, Fingerprint, Calendar, Music,
  HardDrive, Search, RotateCw, ArrowUpRight, Loader2, FolderOpen,
} from "lucide-react";

export default function Home({ onNavigate }) {
  const [filter, setFilter] = useState("all");
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [scanPath, setScanPath] = useState("");
  const [showScanModal, setShowScanModal] = useState(false);

  const { data: stats, loading: statsLoading, error: statsError } = useApi("/api/library/stats");
  const { data: genreData, loading: genresLoading } = useApi("/api/library/genres");
  const { data: trackData, loading: tracksLoading } = useApi(
    `/api/library/tracks?filter=${filter}&limit=20`
  );

  const s = stats || {};
  const comp = s.completeness || {};
  const issues = s.issues || {};
  const genres = genreData?.genres || [];
  const tracks = trackData?.tracks || [];
  const trackTotal = trackData?.total || 0;

  const runScan = async () => {
    if (!scanPath.trim()) return;
    setScanning(true);
    setScanResult(null);
    try {
      const resp = await fetch(
        `${import.meta.env.VITE_API_URL || "http://127.0.0.1:8899"}/api/scan?path=${encodeURIComponent(scanPath.trim())}`,
        { method: "POST" },
      );
      if (!resp.ok) throw new Error(`${resp.status}`);
      const data = await resp.json();
      if (data.error) {
        setScanResult({ error: data.error });
      } else {
        setScanResult({ success: `Scanned ${data.scanned} tracks from ${data.total_files} files` });
        // Refresh the page data after a short delay
        setTimeout(() => window.location.reload(), 1500);
      }
    } catch (e) {
      setScanResult({ error: "Scan failed — check the API is running" });
    }
    setScanning(false);
  };

  return (
    <>
      {/* ═══ HEADER ═══ */}
      <div style={{ padding: "20px 20px 0" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
          {/* Logo — mobile only */}
          <div className="mobile-only" style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 28, height: 28, position: "relative", flexShrink: 0 }}>
              <div style={{ position: "absolute", width: 15, height: 15, background: P.terracotta, top: 0, left: 0, borderRadius: 3 }} />
              <div style={{ position: "absolute", width: 15, height: 15, background: P.lime, bottom: 0, right: 0, borderRadius: 3, opacity: 0.85 }} />
              <div style={{ position: "absolute", width: 9, height: 9, background: P.azure, top: 10, left: 10, borderRadius: 2 }} />
            </div>
            <div style={{ lineHeight: 1 }}>
              <span style={{ fontSize: 15, fontWeight: 800, fontFamily: F.d, color: P.cream, letterSpacing: 1 }}>CRATE</span>
              <span style={{ fontSize: 15, fontWeight: 800, fontFamily: F.d, color: P.terracotta, letterSpacing: 1 }}>DIGGER</span>
            </div>
          </div>
          <div className="desktop-sidebar" style={{ flex: 1 }} />
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button onClick={() => onNavigate?.("library")} style={{
              width: 36, height: 36, borderRadius: 9,
              background: P.bgCard, border: `1px solid ${P.border}`,
              display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer",
              transition: "all 0.15s ease",
            }}>
              <Search size={15} color={P.textSec} strokeWidth={2} />
            </button>
            <button onClick={() => setShowScanModal(true)} style={{
              padding: "8px 16px", background: P.terracotta, border: "none", borderRadius: 9,
              color: "#fff", fontFamily: F.d, fontSize: 12, fontWeight: 700, letterSpacing: 0.3,
              boxShadow: `0 4px 20px ${P.terracotta}25`,
              cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
              transition: "all 0.15s ease",
            }}>
              <RotateCw size={13} strokeWidth={2.5} />
              Scan
            </button>
          </div>
        </div>

        {/* Source card */}
        <Card style={{ padding: "12px 14px", marginBottom: 4 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 36, height: 36, borderRadius: 9,
              background: `${s.total_tracks > 0 ? P.healthy : P.warning}08`,
              border: `1px solid ${s.total_tracks > 0 ? P.healthy : P.warning}15`,
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <HardDrive size={16} color={s.total_tracks > 0 ? P.healthy : P.warning} strokeWidth={2} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ fontSize: 13, fontFamily: F.b, fontWeight: 600, color: P.text }}>
                  {s.total_tracks > 0 ? "Library Connected" : "No Library Data"}
                </span>
                {s.total_tracks > 0 && (
                  <div style={{
                    width: 6, height: 6, borderRadius: "50%", background: P.healthy,
                    boxShadow: `0 0 8px ${P.healthy}50`, animation: "pulseGlow 2.5s infinite",
                  }} />
                )}
              </div>
              <span style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>
                {s.total_tracks > 0
                  ? `${s.total_tracks.toLocaleString()} tracks`
                  : "Run a scan to populate"}
              </span>
            </div>
            <Waveform count={10} style={{ opacity: 0.35 }} />
          </div>
        </Card>
      </div>

      {/* ═══ CONTENT ═══ */}
      <div style={{ padding: "0 20px" }}>

        {statsError && (
          <div style={{
            textAlign: "center", padding: "40px 20px",
            background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14,
            marginTop: 20,
          }}>
            <div style={{ fontSize: 14, fontFamily: F.b, color: P.warning, marginBottom: 8 }}>
              Could not connect to the API
            </div>
            <div style={{ fontSize: 12, fontFamily: F.m, color: P.textMut }}>
              Make sure the backend is running on the configured port
            </div>
          </div>
        )}
        {statsLoading ? <Loader text="Loading library stats..." /> : (
          <>
            {/* Library Health — hero treatment */}
            <Sec label="Library Health" icon={Radio} color={P.healthy} />
            <div className="section-enter" style={{ display: "flex", gap: 14, marginBottom: 6 }}>
              <Card hero style={{
                padding: "20px 18px", display: "flex", flexDirection: "column", alignItems: "center",
              }}>
                <Ring pct={s.health_score || 0} />
                <div style={{ display: "flex", gap: 16, marginTop: 16 }}>
                  {[
                    { n: s.good || 0, c: P.healthy, l: "Good" },
                    { n: s.partial || 0, c: P.warning, l: "Partial" },
                    { n: s.missing || 0, c: P.critical, l: "Poor" },
                  ].map((x, i) => (
                    <div key={i} style={{ textAlign: "center" }}>
                      <div style={{ fontSize: 15, fontWeight: 700, fontFamily: F.d, color: x.c, lineHeight: 1 }}>{x.n}</div>
                      <div style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 1, marginTop: 4 }}>{x.l}</div>
                    </div>
                  ))}
                </div>
              </Card>
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 7 }}>
                <IssueRow icon={AudioLines} label="Missing BPM" value={issues.missing_bpm || 0} color={P.warning}
                  onClick={() => onNavigate?.("library", { filter: "missing" })} />
                <IssueRow icon={Hash} label="No Key" value={issues.missing_key || 0} color={P.terracotta}
                  onClick={() => onNavigate?.("library", { filter: "partial" })} />
                <IssueRow icon={Tag} label="No Genre" value={issues.missing_genre || 0} color={P.azure}
                  onClick={() => onNavigate?.("library", { filter: "partial" })} />
              </div>
            </div>

            {/* Metadata + Genre — side by side on desktop */}
            <div className="two-col-grid">
              <div className="section-enter">
                <Sec label="Metadata" icon={SlidersHorizontal} color={P.azure} />
                <Card>
                  <CBar label="Title & Artist" value={comp.title_artist?.count || 0} max={comp.title_artist?.total || 1} color={P.healthy} icon={Music} />
                  <CBar label="BPM / Tempo" value={comp.bpm?.count || 0} max={comp.bpm?.total || 1} color={P.lime} icon={AudioLines} />
                  <CBar label="Musical Key" value={comp.key?.count || 0} max={comp.key?.total || 1} color={P.azure} icon={Hash} />
                  <CBar label="Genre" value={comp.genre?.count || 0} max={comp.genre?.total || 1} color={P.mauve} icon={Tag} />
                </Card>
              </div>
              {!genresLoading && genres.length > 0 && (
                <div className="section-enter">
                  <Sec label="Genre Spread" icon={Target} color={P.mauve} />
                  <Card>
                    {genres.slice(0, 8).map((g, i) => (
                      <Genre key={g.name} name={g.name} pct={g.pct} color={genreColor(i)} />
                    ))}
                  </Card>
                </div>
              )}
            </div>
          </>
        )}

        {/* Tracks */}
        <div className="section-enter">
          <Sec label="Tracks" icon={Disc3} color={P.lime} />
          <Card style={{ padding: "14px 16px" }}>
            <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 8, marginBottom: 4 }}>
              {[
                { label: "All", key: "all" },
                { label: "Complete", key: "complete" },
                { label: "Attention", key: "partial" },
                { label: "Missing", key: "missing" },
              ].map(f => (
                <Pill key={f.key} label={f.label} active={filter === f.key} onClick={() => setFilter(f.key)} />
              ))}
            </div>
            {tracksLoading ? <Loader text="Loading tracks..." /> : (
              <>
                {tracks.map((t, i) => <Track key={t.filepath || i} t={t} i={i} />)}
                {trackTotal > 20 && (
                  <div style={{ textAlign: "center", padding: "18px 0 8px" }}>
                    <span style={{
                      fontSize: 12, fontFamily: F.m, color: P.terracotta,
                      cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 5,
                      padding: "6px 14px", borderRadius: 8,
                      background: `${P.terracotta}08`, border: `1px solid ${P.terracotta}15`,
                      transition: "all 0.15s ease",
                    }}
                    onClick={() => onNavigate?.("library")}
                  >
                      View all {trackTotal.toLocaleString()} tracks <ArrowUpRight size={12} strokeWidth={2.5} />
                    </span>
                  </div>
                )}
                {tracks.length === 0 && (
                  <div style={{ textAlign: "center", padding: "40px 0" }}>
                    <div style={{
                      width: 48, height: 48, borderRadius: 12, margin: "0 auto 12px",
                      background: `${P.terracotta}08`, border: `1px solid ${P.terracotta}15`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <Disc3 size={20} color={P.terracotta} />
                    </div>
                    <div style={{ color: P.textSec, fontFamily: F.b, fontSize: 13, marginBottom: 12 }}>
                      No tracks in your library yet
                    </div>
                    <button onClick={() => onNavigate?.("library")} style={{
                      padding: "8px 16px", borderRadius: 8, border: "none",
                      background: P.terracotta, color: "#fff",
                      fontFamily: F.d, fontSize: 12, fontWeight: 700,
                      cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 5,
                    }}>
                      <RotateCw size={12} strokeWidth={2.5} /> Scan Library
                    </button>
                  </div>
                )}
              </>
            )}
          </Card>
        </div>

        {/* Footer */}
        <div style={{
          display: "flex", justifyContent: "center", alignItems: "center", gap: 6,
          padding: "32px 0 16px",
        }}>
          {[P.terracotta, P.lime, P.azure, P.mauve].map((c, i) => (
            <div key={i} style={{ width: 5, height: 5, background: c, borderRadius: 1.5, opacity: 0.4 }} />
          ))}
          <span style={{ fontSize: 8, fontFamily: F.m, color: P.textMut, letterSpacing: 2, marginLeft: 4 }}>
            CRATEDIGGER
          </span>
        </div>
      </div>

      {/* Scan modal */}
      {showScanModal && (
        <div onClick={() => { if (!scanning) setShowScanModal(false); }} style={{
          position: "fixed", inset: 0, zIndex: 200,
          background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)",
          display: "flex", justifyContent: "center", alignItems: "center",
        }}>
          <div onClick={e => e.stopPropagation()} style={{
            width: "100%", maxWidth: 440,
            background: P.bgElevated, border: `1px solid ${P.border}`,
            borderRadius: 16, padding: "24px",
            boxShadow: "0 24px 80px rgba(0,0,0,0.5)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
              <FolderOpen size={20} color={P.terracotta} />
              <span style={{ fontSize: 18, fontWeight: 700, fontFamily: F.d, color: P.cream }}>Scan Library</span>
            </div>
            <div style={{ fontSize: 12, fontFamily: F.b, color: P.textSec, marginBottom: 14, lineHeight: 1.6 }}>
              Enter the folder path containing your audio files (MP3, FLAC, WAV, etc.)
            </div>
            <input
              value={scanPath}
              onChange={e => setScanPath(e.target.value)}
              placeholder="e.g. /mnt/c/Users/DJ/Music"
              disabled={scanning}
              onKeyDown={e => { if (e.key === "Enter") runScan(); }}
              style={{
                width: "100%", padding: "10px 14px", borderRadius: 10,
                background: P.bgCard, border: `1px solid ${P.border}`,
                color: P.text, fontFamily: F.m, fontSize: 13,
                outline: "none", boxSizing: "border-box", marginBottom: 14,
              }}
            />
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button onClick={() => { if (!scanning) { setShowScanModal(false); setScanResult(null); } }} style={{
                padding: "8px 16px", borderRadius: 8, border: `1px solid ${P.border}`,
                background: "transparent", color: P.textSec,
                fontFamily: F.d, fontSize: 12, fontWeight: 600, cursor: "pointer",
              }}>
                Cancel
              </button>
              <button onClick={runScan} disabled={scanning || !scanPath.trim()} style={{
                padding: "8px 20px", borderRadius: 8, border: "none",
                background: scanning || !scanPath.trim() ? P.bgSurface : P.terracotta,
                color: scanning || !scanPath.trim() ? P.textMut : "#fff",
                fontFamily: F.d, fontSize: 12, fontWeight: 700,
                cursor: scanning || !scanPath.trim() ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", gap: 6,
              }}>
                {scanning ? <><Loader2 size={13} className="spin" /> Scanning...</> : <><RotateCw size={13} strokeWidth={2.5} /> Scan</>}
              </button>
            </div>
            {scanResult && (
              <div style={{
                marginTop: 12, padding: "8px 12px", borderRadius: 8,
                background: scanResult.error ? `${P.critical}10` : `${P.healthy}10`,
                border: `1px solid ${scanResult.error ? P.critical : P.healthy}20`,
                fontSize: 12, fontFamily: F.m,
                color: scanResult.error ? P.critical : P.healthy,
              }}>
                {scanResult.error || scanResult.success}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
