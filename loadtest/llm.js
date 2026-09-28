// LLM-in-the-loop load test for /ask (plan.md §8 Phase 7 B4). Unlike
// spike.js, the orchestrator here runs WITH its Gemini/Groq/Bhashini keys, so
// every /ask call makes real, quota-limited API calls — there is no narration
// cache, each request narrates afresh. Run via `loadtest/run.sh llm`, which
// refuses to start without LLM_LOADTEST_CONFIRM=1.
//
// The rate is deliberately low and the request count bounded
// (RATE_PER_MIN × DURATION). A 150 rps spike against a free-tier LLM only
// measures 429s and template fallbacks, not narration latency. The fallback
// share is reported alongside the p95 so a "fast" p95 that is really the
// template answering can't pass as an LLM number.
//
// Only weather-intent queries: warnings answers are the feed headline
// verbatim (no LLM), so they'd dilute the measurement.
import http from "k6/http";
import { check } from "k6";
import { Counter, Rate, Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const RATE_PER_MIN = parseInt(__ENV.RATE_PER_MIN || "10", 10);
const DURATION = __ENV.DURATION || "6m";

export const options = {
  scenarios: {
    llm: {
      executor: "constant-arrival-rate",
      rate: RATE_PER_MIN,
      timeUnit: "1m",
      duration: DURATION,
      preAllocatedVUs: 10,
      maxVUs: 40,
    },
  },
  // The 2 s target from plan.md §1. These go red rather than abort: the
  // point of the run is to record the number, whatever it is.
  thresholds: {
    http_req_duration: ["p(95)<2000"],
    http_req_failed: ["rate<0.01"],
    ask_llm_answered: ["rate>0"],
    // Listed so the summary export carries them; the bounds are not targets.
    ask_llm_en_ms: ["p(95)>=0"],
    ask_llm_indic_ms: ["p(95)>=0"],
    ask_template_ms: ["p(95)>=0"],
  },
  summaryTrendStats: ["avg", "min", "med", "p(90)", "p(95)", "p(99)", "max"],
};

// Latency split by who actually produced the answer.
const llmEn = new Trend("ask_llm_en_ms", true);        // LLM, English: one LLM call
const llmIndic = new Trend("ask_llm_indic_ms", true);  // LLM + Bhashini translation
const templateMs = new Trend("ask_template_ms", true); // fell back to the template
const llmAnswered = new Rate("ask_llm_answered");
const byProvider = {
  gemini: new Counter("ask_provider_gemini"),
  groq: new Counter("ask_provider_groq"),
  ollama: new Counter("ask_provider_ollama"),
  template: new Counter("ask_provider_template"),
};
const ungrounded = new Counter("ask_ungrounded");

const CITIES = ["Chennai", "Madurai", "Coimbatore"];
// Half English, half the four Indic languages: a non-English answer is
// narrated in English then translated by Bhashini, so it's the slower path.
const LANGS = ["en", "en", "en", "en", "ta", "hi", "te", "mr"];
const QUERIES = [
  "what is the weather in {city}",
  "will it rain tomorrow in {city}",
  "forecast for the next 3 days in {city}",
  "what is the uv index in {city}",
  "what is the humidity in {city}",
  "how windy is it in {city}",
];

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

export default function () {
  const city = pick(CITIES);
  const lang = pick(LANGS);
  const text = pick(QUERIES).replace("{city}", city);
  // k6's JS runtime doesn't provide URLSearchParams — build the query by hand.
  const url = `${BASE_URL}/ask?text=${encodeURIComponent(text)}&lang=${lang}&city=${encodeURIComponent(city)}`;
  const res = http.get(url, { timeout: "60s", tags: { lang } });

  const ok = check(res, { "ask status is 200": (r) => r.status === 200 });
  if (!ok) return;

  let body;
  try {
    body = res.json();
  } catch (e) {
    return;
  }
  const g = body.grounding || {};
  const provider = g.provider || "template";
  if (byProvider[provider]) byProvider[provider].add(1);
  if (body.response === undefined) ungrounded.add(1);

  const fromLlm = g.narration === "llm" || g.narration === "llm+bhashini";
  llmAnswered.add(fromLlm);
  const ms = res.timings.duration;
  if (!fromLlm) templateMs.add(ms);
  else if (lang === "en") llmEn.add(ms);
  else llmIndic.add(ms);
}
