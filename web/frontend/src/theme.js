// CrateDigger design tokens — from v5 mockup
export const P = {
  bg: "#0B0A10",
  bgElevated: "#12111A",
  bgCard: "#171621",
  bgCardHover: "#1E1D2A",
  bgSurface: "#1F1E2B",
  terracotta: "#E8553A",
  lime: "#C5F536",
  azure: "#3B7EF7",
  mauve: "#C47A9B",
  cream: "#F0EBE3",
  text: "#F0EBE3",
  textSec: "#A9A5B5",
  textMut: "#7A7688",
  border: "#262433",
  borderSub: "#1E1D28",
  healthy: "#4ADE80",
  warning: "#FBBF24",
  critical: "#EF4444",
};

export const F = {
  d: "'Outfit', sans-serif",
  b: "'DM Sans', sans-serif",
  m: "'JetBrains Mono', monospace",
};

// Genre color cycling (excludes warning/cream to avoid false signals)
const GENRE_COLORS = [P.azure, P.terracotta, P.lime, P.mauve, P.healthy, "#A78BFA", "#F97316"];
export const genreColor = (i) => GENRE_COLORS[i % GENRE_COLORS.length];

// Camelot Wheel key colors — each position maps to a hue on the color wheel
// 1=red-orange, 4=yellow, 7=cyan, 10=violet, 12=red
const CAMELOT_COLORS = {
  "1A": "#E85D4A", "1B": "#F06B5A",
  "2A": "#E88A3A", "2B": "#F09848",
  "3A": "#E8B83A", "3B": "#F0C848",
  "4A": "#D4D43A", "4B": "#E0E048",
  "5A": "#8AD43A", "5B": "#98E048",
  "6A": "#3AD44A", "6B": "#48E058",
  "7A": "#3AD4A0", "7B": "#48E0B0",
  "8A": "#3A9CE8", "8B": "#48AAF0",
  "9A": "#5A5AE8", "9B": "#6868F0",
  "10A": "#9A3AE8", "10B": "#A848F0",
  "11A": "#D43AAA", "11B": "#E048B8",
  "12A": "#E83A5A", "12B": "#F04868",
};
export const camelotColor = (key) => CAMELOT_COLORS[key] || P.textMut;

// Energy level to color — blue (low) → green (mid) → red (high)
export const energyColor = (energy) => {
  if (energy == null) return P.textMut;
  const e = Math.max(0, Math.min(1, energy));
  if (e < 0.33) return "#4B7BEC";  // cool blue
  if (e < 0.66) return "#26DE81";  // green
  return "#FC5C65";                 // warm red
};
export const energyPct = (energy) => energy != null ? Math.round(energy * 100) : 0;
