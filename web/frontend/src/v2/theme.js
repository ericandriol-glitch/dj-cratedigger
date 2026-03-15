// V2 Design Tokens — Dekmantel-inspired
export const P = {
  bg: "#0B0A10",
  bgEl: "#12111A",
  bgCard: "#171621",
  bgHover: "#1E1D2A",
  bgSurface: "#1F1E2B",
  terra: "#E8553A",
  lime: "#C5F536",
  azure: "#3B7EF7",
  purple: "#9688F9",
  mauve: "#C47A9B",
  cream: "#F0EBE3",
  text2: "#837F8E",
  text3: "#524E5E",
  border: "#262433",
  green: "#4ADE80",
  warn: "#FBBF24",
};

export const F = {
  d: "'Outfit', sans-serif",
  b: "'DM Sans', sans-serif",
  m: "'JetBrains Mono', monospace",
};

export const camelotColor = (k) =>
  ({
    "8A": "#C47A9B",
    "5A": "#3BD4C4",
    "11B": "#D4F76A",
    "2A": "#F5B731",
    "7A": "#7B6CF7",
    "11A": "#C5F536",
    "6A": "#3B7EF7",
    "3A": "#C5F536",
    "9A": "#E8553A",
    "12A": "#4ADE80",
    "1A": "#E85D4A",
    "1B": "#F06B5A",
    "2B": "#F09848",
    "3B": "#F0C848",
    "4A": "#D4D43A",
    "4B": "#E0E048",
    "5B": "#98E048",
    "6B": "#48E058",
    "7B": "#48E0B0",
    "8B": "#48AAF0",
    "9B": "#6868F0",
    "10A": "#9A3AE8",
    "10B": "#A848F0",
    "12B": "#F04868",
  })[k] || P.text3;

export const srcColor = (s) =>
  ({
    ra: P.azure,
    spotify: "#1DB954",
    mb: "#BA478F",
    web: P.warn,
    acoustid: P.lime,
    "1001": "#FF6B35",
  })[s] || P.text3;

export const SRC = {
  ra: "RA",
  spotify: "SP",
  mb: "MB",
  web: "WEB",
  acoustid: "AID",
  "1001": "1001",
};
