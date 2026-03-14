import { useState, useEffect, useRef } from "react";
import { P, F } from "../theme";
import { Track, Pill, Loader, Sec } from "../components/ui";
import { fetchApi } from "../hooks/useApi";
import { Disc3, Search, ChevronLeft, ChevronRight, ArrowUpDown } from "lucide-react";

const SORT_OPTIONS = [
  { key: "filepath", label: "Name" },
  { key: "bpm", label: "BPM" },
  { key: "key_camelot", label: "Key" },
  { key: "energy", label: "Energy" },
  { key: "genre", label: "Genre" },
];

export default function Library({ onNavigate, navParams = {} }) {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [searchDebounced, setSearchDebounced] = useState("");

  // Apply navigation params from other pages (e.g. IssueRow click)
  useEffect(() => {
    if (navParams.filter) setFilter(navParams.filter);
    if (navParams.search) { setSearch(navParams.search); setSearchDebounced(navParams.search); }
  }, [navParams.filter, navParams.search]);
  const [sort, setSort] = useState("filepath");
  const [order, setOrder] = useState("asc");
  const [page, setPage] = useState(0);
  const [tracks, setTracks] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const searchTimer = useRef(null);

  const PAGE_SIZE = 30;

  // Debounce search input (300ms)
  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => setSearchDebounced(search), 300);
    return () => clearTimeout(searchTimer.current);
  }, [search]);

  // Reset page when filter/search/sort changes
  const prevFilter = useRef(filter);
  const prevSearch = useRef(searchDebounced);
  const prevSort = useRef(sort);
  const prevOrder = useRef(order);
  useEffect(() => {
    if (filter !== prevFilter.current || searchDebounced !== prevSearch.current ||
        sort !== prevSort.current || order !== prevOrder.current) {
      setPage(0);
      prevFilter.current = filter;
      prevSearch.current = searchDebounced;
      prevSort.current = sort;
      prevOrder.current = order;
    }
  }, [filter, searchDebounced, sort, order]);

  // Fetch tracks from API with server-side search + sort
  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams({
      filter,
      offset: String(page * PAGE_SIZE),
      limit: String(PAGE_SIZE),
      sort,
      order,
    });
    if (searchDebounced.trim()) {
      params.set("search", searchDebounced.trim());
    }
    fetchApi(`/api/library/tracks?${params}`)
      .then(data => {
        setTracks(data.tracks || []);
        setTotal(data.total || 0);
      })
      .catch((err) => {
        console.error("Track fetch failed:", err);
        setTracks([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [filter, page, searchDebounced, sort, order]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const toggleSort = (key) => {
    if (sort === key) {
      setOrder(o => o === "asc" ? "desc" : "asc");
    } else {
      setSort(key);
      setOrder(key === "bpm" || key === "energy" ? "desc" : "asc");
    }
  };

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

      {/* Search — server-side */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 10,
        padding: "8px 12px", marginBottom: 14,
      }}>
        <Search size={14} color={P.textMut} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search tracks, artists..."
          style={{
            flex: 1, background: "none", border: "none", outline: "none",
            color: P.text, fontFamily: F.b, fontSize: 13,
          }}
        />
        {search && (
          <button onClick={() => setSearch("")} style={{
            background: "none", border: "none", cursor: "pointer",
            color: P.textMut, fontSize: 12, fontFamily: F.m,
          }}>clear</button>
        )}
      </div>

      {/* Filter pills + sort controls */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, gap: 12 }}>
        <div style={{ display: "flex", gap: 6, overflowX: "auto" }}>
          {[
            { label: "All", key: "all" },
            { label: "Complete", key: "complete" },
            { label: "Attention", key: "partial" },
            { label: "Missing", key: "missing" },
          ].map(f => (
            <Pill key={f.key} label={f.label} active={filter === f.key} onClick={() => setFilter(f.key)} />
          ))}
        </div>

        {/* Sort controls */}
        <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
          {SORT_OPTIONS.map(s => (
            <button key={s.key} onClick={() => toggleSort(s.key)} style={{
              padding: "5px 8px", borderRadius: 6, border: "none",
              background: sort === s.key ? `${P.terracotta}15` : "transparent",
              color: sort === s.key ? P.terracotta : P.textMut,
              fontFamily: F.m, fontSize: 9, letterSpacing: 0.5,
              cursor: "pointer", display: "flex", alignItems: "center", gap: 3,
              transition: "all 0.15s ease",
            }}>
              {s.label}
              {sort === s.key && (
                <span style={{ fontSize: 8 }}>{order === "asc" ? "\u2191" : "\u2193"}</span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Track list */}
      <div style={{
        background: P.bgCard, border: `1px solid ${P.border}`, borderRadius: 14,
        padding: "10px 14px",
      }}>
        {loading ? <Loader text="Loading tracks..." /> : (
          <>
            {tracks.map((t, i) => (
              <Track key={t.filepath || i} t={t} i={page * PAGE_SIZE + i} />
            ))}
            {tracks.length === 0 && (
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
