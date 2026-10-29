"""Historical climate for the demo cities from Open-Meteo's ERA5 reanalysis:
fetch, monthly / seasonal / annual aggregates, a simple trend, cache, and
fixture fallback (plan.md §3.4, §6 P2 item 12, task CLM-2). Every figure is
computed here, in plain Python, from Open-Meteo's daily values — never by an
LLM — and every result is labelled "Open-Meteo / ERA5 reanalysis, not IMD
station data" and never presented as IMD data (plan.md §2). Terms, attribution,
limits and the endpoint were verified in CLM-1 (plan.md §8 Phase 5, 2026-10-29).

SOURCE. `GET https://archive-api.open-meteo.com/v1/archive` with `models=era5`,
which Open-Meteo advises for "consistent data over multiple decades" (its
default, Best Match, blends several models and would put steps into a trend).
Two daily variables are asked for: `precipitation_sum` (mm) and
`temperature_2m_mean` (°C). The true daily mean is requested because
(max + min) / 2 is not the same thing: for Chennai in June 2025 it ran 0.58 °C
too warm on average (up to 1.1 °C), measured against the real API on 2026-10-29.
`temperature_2m_mean` is not in the parameter list printed on Open-Meteo's
documentation page, but the API serves it for ERA5 (checked the same day). The
coordinates are the city's own, from the registry in cities.py; no caller text
reaches a URL.

Like aviation.py and gdacs.py, config.WEATHER_MODE decides where data comes
from: "auto" (default) fetches live and falls back to the snapshot in
data/fixtures/open_meteo/<city>.json when the fetch fails; "live" never falls
back; "fixtures" (and OFFLINE_MODE) never touch the network. A snapshot is dated
by when it was taken and is never shown as live. A failed fetch is `status`
"unavailable" with every data field None: it is never zero rainfall, and never
"no trend".

MISSING DATA. Open-Meteo answers with `null` for days it has not produced yet
(ERA5 lags about 6 days) and the request ends a week before today. A day with no
value is missing, not zero. A month, season or year gets a rainfall total and a
mean temperature only if EVERY one of its days has a value; otherwise that figure
is None, and `rain_days` / `temp_days` say how many days were there. Incomplete
periods are never extrapolated and never enter a trend.

PERIODS. Months are calendar months. Seasons are fixed calendar windows —
winter Jan–Feb, pre_monsoon Mar–May, monsoon Jun–Sep, post_monsoon Oct–Dec —
used only to group days. They are NOT IMD's declared monsoon onset or
withdrawal (plan.md §3.4), and the grid cell is ERA5's 0.25° cell, not a station.
Rainfall is the sum of daily totals; temperature is the mean of the daily means
over all days of the period (so months of different length weigh correctly).
Sums use math.fsum, so the result does not depend on summation order.

TREND (the statistical method). For one series — e.g. every year's June
rainfall — over the years where the figure is complete, an ordinary
least-squares line  value = a + b * year  is fitted:
    b  = sum((x - xbar) * (y - ybar)) / sum((x - xbar)^2)
    s2 = sum(residual^2) / (n - 2),   se(b) = sqrt(s2 / sum((x - xbar)^2)),
    t  = b / se(b)
`slope_per_decade` is 10 * b in the series' unit (mm or °C) per decade;
`stderr_per_decade` is 10 * se(b). `significant_95` is true when |t| reaches the
two-sided 95% critical value of Student's t with n - 2 degrees of freedom (a
table, taken from the largest tabulated df not above n - 2, i.e. slightly
conservative). Fewer than MIN_TREND_YEARS complete years gives
status "insufficient_data", never a slope. A perfect straight-line fit has no
residual: `t` is then None and `significant_95` is whether the slope is non-zero.
This is a descriptive line through ~30 yearly values, not a forecast and not a
claim about causes. It assumes independent yearly errors (year-to-year
rainfall varies far more than any trend), so a result that is not
`significant_95` means "no change can be told apart from natural variation",
not "no change" — consumers must word it that way. Also, a city has 34 separate
trends (12 months, 4 seasons and the year, for rain and for temperature), and
about 1 in 20 would read "significant" by chance alone: a consumer must answer
the question that was asked, not pick whichever series happens to be flagged.

LIMITS. A ~31-year daily request is large for Open-Meteo: it counts requests
over 2 weeks as several calls, roughly (days / 14) calls by its two worked
examples (our inference, not a published formula), so about 800 per city against
10,000 a day for free use. So: one request per city per day at most (the cache),
at most MAX_LIVE_FETCHES_PER_DAY live fetches a day per process, and a back-off
after a failure (longer after HTTP 429). This is a stand-in for the daily-ceiling
breaker planned in IMD-3.

`python climate.py chennai mumbai delhi` (from this directory) refreshes those
cities' fixtures from the live service, pausing between cities.
"""

