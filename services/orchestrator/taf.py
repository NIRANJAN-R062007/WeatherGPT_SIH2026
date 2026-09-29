"""TAF decoder -> plain-language aviation forecast briefing (plan.md §6 P2
item 10, the forecast half next to metar.py).

Decodes one raw TAF (ICAO Annex 3 form: header, validity period, base
conditions, then BECMG / TEMPO / FM / PROBnn change groups and TX/TN
temperatures) into a typed dict, and renders an English briefing from that
dict with fixed templates — no LLM, so every figure in the briefing is a
decoded value or a deterministic unit conversion of one.

The wind, visibility, weather and cloud groups are the same as a METAR's, so
they are parsed and worded by metar.py's shared helpers. Anything this
decoder doesn't recognise (windshear groups, icing, turbulence) comes back in
`unparsed` and is named in the briefing rather than guessed at (plan.md §2
principle 4). Remarks (RMK) are passed through raw.
"""

import re

import metar

MAX_RAW_LENGTH = 2000

_STATION = re.compile(r"^[A-Z][A-Z0-9]{3}$")
_ISSUED = re.compile(r"^(\d{2})(\d{2})(\d{2})Z$")
_PERIOD = re.compile(r"^(\d{2})(\d{2})/(\d{2})(\d{2})$")
_FROM = re.compile(r"^FM(\d{2})(\d{2})(\d{2})$")
_PROB = re.compile(r"^PROB(30|40)$")
_TEMPERATURE = re.compile(r"^T([XN])(M)?(\d{2})/(\d{2})(\d{2})Z$")

_CHANGE_LEAD = {
    "BECMG": "Gradually changing",
    "TEMPO": "Temporarily",
    "INTER": "Temporarily",
}


def _stamp(day: int, hour: int, minute: int = 0) -> dict:
    """A day-of-month plus a UTC hour (00-24; 24 is midnight ending the day,
    as TAF validity periods write it), with the IST clock time alongside."""
    return {"day": day, "hour": hour, "minute": minute, **metar._clock(hour, minute)}


def _new_group() -> dict:
    return {**metar.new_conditions(), "unparsed": []}


def _fold(tokens: list[str], i: int, group: dict) -> int:
    """Read the condition group at tokens[i] into `group`; returns the next index."""
    consumed = metar.parse_condition_token(tokens, i, group)
    if consumed is None:
        group["unparsed"].append(tokens[i])
        return i + 1
    return consumed


def decode(raw: str) -> dict:
    """Decode one TAF. Raises ValueError if the input is empty, too long, or
    doesn't start with a station identifier (after an optional TAF / AMD / COR)."""
    text = " ".join(raw.split()).upper().rstrip("=")
    if not text:
        raise ValueError("empty TAF")
    if len(text) > MAX_RAW_LENGTH:
        raise ValueError(f"TAF longer than {MAX_RAW_LENGTH} characters")

    tokens = text.split(" ")
    report_type = "TAF"
    if tokens[0] == "TAF":
        tokens.pop(0)
    if tokens and tokens[0] in ("AMD", "COR"):
        report_type = f"TAF {tokens.pop(0)}"
    if not tokens or not _STATION.match(tokens[0]):
        raise ValueError("TAF must start with a 4-character ICAO station identifier")
    station = tokens.pop(0)

    remarks = None
    if "RMK" in tokens:
        i = tokens.index("RMK")
        remarks = " ".join(tokens[i + 1:]) or None
        tokens = tokens[:i]

    out = {
        "raw": text,
        "type": report_type,
        "station": station,
        "station_name": metar.STATIONS.get(station),
        "issued": None,
        "valid": None,
        "nil": False,
        "cancelled": False,
        "base": _new_group(),
        "changes": [],
        "max_temperature": [],
        "min_temperature": [],
        "remarks": remarks,
        "unparsed": [],
    }

    current = out["base"]
    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if out["issued"] is None and (m := _ISSUED.match(tok)):
            day, hh, mm = (int(g) for g in m.groups())
            out["issued"] = {"day": day, **metar._clock(hh, mm)}
        elif out["valid"] is None and (m := _PERIOD.match(tok)):
            d1, h1, d2, h2 = (int(g) for g in m.groups())
            out["valid"] = {"from": _stamp(d1, h1), "to": _stamp(d2, h2)}
        elif tok == "NIL":
            out["nil"] = True
        elif tok == "CNL":
            out["cancelled"] = True
        elif m := _FROM.match(tok):
            day, hh, mm = (int(g) for g in m.groups())
            current = _new_group()
            out["changes"].append({"kind": "FM", "probability": None,
                                   "from": _stamp(day, hh, mm), "to": None, "conditions": current})
        elif tok in _CHANGE_LEAD or _PROB.match(tok):
            probability = None
            kind = tok
            if m := _PROB.match(tok):
                probability = int(m.group(1))
                if i + 1 < len(tokens) and tokens[i + 1] == "TEMPO":
                    i += 1
                    kind = f"{tok} TEMPO"
            span = _PERIOD.match(tokens[i + 1]) if i + 1 < len(tokens) else None
            current = _new_group()
            change = {"kind": kind, "probability": probability, "from": None, "to": None,
                      "conditions": current}
            if span:
                d1, h1, d2, h2 = (int(g) for g in span.groups())
                change["from"], change["to"] = _stamp(d1, h1), _stamp(d2, h2)
                i += 1
            out["changes"].append(change)
        elif m := _TEMPERATURE.match(tok):
            kind, minus, temp, day, hh = m.groups()
            entry = {"temp_c": metar._signed(minus, temp), **_stamp(int(day), int(hh))}
            out["max_temperature" if kind == "X" else "min_temperature"].append(entry)
        else:
            i = _fold(tokens, i, current)
            continue
        i += 1

    out["unparsed"] = out["base"]["unparsed"] + [
        t for c in out["changes"] for t in c["conditions"]["unparsed"]
    ]
    return out


