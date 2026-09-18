// Dashboard: one panel per demo city from /cities, each fed by /facts
// (current, rain today, rain tomorrow) + /warnings. Every field in /facts may be
// absent, so each access is guarded and renders "not available".
import {getCities, getFacts, getWarning} from "./api.js";
import {strings} from "./i18n.js";
import {initShell, onPrefs} from "./shell.js";
import {esc, fmtIssued, imdChip, nowIst, temp} from "./format.js";

const $ = id => document.getElementById(id);
let prefs = initShell();
let cities = [];
const panels = new Map(); // key -> {status, data, error}

function L() { return strings(prefs.lang); }

function renderStatic() {
  const s = L();
  document.title = `WeatherGPT — ${s.navDashboard}`;
  $("title").textContent = s.dashTitle;
  $("lead").textContent = s.dashLead;
  $("foot").textContent = s.poweredBy;
}

function num(v) { return typeof v === "number"; }

function deg(c, s) {
  const t = temp(c, prefs.unit);
  return t == null ? `<span class="na">${esc(s.notAvailable)}</span>` : `${t}°`;
}

function panelHtml(city) {
  const s = L();
  const st = panels.get(city.key) || {status: "loading"};
  const name = (city.names && city.names[prefs.lang]) || city.key;
  let body;
  if (st.status === "loading") {
    body = `<div class="state state-loading"><span class="spinner"></span>${esc(s.loading)}</div>`;
  } else if (st.status === "error") {
    body = `<div class="state state-error" data-testid="error-card"><strong>${esc(s.errorTitle)}</strong>` +
      `<span>${esc(s.errorBody)}</span><button type="button" class="btn" data-retry="${esc(city.key)}">${esc(s.retry)}</button></div>`;
  } else {
    body = factsHtml(st.data, s);
  }
  const w = st.status === "ok" ? st.data.warning : undefined;
  const chip = w === undefined ? "" : w
    ? imdChip(w.colour, s.alert[w.colour] || w.colour, "chip")
    : imdChip(null, s.noWarning, "chip");
  return `<section class="panel" data-testid="city-panel" data-city="${esc(city.key)}">
    <header class="panel-head"><h2>${esc(name)}</h2><span data-testid="imd-chip">${chip}</span></header>
    ${body}
  </section>`;
}

