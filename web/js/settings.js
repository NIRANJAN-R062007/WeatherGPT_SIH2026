// Settings: language (the same five-language choice every page reads), °C/°F,
// backend connection check, and the grounding explainer.
import {apiBase, livez} from "./api.js";
import {LANGS, strings} from "./i18n.js";
import {initShell, onPrefs, setLang, setUnit} from "./shell.js";
import {esc} from "./format.js";

const $ = id => document.getElementById(id);
let prefs = initShell();

function L() { return strings(prefs.lang); }

function renderStatic() {
  const s = L();
  document.title = `WeatherGPT — ${s.navSettings}`;
  $("title").textContent = s.settingsTitle;
  $("lang-legend").textContent = s.language;
  $("unit-legend").textContent = s.units;
  $("unit-note").textContent = s.unitsNote;
  $("backend-legend").textContent = s.backend;
  const base = apiBase();
  $("backend-url").innerHTML = base ? `<code class="url">${esc(base)}</code>` : esc(s.sameOrigin);
  $("backend-hint").textContent = s.overrideHint;
  $("guardrail-title").textContent = s.guardrailTitle;
  $("steps").innerHTML = s.steps.map(t => `<li><span>${esc(t)}</span></li>`).join("");
  $("guardrail-footer").textContent = s.guardrailFooter;
  $("foot").textContent = s.poweredBy;

  const lang = $("lang-list").querySelector(`input[value="${prefs.lang}"]`);
  if (lang) lang.checked = true;
  $(prefs.unit === "F" ? "unit-f" : "unit-c").checked = true;
  renderStatus();
}

// Built once: the options are native language names, so they never re-translate.
function buildLangList() {
  $("lang-list").innerHTML = Object.entries(LANGS).map(([k, v]) =>
    `<label class="${v.font || "latin"}"><input type="radio" name="lang" value="${k}">` +
    `<span class="native">${esc(v.label)}</span><span class="code">${k}</span></label>`).join("");
  $("lang-list").querySelectorAll("input").forEach(r => r.addEventListener("change", () => setLang(r.value)));
}

let backendState = "checking";
function renderStatus() {
  const s = L();
  const el = $("backend-status");
  el.dataset.state = backendState;
  el.textContent = backendState === "ok" ? s.connected : backendState === "down" ? s.unreachable : s.checking;
}

async function checkBackend() {
  backendState = "checking"; renderStatus();
  try { await livez(); backendState = "ok"; } catch (e) { backendState = "down"; }
  renderStatus();
}

$("unit-seg").addEventListener("change", e => { if (e.target.name === "unit") setUnit(e.target.value); });
onPrefs(p => { prefs = p; renderStatic(); });

buildLangList();
renderStatic();
checkBackend();
