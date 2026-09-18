// Ask page: query -> /ask -> answer with provenance, validator result and the
// per-figure evidence table on every grounded answer. Answer text is shown
// verbatim from the backend; nothing here rewrites or reformats a figure.
import {ask, getCities} from "./api.js";
import {strings, LANGS} from "./i18n.js";
import {setPrefs} from "./prefs.js";
import {initShell, onPrefs} from "./shell.js";
import {esc, fmtIssued, icon} from "./format.js";

const $ = id => document.getElementById(id);
let prefs = initShell();
let cities = [];
let records = [];
let seq = 0;

function L() { return strings(prefs.lang); }

function renderStatic() {
  const s = L();
  document.title = `WeatherGPT — ${s.navAsk}`;
  $("ask-title").textContent = s.askTitle;
  $("ask-lead").textContent = s.askLead;
  $("city-label").textContent = s.cityLabel;
  $("q").placeholder = s.askPlaceholder;
  $("send").textContent = s.send;
  $("foot").textContent = s.poweredBy;
  $("suggestions").innerHTML = s.suggestions.map(q =>
    `<button type="button" class="chip" role="listitem">${esc(q)}</button>`).join("");
  $("suggestions").querySelectorAll(".chip").forEach(b => b.addEventListener("click", () => {
    $("q").value = b.textContent;
    submit(b.textContent);
  }));
  renderCities();
}

function renderCities() {
  const sel = $("city");
  const current = sel.value || prefs.city;
  sel.innerHTML = cities.map(c =>
    `<option value="${esc(c.key)}">${esc((c.names && c.names[prefs.lang]) || c.key)}</option>`).join("");
  if (cities.some(c => c.key === current)) sel.value = current;
}

async function loadCities() {
  try {
    const data = await getCities();
    cities = (data && data.cities) || [];
  } catch (e) {
    cities = []; // the select stays empty; /ask still resolves the city from the text
  }
  renderCities();
}

function narrationTag(g, s) {
  const k = g && g.narration;
  return k === "llm" ? s.narrationLlm : k === "llm+bhashini" ? s.narrationLlmBhashini
    : k === "template" ? s.narrationTemplate : "";
}

function receiptHtml(d, s) {
  const p = d.provenance || {}, g = d.grounding;
  const live = !!p.is_live;
  const issued = fmtIssued(p.issued) || p.issued || "";
  const parts = [];
  parts.push(`<span class="live-badge" data-live="${live}" data-testid="live-badge">${esc(live ? s.live : s.snapshot)}</span>`);
  if (p.source) parts.push(`<span class="src" data-testid="data-note">${esc(s.source)}: ${esc(p.source)}</span>`);
  if (issued) parts.push(`<span class="tnum">${esc(s.issued(issued))}</span>`);
  if (g && g.total > 0) {
    parts.push(`<span class="validator" data-ok="${!!g.ok}" data-testid="validator">` +
      `${icon(g.ok ? "check" : "alert", 13)}${esc(s.validator(g.matched, g.total))}</span>`);
  } else if (g) {
    parts.push(`<span class="validator" data-testid="validator">${esc(s.noFigures)}</span>`);
  }
  const tag = narrationTag(g, s);
  if (tag) parts.push(`<span class="tag">${esc(tag)}</span>`);
  if (g && g.fallback_used) parts.push(`<span class="fallback">${esc(s.fallbackNote)}</span>`);
  return `<div class="receipt">${parts.join("")}</div>`;
}

