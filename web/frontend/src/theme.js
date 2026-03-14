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
  textSec: "#837F8E",
  textMut: "#524E5E",
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

// Genre color cycling
const GENRE_COLORS = [P.azure, P.terracotta, P.lime, P.mauve, P.warning, P.cream, P.healthy];
export const genreColor = (i) => GENRE_COLORS[i % GENRE_COLORS.length];
