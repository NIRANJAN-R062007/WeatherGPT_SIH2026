"""OASIS CAP 1.2 parser (plan.md §8 Phase 4, "Proactive alerts — CAP parsing").
— **Syed**

Parses Common Alerting Protocol 1.2 XML (namespace
urn:oasis:names:tc:emergency:cap:1.2) as published by NDMA SACHET, India's CAP
aggregator (plan.md §3.3), into frozen dataclasses.

Nothing uses this module yet. imd_warnings.py still reads hand-written
fixtures and alert_engine.py still matches subscribers city-grained; wiring
this parser into either comes later, once the SACHET feed is connected.

Strict by design: parse() either returns a complete CapAlert or raises
CapParseError, never a partial result. A malformed or tampered message must
not reach users as a half-read warning (plan.md §2 principle 3).

Text is kept verbatim. severity, event, headline and the rest are stored
exactly as the sender wrote them; nothing here maps CAP severity onto the IMD
Red/Orange/Yellow/Green colours (plan.md §2 principle 4).

Nothing here logs message contents, and CapParseError messages name the
offending field but not its value, so a caller that logs the error doesn't
leak the message either.
"""

import math
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from xml.etree import ElementTree as ET

CAP_NS = "urn:oasis:names:tc:emergency:cap:1.2"
_NS = f"{{{CAP_NS}}}"

# A real SACHET alert is a few KB; anything this big is not one.
MAX_BYTES = 256 * 1024

DEFAULT_LANGUAGE = "en-US"  # CAP 1.2 §3.2.2: language defaults to en-US when absent

STATUSES = frozenset({"Actual", "Exercise", "System", "Test", "Draft"})
MSG_TYPES = frozenset({"Alert", "Update", "Cancel", "Ack", "Error"})
SCOPES = frozenset({"Public", "Restricted", "Private"})
URGENCIES = frozenset({"Immediate", "Expected", "Future", "Past", "Unknown"})
SEVERITIES = frozenset({"Extreme", "Severe", "Moderate", "Minor", "Unknown"})
CERTAINTIES = frozenset({"Observed", "Likely", "Possible", "Unlikely", "Unknown"})
CATEGORIES = frozenset({
    "Geo", "Met", "Safety", "Security", "Rescue", "Fire",
    "Health", "Env", "Transport", "Infra", "CBRNE", "Other",
})


class CapParseError(ValueError):
    """The input is not a valid CAP 1.2 alert this parser will accept."""


@dataclass(frozen=True)
class CapCircle:
    lat: float
    lon: float
    radius_km: float


@dataclass(frozen=True)
class CapGeocode:
    value_name: str
    value: str


@dataclass(frozen=True)
class CapArea:
    area_desc: str
    polygons: tuple[tuple[tuple[float, float], ...], ...]  # each a closed ring of (lat, lon)
    circles: tuple[CapCircle, ...]
    geocodes: tuple[CapGeocode, ...]


@dataclass(frozen=True)
class CapInfo:
    language: str
    categories: tuple[str, ...]
    event: str
    urgency: str
    # Verbatim CAP severity. Mapping it to an IMD colour (if ever) is a later
    # decision, not this parser's (plan.md §2 principle 4).
    severity: str
    certainty: str
    effective: datetime | None
    onset: datetime | None
    expires: datetime | None
    sender_name: str | None
    headline: str | None
    description: str | None
    instruction: str | None
    web: str | None
    contact: str | None
    areas: tuple[CapArea, ...]


@dataclass(frozen=True)
class CapAlert:
    identifier: str
    sender: str
    sent: datetime
    status: str
    msg_type: str
    scope: str
    references: str | None
    infos: tuple[CapInfo, ...]

    def to_dict(self) -> dict:
        """JSON-serialisable dict: datetimes as ISO-8601 strings, tuples as lists."""
        return _to_jsonable(self)


