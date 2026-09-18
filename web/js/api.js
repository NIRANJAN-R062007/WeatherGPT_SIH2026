// Backend access. Same-origin by default (relative URLs), `?apiBase=` overrides —
// the same idea as the prototype's baseUrl(). No baked-in host: when this folder is
// served by the orchestrator (/web/) nothing needs configuring; when it is served
// separately (http.server, Vercel) the override points it at a backend.

export const API_TIMEOUT_MS = 15000;

export function apiBase() {
  const override = new URLSearchParams(window.location.search).get("apiBase");
  return (override || "").replace(/\/+$/, "");
}

export function apiBaseLabel(sameOriginText) {
  return apiBase() || sameOriginText;
}

export class ApiError extends Error {
  constructor(kind, status) {
    super(kind);
    this.kind = kind; // "http" | "network" | "timeout"
    this.status = status;
  }
}

export async function api(path, params) {
  const qs = params && Object.keys(params).length ? "?" + new URLSearchParams(params) : "";
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), API_TIMEOUT_MS);
  try {
    const res = await fetch(apiBase() + path + qs, {signal: ctrl.signal});
    if (!res.ok) throw new ApiError("http", res.status);
    return await res.json();
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(e && e.name === "AbortError" ? "timeout" : "network");
  } finally {
    clearTimeout(timer);
  }
}

export const getCities = () => api("/cities");
export const getFacts = (city, lang, intent = "current_weather", day = "today") =>
  api("/facts", {city, lang, intent, day});
export const getWarning = (city, lang) => api("/warnings", {city, lang});
export const ask = (text, lang, city) => api("/ask", city ? {text, lang, city} : {text, lang});
export const livez = () => api("/livez");
