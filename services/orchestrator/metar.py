"""METAR decoder -> plain-language aviation briefing (plan.md §6 P2 item 10).

Decodes one raw METAR/SPECI report (WMO FM 15 / FM 16, the ICAO Annex 3 form
Indian airports issue, plus the US statute-mile and inHg variants) into a
typed dict, and renders an English briefing from that dict with fixed
templates — no LLM, so every figure in the briefing is either a decoded value
or a deterministic unit conversion of one.

Tokens this decoder doesn't recognise are returned in `unparsed` and named in
the briefing rather than guessed at (plan.md §2 principle 4). The trend group
(BECMG/TEMPO) and remarks (RMK) are passed through raw, not decoded.

TAF (the forecast format) is decoded by taf.py, which reuses this module's
wind / visibility / weather / cloud parsers and sentence templates.
"""

import re

MAX_RAW_LENGTH = 300

# The demo cities' airports (data/cities.json); other stations decode fine,
# they just have no display name.
STATIONS = {
    "VOMM": "Chennai",
    "VOMD": "Madurai",
    "VOCB": "Coimbatore",
    "VOBL": "Bengaluru",
    "VOHS": "Hyderabad",
    "VABB": "Mumbai",
    "VIDP": "Delhi",
    "VOTV": "Thiruvananthapuram",
    # TFA-8: airports for the travel advisory's added destinations. Each code was
    # checked against a live aviationweather.gov METAR on 2026-10-05.
    "VOGO": "Panaji",            # Goa (Dabolim)
    "VILH": "Leh",
    "VOPB": "Port Blair",
    "VOCI": "Kochi",
    "VECC": "Kolkata",
    "VIJP": "Jaipur",
    "VAAH": "Ahmedabad",
    "VILK": "Lucknow",
    "VEBN": "Varanasi",
    "VEGT": "Guwahati",
    "VISR": "Srinagar",
    "VOVZ": "Visakhapatnam",
    "VOTR": "Tiruchirappalli",
}

_INTENSITY = {"-": "light", "+": "heavy", "VC": "in the vicinity"}
_DESCRIPTOR = {
    "MI": "shallow", "PR": "partial", "BC": "patches of", "DR": "low drifting",
    "BL": "blowing", "SH": "showers", "TS": "thunderstorm", "FZ": "freezing",
}
_PHENOMENA = {
    "DZ": "drizzle", "RA": "rain", "SN": "snow", "SG": "snow grains",
    "IC": "ice crystals", "PL": "ice pellets", "GR": "hail", "GS": "small hail",
    "UP": "unknown precipitation", "BR": "mist", "FG": "fog", "FU": "smoke",
    "VA": "volcanic ash", "DU": "widespread dust", "SA": "sand", "HZ": "haze",
    "PY": "spray", "PO": "dust whirls", "SQ": "squalls", "FC": "funnel cloud",
    "SS": "sandstorm", "DS": "duststorm",
}
_COVER = {"FEW": "few", "SCT": "scattered", "BKN": "broken", "OVC": "overcast"}
_CLOUD_TYPE = {"CB": "cumulonimbus", "TCU": "towering cumulus"}
_SKY_CLEAR = {
    "NSC": "No significant cloud.",
    "NCD": "No cloud detected.",
    "SKC": "Sky clear.",
    "CLR": "No cloud below 12,000 ft.",
}
_COMPASS = ["north", "north-northeast", "northeast", "east-northeast", "east",
            "east-southeast", "southeast", "south-southeast", "south",
            "south-southwest", "southwest", "west-southwest", "west",
            "west-northwest", "northwest", "north-northwest"]

_STATION = re.compile(r"^[A-Z][A-Z0-9]{3}$")
_TIME = re.compile(r"^(\d{2})(\d{2})(\d{2})Z$")
_WIND = re.compile(r"^(\d{3}|VRB)(\d{2,3})(?:G(\d{2,3}))?(KT|MPS|KMH)$")
_WIND_VARYING = re.compile(r"^(\d{3})V(\d{3})$")
_VIS_METRES = re.compile(r"^(\d{4})(NDV)?$")
_VIS_SM = re.compile(r"^([MP])?(?:(\d+)|(\d+)/(\d+))SM$")
_VIS_SM_FRACTION = re.compile(r"^(\d)/(\d)SM$")
_RVR = re.compile(r"^R(\d{2}[LCR]?)/([PM])?(\d{4})(?:V([PM])?(\d{4}))?(FT)?/?([UDN])?$")
_WEATHER = re.compile(
    r"^(-|\+|VC)?(MI|PR|BC|DR|BL|SH|TS|FZ)?((?:" + "|".join(_PHENOMENA) + r")*)$"
)
# Indian reports write "FEW025TCU/CB" when either type may occur.
_CLOUD = re.compile(r"^(FEW|SCT|BKN|OVC)(\d{3})((?:CB|TCU)(?:/(?:CB|TCU))?)?$")
_VERTICAL_VIS = re.compile(r"^VV(\d{3})$")
_TEMP = re.compile(r"^(M)?(\d{2})/(M)?(\d{2})$")
_QNH = re.compile(r"^Q(\d{4})$")
_ALTIMETER = re.compile(r"^A(\d{4})$")