import calendar
import copy
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import cities
import config
import httpx

_LOG = logging.getLogger("weathergpt.climate")

HOST = "archive-api.open-meteo.com"
API_URL = f"https://{HOST}/v1/archive"
SOURCE = "Open-Meteo"
MODEL = "era5"
LABEL = "Open-Meteo / ERA5 reanalysis, not IMD station data"
SOURCE_URL = "https://open-meteo.com/"
LICENCE_URL = "https://open-meteo.com/en/licence"
TERMS_URL = "https://open-meteo.com/en/terms"
#: CC BY 4.0 (CLM-1): a link next to wherever the data is shown, and "indicate if
#: changes were made" — our aggregates and trends are changes.
CREDIT = {"text": "Weather data by Open-Meteo.com", "url": SOURCE_URL}
CHANGES_NOTE = ("Monthly, seasonal and annual figures and trends are computed by WeatherGPT "
                "from Open-Meteo's daily ERA5 values.")
CALENDAR_NOTE = ("Months and seasons are fixed calendar windows. They are not IMD's declared "
                 "monsoon onset or withdrawal.")

DAILY_VARS = ("precipitation_sum", "temperature_2m_mean")
UNITS = {"precipitation_sum": "mm", "temperature_2m_mean": "°C"}
SEASONS = {
    "winter": (1, 2),
    "pre_monsoon": (3, 4, 5),
    "monsoon": (6, 7, 8, 9),
    "post_monsoon": (10, 11, 12),
}

BASELINE_YEARS = 30          # whole years before the current one, plus this year so far
END_LAG_DAYS = 7             # ERA5 trails by about 6 days; the request ends this far back
MIN_TREND_YEARS = 10         # fewer complete years than this: no trend (our choice)
RAIN_MAX_MM = 2000.0         # a day above this is not a rainfall total: treated as missing
TEMP_RANGE_C = (-90.0, 60.0)  # outside this is not an air temperature: treated as missing

TIMEOUT = 30.0               # seconds, per network operation
MAX_BYTES = 3_000_000        # cap on one response body, after decompression
MAX_DAYS = 13_000            # cap on days read from one response (~35 years)
TTL_SECONDS = 24 * 3600      # history barely changes; one fetch per city per day at most
MAX_LIVE_FETCHES_PER_DAY = 8  # per process, by UTC date (~800 calls each vs 10,000 a day)
FAILURE_BACKOFF_SECONDS = 120
RATE_LIMIT_BACKOFF_SECONDS = 3600  # after HTTP 429 (the usual status; Open-Meteo does not say)

_CACHE: dict[str, tuple[float, "Snapshot"]] = {}
_BACKOFF = {"until": 0.0}                # time.monotonic() before which no live fetch is tried
_FETCHES: dict = {"day": None, "count": 0}
_monotonic = time.monotonic


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Snapshot:
    city: str
    #: analyze() of the response: periods, trends, grid, data quality.
    analysis: dict
    is_live: bool
    #: When this data was fetched (a fixture's own date when it is a fixture).
    retrieved_at: str
    #: The date range that was asked for.
    requested: dict


class FetchError(Exception):
    """A response that cannot be used: too large, not the documented shape,
    or Open-Meteo reporting an error."""


# --- fetching -----------------------------------------------------------------


