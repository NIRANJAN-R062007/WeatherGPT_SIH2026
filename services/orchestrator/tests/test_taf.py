"""TAF decoder and GET /taf/decode (plan.md §6 P2 item 10). Pure parsing, fully
offline. The Chennai and Mumbai reports are real ones snapshotted from
aviationweather.gov into data/fixtures/aviation/."""

import main
import metar
import pytest
import taf
from fastapi.testclient import TestClient

client = TestClient(main.app)

CHENNAI = (
    "TAF VOMM 291700Z 2918/3024 25010KT 4000 -DZ/BR SCT018 SCT100 "
    "TEMPO 2921/3003 SCT018 FEW025TCU/CB SCT100 "
    "BECMG 3003/3004 6000 "
    "BECMG 3009/3010 12010KT "
    "TEMPO 3009/3015 SCT018 FEW025TCU/CB "
    "BECMG 3015/3016 25010KT 4000 BR"
)
MUMBAI = (
    "TAF VABB 292000Z 2921/3006 09008KT 2000 -SHRA RA BR FEW010 SCT015 FEW030CB OVC080 "
    "TEMPO 2921/3003 02010G20KT 0800 TSRA +SHRA +RA SCT008 SCT015 FEW030CB OVC080 "
    "BECMG 3004/3006 34010KT 3000 -SHRA BR HZ SCT018 FEW025TCU BKN090"
)


# --- decode(): the header and validity ----------------------------------------


def test_chennai_header_and_validity():
    d = taf.decode(CHENNAI)
    assert d["type"] == "TAF"
    assert d["station"] == "VOMM" and d["station_name"] == "Chennai"
    assert d["issued"] == {"day": 29, "time_utc": "17:00", "time_ist": "22:30"}
    v = d["valid"]
    assert (v["from"]["day"], v["from"]["hour"], v["from"]["time_ist"]) == (29, 18, "23:30")
    # 24 is midnight ending the day, as TAF validity writes it.
    assert (v["to"]["day"], v["to"]["hour"], v["to"]["time_utc"]) == (30, 24, "24:00")
    assert v["to"]["time_ist"] == "05:30"


def test_chennai_base_conditions_decode_fully():
    d = taf.decode(CHENNAI)
    base = d["base"]
    assert (base["wind"]["direction_deg"], base["wind"]["speed_kt"]) == (250, 10)
    assert base["visibility"]["metres"] == 4000
    # "-DZ/BR" is Indian style for light drizzle and mist.
    assert [w["text"] for w in base["weather"]] == ["light drizzle", "mist"]
    assert [(c["code"], c["base_ft"]) for c in base["clouds"]] == [("SCT", 1800), ("SCT", 10000)]
    assert d["unparsed"] == []


def test_change_groups_in_order():
    d = taf.decode(CHENNAI)
    assert [c["kind"] for c in d["changes"]] == ["TEMPO", "BECMG", "BECMG", "TEMPO", "BECMG"]
    tempo = d["changes"][0]
    assert (tempo["from"]["day"], tempo["from"]["hour"]) == (29, 21)
    assert (tempo["to"]["day"], tempo["to"]["hour"]) == (30, 3)
    cloud = tempo["conditions"]["clouds"][1]
    assert cloud["type"] == "towering cumulus / cumulonimbus"  # "TCU/CB"
    assert d["changes"][1]["conditions"]["visibility"]["metres"] == 6000
    assert d["changes"][2]["conditions"]["wind"]["direction_deg"] == 120


def test_mumbai_thunderstorm_group():
    d = taf.decode(MUMBAI)
    assert d["unparsed"] == []
    tempo = d["changes"][0]["conditions"]
    assert tempo["wind"]["gust_kt"] == 20 and tempo["wind"]["gust_kmh"] == 37
    assert tempo["visibility"]["metres"] == 800
    assert [w["text"] for w in tempo["weather"]] == [
        "thunderstorm with rain", "heavy rain showers", "heavy rain",
    ]
    assert tempo["clouds"][2]["type"] == "cumulonimbus"


# --- the other change indicators ----------------------------------------------