def _kmh(speed: int, unit: str) -> int:
    if unit == "KT":
        return round(speed * 1.852)
    if unit == "MPS":
        return round(speed * 3.6)
    return speed


def _knots(speed: int, unit: str) -> int:
    if unit == "KT":
        return speed
    if unit == "MPS":
        return round(speed * 3.6 / 1.852)
    return round(speed / 1.852)


def _signed(minus: str | None, digits: str) -> int:
    return -int(digits) if minus else int(digits)


def _compass(degrees: int) -> str:
    return _COMPASS[round(degrees / 22.5) % 16]


def _weather(token: str) -> dict | None:
    m = _WEATHER.match(token)
    if not m or not (m.group(2) or m.group(3)):
        return None
    intensity, descriptor, codes = m.groups()
    phenomena = [_PHENOMENA[codes[i:i + 2]] for i in range(0, len(codes), 2)]
    words = " and ".join(phenomena)
    if intensity in ("-", "+") and phenomena:
        # Intensity qualifies the precipitation: +TSRA is "thunderstorm with heavy rain".
        words = f"{_INTENSITY[intensity]} {words}"
    if descriptor == "SH" and phenomena:
        text = f"{words} showers"
    elif descriptor == "TS" and phenomena:
        text = f"thunderstorm with {words}"
    else:
        text = " ".join(filter(None, [_DESCRIPTOR.get(descriptor), words]))
    if intensity == "VC":
        text = f"{text} in the vicinity"
    return {
        "code": token,
        "intensity": _INTENSITY.get(intensity),
        "descriptor": _DESCRIPTOR.get(descriptor),
        "phenomena": phenomena,
        "text": text,
    }


def _weather_groups(token: str) -> list[dict]:
    """One weather group, or several joined by "/" as Indian reports write
    them ("-DZ/BR" = light drizzle and mist). Empty if any part isn't weather."""
    found = [_weather(part) for part in token.split("/")]
    return found if all(found) else []


def decode(raw: str) -> dict:
    """Decode one METAR/SPECI. Raises ValueError if the input is empty, too
    long, or doesn't start with a station identifier."""
    text = " ".join(raw.split()).upper().rstrip("=")
    if not text:
        raise ValueError("empty METAR")
    if len(text) > MAX_RAW_LENGTH:
        raise ValueError(f"METAR longer than {MAX_RAW_LENGTH} characters")

    tokens = text.split(" ")
    report_type = "METAR"
    if tokens[0] in ("METAR", "SPECI"):
        report_type = tokens.pop(0)
    if not tokens or not _STATION.match(tokens[0]):
        raise ValueError("METAR must start with a 4-character ICAO station identifier")
    station = tokens.pop(0)

    remarks = None
    if "RMK" in tokens:
        i = tokens.index("RMK")
        remarks = " ".join(tokens[i + 1:]) or None
        tokens = tokens[:i]
    trend = None
    for marker in ("NOSIG", "BECMG", "TEMPO"):
        if marker in tokens:
            i = tokens.index(marker)
            trend = " ".join(tokens[i:])
            tokens = tokens[:i]
            break

    out = {
        "raw": text,
        "type": report_type,
        "station": station,
        "station_name": STATIONS.get(station),
        "observed": None,
        "auto": False,
        "corrected": False,
        "nil": False,
        "wind": None,
        "visibility": None,
        "runway_visual_range": [],
        "weather": [],
        "no_significant_weather": False,
        "clouds": [],
        "sky_condition": None,
        "vertical_visibility_ft": None,
        "temperature_c": None,
        "dewpoint_c": None,
        "pressure_hpa": None,
        "pressure_inhg": None,
        "trend": trend,
        "remarks": remarks,
        "unparsed": [],
    }

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1

        if m := _TIME.match(tok):
            day, hh, mm = (int(g) for g in m.groups())
            out["observed"] = {"day": day, **_clock(hh, mm)}
        elif tok == "AUTO":
            out["auto"] = True
        elif tok == "COR":
            out["corrected"] = True
        elif tok == "NIL":
            out["nil"] = True
        elif m := _RVR.match(tok):
            runway, lo_pfx, lo, hi_pfx, hi, feet, tendency = m.groups()
            out["runway_visual_range"].append({
                "runway": runway,
                "unit": "ft" if feet else "m",
                "min": int(lo),
                "max": int(hi) if hi else None,
                "above": (hi_pfx or lo_pfx) == "P",
                "below": lo_pfx == "M",
                "tendency": {"U": "rising", "D": "falling", "N": "no change"}.get(tendency),
            })
        elif m := _TEMP.match(tok):
            t_minus, t, d_minus, d = m.groups()
            out["temperature_c"] = _signed(t_minus, t)
            out["dewpoint_c"] = _signed(d_minus, d)
        elif m := _QNH.match(tok):
            out["pressure_hpa"] = int(m.group(1))
        elif m := _ALTIMETER.match(tok):
            inhg = int(m.group(1)) / 100
            out["pressure_inhg"] = inhg
            out["pressure_hpa"] = round(inhg * 33.8639)
        elif (consumed := parse_condition_token(tokens, i - 1, out)) is not None:
            i = consumed
        else:
            out["unparsed"].append(tok)

    return out


