import { useState } from "react";
import { P, F, genreColor } from "../theme";
import { useApi } from "../hooks/useApi";
import {
  Ring, CBar, IssueRow, Track, Genre, Sec, Pill, Loader, Waveform, Card,
} from "../components/ui";
import {
  Radio, SlidersHorizontal, Target, Disc3,
  AudioLines, Hash, Tag, Image, Fingerprint, Calendar, Music,
  HardDrive, Search, RotateCw, ArrowUpRight,
} from "lucide-react";

export default function Home({ onNavigate }) {
  const [filter, setFilter] = useState("all");

  const { data: stats, loading: statsLoading } = useApi("/api/library/stats");
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
            <button style={{
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

        {statsLoading ? <Loader text="Loading library stats..." /> : (
          <>
            {/* Library Health — hero treatment */}
            <Sec label="Library Health" icon={Radio} />
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
                <IssueRow icon={AudioLines} label="Missing BPM" value={issues.missing_bpm || 0} color={P.warning} />
                <IssueRow icon={Hash} label="No Key" value={issues.missing_key || 0} color={P.terracotta} />
                <IssueRow icon={Tag} label="No Genre" value={issues.missing_genre || 0} color={P.azure} />
              </div>
            </div>

            {/* Metadata + Genre — side by side on desktop */}
            <div className="two-col-grid">
              <div className="section-enter">
                <Sec label="Metadata" icon={SlidersHorizontal} />
                <Card>
                  <CBar label="Title & Artist" value={comp.title_artist?.count || 0} max={comp.title_artist?.total || 1} color={P.healthy} icon={Music} />
                  <CBar label="BPM / Tempo" value={comp.bpm?.count || 0} max={comp.bpm?.total || 1} color={P.lime} icon={AudioLines} />
                  <CBar label="Musical Key" value={comp.key?.count || 0} max={comp.key?.total || 1} color={P.azure} icon={Hash} />
                  <CBar label="Genre" value={comp.genre?.count || 0} max={comp.genre?.total || 1} color={P.mauve} icon={Tag} />
                </Card>
              </div>
              {!genresLoading && genres.length > 0 && (
                <div className="section-enter">
                  <Sec label="Genre Spread" icon={Target} />
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
          <Sec label="Tracks" icon={Disc3} />
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
                      onClick={() => onNavigate?.("library")}
                    }}>
                      View all {trackTotal.toLocaleString()} tracks <ArrowUpRight size={12} strokeWidth={2.5} />
                    </span>
                  </div>
                )}
                {tracks.length === 0 && (
                  <div style={{ textAlign: "center", padding: "40px 0", color: P.textMut, fontFamily: F.m, fontSize: 12 }}>
                    No tracks found. Run a scan first.
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
    </>
  );
}