function factsHtml(d, s) {
  const cur = d.current && d.current.facts;
  const unit = prefs.unit === "F" ? "°F" : "°C";
  if (!cur) {
    return `<div class="state state-empty" data-testid="empty"><strong>${esc(s.notAvailable)}</strong>` +
      `<span>${esc((d.current && d.current.message) || "")}</span></div>`;
  }
  const t = temp(cur.temp_c, prefs.unit);
  const hero = `<div class="hero">
    <span class="hero-num" data-testid="hero-temp">${t == null ? "—" : t}</span><span class="hero-unit">${unit}</span>
    <span class="cond">${esc(d.current.condition_label || "")}</span>
  </div>`;
  const tiles = `<div class="tiles">
    <div class="tile"><span class="label">${esc(s.feelsLike)}</span><span class="value">${deg(cur.feels_like_c, s)}</span></div>
    <div class="tile"><span class="label">${esc(s.humidity)}</span><span class="value">${num(cur.humidity_pct) ? cur.humidity_pct + "%" : `<span class="na">${esc(s.notAvailable)}</span>`}</span></div>
    <div class="tile"><span class="label">${esc(s.wind)}</span><span class="value">${num(cur.wind_kmh) ? `${cur.wind_kmh}<small>km/h${cur.wind_dir ? " " + esc(cur.wind_dir) : ""}</small>` : `<span class="na">${esc(s.notAvailable)}</span>`}</span></div>
    <div class="tile"><span class="label">${esc(s.uv)}</span><span class="value">${num(cur.uv_index) ? cur.uv_index : `<span class="na">${esc(s.notAvailable)}</span>`}</span></div>
  </div>`;
  const today = d.today && d.today.facts;
  const p = today && num(today.rain_probability_pct) ? today.rain_probability_pct : null;
  const meter = `<div class="meter-block">
    <div class="meter-head"><span>${esc(s.rainToday)}</span><span class="value">${p == null ? `<span class="na">${esc(s.notAvailable)}</span>` : p + "%"}</span></div>
    <div class="meter" role="meter" aria-valuemin="0" aria-valuemax="100" ${p == null ? "" : `aria-valuenow="${p}"`} aria-label="${esc(s.rainToday)}"><span style="width:${p == null ? 0 : p}%"></span></div>
  </div>`;
  const tm = d.tomorrow && d.tomorrow.facts;
  const tomorrow = `<div class="tomorrow">
    <span class="eyebrow">${esc(s.tomorrow)}</span>
    <div class="row">
      <span>${esc(s.high)} <b>${tm ? deg(tm.high_c, s) : `<span class="na">${esc(s.notAvailable)}</span>`}</b></span>
      <span>${esc(s.low)} <b>${tm ? deg(tm.low_c, s) : `<span class="na">${esc(s.notAvailable)}</span>`}</b></span>
      <span>${esc(s.rain)} <b>${tm && num(tm.rain_probability_pct) ? tm.rain_probability_pct + "%" : `<span class="na">${esc(s.notAvailable)}</span>`}</b></span>
    </div>
    ${tm && d.tomorrow.condition_label ? `<span class="cond">${esc(d.tomorrow.condition_label)}</span>` : ""}
  </div>`;
  const issued = fmtIssued(cur.issued);
  const foot = `<footer class="panel-foot">
    <span class="live-badge" data-live="${!!cur.is_live}" data-testid="live-badge">${esc(cur.is_live ? s.live : s.snapshot)}</span>
    ${issued ? `<span class="tnum">${esc(s.issued(issued))}</span>` : ""}
    ${cur.source ? `<span class="src">${esc(cur.source)}</span>` : ""}
  </footer>`;
  return hero + tiles + meter + tomorrow + foot;
}

function render() {
  const el = $("cities");
  el.innerHTML = cities.map(panelHtml).join("");
  el.querySelectorAll("[data-retry]").forEach(b => b.addEventListener("click", () => loadCity(b.dataset.retry)));
}

async function loadCity(key) {
  panels.set(key, {status: "loading"});
  render();
  const lang = prefs.lang;
  try {
    const [current, today, tomorrow, warn] = await Promise.all([
      getFacts(key, lang, "current_weather", "today"),
      getFacts(key, lang, "will_it_rain", "today"),
      getFacts(key, lang, "will_it_rain", "tomorrow"),
      getWarning(key, lang),
    ]);
    panels.set(key, {status: "ok", data: {current, today, tomorrow, warning: warn ? warn.warning : null}});
  } catch (e) {
    panels.set(key, {status: "error"});
  }
  render();
  $("updated").textContent = L().updated(nowIst());
}

async function loadAll() {
  $("updated").textContent = "";
  try {
    if (!cities.length) cities = ((await getCities()).cities) || [];
  } catch (e) {
    $("cities").innerHTML = `<div class="state state-error" data-testid="error-card"><strong>${esc(L().errorTitle)}</strong>` +
      `<span>${esc(L().errorBody)}</span><button type="button" class="btn" id="retry-all">${esc(L().retry)}</button></div>`;
    $("retry-all").addEventListener("click", loadAll);
    return;
  }
  await Promise.all(cities.map(c => loadCity(c.key)));
}

$("refresh").addEventListener("click", loadAll);
onPrefs(p => {
  const langChanged = p.lang !== prefs.lang;
  prefs = p;
  renderStatic();
  if (langChanged) loadAll(); else render(); // labels come localised from the backend
});

renderStatic();
loadAll();
