"""cap_parser: CAP 1.2 parsing of the simulated samples, and rejection of
everything the parser must refuse (plan.md §8 Phase 4 CAP parsing)."""

import json
import re

import cap_parser
import config
import pytest
from cap_parser import CapParseError

CAP_DIR = config.FIXTURES_DIR / "cap"


def _sample(name: str) -> bytes:
    return (CAP_DIR / name).read_bytes()


# Minimal valid alert used as the base for the rejection tests: each test
# breaks exactly one thing in it.
MINIMAL = """<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>T-1</identifier>
  <sender>simulated@weathergpt.invalid</sender>
  <sent>2026-10-01T08:30:00+05:30</sent>
  <status>Exercise</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <info>
    <language>en-IN</language>
    <category>Met</category>
    <event>Heavy Rain</event>
    <urgency>Expected</urgency>
    <severity>Severe</severity>
    <certainty>Likely</certainty>
    <area>
      <areaDesc>Chennai</areaDesc>
      <polygon>13.25,80.10 13.25,80.32 12.85,80.32 12.85,80.10 13.25,80.10</polygon>
    </area>
  </info>
</alert>"""


def _without(tag: str) -> str:
    out, n = re.subn(rf"\s*<{tag}>[^<]*</{tag}>", "", MINIMAL)
    assert n == 1, tag
    return out


def _with(tag: str, value: str) -> str:
    out, n = re.subn(rf"<{tag}>[^<]*</{tag}>", f"<{tag}>{value}</{tag}>", MINIMAL)
    assert n == 1, tag
    return out


def test_minimal_parses():
    alert = cap_parser.parse(MINIMAL)
    assert alert.identifier == "T-1"
    assert alert.infos[0].areas[0].polygons[0][0] == (13.25, 80.10)


# --- the three simulated samples ---------------------------------------------

def test_alert_sample():
    alert = cap_parser.parse(_sample("SIMULATED_cap_alert_chennai_heavy_rain.xml"))
    assert alert.identifier == "SIMULATED-WGPT-2026-10-01-0001"
    assert alert.sender == "simulated@weathergpt.invalid"
    assert alert.status == "Exercise"
    assert alert.msg_type == "Alert"
    assert alert.scope == "Public"
    assert alert.references is None
    assert alert.sent.isoformat() == "2026-10-01T08:30:00+05:30"

    assert [i.language for i in alert.infos] == ["en-IN", "ta-IN"]
    en, ta = alert.infos
    assert en.categories == ("Met",)
    assert en.event == "Heavy Rain"
    assert (en.urgency, en.severity, en.certainty) == ("Expected", "Severe", "Likely")
    assert en.expires.isoformat() == "2026-10-02T08:30:00+05:30"
    assert ta.event == "கனமழை"
    assert ta.areas[0].area_desc == "சென்னை"

    area = en.areas[0]
    assert area.area_desc == "Chennai"
    assert len(area.polygons) == 1
    ring = area.polygons[0]
    assert len(ring) == 5 and ring[0] == ring[-1]
    assert area.circles == ()
    assert [(g.value_name, g.value) for g in area.geocodes] == [("District", "Chennai")]


def test_update_sample():
    alert = cap_parser.parse(_sample("SIMULATED_cap_update_chennai_heavy_rain.xml"))
    assert alert.msg_type == "Update"
    assert "SIMULATED-WGPT-2026-10-01-0001" in alert.references
    assert len(alert.infos) == 1
    area = alert.infos[0].areas[0]
    assert area.polygons == ()
    assert len(area.circles) == 1
    circle = area.circles[0]
    assert (circle.lat, circle.lon, circle.radius_km) == (13.0827, 80.2707, 15.0)


def test_cancel_sample():
    alert = cap_parser.parse(_sample("SIMULATED_cap_cancel_chennai_heavy_rain.xml"))
    assert alert.msg_type == "Cancel"
    assert alert.status == "Exercise"
    assert "SIMULATED-WGPT-2026-10-01-0001" in alert.references
    assert alert.infos == ()


@pytest.mark.parametrize("name", sorted(p.name for p in CAP_DIR.glob("*.xml")))
def test_samples_are_marked_simulated(name):
    raw = _sample(name).decode("utf-8")
    assert raw.startswith("<!-- SIMULATED sample")
    alert = cap_parser.parse(raw)  # str input works as well as bytes
    assert alert.sender == "simulated@weathergpt.invalid"
    assert alert.status == "Exercise"


