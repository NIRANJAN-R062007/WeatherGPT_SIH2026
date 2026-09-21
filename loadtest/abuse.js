// Abuse / security load test, run THROUGH THE GATEWAY (not the orchestrator
// directly) so the whole X-Forwarded-For chain is proven end to end
// (services/gateway/main.py `_forward_headers` + services/orchestrator/limits.py).
//
// Run via loadtest/run.sh abuse, which sets RATE_LIMIT_PER_MINUTE=30 on the
// orchestrator and starts both servers with --no-proxy-headers (see the
// comment there — without it uvicorn itself rewrites the peer address from
// the header for connections from 127.0.0.1, i.e. from k6). TRUSTED_PROXY_HOPS
// is left at its default of 1: the gateway is the one proxy in front of the
// orchestrator, and it appends the address it accepted the connection from
// (k6's) as the rightmost X-Forwarded-For hop — that hop is the limiter key.
// Everything a client puts in the header itself lands to the LEFT of it and
// is ignored.
//
// Scenario 1: an honest client (no X-Forwarded-For — the gateway fills one in
//   from the real peer address), 40 sequential /ask calls. Expect the first 30
//   to be 200, the rest 429 with Retry-After: 60.
// Scenario 2: a spoofing client from the same host, starting once scenario 1
//   is over (startTime 10s; scenario 1's maxDuration guarantees it has
//   stopped by then). Every request carries a fresh, client-supplied
//   X-Forwarded-For — the header rotation that used to buy a new budget per
//   request. The gateway appends k6's real address after it, the orchestrator
//   keys on that, so the spoofer shares scenario 1's already-spent budget:
//   all 25 calls must be 429, none 200. Running it after scenario 1 rather
//   than concurrently is what makes the per-scenario thresholds deterministic
//   (interleaved, the 30 successes would split between the two unpredictably).
//   Everything still fits inside one 60 s window.
// Scenario 3: one POST /asr with a ~3 MB JSON body — over MAX_BODY_BYTES
//   (2 MiB default) — expect 413 before the request even reaches Bhashini.
//   (Rejected before the limiter runs, so it doesn't spend budget.)
//
// Not covered here: two genuinely distinct clients getting independent
// budgets. k6 on one host presents one source address, so that lives in
// services/orchestrator/tests/test_limits.py instead.
import http from "k6/http";
import { check } from "k6";
import { Counter } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

const honestOk = new Counter("honest_client_200s");
const honestBlocked = new Counter("honest_client_429s");
const honestRetryAfterCorrect = new Counter("honest_client_retry_after_60");
const spoofOk = new Counter("spoofing_client_200s");
const spoofBlocked = new Counter("spoofing_client_429s");
const oversizedRejected = new Counter("oversized_body_413s");

export const options = {
  scenarios: {
    honest_client: {
      executor: "shared-iterations",
      vus: 1,
      iterations: 40,
      maxDuration: "10s",
      exec: "honestClient",
      startTime: "0s",
    },
    spoofing_client: {
      executor: "shared-iterations",
      vus: 1,
      iterations: 25,
      maxDuration: "30s",
      exec: "spoofingClient",
      startTime: "10s",
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
    // First 30 calls from the honest client must succeed, the rest must be
    // blocked with the documented Retry-After.
    honest_client_200s: ["count==30"],
    honest_client_429s: ["count==10"],
    honest_client_retry_after_60: ["count==10"],
    // The spoofer's rotating header buys nothing: the budget is already
    // spent, every call is refused.
    spoofing_client_200s: ["count==0"],
    spoofing_client_429s: ["count==25"],
    oversized_body_413s: ["count==1"],
  },
};

export function honestClient() {
  const res = http.get(`${BASE_URL}/ask?text=${encodeURIComponent("weather in Chennai")}`, {
    headers: { "ngrok-skip-browser-warning": "1" },
  });
  if (res.status === 200) {
    honestOk.add(1);
  } else if (res.status === 429) {
    honestBlocked.add(1);
    if (res.headers["Retry-After"] === "60") {
      honestRetryAfterCorrect.add(1);
    }
  }
  check(res, { "status is 200 or 429": (r) => r.status === 200 || r.status === 429 });
}

export function spoofingClient() {
  // One VU, so __ITER is 0..24: a never-repeated forged hop per request.
  const res = http.get(`${BASE_URL}/ask?text=${encodeURIComponent("weather in Madurai")}`, {
    headers: {
      "X-Forwarded-For": `198.51.100.${__ITER + 1}`,
      "ngrok-skip-browser-warning": "1",
    },
  });
  if (res.status === 200) {
    spoofOk.add(1);
  } else if (res.status === 429) {
    spoofBlocked.add(1);
  }
  check(res, { "spoofed hop is still rate limited": (r) => r.status === 429 });
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
