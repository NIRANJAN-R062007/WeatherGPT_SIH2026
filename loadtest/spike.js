// Spike load test against the gateway's public surface (plan.md §14).
// Ramps a synthetic arrival-rate spike to 150 rps across /ask, /facts and
// /warnings, weighted 60/25/15. Run via loadtest/run.sh spike (starts the
// two services locally with WEATHER_MODE=fixtures and no LLM/Bhashini keys,
// so /ask always answers from the i18n template — this is the floor the LLM
// path sits on top of, not a measurement of LLM latency).
import http from "k6/http";
import { check } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

export const options = {
  scenarios: {
    spike: {
      executor: "ramping-arrival-rate",
      startRate: 0,
      timeUnit: "1s",
      preAllocatedVUs: 50,
      maxVUs: 300,
      stages: [
        { target: 150, duration: "30s" },
        { target: 150, duration: "60s" },
        { target: 0, duration: "15s" },
      ],
    },
  },
  thresholds: {
    http_req_duration: ["p(95)<2000"],
    http_req_failed: ["rate<0.01"],
  },
};

const CITIES = ["Chennai", "Madurai", "Coimbatore"];
const LANGS = ["en", "ta", "hi", "te", "mr"];
const QUERIES = [
  "what is the weather in {city}",
  "will it rain tomorrow in {city}",
  "will it rain day after tomorrow in {city}",
  "forecast for the next 3 days in {city}",
  "what is the uv index in {city}",
  "how much rain has fallen so far today in {city}",
  "what is the humidity in {city}",
  "how windy is it in {city}",
];

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

// Non-English `lang` values keep the query text in English on purpose — with
// no LLM/Bhashini keys configured (loadtest/run.sh), the answer always comes
// from the i18n template regardless of `lang`, so this exercises the
// template-rendering path per language rather than real Bhashini translation.
// k6's JS runtime doesn't provide URLSearchParams — build query strings by hand.
function askUrl(vu, iter) {
  const city = pick(CITIES);
  const lang = pick(LANGS);
  const text = pick(QUERIES).replace("{city}", city);
  return `${BASE_URL}/ask?text=${encodeURIComponent(text)}&lang=${encodeURIComponent(lang)}&city=${encodeURIComponent(city)}`;
}

function factsUrl() {
  const city = pick(CITIES);
  return `${BASE_URL}/facts?city=${encodeURIComponent(city)}`;
}

function warningsUrl() {
  const city = pick(CITIES);
  const lang = pick(LANGS);
  return `${BASE_URL}/warnings?city=${encodeURIComponent(city)}&lang=${lang}`;
}

const HEADERS = (vu, iter) => ({
  "X-Forwarded-For": `10.0.${vu}.${iter % 250}`,
  "ngrok-skip-browser-warning": "1",
});

export default function () {
  const vu = __VU;
  const iter = __ITER;
  const roll = Math.random();
  const headers = HEADERS(vu, iter);

  if (roll < 0.60) {
    const res = http.get(askUrl(vu, iter), { headers });
    check(res, {
      "ask status is 200": (r) => r.status === 200,
      "ask body has response": (r) => r.body && r.body.indexOf('"response"') !== -1,
    });
  } else if (roll < 0.85) {
    const res = http.get(factsUrl(), { headers });
    check(res, { "facts status is 200": (r) => r.status === 200 });
  } else {
    const res = http.get(warningsUrl(), { headers });
    check(res, { "warnings status is 200": (r) => r.status === 200 });
  }
}
