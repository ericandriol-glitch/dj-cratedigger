import { useState, useEffect } from "react";
import { P, F } from "../theme";
import { Track, Pill, Loader, Sec } from "../components/ui";
import { fetchApi } from "../hooks/useApi";
import { Disc3, Search, ChevronLeft, ChevronRight } from "lucide-react";

export default function Library() {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [tracks, setTracks] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const PAGE_SIZE = 30;

  useEffect(() => {
    setLoading(true);
    fetchApi(`/api/library/tracks?filter=${filter}&offset=${page * PAGE_SIZE}&limit=${PAGE_SIZE}`)
      .then(data => {
        setTracks(data.tracks || []);
        setTotal(data.total || 0);
      })
      .catch(() => {
        setTracks([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [filter, page]);

  // Reset page when filter changes
  useEffect(() => { setPage(0); }, [filter]);

  // Client-side search filter (on top of server filter)
  const displayed = search.trim()
    ? tracks.filter(t =>
        t.title?.toLowerCase().includes(search.toLowerCase()) ||
        t.artist?.toLowerCase().includes(search.toLowerCase())
      )
    : tracks;

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div style={{ padding: "20px" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <div style={{
          width: 36, height: 36, borderRadius: 10,
          background: `${P.lime}12`, border: `1px solid ${P.lime}20`,
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <Disc3 size={18} color={P.lime} />
        </div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: F.d, color: P.cream }}>Library</div>
          <div style={{ fontSize: 11, fontFamily: F.m, color: P.textMut }}>
            {total.toLocaleString()} tracks
          </div>
        </div>
      </div>

      {/* Search */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 10,
        padding: "8px 12px", marginBottom: 14,
      }}>
        <Search size={14} color={P.textMut} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search tracks..."
          style={{
            flex: 1, background: "none", border: "none", outline: "none",
            color: P.text, fontFamily: F.b, fontSize: 13,
          }}
        />
      </div>

      {/* Filter pills */}
      <div style={{ display: "flex", gap: 6, overflowX: "auto", marginBottom: 16 }}>
        {[
          { label: "All", key: "all" },
          { label: "Complete", key: "complete" },
          { label: "Attention", key: "partial" },
          { label: "Missing", key: "missing" },
        ].map(f => (
          <Pill key={f.key} label={f.label} active={filter === f.key} onClick={() => setFilter(f.key)} />
        ))}
      </div>

      {/* Track list */}
      <div style={{
        background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14,
        padding: "10px 14px",
      }}>
        {loading ? <Loader text="Loading tracks..." /> : (
          <>
            {displayed.map((t, i) => (
              <Track key={t.filepath || i} t={t} i={page * PAGE_SIZE + i} />
            ))}
            {displayed.length === 0 && (
              <div style={{ textAlign: "center", padding: 30, color: P.textMut, fontFamily: F.m, fontSize: 12 }}>
                {search ? "No matching tracks" : "No tracks found. Run a scan first."}
              </div>
            )}
          </>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{
          display: "flex", justifyContent: "center", alignItems: "center", gap: 16,
          padding: "16px 0",
        }}>
          <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={{
            background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 8,
            padding: "8px 12px", cursor: page > 0 ? "pointer" : "default",
            opacity: page > 0 ? 1 : 0.3, display: "flex", alignItems: "center",
          }}>
            <ChevronLeft size={14} color={P.textSec} />
          </button>
          <span style={{ fontSize: 11, fontFamily: F.m, color: P.textSec }}>
            {page + 1} / {totalPages}
          </span>
          <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1} style={{
            background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 8,
            padding: "8px 12px", cursor: page < totalPages - 1 ? "pointer" : "default",
            opacity: page < totalPages - 1 ? 1 : 0.3, display: "flex", alignItems: "center",
          }}>
            <ChevronRight size={14} color={P.textSec} />
          </button>
        </div>
      )}
    </div>
  );
}
