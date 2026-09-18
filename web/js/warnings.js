// Warnings: /warnings per demo city, rendered as severity bands sorted
// red -> orange -> yellow -> green -> none. Category and headline are shown as
// issued — this page never re-grades a warning (plan.md §2 principle 4).
import {getCities, getWarning} from "./api.js";
import {strings} from "./i18n.js";
import {initShell, onPrefs} from "./shell.js";
import {esc, fmtIstDateTime, icon, IMD, IMD_ORDER} from "./format.js";

const $ = id => document.getElementById(id);
let prefs = initShell();
let cities = [];
let rows = []; // {city, status, warning}

function L() { return strings(prefs.lang); }

function renderStatic() {
  const s = L();
  document.title = `WeatherGPT — ${s.navWarnings}`;
  $("title").textContent = s.warnTitle;
  $("lead").textContent = s.warnLead;
  $("foot").textContent = s.poweredBy;
  $("legend").innerHTML = ["green", "yellow", "orange", "red"].map(c =>
    `<li><span class="swatch" data-colour="${c}">${icon(IMD[c].icon, 15)}</span><b>${esc(s.colour[c])}</b><span class="m">${esc(s.meaning[c])}</span></li>`).join("");
}

function rank(row) {
  if (row.status !== "ok") return 99;
  const i = row.warning ? IMD_ORDER.indexOf(row.warning.colour) : -1;
  return i < 0 ? 50 : i;
}

function bandHtml(row) {
  const s = L();
  const name = (row.city.names && row.city.names[prefs.lang]) || row.city.key;
  if (row.status === "loading") {
    return `<div class="state state-loading"><span class="spinner"></span>${esc(name)} — ${esc(s.loading)}</div>`;
  }
  if (row.status === "error") {
    return `<div class="state state-error" data-testid="error-card"><strong>${esc(name)} — ${esc(s.errorTitle)}</strong>` +
      `<span>${esc(s.errorBody)}</span><button type="button" class="btn" data-retry="${esc(row.city.key)}">${esc(s.retry)}</button></div>`;
  }
  const w = row.warning;
  if (!w) {
    return `<article class="band band-none" data-testid="warning-band" data-colour="none">
      <div class="band-code">${icon("none", 34)}<span class="code-name">${esc(s.noWarning)}</span></div>
      <div class="band-body"><span class="where">${esc(name)}</span>
        <h2 class="headline">${esc(s.noWarningTitle)}</h2><p class="advice">${esc(s.noWarningBody)}</p></div>
    </article>`;
  }
  const c = IMD[w.colour] ? w.colour : null;
  const from = fmtIstDateTime(w.valid_from), to = fmtIstDateTime(w.valid_to);
  return `<article class="band band-${c || "none"}" data-testid="warning-band" data-colour="${c || "none"}">
    <div class="band-code">
      ${icon(c ? IMD[c].icon : "none", 34)}
      <span class="code-name" data-testid="code-name">${esc(c ? s.colour[c] : w.colour)}</span>
      <span class="code-meaning">${esc(c ? s.meaning[c] : "")}</span>
    </div>
    <div class="band-body">
      <span class="where">${esc(name)}${w.district ? ` · ${esc(s.district)}: ${esc(w.district)}` : ""}</span>
      <h2 class="headline" data-testid="headline">${esc(w.headline || "")}</h2>
      ${w.category ? `<p class="category"><span class="k">${esc(s.category)}</span>${esc(w.category)}</p>` : ""}
      ${w.advice ? `<p class="advice"><span class="k">${esc(s.advice)}</span>${esc(w.advice)}</p>` : ""}
    </div>
    <dl class="band-meta">
      ${from || to ? `<dt>${esc(s.validity)}</dt><dd data-testid="validity"><span class="tnum">${esc(from || "…")}</span> → <span class="tnum">${esc(to || "…")}</span></dd>` : ""}
      ${w.issued_by ? `<dt>${esc(s.issuedBy)}</dt><dd>${esc(w.issued_by)}${w.source === "fixture" ? `<br><span class="fixture-badge">${esc(s.fixtureBadge)}</span>` : ""}</dd>` : ""}
    </dl>
  </article>`;
}

function render() {
  const el = $("list");
  el.innerHTML = [...rows].sort((a, b) => rank(a) - rank(b)).map(bandHtml).join("");
  el.querySelectorAll("[data-retry]").forEach(b => b.addEventListener("click", () => loadCity(b.dataset.retry)));
}

async function loadCity(key) {
  const row = rows.find(r => r.city.key === key);
  row.status = "loading"; render();
  try {
    const data = await getWarning(key, prefs.lang);
    row.warning = data ? data.warning : null; row.status = "ok";
  } catch (e) {
    row.status = "error";
  }
  render();
}

async function loadAll() {
  try {
    if (!cities.length) cities = ((await getCities()).cities) || [];
  } catch (e) {
    const s = L();
    $("list").innerHTML = `<div class="state state-error" data-testid="error-card"><strong>${esc(s.errorTitle)}</strong>` +
      `<span>${esc(s.errorBody)}</span><button type="button" class="btn" id="retry-all">${esc(s.retry)}</button></div>`;
    $("retry-all").addEventListener("click", loadAll);
    return;
  }
  rows = cities.map(city => ({city, status: "loading", warning: null}));
  await Promise.all(cities.map(c => loadCity(c.key)));
}

onPrefs(p => { prefs = p; renderStatic(); loadAll(); });
renderStatic();
loadAll();