def _when(s: dict) -> str:
    return f"{s['time_ist']} IST ({s['time_utc']} UTC, day {s['day']})"


def _sentences(group: dict) -> list[str]:
    return [t for t in (
        metar.wind_text(group["wind"]),
        metar.visibility_text(group["visibility"]),
        metar.weather_text(group),
        metar.sky_text(group),
    ) if t]


def _lead(change: dict) -> str:
    kind, probability = change["kind"], change["probability"]
    if kind == "FM":
        return f"From {_when(change['from'])}"
    span = ""
    if change["from"]:
        span = f" between {_when(change['from'])} and {_when(change['to'])}"
    if probability is None:
        return f"{_CHANGE_LEAD[kind]}{span}"
    if kind.endswith("TEMPO"):
        return f"{probability}% chance of temporary conditions{span}"
    return f"{probability}% chance{span}"


def briefing(d: dict) -> str:
    """Plain-language English briefing built only from decode()'s output."""
    return " ".join(briefing_lines(d))


def briefing_lines(d: dict) -> list[str]:
    """The briefing one sentence group per line: the header, then each element or period."""
    name = d["station_name"]
    where = f"{name} airport ({d['station']})" if name else f"Station {d['station']}"
    kind = {
        "TAF AMD": "amended terminal forecast (TAF)",
        "TAF COR": "corrected terminal forecast (TAF)",
    }.get(d["type"], "terminal forecast (TAF)")
    head = f"{where}, {kind}"
    if iss := d["issued"]:
        head += (f" issued at {iss['time_ist']} IST ({iss['time_utc']} UTC"
                 f" on day {iss['day']} of the month)")
    if v := d["valid"]:
        head += f", valid from {_when(v['from'])} to {_when(v['to'])}"
    parts = [head + "."]

    if d["cancelled"]:
        parts.append("This forecast has been cancelled (CNL).")
    if d["nil"]:
        parts.append("No forecast was issued (NIL).")

    parts += _sentences(d["base"])

    for change in d["changes"]:
        body = " ".join(_sentences(change["conditions"])) or "no element decoded."
        parts.append(f"{_lead(change)}: {body}")

    for label, key in (("Highest", "max_temperature"), ("Lowest", "min_temperature")):
        for t in d[key]:
            parts.append(f"{label} temperature {t['temp_c']}°C expected around {_when(t)}.")

    if d["remarks"]:
        parts.append(f"Remarks (not decoded): {d['remarks']}.")
    if d["unparsed"]:
        parts.append(f"Not decoded: {' '.join(d['unparsed'])}.")

    return parts