@pytest.mark.parametrize("name", sorted(p.name for p in CAP_DIR.glob("*.xml")))
def test_to_dict_is_json_serialisable(name):
    d = cap_parser.parse(_sample(name)).to_dict()
    roundtrip = json.loads(json.dumps(d, ensure_ascii=False))
    assert roundtrip["sent"].startswith("2026-10-01T")
    assert roundtrip == d  # to_dict already turned tuples into lists


def test_to_dict_shape():
    d = cap_parser.parse(_sample("SIMULATED_cap_alert_chennai_heavy_rain.xml")).to_dict()
    assert d["msg_type"] == "Alert"
    info = d["infos"][0]
    assert info["expires"] == "2026-10-02T08:30:00+05:30"
    assert info["areas"][0]["polygons"][0][0] == [13.25, 80.10]
    assert info["areas"][0]["geocodes"][0] == {"value_name": "District", "value": "Chennai"}


# --- verbatim -----------------------------------------------------------------

def test_text_kept_verbatim():
    odd = "  SIMULATED:  Heavy   rain,\n  'Orange'?  "
    xml = MINIMAL.replace(
        "<event>Heavy Rain</event>",
        f"<event>Heavy Rain</event><headline>{odd}</headline>"
        f"<description>{odd}</description>",
    )
    info = cap_parser.parse(xml).infos[0]
    assert info.headline == odd
    assert info.description == odd


def test_severity_not_mapped_to_colour():
    for sev in sorted(cap_parser.SEVERITIES):
        assert cap_parser.parse(_with("severity", sev)).infos[0].severity == sev


# --- required fields ----------------------------------------------------------

@pytest.mark.parametrize("tag", [
    "identifier", "sender", "sent", "status", "msgType", "scope",
    "category", "event", "urgency", "severity", "certainty", "areaDesc",
])
def test_missing_required_field_rejected(tag):
    with pytest.raises(CapParseError, match=tag):
        cap_parser.parse(_without(tag))


@pytest.mark.parametrize("tag", ["identifier", "event", "areaDesc"])
def test_empty_required_field_rejected(tag):
    with pytest.raises(CapParseError, match=tag):
        cap_parser.parse(_with(tag, "   "))


def test_geocode_without_value_rejected():
    xml = MINIMAL.replace(
        "<areaDesc>Chennai</areaDesc>",
        "<areaDesc>Chennai</areaDesc><geocode><valueName>District</valueName></geocode>",
    )
    with pytest.raises(CapParseError, match="value"):
        cap_parser.parse(xml)


# --- enums --------------------------------------------------------------------

@pytest.mark.parametrize("tag,bad", [
    ("status", "Real"),
    ("msgType", "Warning"),
    ("scope", "Everyone"),
    ("category", "Weather"),
    ("urgency", "Soon"),
    ("severity", "Red"),
    ("certainty", "Certain"),
    ("severity", "severe"),  # case matters
])
def test_bad_enum_rejected(tag, bad):
    with pytest.raises(CapParseError, match=tag):
        cap_parser.parse(_with(tag, bad))


# --- hostile / broken input ---------------------------------------------------

def test_doctype_rejected():
    xml = '<!DOCTYPE alert [<!ELEMENT alert ANY>]>\n' + MINIMAL
    with pytest.raises(CapParseError, match="DOCTYPE"):
        cap_parser.parse(xml)


def test_entity_rejected_any_case():
    xml = MINIMAL.replace("<identifier>", '<!eNtItY x "y"><identifier>')
    with pytest.raises(CapParseError, match="ENTITY"):
        cap_parser.parse(xml)


def test_billion_laughs_rejected_before_parsing():
    xml = (
        '<?xml version="1.0"?><!doctype lolz [<!entity lol "lol">'
        '<!entity lol2 "&lol;&lol;&lol;&lol;&lol;">]><lolz>&lol2;</lolz>'
    )
    with pytest.raises(CapParseError, match="DOCTYPE"):
        cap_parser.parse(xml.encode())


def test_oversize_rejected():
    big = MINIMAL.replace("<scope>", "<!--" + "x" * cap_parser.MAX_BYTES + "--><scope>")
    with pytest.raises(CapParseError, match="limit"):
        cap_parser.parse(big)
    with pytest.raises(CapParseError, match="limit"):
        cap_parser.parse(big.encode())


def test_malformed_xml_rejected():
    with pytest.raises(CapParseError, match="malformed"):
        cap_parser.parse(MINIMAL.replace("</scope>", ""))