def _window(today: date) -> tuple[date, date]:
    return date(today.year - BASELINE_YEARS, 1, 1), today - timedelta(days=END_LAG_DAYS)


def _params(city: cities.City, start: date, end: date) -> dict:
    return {
        "latitude": city.lat,
        "longitude": city.lon,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": ",".join(DAILY_VARS),
        "models": MODEL,
        "timezone": city.timezone,
    }


def _get_json(params: dict) -> dict:
    with httpx.stream("GET", API_URL, params=params, timeout=TIMEOUT,
                      follow_redirects=False) as resp:
        resp.raise_for_status()  # a redirect is an error too: we never follow one
        declared = resp.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > MAX_BYTES:
            raise FetchError(f"response of {declared} bytes is over the {MAX_BYTES} cap")
        body = bytearray()
        for chunk in resp.iter_bytes():
            body += chunk
            if len(body) > MAX_BYTES:
                raise FetchError(f"response is over the {MAX_BYTES} byte cap")
    try:
        doc = json.loads(bytes(body))
    except (ValueError, RecursionError) as exc:  # RecursionError: absurdly nested JSON
        raise FetchError("response is not JSON") from exc
    if not isinstance(doc, dict):
        raise FetchError("response is not a JSON object")
    if doc.get("error"):  # {"error": true, "reason": "..."} (normally with HTTP 400)
        raise FetchError("Open-Meteo reported an error")
    return doc


def _fetch_raw(city_key: str, now: datetime) -> dict:
    """One live request for a city, in the shape the fixture is saved in. Raises
    httpx.HTTPError or FetchError, and never returns a response analyze() cannot
    read."""
    city = cities.CITIES[city_key]
    start, end = _window(now.date())
    params = _params(city, start, end)
    doc = _get_json(params)
    analyze(doc)  # raises FetchError for anything unusable
    return {
        "source": f"{SOURCE} historical weather API (ERA5, {HOST}), snapshot",
        "fetched_at": now.isoformat(timespec="seconds"),
        "city": city_key,
        "request": {"url": API_URL, "params": params},
        "response": doc,
    }


# --- parsing ------------------------------------------------------------------