def _clock(hh: int, mm: int) -> dict:
    """UTC hour/minute as the {time_utc, time_ist} pair both decoders report."""
    ist = (hh * 60 + mm + 330) % 1440
    return {"time_utc": f"{hh:02d}:{mm:02d}", "time_ist": f"{ist // 60:02d}:{ist % 60:02d}"}


def new_conditions() -> dict:
    """The condition fields a METAR and each TAF period share."""
    return {
        "wind": None,
        "visibility": None,
        "weather": [],
        "no_significant_weather": False,
        "clouds": [],
        "sky_condition": None,
        "vertical_visibility_ft": None,
    }


def parse_condition_token(tokens: list[str], i: int, out: dict) -> int | None:
    """Fold tokens[i] into `out` when it is a wind, visibility, weather or
    cloud group (the groups a METAR and a TAF spell identically). Returns the
    index of the next unread token, or None if tokens[i] isn't one of them.
    A statute-mile visibility like "1 1/2SM" spans two tokens, hence the index."""
    tok = tokens[i]
    if m := _WIND.match(tok):
        direction, speed, gust, unit = m.groups()
        speed = int(speed)
        gust = int(gust) if gust else None
        out["wind"] = {
            "calm": direction == "000" and speed == 0,
            "variable": direction == "VRB",
            "direction_deg": None if direction == "VRB" else int(direction),
            "speed_kt": _knots(speed, unit),
            "speed_kmh": _kmh(speed, unit),
            "gust_kt": _knots(gust, unit) if gust else None,
            "gust_kmh": _kmh(gust, unit) if gust else None,
            "varying_from_deg": None,
            "varying_to_deg": None,
        }
    elif (m := _WIND_VARYING.match(tok)) and out["wind"]:
        out["wind"]["varying_from_deg"] = int(m.group(1))
        out["wind"]["varying_to_deg"] = int(m.group(2))
    elif tok == "CAVOK":
        out["visibility"] = {"cavok": True, "metres": 10000, "statute_miles": None,
                             "at_least": True, "less_than": False}
    elif (m := _VIS_METRES.match(tok)) and out["visibility"] is None:
        metres = int(m.group(1))
        out["visibility"] = {"cavok": False, "metres": 10000 if metres == 9999 else metres,
                             "statute_miles": None, "at_least": metres == 9999,
                             "less_than": False}
    elif (tok.isdigit() and len(tok) == 1 and i + 1 < len(tokens)
          and (m := _VIS_SM_FRACTION.match(tokens[i + 1]))):
        # "1 1/2SM" arrives as two tokens.
        miles = int(tok) + int(m.group(1)) / int(m.group(2))
        out["visibility"] = {"cavok": False, "metres": round(miles * 1609.344),
                             "statute_miles": miles, "at_least": False,
                             "less_than": False}
        return i + 2
    elif m := _VIS_SM.match(tok):
        prefix, whole, num, den = m.groups()
        miles = int(whole) if whole else int(num) / int(den)
        out["visibility"] = {"cavok": False, "metres": round(miles * 1609.344),
                             "statute_miles": miles, "at_least": prefix == "P",
                             "less_than": prefix == "M"}
    elif tok == "NSW":
        out["no_significant_weather"] = True
    elif m := _CLOUD.match(tok):
        cover, height, kind = m.groups()
        out["clouds"].append({
            "code": cover,
            "cover": _COVER[cover],
            "base_ft": int(height) * 100,
            "type": " / ".join(_CLOUD_TYPE[k] for k in kind.split("/")) if kind else None,
        })
    elif m := _VERTICAL_VIS.match(tok):
        out["vertical_visibility_ft"] = int(m.group(1)) * 100
    elif tok in _SKY_CLEAR:
        out["sky_condition"] = tok
    elif wx := _weather_groups(tok):
        out["weather"].extend(wx)
    else:
        return None
    return i + 1


