// Theme system -- ported directly from the approved mockup
// (dev_notes/mockups/Guild Wars Launcher Redesign_4.zip, _launcher_export_src.html,
// Component.buildTheme/hx/toHex/mix/lum/rgba/fontStack/hashStr/avatarColor/initials),
// not re-derived. Pure JS, no framework -- the mockup's version is a React class
// component's methods; this is the same math as plain functions.
//
// No Google Fonts fetch (RELAY 010 -- no CDN dependencies, verify offline). Every
// mockup font (Sora, Manrope, Chakra Petch, Spectral) falls back to the OS's own
// system-ui sans-serif via fontStack below instead of being self-hosted -- visually
// close enough for this phase, and zero network dependency either way.

function hexToRgb(hex) {
  hex = (hex || "#000000").replace("#", "");
  if (hex.length === 3) hex = hex.split("").map((c) => c + c).join("");
  return [parseInt(hex.slice(0, 2), 16), parseInt(hex.slice(2, 4), 16), parseInt(hex.slice(4, 6), 16)];
}

function rgbToHex(r, g, b) {
  return "#" + [r, g, b].map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
}

function mixColor(a, b, t) {
  const A = hexToRgb(a), B = hexToRgb(b);
  return rgbToHex(A[0] + (B[0] - A[0]) * t, A[1] + (B[1] - A[1]) * t, A[2] + (B[2] - A[2]) * t);
}

function luminance(hex) {
  const c = hexToRgb(hex).map((v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

function rgbaColor(hex, a) {
  const c = hexToRgb(hex);
  return `rgba(${c[0]},${c[1]},${c[2]},${a})`;
}

function fontStack(f) {
  return f === "JetBrains Mono" ? "'JetBrains Mono',monospace" : `'${f}',system-ui,sans-serif`;
}

function buildTheme(p) {
  const light = luminance(p.bg) > 0.5;
  const R = p.radius;
  const ink = luminance(p.accent) > 0.5 ? mixColor(p.accent, "#05060f", 0.86) : "#ffffff";
  return {
    "--bg": p.bg,
    "--surface": p.surface,
    "--panel": mixColor(p.surface, p.text, 0.05),
    "--panel2": mixColor(p.surface, p.text, 0.11),
    "--rail": mixColor(p.bg, p.surface, 0.5),
    "--border": mixColor(p.surface, p.text, 0.17),
    "--border-soft": mixColor(p.surface, p.text, 0.09),
    "--text": p.text,
    "--muted": mixColor(p.text, p.bg, 0.36),
    "--faint": mixColor(p.text, p.bg, 0.58),
    "--accent": p.accent,
    "--accent-ink": ink,
    "--accent-soft": rgbaColor(p.accent, 0.16),
    "--good": p.good,
    "--warn": p.warn,
    "--bad": p.bad,
    "--good-soft": rgbaColor(p.good, 0.16),
    "--warn-soft": rgbaColor(p.warn, 0.16),
    "--bad-soft": rgbaColor(p.bad, 0.16),
    "--radius": R + "px",
    "--radius-sm": Math.max(4, R - 3) + "px",
    "--avatar-radius": Math.max(4, R - 2) + "px",
    "--font-ui": fontStack(p.font),
    "--font-display": fontStack(p.font),
    "--font-mono": "'JetBrains Mono',monospace",
    "--stagebg": light ? mixColor(p.bg, "#000000", 0.07) : mixColor(p.bg, "#000000", 0.45),
  };
}

function applyTheme(palette) {
  const vars = buildTheme(palette);
  const root = document.documentElement.style;
  for (const [k, v] of Object.entries(vars)) root.setProperty(k, v);
}

function hashStr(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

const AVATAR_HUES = ["#e0736f", "#3aa79a", "#7d76d6", "#d69a3a", "#46b07f", "#4c9bd0", "#d67f4c", "#c95faf"];

function avatarColor(name) {
  return AVATAR_HUES[hashStr(name || "?") % AVATAR_HUES.length];
}

function initials(name) {
  const parts = (name || "?").trim().split(/\s+/);
  return (((parts[0] || "")[0] || "") + ((parts[1] || "")[0] || "")).toUpperCase();
}

// Same 5 presets as the mockup (Component constructor's this._presets).
const THEME_PRESETS = [
  { name: "Indigo Aurora", accent: "#7c8cff", bg: "#0d0f1f", surface: "#14162b", text: "#e6e8ff", good: "#5ce0b0", warn: "#ffd166", bad: "#ff6b8a", radius: 12, font: "Sora" },
  { name: "Ember Carbon", accent: "#ff7a45", bg: "#131110", surface: "#1b1917", text: "#f0e9e0", good: "#8fbf6a", warn: "#f0b429", bad: "#f05e5e", radius: 8, font: "Sora" },
  { name: "Signal Mint", accent: "#3ddc84", bg: "#08100d", surface: "#0c1613", text: "#dbf5e9", good: "#3ddc84", warn: "#e8c15a", bad: "#f0616d", radius: 8, font: "Chakra Petch" },
  { name: "Rosé Dusk", accent: "#ebbcba", bg: "#16141f", surface: "#1f1d2e", text: "#e0def4", good: "#9ccfd8", warn: "#f6c177", bad: "#eb6f92", radius: 12, font: "Spectral" },
  { name: "Porcelain", accent: "#1f6f5c", bg: "#ece9e2", surface: "#ffffff", text: "#211f1b", good: "#2f8f5b", warn: "#bd8321", bad: "#c0453b", radius: 10, font: "Manrope" },
];
