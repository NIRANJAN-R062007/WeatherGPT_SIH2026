// Page shell shared by every page: top nav, language switcher, per-language
// font class on <html>, and the `?apiBase=` override carried across links.
import {LANGS, strings} from "./i18n.js";
import {getPrefs, setPrefs} from "./prefs.js";
import {apiBase} from "./api.js";
import {esc} from "./format.js";

const PAGES = [
  ["ask", "index.html", "navAsk"],
  ["dashboard", "dashboard.html", "navDashboard"],
  ["warnings", "warnings.html", "navWarnings"],
  ["settings", "settings.html", "navSettings"],
];

export function href(file) {
  const base = apiBase();
  return base ? `${file}?apiBase=${encodeURIComponent(base)}` : file;
}

export function applyLang(lang) {
  const root = document.documentElement;
  root.lang = lang;
  root.className = LANGS[lang] ? LANGS[lang].font : "";
}

const listeners = [];
export function onPrefs(fn) { listeners.push(fn); }

export function state() {
  return getPrefs();
}

export function setLang(lang) {
  if (!LANGS[lang]) return;
  setPrefs({lang});
  applyLang(lang);
  renderNav();
  listeners.forEach(fn => fn(getPrefs()));
}

export function setUnit(unit) {
  setPrefs({unit: unit === "F" ? "F" : "C"});
  listeners.forEach(fn => fn(getPrefs()));
}

function renderNav() {
  const el = document.querySelector("[data-shell]");
  if (!el) return;
  const {lang} = getPrefs();
  const L = strings(lang);
  const current = el.dataset.shell;
  el.innerHTML = `
    <a class="brand" href="${href("index.html")}" aria-label="WeatherGPT">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="9" cy="8.5" r="3" stroke="var(--sun)" stroke-width="1.8"/>
        <path d="M17.5 20a3.5 3.5 0 0 0 0-7 5 5 0 0 0-9.6-1.3A3.4 3.4 0 0 0 8 20Z" fill="var(--cloud-fill)" stroke="var(--cloud)" stroke-width="1.8"/>
      </svg>
      <span>WeatherGPT</span>
    </a>
    <nav aria-label="Pages">
      ${PAGES.map(([key, file, label]) =>
        `<a href="${href(file)}" ${key === current ? 'aria-current="page"' : ""}>${esc(L[label])}</a>`).join("")}
    </nav>
    <label class="lang-pick">
      <span class="sr-only">${esc(L.langLabel)}</span>
      <select id="lang-select" aria-label="${esc(L.langLabel)}">
        ${Object.entries(LANGS).map(([k, v]) =>
          `<option value="${k}" class="${v.font || "latin"}" ${k === lang ? "selected" : ""}>${esc(v.label)}</option>`).join("")}
      </select>
    </label>`;
  el.querySelector("#lang-select").addEventListener("change", e => setLang(e.target.value));
}

// Call once per page. Returns the current prefs; `onPrefs` fires on every change.
export function initShell() {
  const p = getPrefs();
  applyLang(p.lang);
  renderNav();
  return p;
}