def _distance(v: dict) -> str:
    metres = v["metres"]
    if metres >= 5000:
        km = f"{metres // 1000} km"
    elif metres >= 1000:
        km = f"{round(metres / 1000, 1):g} km"
    else:
        km = f"{metres} m"
    if (miles := v.get("statute_miles")) is not None:
        return f"{miles:g} statute miles ({km})"
    return km


def wind_text(w: dict | None) -> str | None:
    if not w:
        return None
    if w["calm"]:
        return "Wind calm."
    if w["variable"]:
        s = f"Wind variable in direction at {w['speed_kmh']} km/h ({w['speed_kt']} kt)"
    else:
        s = (f"Wind from the {_compass(w['direction_deg'])} ({w['direction_deg']}°)"
             f" at {w['speed_kmh']} km/h ({w['speed_kt']} kt)")
    if w["gust_kmh"]:
        s += f", gusting to {w['gust_kmh']} km/h ({w['gust_kt']} kt)"
    if w["varying_from_deg"] is not None:
        s += f", varying between {w['varying_from_deg']}° and {w['varying_to_deg']}°"
    return s + "."


def visibility_text(v: dict | None) -> str | None:
    if not v:
        return None
    if v["cavok"]:
        return ("Ceiling and visibility OK: visibility 10 km or more, "
                "no cloud below 5,000 ft and no significant weather.")
    if v["at_least"]:
        return f"Visibility {_distance(v)} or more."
    if v["less_than"]:
        return f"Visibility less than {_distance(v)}."
    return f"Visibility {_distance(v)}."


def weather_text(d: dict) -> str | None:
    if d["weather"]:
        return "Weather: " + ", ".join(wx["text"] for wx in d["weather"]) + "."
    if d["no_significant_weather"]:
        return "No significant weather."
    return None


def sky_text(d: dict) -> str | None:
    if d["clouds"]:
        layers = []
        for c in d["clouds"]:
            layer = f"{c['cover']} at {c['base_ft']:,} ft"
            if c["type"]:
                layer += f" ({c['type']})"
            layers.append(layer)
        return "Cloud: " + ", ".join(layers) + "."
    if d["vertical_visibility_ft"] is not None:
        return f"Sky obscured, vertical visibility {d['vertical_visibility_ft']:,} ft."
    if d["sky_condition"]:
        return _SKY_CLEAR[d["sky_condition"]]
    return None


def briefing(d: dict) -> str:
    """Plain-language English briefing built only from decode()'s output."""
    return " ".join(briefing_lines(d))


def briefing_lines(d: dict) -> list[str]:
    """The briefing one sentence group per line: the header, then each element or period."""
    name = d["station_name"]
    where = f"{name} airport ({d['station']})" if name else f"Station {d['station']}"
    head = f"{where}, {'special report' if d['type'] == 'SPECI' else 'routine report'}"
    if obs := d["observed"]:
        # The METAR day belongs to the UTC time; IST can already be the next day.
        head += (f" observed at {obs['time_ist']} IST ({obs['time_utc']} UTC"
                 f" on day {obs['day']} of the month)")
    parts = [head + "."]
    if d["corrected"]:
        parts.append("This is a corrected report.")
    if d["auto"]:
        parts.append("Fully automated observation.")
    if d["nil"]:
        parts.append("No observation was reported (NIL).")

    parts += [t for t in (wind_text(d["wind"]), visibility_text(d["visibility"])) if t]

    for r in d["runway_visual_range"]:
        unit = r["unit"]
        if r["max"] is not None:
            s = f"Runway {r['runway']} visual range {r['min']} to {r['max']} {unit}"
        else:
            qualifier = "more than " if r["above"] else "less than " if r["below"] else ""
            s = f"Runway {r['runway']} visual range {qualifier}{r['min']} {unit}"
        if r["tendency"]:
            s += f", {r['tendency']}"
        parts.append(s + ".")

    parts += [t for t in (weather_text(d), sky_text(d)) if t]

    if d["temperature_c"] is not None:
        parts.append(f"Temperature {d['temperature_c']}°C, dew point {d['dewpoint_c']}°C.")
    if d["pressure_hpa"] is not None:
        if d["pressure_inhg"] is not None:
            parts.append(f"Pressure {d['pressure_hpa']} hPa ({d['pressure_inhg']:.2f} inHg).")
        else:
            parts.append(f"Pressure (QNH) {d['pressure_hpa']} hPa.")

    if d["trend"] == "NOSIG":
        parts.append("No significant change expected in the next 2 hours.")
    elif d["trend"]:
        parts.append(f"Trend (not decoded): {d['trend']}.")
    if d["remarks"]:
        parts.append(f"Remarks (not decoded): {d['remarks']}.")
    if d["unparsed"]:
        parts.append(f"Not decoded: {' '.join(d['unparsed'])}.")

    return parts