function evidenceHtml(rec, s) {
  const g = rec.data.grounding;
  const figures = (g && g.figures) || [];
  if (!figures.length) return "";
  const rows = figures.map(f => `
    <tr>
      <td class="fig">${esc(f.reading)}</td>
      <td><code data-testid="figure-path">${esc(f.path || "—")}</code></td>
      <td><span class="match" data-ok="${!!f.matched}">${icon(f.matched ? "check" : "alert", 13)}${esc(f.matched ? s.matchedYes : s.matchedNo)}</span></td>
    </tr>`).join("");
  return `
    <details class="evidence" data-id="${rec.id}" ${rec.open ? "open" : ""}>
      <summary data-testid="view-source">${esc(rec.open ? s.evidenceHide : s.evidenceShow)}</summary>
      <div class="scroll">
        <table>
          <thead><tr><th>${esc(s.figureCol)}</th><th>${esc(s.pathCol)}</th><th></th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <p class="note">${esc(s.guardrailFooter)}</p>
    </details>`;
}

function exchangeHtml(rec) {
  const s = strings(rec.lang);
  const font = LANGS[rec.lang] ? LANGS[rec.lang].font : "";
  let body;
  if (rec.status === "pending") {
    body = `<div class="state state-loading"><span class="spinner"></span>${esc(s.loading)}</div>`;
  } else if (rec.status === "error") {
    body = `<div class="state state-error" data-testid="error-card">
      <strong>${esc(s.errorTitle)}</strong><span>${esc(s.errorBody)}</span>
      <button type="button" class="btn" data-retry="${rec.id}">${esc(s.retry)}</button></div>`;
  } else {
    const d = rec.data;
    const intentLabel = (s.intent && s.intent[d.intent]) || "";
    const notice = d.notice ? `<p class="notice">${esc(d.notice)}</p>` : "";
    if (d.response) {
      body = `<p class="answer" data-testid="answer">${esc(d.response)}</p>${notice}` +
        receiptHtml(d, s) + evidenceHtml(rec, s);
    } else {
      // message-only shapes: unrecognised / unsupported city / no city / no data / guardrail refusal
      body = `<p class="answer is-message" data-testid="answer">${esc(d.message || "")}` +
        (intentLabel ? `<span class="intent-tag">${esc(intentLabel)}</span>` : "") + `</p>${notice}` +
        (d.grounding ? receiptHtml(d, s) + evidenceHtml(rec, s) : "");
    }
  }
  return `<article class="exchange ${font}" data-testid="exchange">
    <div class="q"><span class="eyebrow">${esc(s.youAsked)}</span><span>${esc(rec.query)}</span></div>
    ${body}
  </article>`;
}

function renderTranscript() {
  const s = L();
  const el = $("transcript");
  if (!records.length) {
    el.innerHTML = `<div class="state state-empty" data-testid="empty"><strong>${esc(s.emptyTitle)}</strong><span>${esc(s.emptyBody)}</span></div>`;
    return;
  }
  el.innerHTML = records.map(exchangeHtml).join("");
  el.querySelectorAll("[data-retry]").forEach(b => b.addEventListener("click", () => {
    const rec = records.find(r => r.id === Number(b.dataset.retry));
    if (rec) submit(rec.query, rec);
  }));
  el.querySelectorAll("details.evidence").forEach(d => d.addEventListener("toggle", () => {
    const rec = records.find(r => r.id === Number(d.dataset.id));
    if (rec && rec.open !== d.open) { rec.open = d.open; renderTranscript(); }
  }));
}

async function submit(text, existing) {
  const query = (text || "").trim();
  if (!query) return;
  const city = $("city").value || undefined;
  const rec = existing || {id: ++seq, query, lang: prefs.lang, open: false};
  rec.status = "pending"; rec.lang = prefs.lang;
  if (!existing) records.unshift(rec);
  renderTranscript();
  try {
    rec.data = await ask(query, rec.lang, city);
    rec.status = "ok";
    if (rec.data && rec.data.city) setPrefs({city: rec.data.city});
  } catch (e) {
    rec.status = "error";
  }
  renderTranscript();
}

$("ask-form").addEventListener("submit", e => {
  e.preventDefault();
  submit($("q").value);
});
$("city").addEventListener("change", () => setPrefs({city: $("city").value}));

onPrefs(p => { prefs = p; renderStatic(); renderTranscript(); });

renderStatic();
renderTranscript();
loadCities();