def _value(x, low: float, high: float) -> float | None:
    """A daily value, or None when it is missing or not credible."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    try:
        value = float(x)
    except OverflowError:
        return None
    return value if math.isfinite(value) and low <= value <= high else None


def _day(text) -> date:
    if not isinstance(text, str) or len(text) != 10:
        raise FetchError("a day in the response is not yyyy-mm-dd")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise FetchError("a day in the response is not a date") from exc


def daily_from_response(doc: dict) -> dict[date, tuple[float | None, float | None]]:
    """{day: (rain_mm, mean_temp_c)} with None for a missing value. Raises
    FetchError unless the response has the documented shape and the units we
    compute in — it never guesses."""
    daily, units = doc.get("daily"), doc.get("daily_units")
    if not isinstance(daily, dict) or not isinstance(units, dict):
        raise FetchError("response has no daily data")
    for name, unit in UNITS.items():
        if units.get(name) != unit:
            raise FetchError(f"{name} is not in {unit}")
    times = daily.get("time")
    if not isinstance(times, list) or not times or len(times) > MAX_DAYS:
        raise FetchError("response has no usable list of days")
    rain, temp = daily.get("precipitation_sum"), daily.get("temperature_2m_mean")
    if not isinstance(rain, list) or not isinstance(temp, list):
        raise FetchError("response lacks a requested variable")
    if not len(times) == len(rain) == len(temp):
        raise FetchError("daily lists differ in length")
    days: dict[date, tuple] = {}
    for stamp, r, t in zip(times, rain, temp):
        day = _day(stamp)
        if day in days:
            raise FetchError("a day appears twice")
        days[day] = (_value(r, 0.0, RAIN_MAX_MM), _value(t, *TEMP_RANGE_C))
    return days


# --- aggregates ---------------------------------------------------------------


def _by_month(days: dict) -> dict[tuple[int, int], dict]:
    """{(year, month): {"rain": [values present], "temp": [values present]}}"""
    months: dict[tuple[int, int], dict] = {}
    for day, (rain, temp) in days.items():
        slot = months.setdefault((day.year, day.month), {"rain": [], "temp": []})
        if rain is not None:
            slot["rain"].append(rain)
        if temp is not None:
            slot["temp"].append(temp)
    return months


def _period(months: dict, year: int, wanted) -> dict | None:
    """One period (some months of one year): total rain and mean temperature,
    each None unless every day of the period has a value. None if no day of it
    is in the data at all."""
    need, rain, temp, seen = 0, [], [], False
    for month in wanted:
        need += calendar.monthrange(year, month)[1]
        slot = months.get((year, month))
        if slot is not None:
            seen = True
            rain += slot["rain"]
            temp += slot["temp"]
    if not seen:
        return None
    return {
        "days": need,
        "rain_days": len(rain),
        "temp_days": len(temp),
        "rain_mm": round(math.fsum(rain), 2) if len(rain) == need else None,
        "temp_mean_c": round(math.fsum(temp) / need, 2) if len(temp) == need else None,
    }


# Two-sided 95% critical values of Student's t by degrees of freedom (standard
# table; checked against the distribution by test_t_table_matches_the_distribution).
_T95 = ((1, 12.706), (2, 4.303), (3, 3.182), (4, 2.776), (5, 2.571), (6, 2.447), (7, 2.365),
        (8, 2.306), (9, 2.262), (10, 2.228), (11, 2.201), (12, 2.179), (13, 2.160), (14, 2.145),
        (15, 2.131), (16, 2.120), (17, 2.110), (18, 2.101), (19, 2.093), (20, 2.086),
        (21, 2.080), (22, 2.074), (23, 2.069), (24, 2.064), (25, 2.060), (26, 2.056),
        (27, 2.052), (28, 2.048), (29, 2.045), (30, 2.042), (40, 2.021), (60, 2.000),
        (120, 1.980))


def t_critical_95(df: int) -> float:
    """The table value for the largest tabulated df not above `df` (so never
    smaller than the exact value: slightly conservative between rows)."""
    value = _T95[0][1]
    for known, crit in _T95:
        if known <= df:
            value = crit
    return value


def linear_trend(points: list[tuple[int, float]]) -> dict:
    """Least-squares line through (year, value) points; see the TREND section of
    the module docstring. Always returns a dict with a `status`."""
    n = len(points)
    if n < MIN_TREND_YEARS:
        return {"status": "insufficient_data", "n": n, "min_years": MIN_TREND_YEARS}
    xs, ys = [float(x) for x, _ in points], [float(y) for _, y in points]
    xbar, ybar = math.fsum(xs) / n, math.fsum(ys) / n
    sxx = math.fsum((x - xbar) ** 2 for x in xs)
    if sxx == 0:  # every point in the same year: no line to fit
        return {"status": "insufficient_data", "n": n, "min_years": MIN_TREND_YEARS}
    slope = math.fsum((x - xbar) * (y - ybar) for x, y in zip(xs, ys)) / sxx
    intercept = ybar - slope * xbar
    sse = math.fsum((y - intercept - slope * x) ** 2 for x, y in zip(xs, ys))
    df = n - 2
    stderr = math.sqrt(sse / df / sxx)
    # A perfect fit leaves no residual to judge the slope against.
    t = slope / stderr if stderr > 1e-12 * max(1.0, abs(slope)) else None
    significant = (slope != 0) if t is None else abs(t) >= t_critical_95(df)
    return {
        "status": "ok",
        "n": n,
        "first_year": int(min(xs)),
        "last_year": int(max(xs)),
        "mean": round(ybar, 2),
        "slope_per_decade": round(10 * slope, 3),
        "stderr_per_decade": round(10 * stderr, 3),
        "t": None if t is None else round(t, 2),
        "significant_95": bool(significant),
    }


def _trends_of(rows: list[dict]) -> dict:
    out = {}
    for metric in ("rain_mm", "temp_mean_c"):
        out[metric] = linear_trend([(r["year"], r[metric]) for r in rows if r[metric] is not None])
    return out


def analyze(doc: dict) -> dict:
    """Everything computed from one Open-Meteo response: monthly, seasonal and
    annual rows, a trend for each month, season and the year, the grid cell, and
    how much data was missing. Pure and deterministic; raises FetchError."""
    days = daily_from_response(doc)
    months = _by_month(days)
    years = sorted({year for year, _ in months})

    monthly = [{"year": y, "month": m, **_period(months, y, (m,))} for y, m in sorted(months)]
    seasonal, annual = [], []
    for year in years:
        for season, wanted in SEASONS.items():
            period = _period(months, year, wanted)
            if period is not None:
                seasonal.append({"year": year, "season": season, "months": list(wanted), **period})
        annual.append({"year": year, **_period(months, year, range(1, 13))})

    trends = {
        "month": {str(m): _trends_of([r for r in monthly if r["month"] == m])
                  for m in range(1, 13)},
        "season": {s: _trends_of([r for r in seasonal if r["season"] == s]) for s in SEASONS},
        "year": _trends_of(annual),
    }

    have = sorted(d for d, (rain, temp) in days.items() if rain is not None or temp is not None)
    last = have[-1] if have else None
    inside = [v for d, v in days.items() if last is not None and d <= last]
    quality = {
        "days": len(days),
        "first_date": min(days).isoformat(),
        "last_date_with_data": last.isoformat() if last else None,
        "trailing_days_without_data": sum(1 for d in days if last is None or d > last),
        "rain_gap_days": sum(1 for rain, _ in inside if rain is None),
        "temp_gap_days": sum(1 for _, temp in inside if temp is None),
    }
    grid = {k: _value(doc.get(k), -1000.0, 10000.0) for k in ("latitude", "longitude", "elevation")}
    return {"grid": grid, "monthly": monthly, "seasonal": seasonal, "annual": annual,
            "trends": trends, "data_quality": quality}


# --- snapshots, modes, cache --------------------------------------------------


def fixture_path(city_key: str) -> Path:
    return config.FIXTURES_DIR / "open_meteo" / f"{city_key}.json"


def _snapshot_from_raw(city_key: str, raw: dict, is_live: bool) -> Snapshot | None:
    """Analyse a saved or fresh bundle; None if it is not the shape _fetch_raw
    makes or cannot be analysed."""
    if not isinstance(raw, dict) or not isinstance(raw.get("response"), dict):
        return None
    stamp = raw.get("fetched_at")
    if not isinstance(stamp, str):
        return None
    try:
        fetched = datetime.fromisoformat(stamp)
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        retrieved_at = fetched.astimezone(timezone.utc).isoformat(timespec="seconds")
        analysis = analyze(raw["response"])
    except (ValueError, OverflowError, FetchError):
        return None
    request = raw.get("request") if isinstance(raw.get("request"), dict) else {}
    params = request.get("params") if isinstance(request.get("params"), dict) else {}
    requested = {"start_date": params.get("start_date"), "end_date": params.get("end_date")}
    return Snapshot(city_key, analysis, is_live, retrieved_at, requested)


def _live(city_key: str) -> Snapshot:
    snap = _snapshot_from_raw(city_key, _fetch_raw(city_key, _utcnow()), True)
    if snap is None:  # _fetch_raw only returns what _snapshot_from_raw accepts
        raise FetchError("unreadable response")
    return snap


def _fixture(city_key: str) -> Snapshot | None:
    try:
        raw = json.loads(fixture_path(city_key).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _snapshot_from_raw(city_key, raw, False)


def _fetch_allowed() -> bool:
    """Counts a live fetch against today's allowance (by UTC date); False once spent."""
    today = _utcnow().date()
    if _FETCHES["day"] != today:
        _FETCHES.update(day=today, count=0)
    if _FETCHES["count"] >= MAX_LIVE_FETCHES_PER_DAY:
        _LOG.warning("%d live Open-Meteo fetches already made today; not making another",
                     MAX_LIVE_FETCHES_PER_DAY)
        return False
    _FETCHES["count"] += 1
    return True


