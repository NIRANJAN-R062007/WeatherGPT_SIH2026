// Abuse / security load test, run THROUGH THE GATEWAY (not the orchestrator
// directly) so the whole X-Forwarded-For chain is proven end to end
// (services/gateway/main.py `_forward_headers` + services/orchestrator/limits.py).
//
// Run via loadtest/run.sh abuse, which sets RATE_LIMIT_PER_MINUTE=30 on the
// orchestrator before starting it.
//
// Scenario 1: one client (no X-Forwarded-For override — the gateway fills
//   one in from the real peer address), 40 sequential /ask calls inside a
//   minute. Expect the first 30 to be 200, the rest 429 with Retry-After: 60.
// Scenario 2: a second, distinct client (explicit X-Forwarded-For:
//   203.0.113.9) making calls concurrently, comfortably under ITS OWN
//   30/minute budget (25, not 40 — this scenario proves the first client's
//   usage doesn't touch the second client's budget, not that the second
//   client is immune to the limit too) — it must keep getting 200s, proving
//   the rate limit budget is per-client, not global.
// Scenario 3: one POST /asr with a ~3 MB JSON body — over MAX_BODY_BYTES
//   (2 MiB default) — expect 413 before the request even reaches Bhashini.
import http from "k6/http";
import { check } from "k6";
import { Counter } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

const limitedOk = new Counter("limited_client_200s");
const limitedBlocked = new Counter("limited_client_429s");
const limitedRetryAfterCorrect = new Counter("limited_client_retry_after_60");
const otherOk = new Counter("other_client_200s");
const otherBlocked = new Counter("other_client_non_200s");
const oversizedRejected = new Counter("oversized_body_413s");

export const options = {
  scenarios: {
    rate_limited_client: {
      executor: "shared-iterations",
      vus: 1,
      iterations: 40,
      maxDuration: "60s",
      exec: "rateLimitedClient",
      startTime: "0s",
    },
    independent_client: {
      executor: "shared-iterations",
      vus: 1,
      iterations: 25,
      maxDuration: "60s",
      exec: "independentClient",
      startTime: "0s",
    },
    oversized_body: {
      executor: "shared-iterations",
      vus: 1,
      iterations: 1,
      exec: "oversizedBody",
      startTime: "1s",
    },
  },
  thresholds: {
    // First 30 calls from the rate-limited client must succeed, the rest
    // must be blocked with the documented Retry-After.
    limited_client_200s: ["count==30"],
    limited_client_429s: ["count==10"],
    limited_client_retry_after_60: ["count==10"],
    // The independent client's budget must never be touched by the first
    // client's usage.
    other_client_200s: ["count==25"],
    other_client_non_200s: ["count==0"],
    oversized_body_413s: ["count==1"],
  },
};

export function rateLimitedClient() {
  const res = http.get(`${BASE_URL}/ask?text=${encodeURIComponent("weather in Chennai")}`, {
    headers: { "ngrok-skip-browser-warning": "1" },
  });
  if (res.status === 200) {
    limitedOk.add(1);
  } else if (res.status === 429) {
    limitedBlocked.add(1);
    if (res.headers["Retry-After"] === "60") {
      limitedRetryAfterCorrect.add(1);
    }
  }
  check(res, { "status is 200 or 429": (r) => r.status === 200 || r.status === 429 });
}

export function independentClient() {
  const res = http.get(`${BASE_URL}/ask?text=${encodeURIComponent("weather in Madurai")}`, {
    headers: {
      "X-Forwarded-For": "203.0.113.9",
      "ngrok-skip-browser-warning": "1",
    },
  });
  if (res.status === 200) {
    otherOk.add(1);
  } else {
    otherBlocked.add(1);
  }
  check(res, { "independent client status is 200": (r) => r.status === 200 });
}

export function oversizedBody() {
  // ~3 MB of JSON, over the 2 MiB (2097152 byte) default MAX_BODY_BYTES cap.
  const audio = "A".repeat(3 * 1024 * 1024);
  const res = http.post(
    `${BASE_URL}/asr`,
    JSON.stringify({ audio, lang: "en" }),
    { headers: { "Content-Type": "application/json" } },
  );
  if (res.status === 413) {
    oversizedRejected.add(1);
  }
  check(res, { "oversized /asr body is 413": (r) => r.status === 413 });
}