def test_from_group_replaces_conditions_at_a_time():
    d = taf.decode("TAF VIDP 300500Z 3006/3106 09008KT 5000 HZ FM301200 27010KT 9999 NSW")
    (fm,) = d["changes"]
    assert fm["kind"] == "FM" and fm["to"] is None
    assert (fm["from"]["day"], fm["from"]["hour"], fm["from"]["minute"]) == (30, 12, 0)
    assert fm["conditions"]["wind"]["direction_deg"] == 270
    assert fm["conditions"]["visibility"]["at_least"] is True
    assert fm["conditions"]["no_significant_weather"] is True


def test_from_group_with_minutes():
    d = taf.decode("TAF VIDP 300500Z 3006/3106 09008KT FM301245 27010KT")
    assert d["changes"][0]["from"]["minute"] == 45
    assert d["changes"][0]["from"]["time_utc"] == "12:45"


@pytest.mark.parametrize(
    "groups, kind, probability",
    [
        ("PROB30 3010/3014 3000 TSRA", "PROB30", 30),
        ("PROB40 3010/3014 3000 TSRA", "PROB40", 40),
        ("PROB30 TEMPO 3010/3014 3000 TSRA", "PROB30 TEMPO", 30),
    ],
)
def test_probability_groups(groups, kind, probability):
    d = taf.decode(f"TAF VOMM 300500Z 3006/3106 09008KT 5000 HZ {groups}")
    (change,) = d["changes"]
    assert (change["kind"], change["probability"]) == (kind, probability)
    assert (change["from"]["hour"], change["to"]["hour"]) == (10, 14)
    assert change["conditions"]["visibility"]["metres"] == 3000


def test_temperatures():
    d = taf.decode("TAF VIDP 300500Z 3006/3106 09008KT 5000 HZ TX32/3109Z TNM02/3121Z")
    assert d["max_temperature"][0]["temp_c"] == 32
    assert (d["max_temperature"][0]["day"], d["max_temperature"][0]["hour"]) == (31, 9)
    assert d["min_temperature"][0]["temp_c"] == -2  # M = minus


def test_amended_and_corrected_headers():
    assert taf.decode("TAF AMD VOMM 300500Z 3006/3106 09008KT 5000")["type"] == "TAF AMD"
    assert taf.decode("TAF COR VOMM 300500Z 3006/3106 09008KT 5000")["type"] == "TAF COR"
    assert taf.decode("VOMM 300500Z 3006/3106 09008KT 5000")["type"] == "TAF"  # "TAF" optional


def test_cancelled_and_nil():
    assert taf.decode("TAF VOMM 300500Z 3006/3106 CNL")["cancelled"] is True
    assert taf.decode("TAF VOMM 300500Z NIL")["nil"] is True


def test_remarks_passed_through_raw():
    d = taf.decode("TAF VOMM 300500Z 3006/3106 09008KT 5000 RMK NXT FCST BY 301100Z")
    assert d["remarks"] == "NXT FCST BY 301100Z"


def test_unknown_group_is_reported_not_guessed():
    d = taf.decode("TAF VOMM 300500Z 3006/3106 09008KT 5000 WS020/24045KT")
    assert d["unparsed"] == ["WS020/24045KT"]
    assert "Not decoded: WS020/24045KT." in taf.briefing(d)


def test_unknown_group_inside_a_change_group_is_collected():
    d = taf.decode("TAF VOMM 300500Z 3006/3106 09008KT 5000 TEMPO 3010/3012 620304 3000")
    assert d["unparsed"] == ["620304"]
    assert d["changes"][0]["conditions"]["visibility"]["metres"] == 3000


# --- errors -------------------------------------------------------------------


@pytest.mark.parametrize("raw", ["", "   ", "TAF", "TAF 291700Z 2918/3024", "TAF X 291700Z"])
def test_rejects_input_without_a_station(raw):
    with pytest.raises(ValueError):
        taf.decode(raw)


def test_rejects_overlong_input():
    with pytest.raises(ValueError, match="longer than"):
        taf.decode("TAF VOMM " + "3000 " * 500)


# --- briefing() ---------------------------------------------------------------