def snapshot(city_key: str) -> Snapshot | None:
    """Climate for a demo city from the current mode's source, or None when there
    is nothing to show (which is not the same as "no trend")."""
    if config.WEATHER_MODE == "fixtures":
        return _fixture(city_key)

    now = _monotonic()
    cached = _CACHE.get(city_key)
    if cached and now - cached[0] < TTL_SECONDS:
        return cached[1]

    if now >= _BACKOFF["until"] and _fetch_allowed():
        try:
            fresh = _live(city_key)
        except (httpx.HTTPError, FetchError) as exc:
            limited = isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429
            pause = RATE_LIMIT_BACKOFF_SECONDS if limited else FAILURE_BACKOFF_SECONDS
            _BACKOFF["until"] = _monotonic() + pause
            _LOG.warning("live Open-Meteo fetch for %s failed (%s: %s); not retrying for %ds",
                         city_key, type(exc).__name__, exc, pause)
        else:
            _CACHE[city_key] = (_monotonic(), fresh)
            return fresh

    # The live fetch failed just now, or is being left alone (back-off, daily allowance).
    if config.WEATHER_MODE == "live":
        return None  # live mode never replays a snapshot
    return _fixture(city_key)


def cache_clear() -> None:
    _CACHE.clear()
    _BACKOFF["until"] = 0.0
    _FETCHES.update(day=None, count=0)