def test_not_xml_rejected():
    with pytest.raises(CapParseError, match="malformed"):
        cap_parser.parse("not xml at all")


def test_invalid_utf8_rejected():
    with pytest.raises(CapParseError, match="UTF-8"):
        cap_parser.parse(b"\xff\xfe<alert/>")


def test_wrong_namespace_rejected():
    xml = MINIMAL.replace("cap:1.2", "cap:1.1")
    with pytest.raises(CapParseError, match="root"):
        cap_parser.parse(xml)


def test_no_namespace_rejected():
    xml = MINIMAL.replace(' xmlns="urn:oasis:names:tc:emergency:cap:1.2"', "")
    with pytest.raises(CapParseError, match="root"):
        cap_parser.parse(xml)


def test_wrong_root_rejected():
    xml = '<feed xmlns="urn:oasis:names:tc:emergency:cap:1.2"/>'
    with pytest.raises(CapParseError, match="root"):
        cap_parser.parse(xml)


# --- datetimes ----------------------------------------------------------------

def test_naive_sent_rejected():
    with pytest.raises(CapParseError, match="timezone"):
        cap_parser.parse(_with("sent", "2026-10-01T08:30:00"))


def test_naive_expires_rejected():
    xml = MINIMAL.replace(
        "<certainty>Likely</certainty>",
        "<certainty>Likely</certainty><expires>2026-10-02T08:30:00</expires>",
    )
    with pytest.raises(CapParseError, match="expires"):
        cap_parser.parse(xml)


def test_garbage_datetime_rejected():
    with pytest.raises(CapParseError, match="ISO-8601"):
        cap_parser.parse(_with("sent", "yesterday"))


# --- geometry -----------------------------------------------------------------

@pytest.mark.parametrize("polygon,why", [
    ("13.25,80.10 13.25,80.32 12.85,80.32 12.85,80.10 13.0,80.0", "not closed"),
    ("13.25,80.10 13.25,80.32 13.25,80.10", "at least 4"),
    ("", "at least 4"),
    ("95.0,80.10 13.25,80.32 12.85,80.32 95.0,80.10", "out of range"),
    ("13.25,190.0 13.25,80.32 12.85,80.32 13.25,190.0", "out of range"),
    ("nan,80.10 13.25,80.32 12.85,80.32 nan,80.10", "out of range"),
    ("13.25;80.10 13.25,80.32 12.85,80.32 13.25;80.10", "lat,lon"),
    ("a,b 13.25,80.32 12.85,80.32 a,b", "non-numeric"),
])
def test_bad_polygon_rejected(polygon, why):
    with pytest.raises(CapParseError, match=why):
        cap_parser.parse(_with("polygon", polygon))


@pytest.mark.parametrize("circle,why", [
    ("13.08,80.27 -1", ">= 0"),
    ("13.08,80.27 inf", ">= 0"),
    ("13.08,80.27", "lat,lon radius"),
    ("91,80.27 10", "out of range"),
    ("13.08,80.27 ten", "not numeric"),
])
def test_bad_circle_rejected(circle, why):
    xml = MINIMAL.replace(
        "<areaDesc>Chennai</areaDesc>",
        f"<areaDesc>Chennai</areaDesc><circle>{circle}</circle>",
    )
    with pytest.raises(CapParseError, match=why):
        cap_parser.parse(xml)


def test_zero_radius_circle_accepted():
    xml = MINIMAL.replace(
        "<areaDesc>Chennai</areaDesc>",
        "<areaDesc>Chennai</areaDesc><circle>13.08,80.27 0</circle>",
    )
    assert cap_parser.parse(xml).infos[0].areas[0].circles[0].radius_km == 0.0


# --- leniency -----------------------------------------------------------------

def test_unknown_elements_ignored():
    xml = MINIMAL.replace(
        "<scope>Public</scope>",
        "<scope>Public</scope><code>IMD-TEST</code><futureThing a='1'><x/></futureThing>",
    ).replace(
        "<event>Heavy Rain</event>",
        "<event>Heavy Rain</event><parameter><valueName>colour</valueName>"
        "<value>Orange</value></parameter>",
    )
    alert = cap_parser.parse(xml)
    assert alert.identifier == "T-1"
    assert alert.infos[0].severity == "Severe"


def test_missing_language_defaults_to_en_us():
    assert cap_parser.parse(_without("language")).infos[0].language == "en-US"


def test_dataclasses_are_frozen():
    alert = cap_parser.parse(MINIMAL)
    with pytest.raises(AttributeError):
        alert.status = "Actual"