def _to_jsonable(value):
    if is_dataclass(value):
        return {f.name: _to_jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        return [_to_jsonable(v) for v in value]
    return value


def parse(xml: str | bytes) -> CapAlert:
    """Parse one CAP 1.2 <alert>. Raises CapParseError on anything invalid."""
    text = _decode(xml)
    _reject_dtd(text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise CapParseError(f"malformed XML ({exc.code})") from None
    if root.tag != f"{_NS}alert":
        raise CapParseError("root element is not a CAP 1.2 <alert>")
    return _parse_alert(root)


def _decode(xml: str | bytes) -> str:
    if isinstance(xml, str):
        size = len(xml.encode("utf-8"))
    elif isinstance(xml, (bytes, bytearray)):
        size = len(xml)
    else:
        raise CapParseError("input must be str or bytes")
    if size > MAX_BYTES:
        raise CapParseError(f"input is {size} bytes, over the {MAX_BYTES}-byte limit")
    if isinstance(xml, str):
        return xml
    # Decode up front so the DOCTYPE/ENTITY check below can't be dodged with
    # a non-UTF-8 encoding. SACHET publishes UTF-8.
    try:
        return bytes(xml).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise CapParseError("input is not valid UTF-8") from None


def _reject_dtd(text: str) -> None:
    # CAP never needs a DTD; refusing one outright closes off entity-expansion
    # ("billion laughs") and external-entity tricks before the XML parser runs.
    lowered = text.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        raise CapParseError("DOCTYPE/ENTITY declarations are not allowed")


def _parse_alert(el: ET.Element) -> CapAlert:
    return CapAlert(
        identifier=_required(el, "identifier", "alert"),
        sender=_required(el, "sender", "alert"),
        sent=_datetime(_required(el, "sent", "alert"), "alert/sent"),
        status=_enum(_required(el, "status", "alert"), STATUSES, "alert/status"),
        msg_type=_enum(_required(el, "msgType", "alert"), MSG_TYPES, "alert/msgType"),
        scope=_enum(_required(el, "scope", "alert"), SCOPES, "alert/scope"),
        references=_optional(el, "references"),
        infos=tuple(_parse_info(i) for i in el.findall(f"{_NS}info")),
    )


def _parse_info(el: ET.Element) -> CapInfo:
    category_els = el.findall(f"{_NS}category")
    categories = tuple(
        _enum((c.text or "").strip(), CATEGORIES, "info/category") for c in category_els
    )
    if not categories:
        raise CapParseError("info/category is missing")
    return CapInfo(
        language=_optional(el, "language", strip=True) or DEFAULT_LANGUAGE,
        categories=categories,
        event=_required(el, "event", "info", verbatim=True),
        urgency=_enum(_required(el, "urgency", "info"), URGENCIES, "info/urgency"),
        severity=_enum(_required(el, "severity", "info"), SEVERITIES, "info/severity"),
        certainty=_enum(_required(el, "certainty", "info"), CERTAINTIES, "info/certainty"),
        effective=_optional_datetime(el, "effective"),
        onset=_optional_datetime(el, "onset"),
        expires=_optional_datetime(el, "expires"),
        sender_name=_optional(el, "senderName"),
        headline=_optional(el, "headline"),
        description=_optional(el, "description"),
        instruction=_optional(el, "instruction"),
        web=_optional(el, "web", strip=True),
        contact=_optional(el, "contact"),
        areas=tuple(_parse_area(a) for a in el.findall(f"{_NS}area")),
    )


def _parse_area(el: ET.Element) -> CapArea:
    return CapArea(
        area_desc=_required(el, "areaDesc", "area", verbatim=True),
        polygons=tuple(_polygon(p.text) for p in el.findall(f"{_NS}polygon")),
        circles=tuple(_circle(c.text) for c in el.findall(f"{_NS}circle")),
        geocodes=tuple(_geocode(g) for g in el.findall(f"{_NS}geocode")),
    )


def _geocode(el: ET.Element) -> CapGeocode:
    return CapGeocode(
        value_name=_required(el, "valueName", "geocode"),
        value=_required(el, "value", "geocode"),
    )


def _optional(el: ET.Element, tag: str, strip: bool = False) -> str | None:
    """Text of the first <tag> child, or None if absent/blank. Kept verbatim
    unless strip=True (used only for tokens like language and URLs)."""
    child = el.find(f"{_NS}{tag}")
    if child is None or child.text is None or not child.text.strip():
        return None
    return child.text.strip() if strip else child.text


def _required(el: ET.Element, tag: str, where: str, verbatim: bool = False) -> str:
    value = _optional(el, tag, strip=not verbatim)
    if value is None:
        raise CapParseError(f"{where}/{tag} is missing or empty")
    return value


def _enum(value: str, allowed: frozenset[str], where: str) -> str:
    if value not in allowed:
        raise CapParseError(f"{where} is not one of {sorted(allowed)}")
    return value


def _datetime(value: str, where: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise CapParseError(f"{where} is not an ISO-8601 datetime") from None
    if parsed.tzinfo is None:
        raise CapParseError(f"{where} has no timezone offset")
    return parsed


def _optional_datetime(el: ET.Element, tag: str) -> datetime | None:
    value = _optional(el, tag, strip=True)
    return None if value is None else _datetime(value, f"info/{tag}")


def _point(token: str, where: str) -> tuple[float, float]:
    parts = token.split(",")
    if len(parts) != 2:
        raise CapParseError(f"{where} has a point that is not 'lat,lon'")
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        raise CapParseError(f"{where} has a non-numeric coordinate") from None
    # NaN fails both comparisons, so it's rejected here too.
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise CapParseError(f"{where} has a coordinate out of range")
    return lat, lon


def _polygon(text: str | None) -> tuple[tuple[float, float], ...]:
    points = tuple(_point(t, "area/polygon") for t in (text or "").split())
    if len(points) < 4:
        raise CapParseError("area/polygon needs at least 4 points")
    if points[0] != points[-1]:
        raise CapParseError("area/polygon is not closed (first point != last point)")
    return points


def _circle(text: str | None) -> CapCircle:
    parts = (text or "").split()
    if len(parts) != 2:
        raise CapParseError("area/circle is not 'lat,lon radius'")
    lat, lon = _point(parts[0], "area/circle")
    try:
        radius = float(parts[1])
    except ValueError:
        raise CapParseError("area/circle radius is not numeric") from None
    if not math.isfinite(radius) or radius < 0:
        raise CapParseError("area/circle radius must be a finite number >= 0")
    return CapCircle(lat=lat, lon=lon, radius_km=radius)