def city_key_for(text: str | None) -> str | None:
    """A demo city's key from its key or any name the registry knows; None for
    anything else (travel-only destinations included)."""
    if not isinstance(text, str):
        return None
    key = text.strip().lower()
    if key in cities.CITIES:
        return key
    resolved = cities.resolve(text)
    return resolved if resolved in cities.CITIES else None


def public(city: str | None) -> dict:
    """Climate for one demo city with the source metadata every surface must
    show. `status` is "ok" when ERA5 data was read (live, or a dated snapshot
    when `is_live` is false), "unavailable" when none could be — then every data
    field is None, which a UI must show as "not available", never as zero or as
    "no change" (plan.md §2 principle 3) — and "unsupported_city" for anything
    that is not a demo city."""
    key = city_key_for(city)
    result = {
        "status": "unsupported_city" if key is None else "unavailable",
        "city": key,
        "is_live": False,
        "retrieved_at": None,
        "requested": None,
        "grid": None,
        "monthly": None,
        "seasonal": None,
        "annual": None,
        "trends": None,
        "data_quality": None,
        "source": SOURCE,
        "model": MODEL,
        "label": LABEL,
        "credit": dict(CREDIT),
        "changes_note": CHANGES_NOTE,
        "calendar_note": CALENDAR_NOTE,
        "licence_url": LICENCE_URL,
        "terms_url": TERMS_URL,
        "seasons": {name: list(months) for name, months in SEASONS.items()},
        "units": dict(UNITS),
        "min_trend_years": MIN_TREND_YEARS,
    }
    snap = snapshot(key) if key is not None else None
    if snap is not None:
        result.update(copy.deepcopy(snap.analysis))
        result.update(status="ok", is_live=snap.is_live, retrieved_at=snap.retrieved_at,
                      requested=dict(snap.requested))
    return result


# --- fixture refresh ----------------------------------------------------------


def write_fixture(city_key: str, path: Path | None = None) -> Path:
    """Fetch the live service for one demo city and save the raw response as its
    fixture. Raises when the fetch fails, so a failed refresh never overwrites a
    good snapshot."""
    if city_key not in cities.CITIES:
        raise ValueError(f"{city_key!r} is not a demo city")
    target = Path(path) if path is not None else fixture_path(city_key)
    raw = _fetch_raw(city_key, _utcnow())
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False, separators=(",", ":")) + "\n",
                   encoding="utf-8")
    os.replace(tmp, target)
    return target


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    wanted = sys.argv[1:] or ["chennai"]
    for position, name in enumerate(wanted):
        if position:
            time.sleep(70)  # a large request is several "calls" to Open-Meteo: keep the pace low
        print(write_fixture(name))
