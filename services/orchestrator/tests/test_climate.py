"""climate.py: Open-Meteo ERA5 history — response validation, monthly / seasonal /
annual aggregates, the least-squares trend, live fetch with bounds, cache,
back-off, daily allowance and fixture fallback, and the rule that a failed fetch
is never zero rainfall and never "no trend" (CLM-2). No test touches the real
service: the fetch is stubbed (httpx.stream), and the fixtures in
data/fixtures/open_meteo/ are real responses saved from archive-api.open-meteo.com.

Three kinds of input. "Real" tests read those fixtures and check the module
against an independent recomputation in exact arithmetic (fractions.Fraction)
straight from the raw daily values. A guard test pins the snapshot date: if a
fixture is refreshed, the few tests that pin headline numbers must be re-pinned.
"Synthetic" tests build tiny daily records by hand, only to exercise logic —
they are unit-test inputs, not climate data anyone should read.
"""

import calendar
import copy
import json
import math
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction

import cities
import climate
import config
import httpx
import pytest

NOW = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
DEMO = ("chennai", "mumbai", "delhi")
SNAPSHOT_DAY = "2026-10-29"
CHENNAI_SNAPSHOT = "2026-10-29T12:51:12+00:00"
RAW = {k: json.loads(climate.fixture_path(k).read_text(encoding="utf-8")) for k in DEMO}


@pytest.fixture(autouse=True)
def _fresh_climate(monkeypatch):
    climate.cache_clear()
    monkeypatch.setattr(climate, "_utcnow", lambda: NOW)
    yield
    climate.cache_clear()


# --- helpers -------------------------------------------------------------------


def make_doc(start, end, rain=lambda d: 1.0, temp=lambda d: 30.0, **over):
    """A synthetic Open-Meteo response with one value per day (unit-test input)."""
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    doc = {
        "latitude": 13.0, "longitude": 80.25, "elevation": 12.0, "utc_offset_seconds": 19800,
        "timezone": "Asia/Kolkata",
        "daily_units": {"time": "iso8601", "precipitation_sum": "mm", "temperature_2m_mean": "°C"},
        "daily": {"time": [d.isoformat() for d in days],
                  "precipitation_sum": [rain(d) for d in days],
                  "temperature_2m_mean": [temp(d) for d in days]},
    }
    doc.update(over)
    return doc


def set_day(doc, day, rain=..., temp=...):
    """Change one day of a synthetic response; `None` makes a value missing."""
    i = doc["daily"]["time"].index(day.isoformat())
    if rain is not ...:
        doc["daily"]["precipitation_sum"][i] = rain
    if temp is not ...:
        doc["daily"]["temperature_2m_mean"][i] = temp


def row(rows, **match):
    (found,) = [r for r in rows if all(r[k] == v for k, v in match.items())]
    return found


class Network:
    """Stands in for httpx.stream. `calls` records each request; `reply` is a
    callable (params -> (status, body[, headers])) or an Exception to raise."""

    def __init__(self):
        self.calls = []
        self.reply = self.fixture_reply

    @staticmethod
    def fixture_reply(params):
        for raw in RAW.values():
            if raw["request"]["params"]["latitude"] == params["latitude"]:
                return 200, raw["response"]
        return 200, RAW["chennai"]["response"]


@pytest.fixture
def net(monkeypatch):
    stub = Network()

    @contextmanager
    def fake_stream(method, url, params=None, timeout=None, follow_redirects=None, **_):
        stub.calls.append({"method": method, "url": url, "params": dict(params or {}),
                           "timeout": timeout, "follow_redirects": follow_redirects})
        reply = stub.reply(dict(params or {})) if callable(stub.reply) else stub.reply
        if isinstance(reply, Exception):
            raise reply
        status, body, *rest = reply
        if isinstance(body, list):  # chunks, sent with no declared length (chunked)
            content = iter(body)
        else:
            content = body if isinstance(body, bytes) else json.dumps(body).encode()
        yield httpx.Response(status, content=content, headers=(rest[0] if rest else {}),
                             request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "stream", fake_stream)
    return stub


@pytest.fixture
def auto_mode(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "auto")


@pytest.fixture
def live_mode(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "live")


@pytest.fixture
def fixtures_mode(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "fixtures")


@pytest.fixture
def fixture_dir(monkeypatch, tmp_path):
    """Points the module at an empty fixtures folder in tmp_path; returns it."""
    monkeypatch.setattr(climate, "fixture_path", lambda key: tmp_path / f"{key}.json")
    return tmp_path


def oversize_json():
    """Valid JSON over the size cap, so only the cap can reject it."""
    return b'{"padding":"' + b"x" * climate.MAX_BYTES + b'"}'


