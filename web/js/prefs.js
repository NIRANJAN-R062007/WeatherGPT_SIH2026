// Language + unit preferences, shared by every page (one localStorage key).
// `?lang=` in the URL wins for that load and is persisted, so a link can open
// the site in a given language.
import {LANGS} from "./i18n.js";

const KEY = "wg-web-prefs";

function read() {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? JSON.parse(raw) : {};
  } catch (e) {
    return {};
  }
}

function write(p) {
  try { window.localStorage.setItem(KEY, JSON.stringify(p)); } catch (e) { /* private mode */ }
}

let urlLangConsumed = false;

export function getPrefs() {
  const p = read();
  let lang = LANGS[p.lang] ? p.lang : "en";
  if (!urlLangConsumed) { // applied once per page load, then the user's choice wins
    urlLangConsumed = true;
    const urlLang = new URLSearchParams(window.location.search).get("lang");
    if (LANGS[urlLang]) lang = urlLang;
  }
  const unit = p.unit === "F" ? "F" : "C";
  const city = typeof p.city === "string" ? p.city : "chennai";
  if (lang !== p.lang) write({...p, lang});
  return {lang, unit, city};
}

export function setPrefs(patch) {
  const next = {...read(), ...patch};
  write(next);
  return next;
}