def test_briefing_header_and_groups():
    text = taf.briefing(taf.decode(CHENNAI))
    assert text.startswith(
        "Chennai airport (VOMM), terminal forecast (TAF) issued at 22:30 IST "
        "(17:00 UTC on day 29 of the month), valid from 23:30 IST (18:00 UTC, day 29) "
        "to 05:30 IST (24:00 UTC, day 30)."
    )
    assert "Wind from the west-southwest (250°) at 19 km/h (10 kt)." in text
    assert "Weather: light drizzle, mist." in text
    assert "Temporarily between 02:30 IST (21:00 UTC, day 29)" in text
    assert "Gradually changing between 08:30 IST (03:00 UTC, day 30)" in text
    assert "few at 2,500 ft (towering cumulus / cumulonimbus)" in text
    assert "Not decoded" not in text


def test_briefing_wording_of_each_indicator():
    d = taf.decode(
        "TAF VOMM 300500Z 3006/3106 09008KT 5000 FM301200 27010KT "
        "PROB30 3010/3014 3000 TSRA PROB40 TEMPO 3016/3018 1500 FG TX32/3109Z"
    )
    text = taf.briefing(d)
    assert "From 17:30 IST (12:00 UTC, day 30): Wind from the west (270°)" in text
    assert (
        "30% chance between 15:30 IST (10:00 UTC, day 30) and 19:30 IST (14:00 UTC, day 30):"
        in text
    )
    assert "40% chance of temporary conditions between" in text
    assert "Highest temperature 32°C expected around 14:30 IST (09:00 UTC, day 31)." in text


def test_briefing_names_station_without_a_display_name():
    d = taf.decode("TAF VECC 300500Z 3006/3106 09008KT 5000")
    assert d["station_name"] is None
    assert taf.briefing(d).startswith("Station VECC, terminal forecast (TAF)")


def test_briefing_says_when_nothing_was_decoded_in_a_group():
    d = taf.decode("TAF VOMM 300500Z 3006/3106 09008KT 5000 TEMPO 3010/3012")
    assert "Temporarily between" in taf.briefing(d)
    assert "no element decoded." in taf.briefing(d)


def test_briefing_for_cancelled_forecast():
    text = taf.briefing(taf.decode("TAF VOMM 300500Z 3006/3106 CNL"))
    assert "This forecast has been cancelled (CNL)." in text


# --- shared with metar.py -----------------------------------------------------


def test_metar_understands_the_indian_slash_groups_too():
    d = metar.decode("VOMM 291130Z 24012KT 4000 -DZ/BR FEW025TCU/CB 28/25 Q1006")
    assert [w["text"] for w in d["weather"]] == ["light drizzle", "mist"]
    assert d["clouds"][0]["type"] == "towering cumulus / cumulonimbus"
    assert d["unparsed"] == []


def test_weather_group_with_a_non_weather_part_is_not_decoded():
    d = metar.decode("VOMM 291130Z 24012KT 4000 BR/XYZ")
    assert d["weather"] == [] and d["unparsed"] == ["BR/XYZ"]


# --- GET /taf/decode ----------------------------------------------------------


def test_endpoint_decodes_and_briefs():
    r = client.get("/taf/decode", params={"raw": MUMBAI})
    assert r.status_code == 200
    body = r.json()
    assert body["decoded"]["station"] == "VABB"
    assert body["briefing"].startswith("Mumbai airport (VABB), terminal forecast (TAF)")


def test_endpoint_rejects_bad_input_with_422():
    assert client.get("/taf/decode", params={"raw": "hello"}).status_code == 422
    assert client.get("/taf/decode", params={"raw": ""}).status_code == 422
    assert client.get("/taf/decode").status_code == 422


# --- briefing_lines() ---------------------------------------------------------


def test_briefing_lines_join_to_the_briefing():
    d = taf.decode(CHENNAI)
    lines = taf.briefing_lines(d)
    assert " ".join(lines) == taf.briefing(d)
    assert lines[0].startswith("Chennai airport (VOMM), terminal forecast (TAF)")
    # one line per change group after the header and the base conditions
    assert sum(1 for line in lines if line.startswith(("Temporarily", "Gradually changing"))) == 5


def test_metar_briefing_lines_join_to_the_briefing():
    d = metar.decode("VOMM 291130Z 24012KT 6000 SCT020 BKN080 31/25 Q1006 NOSIG")
    assert " ".join(metar.briefing_lines(d)) == metar.briefing(d)
    assert metar.briefing_lines(d)[0].startswith("Chennai airport (VOMM), routine report")
