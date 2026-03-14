import { P, F } from "../theme";
import { useApi } from "../hooks/useApi";
import { Sec, Ring, IssueRow, CBar, Loader } from "../components/ui";
import {
  Sparkles, AudioLines, Hash, Tag, Fingerprint,
  Music, Image, Calendar, Wand2, ArrowRight,
} from "lucide-react";

export default function Enrich() {
  const { data: stats, loading } = useApi("/api/library/stats");

  const s = stats || {};
  const comp = s.completeness || {};
  const issues = s.issues || {};
  const total = s.total_tracks || 0;

  const actions = [
    {
      title: "Detect BPM & Key",
      desc: "Run Essentia audio analysis on tracks missing BPM or musical key",
      count: issues.missing_bpm || 0,
      color: P.lime,
      icon: AudioLines,
      cmd: "cratedigger scan-essentia /path/to/library",
    },
    {
      title: "Enrich Genres",
      desc: "Look up genres via MusicBrainz for tracks with artist + title but no genre",
      count: issues.missing_genre || 0,
      color: P.mauve,
      icon: Tag,
      cmd: "cratedigger enrich /path/to/library --dry-run",
    },
    {
      title: "Write Essentia Tags",
      desc: "Apply detected BPM and key values back to file tags",
      count: (issues.missing_bpm || 0),
      color: P.azure,
      icon: Wand2,
      cmd: "cratedigger enrich-essentia /path/to/library --apply",
    },
  ];

  return (
    <div style={{ padding: "20px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: `${P.mauve}12`, border: `1px solid ${P.mauve}20`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Sparkles size={18} color={P.mauve} />
        </div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: F.d, color: P.cream }}>Enrich</div>
          <div style={{ fontSize: 11, fontFamily: F.m, color: P.textMut }}>Fill gaps in your library metadata</div>
        </div>
      </div>

      {loading ? <Loader text="Loading library stats..." /> : (
        <>
          {/* Health overview */}
          <div style={{
            background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14,
            padding: "20px 16px", marginBottom: 16, display: "flex", alignItems: "center", gap: 20,
          }}>
            <Ring pct={s.health_score || 0} size={80} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700, fontFamily: F.d, color: P.cream, marginBottom: 6 }}>
                Library Health
              </div>
              <div style={{ fontSize: 12, fontFamily: F.b, color: P.textSec, lineHeight: 1.5 }}>
                {total > 0
                  ? `${total} tracks scanned. ${s.good || 0} complete, ${s.missing || 0} need attention.`
                  : "No tracks scanned yet. Run a scan to get started."
                }
              </div>
            </div>
          </div>

          {/* Completeness breakdown */}
          <Sec label="Completeness" icon={Sparkles} />
          <div style={{ background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14, padding: "18px 16px", marginBottom: 16 }}>
            <CBar label="Title & Artist" value={comp.title_artist?.count || 0} max={comp.title_artist?.total || 1} color={P.healthy} icon={Music} />
            <CBar label="BPM / Tempo" value={comp.bpm?.count || 0} max={comp.bpm?.total || 1} color={P.lime} icon={AudioLines} />
            <CBar label="Musical Key" value={comp.key?.count || 0} max={comp.key?.total || 1} color={P.azure} icon={Hash} />
            <CBar label="Genre" value={comp.genre?.count || 0} max={comp.genre?.total || 1} color={P.mauve} icon={Tag} />
          </div>

          {/* Enrichment actions */}
          <Sec label="Actions" icon={Wand2} />
          {actions.map((a, i) => (
            <div key={i} style={{
              background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 12,
              padding: "14px 14px", marginBottom: 8, display: "flex", gap: 12, alignItems: "flex-start",
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 9,
                background: `${a.color}10`, border: `1px solid ${a.color}18`,
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              }}>
                <a.icon size={16} color={a.color} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontFamily: F.b, fontWeight: 600, color: P.text, marginBottom: 3 }}>
                  {a.title}
                </div>
                <div style={{ fontSize: 11, fontFamily: F.b, color: P.textSec, marginBottom: 6 }}>
                  {a.desc}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{
                    fontSize: 10, fontFamily: F.m, padding: "2px 8px", borderRadius: 5,
                    background: `${a.color}10`, color: a.color,
                  }}>
                    {a.count} tracks
                  </span>
                  <code style={{
                    fontSize: 9, fontFamily: F.m, color: P.textMut,
                    background: P.bgSurface, padding: "2px 6px", borderRadius: 4,
                  }}>
                    {a.cmd}
                  </code>
                </div>
              </div>
            </div>
          ))}

          {total === 0 && (
            <div style={{
              textAlign: "center", padding: "30px 20px", marginTop: 10,
              background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14,
            }}>
              <div style={{ fontSize: 13, fontFamily: F.b, color: P.textSec, marginBottom: 8 }}>
                No library data yet
              </div>
              <code style={{
                fontSize: 11, fontFamily: F.m, color: P.terracotta,
                background: `${P.terracotta}10`, padding: "6px 12px", borderRadius: 6,
              }}>
                cratedigger scan-essentia /path/to/music
              </code>
            </div>
          )}
        </>
      )}
    </div>
  );
}