def oversize_chunks():
    """The same, sent as chunks with no Content-Length: only the cap on the
    streamed bytes can stop it."""
    chunk = b"x" * 100_000
    return [b'{"padding":"'] + [chunk] * (climate.MAX_BYTES // len(chunk) + 1) + [b'"}']


def shifted(doc, **changes):
    out = copy.deepcopy(doc)
    out.update(changes)
    return out


def with_daily(doc, **changes):
    out = copy.deepcopy(doc)
    out["daily"].update(changes)
    return out


GOOD = RAW["chennai"]["response"]
# Ways a live fetch can fail. None of them may ever read as zero rain or "no trend".
FAILURES = {
    "timeout": httpx.ConnectTimeout("timed out"),
    "server_error": (500, {"reason": "boom"}),
    "rate_limited_429": (429, {"reason": "Daily API request limit exceeded"}),
    "open_meteo_400": (400, {"error": True, "reason": "Invalid value: not_a_variable"}),
    "redirect": (302, b"", {"location": "https://elsewhere.example/"}),
    "not_json": (200, b"<html>maintenance</html>"),
    "json_array": (200, b"[]"),
    "error_flag_with_200": (200, {"error": True, "reason": "something went wrong"}),
    # Open-Meteo's error flag is honoured even next to otherwise valid-looking data.
    "error_flag_beside_good_data": (200, shifted(GOOD, error=True, reason="partial failure")),
    "no_daily": (200, {"latitude": 13.0}),
    "wrong_rain_unit": (200, shifted(GOOD, daily_units={
        "time": "iso8601", "precipitation_sum": "inch", "temperature_2m_mean": "°C"})),
    "wrong_temp_unit": (200, shifted(GOOD, daily_units={
        "time": "iso8601", "precipitation_sum": "mm", "temperature_2m_mean": "°F"})),
    "lists_differ_in_length": (200, with_daily(GOOD, precipitation_sum=[1.0])),
    "duplicate_day": (200, with_daily(GOOD, time=GOOD["daily"]["time"][:5] * 2,
                                      precipitation_sum=[1.0] * 10,
                                      temperature_2m_mean=[30.0] * 10)),
    "bad_date": (200, with_daily(GOOD, time=["31/12/2025"] + GOOD["daily"]["time"][1:])),
    "too_many_days": (200, make_doc(date(1900, 1, 1), date(1900, 1, 1) +
                                    timedelta(days=climate.MAX_DAYS))),
    "deeply_nested": (200, b"[" * 100_000 + b"]" * 100_000),
    "too_big": (200, oversize_json()),
    "too_big_streamed": (200, oversize_chunks()),
    "declared_too_big": (200, b"{}", {"content-length": str(climate.MAX_BYTES + 1)}),
}


# --- the fixtures themselves (real) ----------------------------------------------


def test_fixtures_are_the_snapshots_these_tests_pin():
    # If you refresh data/fixtures/open_meteo/*.json (python climate.py <city> ...), the
    # tests that pin headline numbers below must be re-pinned too.
    assert RAW["chennai"]["fetched_at"] == CHENNAI_SNAPSHOT
    assert all(raw["fetched_at"].startswith(SNAPSHOT_DAY) for raw in RAW.values())


@pytest.mark.parametrize("key", DEMO)
def test_fixture_is_the_raw_response_to_the_request_we_make(key):
    raw, city = RAW[key], cities.CITIES[key]
    assert raw["source"].startswith("Open-Meteo historical weather API (ERA5, archive-api")
    assert raw["city"] == key
    assert raw["request"]["url"] == "https://archive-api.open-meteo.com/v1/archive"
    assert raw["request"]["params"] == {
        "latitude": city.lat, "longitude": city.lon, "start_date": "1996-01-01",
        "end_date": "2026-10-22", "daily": "precipitation_sum,temperature_2m_mean",
        "models": "era5", "timezone": "Asia/Kolkata"}
    assert "SIMULATED" not in json.dumps(raw)
    response = raw["response"]
    assert response["daily_units"] == {
        "time": "iso8601", "precipitation_sum": "mm", "temperature_2m_mean": "°C"}
    assert response["timezone"] == "Asia/Kolkata" and response["utc_offset_seconds"] == 19800
    # Nothing was clipped: one value per day from the first to the last day asked for.
    start, end = date(1996, 1, 1), date(2026, 10, 22)
    assert len(response["daily"]["time"]) == (end - start).days + 1 == 11253
    assert response["daily"]["time"][0] == "1996-01-01"
    assert response["daily"]["time"][-1] == "2026-10-22"


@pytest.mark.parametrize("key", DEMO)
def test_fixture_grid_cell_is_era5s_quarter_degree_grid(key):
    grid = climate.analyze(RAW[key]["response"])["grid"]
    assert grid["latitude"] % 0.25 == 0 and grid["longitude"] % 0.25 == 0
    # The cell is a few kilometres from the city, not another place.
    city = cities.CITIES[key]
    assert abs(grid["latitude"] - city.lat) < 0.25 and abs(grid["longitude"] - city.lon) < 0.25


# --- aggregates against an independent exact recomputation (real) -----------------


_RAW_MONTHS: dict = {}


def raw_months(key):
    """{(year, month): ([rain values], [temperature values])} straight from the raw
    fixture arrays, with None kept for a missing value; built once per city."""
    if key not in _RAW_MONTHS:
        d = RAW[key]["response"]["daily"]
        months: dict = {}
        for stamp, r, t in zip(d["time"], d["precipitation_sum"], d["temperature_2m_mean"]):
            slot = months.setdefault((int(stamp[:4]), int(stamp[5:7])), ([], []))
            slot[0].append(r)
            slot[1].append(t)
        _RAW_MONTHS[key] = months
    return _RAW_MONTHS[key]


def oracle_period(key, year, months):
    """(rain total, mean temperature) over the days of `months` in `year`, in exact
    arithmetic; each None unless every day of the period has a value."""
    need = sum(calendar.monthrange(year, m)[1] for m in months)
    rains = [r for m in months for r in raw_months(key).get((year, m), ([], []))[0]]
    temps = [t for m in months for t in raw_months(key).get((year, m), ([], []))[1]]
    rain = None if len(rains) != need or None in rains else sum(Fraction(str(r)) for r in rains)
    temp = (None if len(temps) != need or None in temps
            else sum(Fraction(str(t)) for t in temps) / need)
    return rain, temp


def close(value, exact, tol=0.0051):
    if exact is None:
        return value is None
    return value is not None and abs(value - float(exact)) <= tol


@pytest.mark.parametrize("key", DEMO)
def test_every_month_matches_the_exact_recomputation(key):
    analysis = climate.analyze(RAW[key]["response"])
    assert len(analysis["monthly"]) == 31 * 12 - 2  # Jan 1996 .. Oct 2026
    for r in analysis["monthly"]:
        rain, temp = oracle_period(key, r["year"], (r["month"],))
        assert close(r["rain_mm"], rain), r
        assert close(r["temp_mean_c"], temp), r
        assert r["days"] == calendar.monthrange(r["year"], r["month"])[1]


@pytest.mark.parametrize("key", DEMO)
def test_every_season_and_year_matches_the_exact_recomputation(key):
    analysis = climate.analyze(RAW[key]["response"])
    for r in analysis["seasonal"]:
        rain, temp = oracle_period(key, r["year"], climate.SEASONS[r["season"]])
        assert close(r["rain_mm"], rain), r
        assert close(r["temp_mean_c"], temp), r
    for r in analysis["annual"]:
        rain, temp = oracle_period(key, r["year"], range(1, 13))
        assert close(r["rain_mm"], rain), r
        assert close(r["temp_mean_c"], temp), r


def oracle_trend(points):
    """Slope, its standard error and the 95% decision, from exact arithmetic."""
    n = len(points)
    xs = [Fraction(x) for x, _ in points]
    ys = [Fraction(str(y)) for _, y in points]
    xbar, ybar = sum(xs) / n, sum(ys) / n
    sxx = sum((x - xbar) ** 2 for x in xs)
    sxy = sum((x - xbar) * (y - ybar) for x, y in zip(xs, ys))
    syy = sum((y - ybar) ** 2 for y in ys)
    slope = sxy / sxx
    sse = syy - slope * sxy
    stderr = math.sqrt(float(sse / (n - 2) / sxx))
    return float(slope), stderr, abs(float(slope)) / stderr, float(ybar)


@pytest.mark.parametrize("key", DEMO)
def test_every_trend_matches_the_exact_recomputation(key):
    analysis = climate.analyze(RAW[key]["response"])
    groups = [("month", [(str(m), [r for r in analysis["monthly"] if r["month"] == m])
                         for m in range(1, 13)]),
              ("season", [(s, [r for r in analysis["seasonal"] if r["season"] == s])
                          for s in climate.SEASONS]),
              ("year", [(None, analysis["annual"])])]
    checked = 0
    for kind, items in groups:
        for name, rows in items:
            for metric in ("rain_mm", "temp_mean_c"):
                trend = analysis["trends"][kind][name][metric] if name else \
                    analysis["trends"][kind][metric]
                points = [(r["year"], r[metric]) for r in rows if r[metric] is not None]
                assert trend["status"] == "ok" and trend["n"] == len(points) >= 30
                slope, stderr, t_abs, mean = oracle_trend(points)
                assert abs(trend["slope_per_decade"] - 10 * slope) <= 0.0006
                assert abs(trend["stderr_per_decade"] - 10 * stderr) <= 0.0006
                assert abs(trend["mean"] - mean) <= 0.0051
                crit = climate.t_critical_95(len(points) - 2)
                if abs(t_abs - crit) > 1e-6:
                    assert trend["significant_95"] is (t_abs >= crit)
                checked += 1
    assert checked == (12 + 4 + 1) * 2


def test_real_chennai_headline_figures_are_pinned():
    analysis = climate.analyze(RAW["chennai"]["response"])
    year = analysis["trends"]["year"]
    assert year["rain_mm"]["mean"] == 1034.83 and year["rain_mm"]["significant_95"] is False
    assert year["temp_mean_c"]["slope_per_decade"] == 0.243
    assert year["temp_mean_c"]["significant_95"] is True
    assert (year["rain_mm"]["first_year"], year["rain_mm"]["last_year"]) == (1996, 2025)
    june = analysis["trends"]["month"]["6"]["rain_mm"]
    assert (june["n"], june["first_year"], june["last_year"]) == (31, 1996, 2026)
    assert analysis["grid"] == {"latitude": 13.0, "longitude": 80.25, "elevation": 12.0}


def test_real_incomplete_periods_have_no_figures_and_stay_out_of_trends():
    analysis = climate.analyze(RAW["chennai"]["response"])
    # The data ends 22 Oct 2026: October is partial, so are post-monsoon and the year.
    october = row(analysis["monthly"], year=2026, month=10)
    assert (october["rain_days"], october["days"]) == (22, 31)
    assert october["rain_mm"] is None and october["temp_mean_c"] is None
    post = row(analysis["seasonal"], year=2026, season="post_monsoon")
    assert (post["rain_days"], post["days"]) == (22, 92) and post["rain_mm"] is None
    assert row(analysis["annual"], year=2026)["rain_mm"] is None
    # ...and a complete September 2026 is used.
    assert row(analysis["monthly"], year=2026, month=9)["rain_mm"] is not None
    oct_trend = analysis["trends"]["month"]["10"]["rain_mm"]
    assert oct_trend["last_year"] == 2025 and oct_trend["n"] == 30
    quality = analysis["data_quality"]
    assert quality == {"days": 11253, "first_date": "1996-01-01",
                       "last_date_with_data": "2026-10-22", "trailing_days_without_data": 0,
                       "rain_gap_days": 0, "temp_gap_days": 0}


# --- missing data, periods and units (synthetic) -----------------------------------


def test_a_missing_day_is_missing_not_zero():
    doc = make_doc(date(2025, 6, 1), date(2025, 6, 30), rain=lambda d: 2.0)
    set_day(doc, date(2025, 6, 10), rain=None)
    june = climate.analyze(doc)["monthly"][0]
    assert june["rain_days"] == 29 and june["days"] == 30
    assert june["rain_mm"] is None  # not 58.0, and not 58.0 + 0
    assert june["temp_mean_c"] == 30.0 and june["temp_days"] == 30  # temperature unaffected


def test_rain_and_temperature_are_judged_for_completeness_separately():
    doc = make_doc(date(2025, 6, 1), date(2025, 6, 30), rain=lambda d: 1.5)
    set_day(doc, date(2025, 6, 3), temp=None)
    june = climate.analyze(doc)["monthly"][0]
    assert june["rain_mm"] == 45.0 and june["temp_mean_c"] is None and june["temp_days"] == 29


def test_a_whole_month_missing_makes_its_season_and_year_incomplete():
    doc = make_doc(date(2024, 1, 1), date(2024, 12, 31))
    doc["daily"]["precipitation_sum"] = [
        None if d.startswith("2024-07") else v
        for d, v in zip(doc["daily"]["time"], doc["daily"]["precipitation_sum"])]
    analysis = climate.analyze(doc)
    assert row(analysis["monthly"], month=7)["rain_mm"] is None
    assert row(analysis["monthly"], month=8)["rain_mm"] == 31.0
    assert row(analysis["seasonal"], season="monsoon")["rain_mm"] is None
    assert row(analysis["seasonal"], season="winter")["rain_mm"] == 60.0  # 31 + 29 days
    assert row(analysis["annual"], year=2024)["rain_mm"] is None
    assert row(analysis["annual"], year=2024)["temp_mean_c"] == 30.0


@pytest.mark.parametrize("year, feb_days", [(2024, 29), (2023, 28), (2000, 29), (1900, 28)])
def test_february_needs_every_day_of_a_leap_or_ordinary_year(year, feb_days):
    full = make_doc(date(year, 2, 1), date(year, 2, feb_days))
    assert climate.analyze(full)["monthly"][0]["rain_mm"] == float(feb_days)
    short = make_doc(date(year, 2, 1), date(year, 2, feb_days - 1))
    assert climate.analyze(short)["monthly"][0]["rain_mm"] is None


def test_annual_total_needs_365_or_366_days():
    leap = climate.analyze(make_doc(date(2024, 1, 1), date(2024, 12, 31)))["annual"][0]
    ordinary = climate.analyze(make_doc(date(2025, 1, 1), date(2025, 12, 31)))["annual"][0]
    assert (leap["days"], leap["rain_mm"]) == (366, 366.0)
    assert (ordinary["days"], ordinary["rain_mm"]) == (365, 365.0)


def test_seasonal_temperature_weighs_each_day_not_each_month():
    # Jan (31 days) at 20 °C and Feb 2025 (28 days) at 30 °C: the winter mean is the mean
    # of the 59 days, 24.746..., not the mean of the two monthly means, 25.
    doc = make_doc(date(2025, 1, 1), date(2025, 2, 28),
                   temp=lambda d: 20.0 if d.month == 1 else 30.0)
    winter = row(climate.analyze(doc)["seasonal"], season="winter")
    assert winter["temp_mean_c"] == round((31 * 20 + 28 * 30) / 59, 2) == 24.75


def test_sums_do_not_depend_on_the_order_of_the_days():
    start, end = date(2025, 6, 1), date(2025, 6, 30)
    doc = make_doc(start, end, rain=lambda d: 0.1 * d.day)
    reversed_doc = copy.deepcopy(doc)
    for key in ("time", "precipitation_sum", "temperature_2m_mean"):
        reversed_doc["daily"][key].reverse()
    assert climate.analyze(doc) == climate.analyze(reversed_doc)
    assert climate.analyze(doc)["monthly"][0]["rain_mm"] == 46.5  # 0.1 * (1 + ... + 30)


def test_trailing_days_without_data_are_counted_but_not_gaps():
    doc = make_doc(date(2025, 6, 1), date(2025, 6, 30))
    for day in range(25, 31):
        set_day(doc, date(2025, 6, day), rain=None, temp=None)
    set_day(doc, date(2025, 6, 10), rain=None)
    quality = climate.analyze(doc)["data_quality"]
    assert quality["last_date_with_data"] == "2025-06-24"
    assert quality["trailing_days_without_data"] == 6
    assert (quality["rain_gap_days"], quality["temp_gap_days"]) == (1, 0)


@pytest.mark.parametrize(
    "bad",
    [True, False, "5", None, float("nan"), float("inf"), -float("inf"), 10**400, -1.0,
     climate.RAIN_MAX_MM + 1, [], {}],
)
def test_a_value_that_is_not_a_credible_rainfall_is_missing(bad):
    doc = make_doc(date(2025, 6, 1), date(2025, 6, 2))
    set_day(doc, date(2025, 6, 1), rain=bad)
    days = climate.daily_from_response(doc)
    assert days[date(2025, 6, 1)][0] is None
    assert days[date(2025, 6, 2)][0] == 1.0


@pytest.mark.parametrize("bad", [True, "30", None, float("nan"), 10**400, -91.0, 61.0])
def test_a_value_that_is_not_a_credible_temperature_is_missing(bad):
    doc = make_doc(date(2025, 6, 1), date(2025, 6, 2))
    set_day(doc, date(2025, 6, 1), temp=bad)
    assert climate.daily_from_response(doc)[date(2025, 6, 1)][1] is None


def test_zero_rainfall_is_a_real_value():
    doc = make_doc(date(2025, 6, 1), date(2025, 6, 30), rain=lambda d: 0.0)
    assert climate.analyze(doc)["monthly"][0]["rain_mm"] == 0.0


@pytest.mark.parametrize(
    "doc",
    [{}, {"daily": {}}, {"daily": [], "daily_units": {}},
     shifted(GOOD, daily_units={"precipitation_sum": "mm"}),
     shifted(GOOD, daily_units={"precipitation_sum": "mm", "temperature_2m_mean": "K"}),
     shifted(GOOD, daily_units={"precipitation_sum": "inch", "temperature_2m_mean": "°C"}),
     with_daily(GOOD, time=[]), with_daily(GOOD, time="2025-06-01"),
     with_daily(GOOD, precipitation_sum="x"), with_daily(GOOD, temperature_2m_mean=None),
     with_daily(GOOD, precipitation_sum=GOOD["daily"]["precipitation_sum"][:-1]),
     with_daily(GOOD, time=[20250601] + GOOD["daily"]["time"][1:]),
     with_daily(GOOD, time=["2025-6-1"] + GOOD["daily"]["time"][1:]),
     with_daily(GOOD, time=["2025-02-30"] + GOOD["daily"]["time"][1:]),
     with_daily(GOOD, time=[GOOD["daily"]["time"][1]] + GOOD["daily"]["time"][1:])],
)
def test_a_response_of_the_wrong_shape_or_units_is_refused(doc):
    with pytest.raises(climate.FetchError):
        climate.daily_from_response(doc)
    with pytest.raises(climate.FetchError):
        climate.analyze(doc)


def test_the_grid_cell_is_reported_only_when_credible():
    doc = make_doc(date(2025, 6, 1), date(2025, 6, 2), latitude="13", longitude=None,
                   elevation=float("nan"))
    assert climate.analyze(doc)["grid"] == {"latitude": None, "longitude": None, "elevation": None}


# --- the trend (synthetic, hand-checkable) ------------------------------------------


def series(values, first=2000):
    return [(first + i, v) for i, v in enumerate(values)]


def test_a_perfect_rising_line_has_the_exact_slope_and_no_residual():
    trend = climate.linear_trend(series([100 + 5 * i for i in range(12)]))
    assert trend == {"status": "ok", "n": 12, "first_year": 2000, "last_year": 2011,
                     "mean": 127.5, "slope_per_decade": 50.0, "stderr_per_decade": 0.0,
                     "t": None, "significant_95": True}


def test_a_falling_line_has_a_negative_slope():
    trend = climate.linear_trend(series([100 - 2.5 * i for i in range(10)]))
    assert trend["slope_per_decade"] == -25.0 and trend["significant_95"] is True


def test_a_constant_series_has_zero_slope_and_is_not_significant():
    trend = climate.linear_trend(series([7.5] * 15))
    assert trend["slope_per_decade"] == 0.0 and trend["significant_95"] is False
    assert trend["t"] is None and trend["mean"] == 7.5


def test_a_noisy_series_matches_a_hand_worked_regression():
    # x = 0..9, y below, worked by hand: xbar 4.5, ybar 6, Sxx 82.5, Sxy 66, Syy 60.
    # slope = 66 / 82.5 = 0.8 (8.0 per decade); SSE = Syy - slope * Sxy = 60 - 52.8 = 7.2;
    # s2 = 7.2 / 8 = 0.9; se = sqrt(0.9 / 82.5) = 0.10445; t = 0.8 / 0.10445 = 7.66.
    y = [2, 4, 3, 6, 5, 7, 6, 9, 8, 10]
    assert sum((i - 4.5) ** 2 for i in range(10)) == 82.5
    assert sum((i - 4.5) * (v - 6) for i, v in enumerate(y)) == 66
    assert sum((v - 6) ** 2 for v in y) == 60
    trend = climate.linear_trend(series(y))
    assert trend == {"status": "ok", "n": 10, "first_year": 2000, "last_year": 2009,
                     "mean": 6.0, "slope_per_decade": 8.0,
                     "stderr_per_decade": round(10 * math.sqrt(0.9 / 82.5), 3),  # 1.044
                     "t": 7.66, "significant_95": True}  # 7.66 > 2.306 (df 8)
    slope, stderr, t_abs, _ = oracle_trend(series(y))
    assert abs(slope - 0.8) < 1e-12 and abs(stderr - math.sqrt(0.9 / 82.5)) < 1e-12


def test_a_trend_that_cannot_be_told_from_noise_is_not_significant():
    y = [10, 30, 5, 28, 12, 31, 8, 27, 11, 29, 6, 30]  # no pattern: huge scatter, tiny slope
    trend = climate.linear_trend(series(y))
    assert trend["status"] == "ok" and trend["significant_95"] is False
    assert abs(trend["t"]) < 1


@pytest.mark.parametrize("n, status", [(0, "insufficient_data"), (1, "insufficient_data"),
                                       (9, "insufficient_data"), (10, "ok"), (11, "ok")])
def test_a_trend_needs_the_minimum_number_of_years(n, status):
    trend = climate.linear_trend(series([float(i * i % 7) for i in range(n)]))
    assert trend["status"] == status
    if status != "ok":
        assert trend == {"status": status, "n": n, "min_years": climate.MIN_TREND_YEARS}


def test_points_all_in_one_year_give_no_line():
    assert climate.linear_trend([(2000, float(i)) for i in range(12)])["status"] == \
        "insufficient_data"


def test_the_trend_does_not_depend_on_the_order_of_the_points():
    points = series([3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8])
    assert climate.linear_trend(points) == climate.linear_trend(points[::-1])


def test_end_to_end_a_synthetic_rising_rainfall_series_gives_the_exact_trend():
    # Every day of year Y rains (Y - 2000 + 1) mm: June totals 30 * (Y - 1999), slope 30 mm/year.
    doc = make_doc(date(2000, 1, 1), date(2011, 12, 31), rain=lambda d: float(d.year - 1999),
                   temp=lambda d: 25.0)
    trends = climate.analyze(doc)["trends"]
    june = trends["month"]["6"]["rain_mm"]
    assert (june["n"], june["slope_per_decade"], june["significant_95"]) == (12, 300.0, True)
    assert trends["month"]["6"]["temp_mean_c"]["slope_per_decade"] == 0.0
    assert trends["month"]["6"]["temp_mean_c"]["significant_95"] is False
    monsoon = trends["season"]["monsoon"]["rain_mm"]
    assert monsoon["slope_per_decade"] == 1220.0  # 122 days * 1 mm/year * 10
    # A year's total is days(year) * (year - 1999) and 2000, 2004 and 2008 have 366 days, so
    # the annual series is not an exact line; check it against the exact recomputation.
    annual = [(y, (366 if calendar.isleap(y) else 365) * (y - 1999)) for y in range(2000, 2012)]
    slope, _, _, _ = oracle_trend(annual)
    assert trends["year"]["rain_mm"]["slope_per_decade"] == round(10 * slope, 3) == 3650.664


def test_incomplete_years_do_not_count_toward_the_minimum():
    # Twelve years, but three of them have a missing day in June: only nine are complete.
    doc = make_doc(date(2000, 1, 1), date(2011, 12, 31))
    for year in (2003, 2005, 2008):
        set_day(doc, date(year, 6, 15), rain=None)
    assert climate.analyze(doc)["trends"]["month"]["6"]["rain_mm"] == {
        "status": "insufficient_data", "n": 9, "min_years": 10}
    assert climate.analyze(doc)["trends"]["month"]["7"]["rain_mm"]["status"] == "ok"


def test_t_critical_values_are_conservative_between_rows_and_beyond_the_table():
    assert climate.t_critical_95(8) == 2.306 and climate.t_critical_95(28) == 2.048
    assert climate.t_critical_95(35) == climate.t_critical_95(30) == 2.042
    assert climate.t_critical_95(500) == 1.980
    assert climate.t_critical_95(0) == 12.706  # below the table: the largest value


def test_t_table_matches_the_distribution():
    # Integrate Student's t density (Simpson) and check each row covers 95%.
    def pdf(t, df):
        c = math.exp(math.lgamma((df + 1) / 2) - math.lgamma(df / 2)) / math.sqrt(df * math.pi)
        return c * (1 + t * t / df) ** (-(df + 1) / 2)

    def two_sided_mass(x, df, n=4000):
        h = x / n
        total = pdf(0, df) + pdf(x, df)
        total += sum((4 if i % 2 else 2) * pdf(i * h, df) for i in range(1, n))
        return 2 * total * h / 3

    for df, crit in climate._T95:
        mass = 2 / math.pi * math.atan(crit) if df == 1 else two_sided_mass(crit, df)
        assert abs(mass - 0.95) < 5e-4, (df, crit, mass)


# --- the periods, seasons and units ------------------------------------------------


def test_seasons_cover_every_month_exactly_once():
    months = sorted(m for ms in climate.SEASONS.values() for m in ms)
    assert months == list(range(1, 13))
    assert climate.SEASONS["monsoon"] == (6, 7, 8, 9)


def test_result_rows_have_a_stable_shape():
    analysis = climate.analyze(RAW["chennai"]["response"])
    assert set(analysis) == {"grid", "monthly", "seasonal", "annual", "trends", "data_quality"}
    assert set(analysis["monthly"][0]) == {"year", "month", "days", "rain_days", "temp_days",
                                           "rain_mm", "temp_mean_c"}
    assert set(analysis["seasonal"][0]) == {"year", "season", "months", "days", "rain_days",
                                            "temp_days", "rain_mm", "temp_mean_c"}
    assert set(analysis["annual"][0]) == {"year", "days", "rain_days", "temp_days", "rain_mm",
                                          "temp_mean_c"}
    assert set(analysis["trends"]) == {"month", "season", "year"}
    assert set(analysis["trends"]["month"]) == {str(m) for m in range(1, 13)}
    json.dumps(analysis)  # plain JSON, nothing to convert


# --- cities ----------------------------------------------------------------------


@pytest.mark.parametrize("given, key", [("chennai", "chennai"), ("Chennai", "chennai"),
                                        ("  DELHI ", "delhi"), ("Madras", "chennai"),
                                        ("Bombay", "mumbai")])
def test_a_demo_city_is_found_by_key_or_name(given, key):
    assert climate.city_key_for(given) == key


@pytest.mark.parametrize("given", [None, "", "  ", "nowhere", "13.0827,80.2707", 12, ["chennai"],
                                   "http://evil.example/"])
def test_anything_else_is_not_a_demo_city(given):
    assert climate.city_key_for(given) is None


def test_free_text_only_ever_selects_a_registry_city_and_never_reaches_the_request(auto_mode,
                                                                                  net):
    # cities.resolve (the project's own text -> city lookup) finds a name inside a sentence;
    # what goes upstream is still only the registry's coordinates for that city.
    text = "how is the weather in Chennai; DROP TABLE"
    assert climate.city_key_for(text) == "chennai"
    climate.public(text)
    (call,) = net.calls
    chennai = cities.CITIES["chennai"]
    assert (call["params"]["latitude"], call["params"]["longitude"]) == (chennai.lat, chennai.lon)
    assert "DROP" not in json.dumps(call) and "weather" not in json.dumps(call)


def test_a_travel_only_destination_is_not_supported(monkeypatch):
    travel_only = [k for k in cities.TRAVEL_CITIES if k not in cities.CITIES]
    assert travel_only, "the registry has no travel-only destination to test with"
    assert climate.city_key_for(travel_only[0]) is None
    # Even if the registry's lookup ever returned one, it still must not get through.
    monkeypatch.setattr(cities, "resolve", lambda text, **kw: travel_only[0])
    assert climate.city_key_for("somewhere else entirely") is None


def test_an_unsupported_city_is_refused_without_touching_the_network(auto_mode, net):
    result = climate.public("Atlantis")
    assert result["status"] == "unsupported_city" and result["city"] is None
    assert result["monthly"] is None and result["trends"] is None
    assert net.calls == []


# --- modes: fixtures -------------------------------------------------------------


@pytest.mark.parametrize("key", DEMO)
def test_fixtures_mode_never_touches_the_network_and_is_dated_not_live(fixtures_mode, net, key):
    result = climate.public(key)
    assert net.calls == []
    assert result["status"] == "ok" and result["city"] == key
    assert result["is_live"] is False
    assert result["retrieved_at"] == RAW[key]["fetched_at"]
    assert result["requested"] == {"start_date": "1996-01-01", "end_date": "2026-10-22"}
    assert result["monthly"] and result["trends"]["year"]["rain_mm"]["status"] == "ok"


def test_a_city_without_a_fixture_is_unavailable_not_empty(fixtures_mode, net):
    assert "madurai" in cities.CITIES and not climate.fixture_path("madurai").exists()
    result = climate.public("madurai")
    assert result["status"] == "unavailable" and result["city"] == "madurai"
    for field in ("monthly", "seasonal", "annual", "trends", "grid", "data_quality"):
        assert result[field] is None
    assert net.calls == []


@pytest.mark.parametrize(
    "doc",
    [{}, [], "text", {"fetched_at": CHENNAI_SNAPSHOT}, {"fetched_at": CHENNAI_SNAPSHOT,
                                                         "response": {}},
     {"fetched_at": "garbage", "response": GOOD}, {"response": GOOD},
     {"fetched_at": CHENNAI_SNAPSHOT, "response": shifted(GOOD, daily_units={})}],
)
def test_an_unreadable_fixture_is_unavailable(fixtures_mode, fixture_dir, doc):
    (fixture_dir / "chennai.json").write_text(json.dumps(doc), encoding="utf-8")
    assert climate.public("chennai")["status"] == "unavailable"


def test_a_corrupt_fixture_file_is_unavailable(fixtures_mode, fixture_dir):
    (fixture_dir / "chennai.json").write_text("{not json", encoding="utf-8")
    assert climate.public("chennai")["status"] == "unavailable"


def test_a_fixture_without_a_zone_in_its_date_is_read_as_utc(fixtures_mode, fixture_dir):
    raw = shifted(RAW["chennai"], fetched_at="2026-10-29T12:51:12")
    (fixture_dir / "chennai.json").write_text(json.dumps(raw), encoding="utf-8")
    assert climate.public("chennai")["retrieved_at"] == CHENNAI_SNAPSHOT


# --- modes: live fetch -----------------------------------------------------------


def test_live_fetch_asks_for_era5_daily_rain_and_mean_temperature_for_the_citys_own_point(
        auto_mode, net):
    result = climate.public("chennai")
    assert result["status"] == "ok" and result["is_live"] is True
    assert result["retrieved_at"] == "2026-10-29T12:00:00+00:00"
    (call,) = net.calls
    chennai = cities.CITIES["chennai"]
    assert call["url"] == "https://archive-api.open-meteo.com/v1/archive"
    assert call["params"] == {
        "latitude": chennai.lat, "longitude": chennai.lon,
        "start_date": "1996-01-01",  # Jan 1 of 30 years before this one
        "end_date": "2026-10-22",    # a week before "today"
        "daily": "precipitation_sum,temperature_2m_mean", "models": "era5",
        "timezone": "Asia/Kolkata"}
    assert result["requested"] == {"start_date": "1996-01-01", "end_date": "2026-10-22"}


def test_the_real_service_would_receive_no_user_text(auto_mode, net):
    climate.public("Chennai")  # the caller's spelling never reaches the request
    (call,) = net.calls
    assert set(call["params"]) == {"latitude", "longitude", "start_date", "end_date", "daily",
                                   "models", "timezone"}
    assert isinstance(call["params"]["latitude"], float)
    assert isinstance(call["params"]["longitude"], float)


def test_the_request_is_https_to_the_one_host_without_redirects_and_with_a_timeout(
        auto_mode, net):
    climate.public("delhi")
    (call,) = net.calls
    assert call["method"] == "GET"
    assert call["url"].startswith("https://archive-api.open-meteo.com/v1/archive")
    assert call["follow_redirects"] is False
    assert call["timeout"] == climate.TIMEOUT
    assert climate.HOST == "archive-api.open-meteo.com" and climate.API_URL.startswith("https://")
    assert "apikey" not in call["params"]


@pytest.mark.parametrize("today, start, end", [
    (date(2026, 10, 29), "1996-01-01", "2026-10-22"),
    (date(2026, 1, 3), "1996-01-01", "2025-12-27"),    # early January: last year is not whole yet
    (date(2024, 3, 7), "1994-01-01", "2024-02-29"),    # leap day
])
def test_the_requested_window(today, start, end):
    assert climate._window(today) == (date.fromisoformat(start), date.fromisoformat(end))


def test_live_result_is_the_analysis_of_the_response(auto_mode, net):
    result = climate.public("chennai")
    assert result["trends"] == climate.analyze(GOOD)["trends"]
    assert result["monthly"] == climate.analyze(GOOD)["monthly"]


def test_live_result_is_cached_per_city_for_the_ttl_then_refetched(auto_mode, net, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(climate, "_monotonic", lambda: clock["t"])
    climate.public("chennai")
    climate.public("chennai")
    climate.public("Madras")  # the same city under another name
    assert len(net.calls) == 1
    climate.public("mumbai")
    assert len(net.calls) == 2  # a different city is its own request
    clock["t"] += climate.TTL_SECONDS - 1
    climate.public("chennai")
    assert len(net.calls) == 2
    clock["t"] += 2
    climate.public("chennai")
    assert len(net.calls) == 3


def test_callers_cannot_change_the_cached_analysis(auto_mode, net):
    first = climate.public("chennai")
    first["monthly"].clear()
    first["trends"]["year"]["rain_mm"]["slope_per_decade"] = 999
    first["seasons"]["monsoon"].append(13)
    second = climate.public("chennai")
    assert second["monthly"] and second["trends"]["year"]["rain_mm"]["slope_per_decade"] != 999
    assert climate.SEASONS["monsoon"] == (6, 7, 8, 9)


# --- failures are never zero rain or "no trend" ------------------------------------


@pytest.mark.parametrize("failure", FAILURES.values(), ids=FAILURES.keys())
def test_failed_fetch_in_live_mode_is_unavailable_with_no_figures(live_mode, net, failure):
    net.reply = failure
    result = climate.public("chennai")
    assert result["status"] == "unavailable"
    assert result["is_live"] is False and result["retrieved_at"] is None
    for field in ("monthly", "seasonal", "annual", "trends", "grid", "data_quality", "requested"):
        assert result[field] is None, field  # not [] and not {}: nothing, not zero
    assert result["label"] == climate.LABEL and result["source"] == "Open-Meteo"


@pytest.mark.parametrize("failure", FAILURES.values(), ids=FAILURES.keys())
def test_failed_fetch_in_auto_mode_replays_the_dated_snapshot(auto_mode, net, failure):
    net.reply = failure
    result = climate.public("chennai")
    assert result["status"] == "ok"
    assert result["is_live"] is False
    assert result["retrieved_at"] == CHENNAI_SNAPSHOT  # dated by when it was taken, not now


def test_auto_mode_with_no_fixture_and_a_failure_is_unavailable(auto_mode, net, fixture_dir):
    net.reply = FAILURES["server_error"]
    result = climate.public("chennai")
    assert result["status"] == "unavailable" and result["monthly"] is None


def test_after_a_failure_the_network_is_left_alone_until_the_backoff_ends(auto_mode, net,
                                                                         monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(climate, "_monotonic", lambda: clock["t"])
    net.reply = FAILURES["timeout"]
    for key in ("chennai", "mumbai", "delhi", "chennai", "chennai"):
        result = climate.public(key)  # one struggling service: no city retries it
        assert result["is_live"] is False and result["status"] == "ok"
    assert len(net.calls) == 1

    clock["t"] += climate.FAILURE_BACKOFF_SECONDS - 1
    climate.public("chennai")
    assert len(net.calls) == 1
    clock["t"] += 2
    net.reply = Network.fixture_reply
    assert climate.public("chennai")["is_live"] is True
    assert len(net.calls) == 2


def test_after_http_429_the_network_is_left_alone_much_longer(auto_mode, net, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(climate, "_monotonic", lambda: clock["t"])
    net.reply = FAILURES["rate_limited_429"]
    climate.public("chennai")
    clock["t"] += climate.FAILURE_BACKOFF_SECONDS + 1
    net.reply = Network.fixture_reply
    assert climate.public("chennai")["is_live"] is False and len(net.calls) == 1
    clock["t"] += climate.RATE_LIMIT_BACKOFF_SECONDS
    assert climate.public("chennai")["is_live"] is True
    assert climate.RATE_LIMIT_BACKOFF_SECONDS > climate.FAILURE_BACKOFF_SECONDS


def test_backoff_in_live_mode_is_unavailable_never_a_snapshot(live_mode, net, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(climate, "_monotonic", lambda: clock["t"])
    net.reply = FAILURES["server_error"]
    for _ in range(3):
        result = climate.public("chennai")
        assert result["status"] == "unavailable" and result["monthly"] is None
    assert len(net.calls) == 1


def test_a_failed_refresh_does_not_discard_a_good_cached_result(auto_mode, net, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(climate, "_monotonic", lambda: clock["t"])
    assert climate.public("chennai")["is_live"] is True
    clock["t"] += climate.TTL_SECONDS + 1
    net.reply = FAILURES["timeout"]
    assert climate.public("chennai")["is_live"] is False  # expired and failed: a dated snapshot
    clock["t"] += climate.FAILURE_BACKOFF_SECONDS + 1
    net.reply = Network.fixture_reply
    assert climate.public("chennai")["is_live"] is True


def test_oversize_body_is_cut_off_while_streaming(net):
    net.reply = (200, oversize_chunks())
    with pytest.raises(climate.FetchError, match="byte cap"):
        climate._get_json({})


def test_oversize_declared_length_is_refused_before_reading(net):
    net.reply = (200, oversize_json())  # httpx declares its length (Content-Length)
    with pytest.raises(climate.FetchError, match="over the 3000000 cap"):
        climate._get_json({})


# --- the daily allowance ---------------------------------------------------------------


def test_live_fetches_are_capped_per_day_to_respect_open_meteos_limit(auto_mode, net,
                                                                     monkeypatch):
    monkeypatch.setattr(climate, "MAX_LIVE_FETCHES_PER_DAY", 2)
    results = {key: climate.public(key) for key in ("chennai", "mumbai", "delhi")}
    assert len(net.calls) == 2
    assert results["chennai"]["is_live"] and results["mumbai"]["is_live"]
    assert results["delhi"]["is_live"] is False and results["delhi"]["status"] == "ok"  # snapshot
    assert results["delhi"]["retrieved_at"] == RAW["delhi"]["fetched_at"]


def test_the_allowance_in_live_mode_is_unavailable_not_a_snapshot(live_mode, net, monkeypatch):
    monkeypatch.setattr(climate, "MAX_LIVE_FETCHES_PER_DAY", 1)
    assert climate.public("chennai")["status"] == "ok"
    assert climate.public("mumbai")["status"] == "unavailable"
    assert len(net.calls) == 1


def test_failed_attempts_use_up_the_allowance_too(auto_mode, net, monkeypatch):
    monkeypatch.setattr(climate, "MAX_LIVE_FETCHES_PER_DAY", 1)
    clock = {"t": 1000.0}
    monkeypatch.setattr(climate, "_monotonic", lambda: clock["t"])
    net.reply = FAILURES["timeout"]
    climate.public("chennai")
    clock["t"] += climate.FAILURE_BACKOFF_SECONDS + 1
    net.reply = Network.fixture_reply
    assert climate.public("chennai")["is_live"] is False and len(net.calls) == 1


def test_the_allowance_renews_on_the_next_utc_day(auto_mode, net, monkeypatch):
    monkeypatch.setattr(climate, "MAX_LIVE_FETCHES_PER_DAY", 1)
    climate.public("chennai")
    assert climate.public("mumbai")["is_live"] is False
    monkeypatch.setattr(climate, "_utcnow", lambda: NOW + timedelta(days=1))
    assert climate.public("mumbai")["is_live"] is True
    assert len(net.calls) == 2


def test_the_daily_allowance_fits_open_meteos_free_limit():
    # ~800 calls per request (days / 14), 10,000 a day: eight requests stay well under.
    calls = (11253 / 14) * climate.MAX_LIVE_FETCHES_PER_DAY
    assert calls < 10_000 * 0.7


# --- source metadata ---------------------------------------------------------------------


@pytest.mark.parametrize("scenario", ["fixtures", "live_failure", "unsupported"])
def test_attribution_and_labels_are_always_present(request, net, scenario):
    if scenario == "fixtures":
        request.getfixturevalue("fixtures_mode")
        city = "chennai"
    elif scenario == "live_failure":
        request.getfixturevalue("live_mode")
        net.reply = FAILURES["timeout"]
        city = "chennai"
    else:
        city = "nowhere"
    result = climate.public(city)
    assert result["label"] == "Open-Meteo / ERA5 reanalysis, not IMD station data"
    assert result["source"] == "Open-Meteo" and result["model"] == "era5"
    assert result["credit"] == {"text": "Weather data by Open-Meteo.com",
                                "url": "https://open-meteo.com/"}
    assert result["licence_url"] == "https://open-meteo.com/en/licence"
    assert result["terms_url"] == "https://open-meteo.com/en/terms"
    assert "computed by WeatherGPT" in result["changes_note"]
    assert "not IMD's declared monsoon onset" in result["calendar_note"]
    assert result["seasons"]["monsoon"] == [6, 7, 8, 9]
    assert result["units"] == {"precipitation_sum": "mm", "temperature_2m_mean": "°C"}
    assert result["min_trend_years"] == climate.MIN_TREND_YEARS


def test_nothing_in_a_result_is_presented_as_imd_data(fixtures_mode):
    text = json.dumps(climate.public("chennai"))
    assert "IMD" in text  # only ever in the negative: "not IMD station data", "not IMD's ..."
    for sentence in (climate.LABEL, climate.CALENDAR_NOTE):
        assert "not IMD" in sentence


# --- refreshing a fixture --------------------------------------------------------------------


def test_written_fixture_round_trips_through_the_fixture_reader(
        net, fixtures_mode, monkeypatch, tmp_path):
    target = tmp_path / "snapshots" / "chennai.json"
    assert climate.write_fixture("chennai", target) == target
    assert not list(target.parent.glob("*.tmp"))
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["fetched_at"] == "2026-10-29T12:00:00+00:00" and saved["city"] == "chennai"
    assert saved["response"] == GOOD
    assert saved["request"]["params"]["models"] == "era5"

    monkeypatch.setattr(climate, "fixture_path", lambda key: target)
    result = climate.public("chennai")
    assert result["is_live"] is False and result["retrieved_at"] == "2026-10-29T12:00:00+00:00"
    assert result["trends"] == climate.analyze(GOOD)["trends"]


def test_failed_refresh_never_overwrites_a_good_fixture(net, tmp_path):
    target = tmp_path / "chennai.json"
    target.write_text("KEEP ME", encoding="utf-8")
    net.reply = FAILURES["server_error"]
    with pytest.raises(httpx.HTTPError):
        climate.write_fixture("chennai", target)
    assert target.read_text(encoding="utf-8") == "KEEP ME"
    assert list(tmp_path.glob("*.tmp")) == []


def test_an_unusable_response_is_never_saved_as_a_fixture(net, tmp_path):
    target = tmp_path / "chennai.json"
    net.reply = FAILURES["wrong_rain_unit"]
    with pytest.raises(climate.FetchError):
        climate.write_fixture("chennai", target)
    assert not target.exists() and list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize("name", ["nowhere", "../etc/passwd", "madras", "", "Chennai"])
def test_only_demo_city_keys_can_be_written_and_no_request_is_made(net, tmp_path, name):
    with pytest.raises(ValueError):
        climate.write_fixture(name, tmp_path / "x.json")
    assert net.calls == []


# --- the real service (opt in with -m live) ---------------------------------------------------


@pytest.mark.live
def test_real_open_meteo_answers_with_the_shape_and_units_we_parse():
    # A one-month request (about one API call), not the full history.
    chennai = cities.CITIES["chennai"]
    params = climate._params(chennai, date(2025, 6, 1), date(2025, 6, 30))
    analysis = climate.analyze(climate._get_json(params))
    june = row(analysis["monthly"], year=2025, month=6)
    assert june["days"] == 30 and june["rain_days"] == 30 and june["temp_days"] == 30
    assert june["rain_mm"] is not None and 15 <= june["temp_mean_c"] <= 40
    assert analysis["grid"]["latitude"] % 0.25 == 0  # ERA5's grid
