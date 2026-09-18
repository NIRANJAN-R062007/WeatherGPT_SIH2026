// Formatting helpers: IST timestamps (the data's own issue time, never the
// viewer's zone), unit conversion for display, and the IMD status vocabulary.

const IST = "Asia/Kolkata";

function sameIstDay(a, b) {
  const f = d => d.toLocaleDateString("en-IN", {timeZone: IST});
  return f(a) === f(b);
}

// ISO -> "HH:MM IST", with the date prefixed when it is not today (a snapshot
// from last week must not read as this morning's bulletin).
export function fmtIssued(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d)) return null;
  const time = d.toLocaleTimeString("en-IN", {hour: "2-digit", minute: "2-digit", hour12: false, timeZone: IST});
  if (sameIstDay(d, new Date())) return `${time} IST`;
  const day = d.toLocaleDateString("en-IN", {day: "numeric", month: "short", timeZone: IST});
  return `${day}, ${time} IST`;
}

// ISO -> "14 Sep, 06:00 IST" for warning validity windows (date always shown).
export function fmtIstDateTime(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d)) return null;
  const day = d.toLocaleDateString("en-IN", {day: "numeric", month: "short", timeZone: IST});
  const time = d.toLocaleTimeString("en-IN", {hour: "2-digit", minute: "2-digit", hour12: false, timeZone: IST});
  return `${day}, ${time} IST`;
}

export function nowIst() {
  return new Date().toLocaleTimeString("en-IN", {hour: "2-digit", minute: "2-digit", hour12: false, timeZone: IST}) + " IST";
}

// The backend is metric-only; °F is a display conversion of the raw Celsius reading.
export function temp(c, unit) {
  if (typeof c !== "number") return null;
  const v = unit === "F" ? c * 9 / 5 + 32 : c;
  return Math.round(v * 10) / 10;
}

export const IMD_ORDER = ["red", "orange", "yellow", "green"];

// Prototype IMD_PALETTE semantics kept; text always stays in ink, the colour
// carries only the stripe/icon/border so the label + icon do the work.
export const IMD = {
  green: {fg: "#2e7d32", bg: "#e8f5e9", border: "#a5d6a7", icon: "check"},
  yellow: {fg: "#f9a825", bg: "#fffde7", border: "#fff59d", icon: "info"},
  orange: {fg: "#ef6c00", bg: "#fff3e0", border: "#ffcc80", icon: "warn"},
  red: {fg: "#c62828", bg: "#ffebee", border: "#ef9a9a", icon: "alert"},
};

const ICONS = {
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
  warn: '<path d="M12 3.5L2.5 20h19L12 3.5z"/><path d="M12 10v5M12 17.5v.5"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M8 8l8 8M16 8l-8 8"/>',
  none: '<circle cx="12" cy="12" r="9"/><path d="M8 12h8"/>',
};

export function icon(name, size = 18) {
  return `<svg class="ico" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" ` +
    `stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ` +
    `aria-hidden="true">${ICONS[name] || ICONS.none}</svg>`;
}

// icon + label + colour, together, every time (never colour alone).
export function imdChip(colour, label, extraClass = "") {
  const key = IMD[colour] ? colour : null;
  const cls = key ? `imd imd-${key}` : "imd imd-none";
  return `<span class="${cls} ${extraClass}" data-colour="${key || "none"}">` +
    `${icon(key ? IMD[key].icon : "none", 16)}<span>${esc(label)}</span></span>`;
}

export function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
