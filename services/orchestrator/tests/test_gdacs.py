"""gdacs.py: GDACS tropical-cyclone events near India — parsing, the India
filter, live fetch with bounds, TTL cache, fixture fallback, and the rule that a
failed fetch is never "no cyclones". No test touches the real service: the fetch
is stubbed (httpx.stream), and the fixture in data/fixtures/gdacs/ is a real
response saved from www.gdacs.org (CYC-2).

Two kinds of input are used. Tests marked "real" read that fixture and pin its
actual values, so they are written against the 2026-10-29 snapshot (a guard test
says so loudly if it is ever refreshed). Tests marked "synthetic" build tiny
GeoJSON features by hand, only to exercise parser and filter logic — they are
unit-test inputs, not data anyone should read as a cyclone.
"""

import copy
import json
from contextlib import contextmanager
from datetime import datetime, timezone

import config
import gdacs
import httpx
import pytest

NOW = datetime(2026, 10, 29, 12, 0, 0, tzinfo=timezone.utc)
SNAPSHOT_TIME = "2026-10-29T11:48:18+00:00"
RAW = json.loads(gdacs.fixture_path().read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _fresh_gdacs(monkeypatch):
    gdacs.cache_clear()
    monkeypatch.setattr(gdacs, "_utcnow", lambda: NOW)
    yield
    gdacs.cache_clear()


# --- helpers -------------------------------------------------------------------


def search_doc(features):
    return {"type": "FeatureCollection", "features": features}


def feature(event_id=1, name="TEST-26", lon=81.8, lat=16.4, iso3="", affected=(), **props):
    """A synthetic event-search feature (unit-test input only)."""
    base = {
        "eventtype": "TC", "eventid": event_id, "episodeid": 3, "eventname": name,
        "name": f"Tropical Cyclone {name}", "alertlevel": "Green", "alertscore": 1,
        "episodealertlevel": "Green", "episodealertscore": 1.0, "iscurrent": "true",
        "fromdate": "2026-10-20T00:00:00", "todate": "2026-10-21T06:00:00",
        "datemodified": "2026-10-21T07:00:00", "iso3": iso3, "source": "JTWC",
        "affectedcountries": [{"iso2": "XX", "iso3": i, "countryname": i} for i in affected],
        "severitydata": {"severity": 100.0, "severitytext": "synthetic", "severityunit": "km/h"},
    }
    base.update(props)
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": base}


def india_feature(event_id, **kw):
    return feature(event_id=event_id, name=f"SYN{event_id}-26", **kw)


def far_feature(event_id):
    return feature(event_id=event_id, name=f"FAR{event_id}-26", lon=-108.4, lat=21.0)


def geo_feature(geom_type, coords, **props):
    return {"type": "Feature", "geometry": {"type": geom_type, "coordinates": coords},
            "properties": props}


class Network:
    """Stands in for httpx.stream. `calls` records each request; `search` and
    `geometry` are callables (params -> (status, body)) or an Exception to raise."""

    def __init__(self):
        self.calls = []
        self.search = lambda params: (200, RAW["search"])
        self.geometry = lambda params: (200, RAW["geometry"][str(params["eventid"])])

    def searches(self):
        return [c for c in self.calls if c["url"].endswith("/SEARCH")]

    def geometries(self):
        return [c for c in self.calls if c["url"].endswith("/getgeometry")]


@pytest.fixture
def net(monkeypatch):
    stub = Network()

    @contextmanager
    def fake_stream(method, url, params=None, timeout=None, follow_redirects=None, **_):
        stub.calls.append({"method": method, "url": url, "params": dict(params or {}),
                           "timeout": timeout, "follow_redirects": follow_redirects})
        handler = stub.search if url.endswith("/SEARCH") else stub.geometry
        reply = handler(dict(params or {})) if callable(handler) else handler
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
def fixture_file(monkeypatch, tmp_path):
    """Points the module at a fixture file in tmp_path; returns a writer."""
    path = tmp_path / "cyclones.json"
    monkeypatch.setattr(gdacs, "fixture_path", lambda: path)

    def write(doc):
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    return write


def oversize_json():
    """Valid JSON that is over the size cap, so only the cap can reject it."""
    return b'{"features":[],"padding":"' + b"x" * gdacs.MAX_BYTES + b'"}'


def oversize_chunks():
    """The same, sent as chunks with no Content-Length, so the server never
    admits its size and only the cap on the streamed bytes can stop it."""
    chunk = b"x" * 100_000
    return ([b'{"features":[],"padding":"']
            + [chunk] * (gdacs.MAX_BYTES // len(chunk) + 1) + [b'"}'])


# Ways a live fetch can fail. None of them may ever read as "no cyclones".
FAILURES = {
    "timeout": httpx.ConnectTimeout("timed out"),
    "server_error": (500, {"error": "boom"}),
    "redirect": (302, b"", {"location": "https://elsewhere.example/"}),
    "not_json": (200, b"<html>maintenance</html>"),
    # GDACS's own overload error (seen 2026-10-29): HTTP 400 with a JSON message.
    "gdacs_pool_exhausted": (400, {"message": "Timeout expired. The timeout period "
                                              "elapsed prior to obtaining a connection"}),
    # Found in review: absurdly nested JSON raises RecursionError, not ValueError.
    "deeply_nested": (200, b"[" * 100_000 + b"]" * 100_000),
    "ok_status_error_body": (200, {"message": "something went wrong"}),
    "json_array": (200, b"[]"),
    "no_features": (200, {"type": "FeatureCollection"}),
    "features_not_a_list": (200, {"features": "none"}),
    "too_big": (200, oversize_json()),
    "too_big_streamed": (200, oversize_chunks()),
    "declared_too_big": (200, b'{"features":[]}', {"content-length": str(gdacs.MAX_BYTES + 1)}),
}


# --- the fixture itself (real) ---------------------------------------------------


def test_fixture_is_the_snapshot_these_tests_pin():
    # If you refresh data/fixtures/gdacs/cyclones.json (python gdacs.py), the
    # "real" tests below that pin ARNAB-26 and its track must be re-pinned too.
    assert RAW["fetched_at"] == SNAPSHOT_TIME


def test_fixture_is_raw_gdacs_data_with_its_provenance():
    # The fixture's own provenance, written when the file was saved (2026-10-29), before
    # SOURCE_NAME was corrected to "Awareness"; saved data is not rewritten.
    assert RAW["source"].startswith("Global Disaster Alert and Coordination System, GDACS")
    assert RAW["request"]["url"] == f"{gdacs.API_BASE}/events/geteventlist/SEARCH"
    assert RAW["request"]["params"]["eventlist"] == "TC"
    assert RAW["complete"] is True
    features = RAW["search"]["features"]
    assert features and all(f["properties"]["eventtype"] == "TC" for f in features)
    assert "SIMULATED" not in json.dumps(RAW)
    assert set(RAW["geometry"]) == {"1001345"}


# --- parsing one event (real) --------------------------------------------------


def real_snapshot():
    snap = gdacs._snapshot_from_raw(copy.deepcopy(RAW), False)
    assert snap is not None
    return snap


def test_real_event_is_parsed_with_every_field():
    event = real_snapshot().events[0]
    event.pop("track")
    assert event == {
        "event_id": 1001345, "episode_id": 10, "name": "ARNAB-26",
        "title": "Tropical Cyclone ARNAB-26", "glide": "TC-2026-000197-IND",
        "alert_level": "Red", "alert_score": 3.0,
        "episode_alert_level": "Orange", "episode_alert_score": 2.0,
        "is_current": True,
        "from_date": "2026-10-26T00:00:00+00:00", "to_date": "2026-10-28T06:00:00+00:00",
        "date_modified": "2026-10-29T08:02:06+00:00",
        "lon": 81.8, "lat": 16.4, "country_iso3": "IND",
        "affected_countries": [{"iso2": "IN", "iso3": "IND", "name": "India"}],
        "source_agency": "JTWC",
        "severity": {"value": 222.2208, "unit": "km/h",
                     "text": "Tropical Storm (maximum wind speed of 222 km/h)"},
        "report_url": "https://www.gdacs.org/report.aspx?eventid=1001345&episodeid=10&eventtype=TC",
        "matched_by": ["in_area", "country_iso3", "affected_country"],
        "source": "GDACS",
    }


def test_real_snapshot_keeps_only_events_near_india():
    snap = real_snapshot()
    assert [e["name"] for e in snap.events] == ["ARNAB-26"]
    # The other ten events in the response are all elsewhere, by an independent check.
    kept = {e["event_id"] for e in snap.events}
    others = [f for f in RAW["search"]["features"] if f["properties"]["eventid"] not in kept]
    assert len(others) == 10
    for f in others:
        lon, lat = f["geometry"]["coordinates"]
        assert not gdacs.in_india_box(lon, lat)
        assert f["properties"]["iso3"] != "IND"


def test_real_snapshot_is_dated_and_not_live():
    snap = real_snapshot()
    assert snap.is_live is False
    assert snap.retrieved_at == SNAPSHOT_TIME
    assert snap.complete is True


def test_real_track_is_structured_with_gdacs_labels():
    track = real_snapshot().events[0]["track"]
    assert len(track["segments"]) == 11
    assert [s["is_forecast"] for s in track["segments"]].count(False) == 7
    assert [s["is_forecast"] for s in track["segments"]].count(True) == 4
    assert {s["category"] for s in track["segments"]} == {"HU", "TS", "TD"}
    assert track["segments"][0]["coordinates"] == [[82.7, 16.3], [81.6, 16.4]]
    assert len(track["cones"]) == 1
    assert len(track["areas"]) == 28
    assert {a["feature_type"] for a in track["areas"]} == {None, "WindRadii", "PointRadii"}
    assert {a["class"].split("_")[0] for a in track["areas"]} == {"Poly", "Point"}
    assert track["polygon_date"] == "2026-10-28T06:00:00+00:00"
    assert track["source"] == "GDACS"


def test_real_track_matches_the_raw_geometry_counts():
    raw_features = RAW["geometry"]["1001345"]["features"]
    track = real_snapshot().events[0]["track"]
    lines = [f for f in raw_features if f["geometry"]["type"] == "LineString"]
    polygons = [f for f in raw_features if f["geometry"]["type"] == "Polygon"]
    assert len(track["segments"]) == len(lines)
    assert len(track["cones"]) + len(track["areas"]) == len(polygons)


def test_real_track_coordinates_are_valid_lon_lat():
    track = real_snapshot().events[0]["track"]
    rings = [r for c in track["cones"] for r in c["coordinates"]]
    rings += [r for a in track["areas"] for r in a["coordinates"]]
    points = [p for r in rings for p in r] + [p for s in track["segments"]
                                              for p in s["coordinates"]]
    assert points
    assert all(-180 <= lon <= 180 and -90 <= lat <= 90 for lon, lat in points)


# --- the India filter (synthetic) ----------------------------------------------


@pytest.mark.parametrize(
    "lon, lat, inside",
    [(55.0, 0.0, True), (100.0, 30.0, True), (77.0, 15.0, True), (81.8, 16.4, True),
     (54.99, 15.0, False), (100.01, 15.0, False), (77.0, 30.01, False),
     (77.0, -0.01, False), (-108.4, 21.0, False), (152.9, 16.3, False)],
)
def test_india_box_is_inclusive_and_exact(lon, lat, inside):
    assert gdacs.in_india_box(lon, lat) is inside


def test_open_ocean_event_without_a_country_is_kept_by_position():
    # Many GDACS events carry no iso3: a storm in the Bay of Bengal still counts.
    events = gdacs._events_from(search_doc([india_feature(1, iso3="", lon=88.0, lat=14.0)]))
    assert [e["matched_by"] for e in events] == [["in_area"]]
    assert events[0]["country_iso3"] is None


def test_event_outside_the_box_is_kept_when_gdacs_tags_india():
    tagged = feature(2, lon=102.0, lat=22.0, iso3="IND")
    affected = feature(3, lon=102.0, lat=22.0, iso3="MMR", affected=["MMR", "IND"])
    events = gdacs._events_from(search_doc([tagged, affected]))
    assert {e["event_id"]: e["matched_by"] for e in events} == {
        2: ["country_iso3"], 3: ["affected_country"]}


def test_event_elsewhere_is_dropped():
    far = feature(4, lon=-108.4, lat=21.0, iso3="MEX", affected=["MEX", "USA"])
    assert gdacs._events_from(search_doc([far])) == []


def test_events_are_deduplicated_and_ordered_current_first_then_newest():
    old_current = india_feature(1, datemodified="2026-10-20T00:00:00")
    new_current = india_feature(2, datemodified="2026-10-25T00:00:00")
    new_ended = india_feature(3, iscurrent="false", datemodified="2026-10-28T00:00:00")
    duplicate = india_feature(1, datemodified="2026-10-20T00:00:00")
    events = gdacs._events_from(search_doc([old_current, new_ended, duplicate, new_current]))
    assert [e["event_id"] for e in events] == [2, 1, 3]


# --- malformed input is skipped, never guessed (synthetic) ----------------------


def broken(**changes):
    f = india_feature(9)
    f["properties"].update({k: v for k, v in changes.items() if k != "geometry"})
    if "geometry" in changes:
        f["geometry"] = changes["geometry"]
    return f


@pytest.mark.parametrize(
    "bad",
    [
        None, "text", 7, [], {},
        {"properties": {}, "geometry": None},
        broken(eventtype="EQ"),
        broken(eventid=True),
        broken(eventid="1001345; DROP TABLE"),
        broken(eventid=0),
        broken(eventid=-5),
        broken(eventid=None),
        broken(eventid=gdacs.MAX_ID),  # too big to be exact in JavaScript
        broken(eventid=10**400),
        broken(geometry={"type": "LineString", "coordinates": [[80, 15], [81, 16]]}),
        broken(geometry={"type": "Point"}),
        broken(geometry={"type": "Point", "coordinates": [81.8]}),
        broken(geometry={"type": "Point", "coordinates": [81.8, 91.0]}),
        broken(geometry={"type": "Point", "coordinates": [181.0, 10.0]}),
        broken(geometry={"type": "Point", "coordinates": [float("nan"), 10.0]}),
        broken(geometry={"type": "Point", "coordinates": [float("inf"), 10.0]}),
        broken(geometry={"type": "Point", "coordinates": ["81.8", "16.4"]}),
    ],
)
def test_unusable_features_are_skipped(bad):
    assert gdacs.parse_event(bad) is None
    assert gdacs._events_from(search_doc([bad])) == []


def test_text_fields_are_cleaned_and_bounded():
    f = india_feature(5, eventname="BAD\n\x00NAME" + "x" * 500, source=12, alertlevel="  Red ")
    event = gdacs.parse_event(f)
    assert "\n" not in event["name"] and "\x00" not in event["name"]
    assert len(event["name"]) <= 80
    assert event["source_agency"] is None
    assert event["alert_level"] == "Red"


def test_absurd_numbers_and_dates_are_dropped_not_raised():
    # Found in review: float(10**400) raised OverflowError, and so did shifting a
    # year-1 date to UTC, which would have taken the whole endpoint down.
    f = india_feature(
        5, alertscore=10**400, episodealertscore=-(10**400), episodeid=10**400,
        fromdate="0001-01-01T00:00:00+14:00", todate="9999-12-31T23:59:59-14:00",
        severitydata={"severity": 10**400, "severityunit": "km/h"})
    event = gdacs.parse_event(f)
    assert event is not None and event["event_id"] == 5
    assert event["alert_score"] is None and event["episode_alert_score"] is None
    assert event["episode_id"] is None
    assert event["from_date"] is None and event["to_date"] is None
    assert event["severity"]["value"] is None
    assert event["report_url"] == "https://www.gdacs.org/report.aspx?eventid=5&eventtype=TC"


def test_alert_levels_pass_through_untranslated_for_the_decoder():
    # Mapping to canonical keys is CYC-3's job; an unknown level must survive as is.
    unknown = gdacs.parse_event(india_feature(6, alertlevel="Purple", alertscore=4))
    assert (unknown["alert_level"], unknown["alert_score"]) == ("Purple", 4.0)
    missing = gdacs.parse_event(india_feature(7, alertlevel=None, alertscore=None))
    assert (missing["alert_level"], missing["alert_score"]) == (None, None)


def test_report_link_is_built_from_ids_not_taken_from_the_response():
    f = india_feature(8, url={"report": "https://evil.example/phish",
                              "geometry": "https://evil.example/geo"})
    event = gdacs.parse_event(f)
    base = "https://www.gdacs.org/report.aspx?eventid=8"
    assert event["report_url"] == f"{base}&episodeid=3&eventtype=TC"
    no_episode = gdacs.parse_event(india_feature(8, episodeid=None))
    assert no_episode["report_url"] == f"{base}&eventtype=TC"


@pytest.mark.parametrize(
    "given, expected",
    [("2026-10-26T00:00:00", "2026-10-26T00:00:00+00:00"),
     ("2026-10-26T05:30:00+05:30", "2026-10-26T00:00:00+00:00"),
     ("2026-10-26T00:00:00Z", "2026-10-26T00:00:00+00:00"),
     ("0001-01-01T00:00:00+14:00", None), ("9999-12-31T23:59:59-14:00", None),
     ("not a date", None), ("", None), (None, None), (20261026, None)],
)
def test_times_are_normalised_to_utc(given, expected):
    assert gdacs._utc_iso(given) == expected


# --- track parsing (synthetic) ---------------------------------------------------


def test_track_skips_what_it_cannot_read():
    line = [[80.0, 15.0], [81.0, 16.0]]
    ring = [[80, 15], [81, 15], [81, 16], [80, 15]]
    doc = {"features": [
        geo_feature("LineString", line, polygonlabel="TS", forecast=True),
        geo_feature("LineString", line, polygonlabel="TD", forecast="False"),
        geo_feature("LineString", line, polygonlabel="HU"),  # no forecast flag
        geo_feature("LineString", [[80, 15]], polygonlabel="short"),
        geo_feature("LineString", [[80, 15], [81, 99]], polygonlabel="bad lat"),
        geo_feature("Point", [80, 15]),
        geo_feature("MultiPolygon", [[ring]]),
        geo_feature("Polygon", [ring], Class="Poly_Cones", polygonlabel="Uncertainty Cones"),
        geo_feature("Polygon", [ring], Class="Poly_Red", polygonlabel="120 km/h"),
        geo_feature("Polygon", [[[80, 15], [81, 15]]], Class="Poly_Red"),  # ring too short
        "not a feature", {"geometry": None, "properties": None},
    ]}
    track = gdacs.parse_track(doc)
    assert [(s["category"], s["is_forecast"]) for s in track["segments"]] == [
        ("TS", True), ("TD", False), ("HU", None)]
    assert len(track["cones"]) == 1
    assert [(a["class"], a["label"]) for a in track["areas"]] == [("Poly_Red", "120 km/h")]


@pytest.mark.parametrize(
    "value, expected",
    [(True, True), (False, False), ("true", True), ("True", True), ("false", False),
     (" FALSE ", False), (1, None), (0, None), ("yes", None), ("", None), (None, None),
     ([], None)],
)
def test_forecast_flag_is_only_true_or_false_when_gdacs_says_so(value, expected):
    # Found in review: any other value used to read as False, i.e. "observed".
    doc = {"features": [geo_feature("LineString", [[80, 15], [81, 16]], forecast=value)]}
    assert gdacs.parse_track(doc)["segments"][0]["is_forecast"] is expected
    assert gdacs._flag(value) is expected


@pytest.mark.parametrize("doc", [None, [], "x", {}, {"features": None}, {"features": "no"}])
def test_track_of_a_wrong_document_is_none(doc):
    assert gdacs.parse_track(doc) is None


def test_track_with_too_many_points_is_dropped():
    points = [[80.0 + i * 1e-4, 15.0] for i in range(gdacs.MAX_POINTS + 1)]
    track = gdacs.parse_track({"features": [geo_feature("LineString", points)]})
    assert track["segments"] == []


# --- modes: fixtures -------------------------------------------------------------


def test_fixtures_mode_never_touches_the_network(fixtures_mode, net):
    result = gdacs.public()
    assert net.calls == []
    assert result["status"] == "ok"
    assert result["is_live"] is False
    assert result["retrieved_at"] == SNAPSHOT_TIME
    assert [e["name"] for e in result["events"]] == ["ARNAB-26"]
    assert result["events"][0]["track"] is not None


def test_fixtures_mode_with_no_fixture_is_unavailable_not_empty(fixtures_mode, net, tmp_path,
                                                                monkeypatch):
    monkeypatch.setattr(gdacs, "fixture_path", lambda: tmp_path / "missing.json")
    result = gdacs.public()
    assert result["status"] == "unavailable"
    assert result["events"] is None and result["count"] is None
    assert not gdacs.no_cyclones_confirmed(result)
    assert net.calls == []


@pytest.mark.parametrize(
    "doc",
    [{}, [], {"fetched_at": SNAPSHOT_TIME}, {"fetched_at": SNAPSHOT_TIME, "search": {}},
     {"fetched_at": "garbage", "search": {"features": []}},
     {"search": {"features": []}}],
)
def test_unreadable_fixture_is_unavailable(fixtures_mode, fixture_file, doc):
    fixture_file(doc)
    assert gdacs.public()["status"] == "unavailable"


def test_corrupt_fixture_file_is_unavailable(fixtures_mode, fixture_file):
    path = fixture_file({})
    path.write_text("{not json", encoding="utf-8")
    assert gdacs.public()["status"] == "unavailable"


# --- modes: live fetch ---------------------------------------------------------------


def test_live_fetch_uses_only_the_documented_endpoints_with_our_own_values(auto_mode, net):
    result = gdacs.public()

    assert result["status"] == "ok" and result["is_live"] is True
    assert result["retrieved_at"] == "2026-10-29T12:00:00+00:00"
    assert result["complete"] is True
    assert [e["name"] for e in result["events"]] == ["ARNAB-26"]
    assert result["events"][0]["track"]["segments"]

    (search,) = net.searches()
    assert search["url"] == "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
    # 14 days back from today, and one day past it so a storm formed later today is inside.
    assert search["params"] == {
        "eventlist": "TC", "alertlevel": "red;orange;green",
        "fromdate": "2026-10-15", "todate": "2026-10-30", "pageSize": 100, "pageNumber": 1}
    (geometry,) = net.geometries()
    assert geometry["url"] == "https://www.gdacs.org/gdacsapi/api/polygons/getgeometry"
    assert geometry["params"] == {"eventtype": "TC", "eventid": 1001345, "episodeid": 10}
    assert all(isinstance(geometry["params"][k], int) for k in ("eventid", "episodeid"))


def test_every_request_is_https_to_the_one_host_without_redirects_and_with_a_timeout(
        auto_mode, net):
    gdacs.public()
    assert net.calls
    for call in net.calls:
        assert call["method"] == "GET"
        assert call["url"].startswith("https://www.gdacs.org/gdacsapi/api/")
        assert call["follow_redirects"] is False
        assert call["timeout"] == gdacs.TIMEOUT
    assert gdacs.HOST == "www.gdacs.org" and gdacs.API_BASE.startswith("https://")


def test_live_result_is_cached_for_the_ttl_and_then_refetched(auto_mode, net, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(gdacs, "_monotonic", lambda: clock["t"])
    gdacs.public()
    first = len(net.calls)
    clock["t"] += gdacs.TTL_SECONDS - 1
    gdacs.public()
    assert len(net.calls) == first  # still cached
    clock["t"] += 2
    gdacs.public()
    assert len(net.calls) == 2 * first  # expired: fetched again


def test_ttl_does_not_poll_faster_than_gdacs_refreshes_its_feeds():
    assert gdacs.TTL_SECONDS >= 6 * 60  # CYC-1: the feeds are updated every 6 minutes


def test_callers_cannot_change_the_cached_events(auto_mode, net):
    first = gdacs.public()
    first["events"][0]["name"] = "TAMPERED"
    first["events"].clear()
    assert [e["name"] for e in gdacs.public()["events"]] == ["ARNAB-26"]


# --- failures are never "no cyclones" ------------------------------------------------


@pytest.mark.parametrize("failure", FAILURES.values(), ids=FAILURES.keys())
def test_failed_fetch_in_live_mode_is_unavailable_not_empty(live_mode, net, failure):
    net.search = failure
    result = gdacs.public()
    assert result["status"] == "unavailable"
    assert result["events"] is None and result["count"] is None
    assert result["is_live"] is False
    assert not gdacs.no_cyclones_confirmed(result)
    assert result["attribution"] and result["source"] == "GDACS"  # still labelled


@pytest.mark.parametrize("failure", FAILURES.values(), ids=FAILURES.keys())
def test_failed_fetch_in_auto_mode_replays_the_dated_snapshot(auto_mode, net, failure):
    net.search = failure
    result = gdacs.public()
    assert result["status"] == "ok"
    assert result["is_live"] is False
    assert result["retrieved_at"] == SNAPSHOT_TIME  # dated by when it was taken, not now
    assert [e["name"] for e in result["events"]] == ["ARNAB-26"]
    assert not gdacs.no_cyclones_confirmed(result)


def test_after_a_failure_the_network_is_left_alone_until_the_backoff_ends(auto_mode, net,
                                                                         monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(gdacs, "_monotonic", lambda: clock["t"])
    net.search = FAILURES["timeout"]
    for _ in range(5):  # a struggling GDACS must not be asked again on every request
        result = gdacs.public()
        assert result["is_live"] is False and result["status"] == "ok"  # dated snapshot
    assert len(net.searches()) == 1

    clock["t"] += gdacs.FAILURE_BACKOFF_SECONDS - 1
    gdacs.public()
    assert len(net.searches()) == 1  # still backing off

    clock["t"] += 2  # backoff over, and GDACS is back
    net.search = lambda params: (200, RAW["search"])
    assert gdacs.public()["is_live"] is True
    assert len(net.searches()) == 2


def test_backoff_in_live_mode_is_unavailable_never_a_snapshot_or_empty(live_mode, net,
                                                                       monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(gdacs, "_monotonic", lambda: clock["t"])
    net.search = FAILURES["server_error"]
    for _ in range(3):
        result = gdacs.public()
        assert result["status"] == "unavailable" and result["events"] is None
        assert not gdacs.no_cyclones_confirmed(result)
    assert len(net.searches()) == 1


def test_a_failed_refresh_does_not_discard_a_good_cached_result(auto_mode, net, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(gdacs, "_monotonic", lambda: clock["t"])
    assert gdacs.public()["is_live"] is True
    clock["t"] += gdacs.TTL_SECONDS + 1
    net.search = FAILURES["timeout"]
    assert gdacs.public()["is_live"] is False  # expired, refresh failed: a dated snapshot
    clock["t"] += gdacs.FAILURE_BACKOFF_SECONDS + 1
    net.search = lambda params: (200, RAW["search"])
    assert gdacs.public()["is_live"] is True


def test_auto_mode_with_no_fixture_and_a_failure_is_unavailable(auto_mode, net, tmp_path,
                                                                monkeypatch):
    monkeypatch.setattr(gdacs, "fixture_path", lambda: tmp_path / "missing.json")
    net.search = FAILURES["server_error"]
    result = gdacs.public()
    assert result["status"] == "unavailable" and result["events"] is None


def test_a_failed_track_fetch_keeps_the_event_without_a_track(auto_mode, net):
    net.geometry = httpx.ReadTimeout("slow")
    result = gdacs.public()
    assert result["status"] == "ok" and result["is_live"] is True
    assert [e["name"] for e in result["events"]] == ["ARNAB-26"]
    assert result["events"][0]["track"] is None


def test_oversize_body_is_cut_off_while_streaming(net):
    net.search = (200, oversize_chunks())
    with pytest.raises(gdacs.FetchError, match="byte cap"):
        gdacs._get_json("events/geteventlist/SEARCH", {}, deadline=float("inf"))


def test_oversize_declared_length_is_refused_before_reading(net):
    net.search = (200, oversize_json())  # httpx declares its length (Content-Length)
    with pytest.raises(gdacs.FetchError, match="over the 2000000 cap"):
        gdacs._get_json("events/geteventlist/SEARCH", {}, deadline=float("inf"))


def test_a_refresh_past_its_time_budget_is_abandoned_before_any_request(net):
    with pytest.raises(gdacs.FetchError, match="time budget"):
        gdacs._get_json("events/geteventlist/SEARCH", {}, deadline=float("-inf"))
    assert net.calls == []


def test_a_slow_body_is_abandoned_mid_read(net, monkeypatch):
    ticks = iter([0.0, 5.0])  # fine when the request starts, over budget on the first chunk
    monkeypatch.setattr(gdacs, "_monotonic", lambda: next(ticks))
    with pytest.raises(gdacs.FetchError, match="time budget"):
        gdacs._get_json("events/geteventlist/SEARCH", {}, deadline=1.0)


# --- "no cyclones" can only be confirmed by a live, complete, empty answer -------------


def test_live_empty_answer_confirms_no_cyclones(auto_mode, net):
    net.search = lambda params: (200, search_doc([far_feature(1), far_feature(2)]))
    result = gdacs.public()
    assert result["status"] == "ok" and result["events"] == [] and result["count"] == 0
    assert result["is_live"] is True and result["complete"] is True
    assert gdacs.no_cyclones_confirmed(result)
    assert net.geometries() == []


def test_a_snapshot_with_no_events_does_not_confirm_anything(fixtures_mode, fixture_file):
    fixture_file({"fetched_at": SNAPSHOT_TIME, "complete": True, "search": search_doc([])})
    result = gdacs.public()
    assert result["status"] == "ok" and result["events"] == []
    assert result["is_live"] is False
    assert not gdacs.no_cyclones_confirmed(result)


def test_an_incomplete_search_does_not_confirm_anything(auto_mode, net):
    net.search = lambda params: (200, search_doc([far_feature(i) for i in range(gdacs.PAGE_SIZE)]))
    result = gdacs.public()
    assert len(net.searches()) == gdacs.MAX_PAGES
    assert result["events"] == [] and result["complete"] is False
    assert not gdacs.no_cyclones_confirmed(result)


@pytest.mark.parametrize(
    "result",
    [{}, {"status": "unavailable", "events": None}, {"status": "ok", "events": []},
     {"status": "ok", "events": [], "is_live": True},
     {"status": "ok", "events": [], "is_live": True, "complete": False},
     {"status": "ok", "events": [], "is_live": False, "complete": True},
     {"status": "ok", "events": [{"x": 1}], "is_live": True, "complete": True}],
)
def test_no_cyclones_confirmed_needs_every_condition(result):
    assert not gdacs.no_cyclones_confirmed(result)


# --- a response we could not read in full never confirms "no cyclones" (synthetic) ------
# Found in the post-merge audit: a feature the parser drops (a TC with a bad id or
# coordinates, a non-object) left `events` empty and `complete` True, so a live
# answer that may have held an Indian cyclone confirmed there was none.

UNREADABLE_FEATURES = {
    "not_an_object": "oops",
    "null": None,
    "number": 42,
    "empty_object": {},
    "properties_null": {"type": "Feature", "properties": None,
                        "geometry": {"type": "Point", "coordinates": [81.8, 16.4]}},
    "geometry_missing": {"type": "Feature", "properties": {"eventtype": "TC", "eventid": 7}},
    "eventtype_missing": broken(eventtype=None),
    "eventid_string": broken(eventid="1001345"),
    "eventid_zero": broken(eventid=0),
    "eventid_too_big": broken(eventid=gdacs.MAX_ID),
    "coordinates_missing": broken(geometry={"type": "Point"}),
    "coordinates_strings": broken(geometry={"type": "Point", "coordinates": ["81.8", "16.4"]}),
    "coordinates_out_of_range": broken(geometry={"type": "Point", "coordinates": [81.8, 91.0]}),
    "not_a_point": broken(geometry={"type": "MultiPoint", "coordinates": [[81.8, 16.4]]}),
}


@pytest.mark.parametrize("bad", UNREADABLE_FEATURES.values(), ids=UNREADABLE_FEATURES.keys())
def test_an_unreadable_feature_never_confirms_no_cyclones(auto_mode, net, bad):
    net.search = lambda params: (200, search_doc([bad]))
    result = gdacs.public()
    assert result["status"] == "ok" and result["events"] == [] and result["is_live"] is True
    assert result["unreadable_features"] == 1
    assert result["complete"] is False
    assert not gdacs.no_cyclones_confirmed(result)


def test_unreadable_features_are_counted_among_valid_events(auto_mode, net):
    page = [india_feature(500), "oops", far_feature(2), broken(eventid="x"), india_feature(501)]
    net.search = lambda params: (200, search_doc(page))
    net.geometry = (404, {})
    result = gdacs.public()
    assert sorted(e["event_id"] for e in result["events"]) == [500, 501]  # nothing lost
    assert result["unreadable_features"] == 2 and result["complete"] is False
    assert not gdacs.no_cyclones_confirmed(result)


def test_a_well_formed_non_cyclone_feature_is_ignored_not_unreadable(auto_mode, net):
    net.search = lambda params: (200, search_doc([broken(eventtype="EQ"), far_feature(1)]))
    result = gdacs.public()
    assert result["unreadable_features"] == 0 and result["complete"] is True
    assert gdacs.no_cyclones_confirmed(result)


def test_a_genuinely_empty_live_answer_still_confirms_no_cyclones(auto_mode, net):
    net.search = lambda params: (200, search_doc([]))
    result = gdacs.public()
    assert result["events"] == [] and result["unreadable_features"] == 0
    assert result["complete"] is True
    assert gdacs.no_cyclones_confirmed(result)


def test_features_past_the_read_limit_are_unreadable_not_ignored():
    search = search_doc([far_feature(i) for i in range(1, gdacs.MAX_FEATURES + 4)])
    raw = {"fetched_at": SNAPSHOT_TIME, "complete": True, "search": search}
    snap = gdacs._snapshot_from_raw(raw, True)
    assert snap.unreadable == 3 and snap.complete is False


def test_an_unreadable_feature_in_a_snapshot_is_reported(fixtures_mode, fixture_file):
    fixture_file({"fetched_at": SNAPSHOT_TIME, "complete": True,
                  "search": search_doc([india_feature(500), "oops"])})
    result = gdacs.public()
    assert result["is_live"] is False and result["unreadable_features"] == 1
    assert result["complete"] is False and not gdacs.no_cyclones_confirmed(result)


def test_the_real_fixture_has_no_unreadable_features(fixtures_mode):
    result = gdacs.public()
    assert result["unreadable_features"] == 0 and result["complete"] is True


def test_unavailable_result_has_no_unreadable_count(live_mode, net):
    net.search = FAILURES["timeout"]
    result = gdacs.public()
    assert result["status"] == "unavailable" and result["unreadable_features"] is None


# --- a snapshot says so, on the result and on every event (real fixture) --------------


def test_a_snapshot_carries_a_notice_and_marks_every_event_not_live(fixtures_mode):
    result = gdacs.public()
    assert result["is_live"] is False
    assert "not live" in result["notice"].lower()
    assert result["retrieved_at"] in result["notice"]
    assert result["events"] and all(e["is_live"] is False for e in result["events"])


def test_a_live_result_has_no_notice_and_marks_events_live(auto_mode, net):
    result = gdacs.public()
    assert result["is_live"] is True and result["notice"] is None
    assert result["events"] and all(e["is_live"] is True for e in result["events"])


def test_an_unavailable_result_has_no_notice(live_mode, net):
    net.search = FAILURES["timeout"]
    assert gdacs.public()["notice"] is None


def test_a_failed_live_fetch_replaying_the_fixture_is_marked_as_a_snapshot(auto_mode, net):
    net.search = FAILURES["timeout"]
    result = gdacs.public()
    assert result["is_live"] is False and "not live" in result["notice"].lower()
    assert all(e["is_live"] is False for e in result["events"])


def test_marking_events_never_changes_cached_or_fixture_data(auto_mode, net):
    first = gdacs.public()
    first["events"][0]["is_live"] = "tampered"
    first["events"].clear()
    cached = gdacs._CACHE["events"][1]
    assert cached.events and all("is_live" not in e for e in cached.events)
    assert all(e["is_live"] is True for e in gdacs.public()["events"])
    assert all("is_live" not in e for e in gdacs._fixture().events)


def test_existing_result_and_event_fields_are_kept(fixtures_mode):
    result = gdacs.public()
    for key in ("status", "events", "count", "is_live", "retrieved_at", "complete", "source",
                "source_name", "source_url", "terms_url", "attribution", "disclaimer", "area",
                "window_days"):
        assert key in result
    event = result["events"][0]
    assert event["is_current"] is True and event["source"] == "GDACS"
    assert event["alert_level"] == "Red" and event["track"] is not None


# --- paging and bounds -------------------------------------------------------------


def test_a_full_page_is_followed_by_the_next_and_duplicates_are_merged(auto_mode, net):
    page1 = [far_feature(i) for i in range(1, gdacs.PAGE_SIZE)] + [india_feature(500)]
    page2 = [india_feature(500), india_feature(501, lon=88.0, lat=12.0)]
    net.search = lambda params: (200, search_doc(page1 if params["pageNumber"] == 1 else page2))
    net.geometry = (404, {})
    result = gdacs.public()
    assert [c["params"]["pageNumber"] for c in net.searches()] == [1, 2]
    assert sorted(e["event_id"] for e in result["events"]) == [500, 501]
    assert result["complete"] is True


def test_tracks_are_fetched_for_at_most_max_tracks_events(auto_mode, net):
    count = gdacs.MAX_TRACKS + 3
    net.search = lambda params: (200, search_doc([india_feature(i) for i in range(1, count + 1)]))
    net.geometry = lambda params: (200, RAW["geometry"]["1001345"])
    result = gdacs.public()
    assert len(result["events"]) == count
    assert len(net.geometries()) == gdacs.MAX_TRACKS
    assert sum(e["track"] is not None for e in result["events"]) == gdacs.MAX_TRACKS


def test_no_track_is_requested_for_an_event_without_an_episode_id(auto_mode, net):
    net.search = lambda params: (200, search_doc([india_feature(1, episodeid=None)]))
    result = gdacs.public()
    assert net.geometries() == []
    assert result["events"][0]["track"] is None


def spend_budget_after_the_first_request(monkeypatch):
    """The first request succeeds, then the whole refresh budget is gone."""
    clock = {"t": 0.0}
    monkeypatch.setattr(gdacs, "_monotonic", lambda: clock["t"])
    real = gdacs._get_json

    def get_json(path, params, deadline):
        doc = real(path, params, deadline)
        clock["t"] += gdacs.DEADLINE_SECONDS + 1
        return doc

    monkeypatch.setattr(gdacs, "_get_json", get_json)


def test_tracks_stop_when_the_refresh_budget_is_used_up(auto_mode, net, monkeypatch):
    net.search = lambda params: (200, search_doc([india_feature(1), india_feature(2)]))
    spend_budget_after_the_first_request(monkeypatch)
    result = gdacs.public()
    assert result["status"] == "ok" and result["is_live"] is True
    assert net.geometries() == []
    assert all(e["track"] is None for e in result["events"])


def test_no_further_page_is_requested_once_the_budget_is_gone(auto_mode, net, monkeypatch):
    net.search = lambda params: (200, search_doc([far_feature(i) for i in range(1, 101)]))
    spend_budget_after_the_first_request(monkeypatch)
    result = gdacs.public()
    assert len(net.searches()) == 1  # page 2 never started
    assert result["is_live"] is False and result["status"] == "ok"  # failed: dated snapshot


# --- source metadata ------------------------------------------------------------------


@pytest.mark.parametrize("mode_fixture", ["fixtures_mode", "live_mode"])
def test_attribution_and_source_are_always_present(request, net, mode_fixture):
    request.getfixturevalue(mode_fixture)
    net.search = FAILURES["timeout"]
    result = gdacs.public()
    assert result["source"] == "GDACS"
    assert result["source_name"] == "Global Disaster Awareness and Coordination System, GDACS"
    assert result["source_name"] in result["attribution"]
    assert result["attribution"] == ("Cyclone data: Global Disaster Awareness and Coordination "
                                     "System, GDACS. Not an IMD product.")
    assert "Not an IMD product" in result["attribution"]
    assert result["source_url"] == "https://www.gdacs.org/"
    assert result["terms_url"].startswith("https://www.gdacs.org/documents/2025/")
    assert "not reviewed by human experts" in result["disclaimer"]
    assert result["area"]["iso3"] == "IND" and result["window_days"] == gdacs.LOOKBACK_DAYS


def test_every_event_names_gdacs_and_the_agency_behind_it(fixtures_mode):
    for event in gdacs.public()["events"]:
        assert event["source"] == "GDACS"
        assert event["source_agency"] == "JTWC"  # GDACS's source, not IMD
        assert event["report_url"].startswith("https://www.gdacs.org/")


# --- refreshing the fixture --------------------------------------------------------------


def test_written_fixture_round_trips_through_the_fixture_reader(
        net, fixtures_mode, monkeypatch, tmp_path):
    target = tmp_path / "snapshots" / "cyclones.json"
    assert gdacs.write_fixture(target) == target
    assert not list(target.parent.glob("*.tmp"))
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved["fetched_at"] == "2026-10-29T12:00:00+00:00"
    assert saved["search"] == RAW["search"] and saved["geometry"] == RAW["geometry"]

    monkeypatch.setattr(gdacs, "fixture_path", lambda: target)  # read the file just written
    result = gdacs.public()
    assert result["is_live"] is False
    assert result["retrieved_at"] == "2026-10-29T12:00:00+00:00"
    assert [e["name"] for e in result["events"]] == ["ARNAB-26"]


def test_failed_refresh_never_overwrites_a_good_fixture(net, tmp_path):
    target = tmp_path / "cyclones.json"
    target.write_text("KEEP ME", encoding="utf-8")
    net.search = FAILURES["server_error"]
    with pytest.raises(httpx.HTTPError):
        gdacs.write_fixture(target)
    assert target.read_text(encoding="utf-8") == "KEEP ME"
    assert list(tmp_path.glob("*.tmp")) == []


# --- the real service (opt in with -m live) -----------------------------------------------


@pytest.mark.live
def test_real_gdacs_answers_with_the_shape_we_parse(monkeypatch):
    monkeypatch.setattr(config, "WEATHER_MODE", "live")
    monkeypatch.setattr(gdacs, "_utcnow", lambda: datetime.now(timezone.utc))  # real clock
    result = gdacs.public()
    assert result["status"] == "ok", "GDACS unreachable or its response shape changed"
    assert result["is_live"] is True and result["complete"] is True
    for event in result["events"]:
        assert event["source"] == "GDACS" and event["matched_by"]
