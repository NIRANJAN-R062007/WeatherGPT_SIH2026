"""METAR decoder and GET /metar/decode (plan.md §6 P2 item 10). Pure
parsing, fully offline."""

import main
import metar
import pytest
from fastapi.testclient import TestClient

client = TestClient(main.app)

CHENNAI = "VOMM 291130Z 24012KT 6000 SCT020 BKN080 31/25 Q1006 NOSIG"


# --- decode(): the groups -----------------------------------------------------


def test_chennai_routine_report():
    d = metar.decode(CHENNAI)
    assert d["type"] == "METAR"
    assert d["station"] == "VOMM" and d["station_name"] == "Chennai"
    assert d["observed"] == {"day": 29, "time_utc": "11:30", "time_ist": "17:00"}
    w = d["wind"]
    assert (w["direction_deg"], w["speed_kt"], w["speed_kmh"]) == (240, 12, 22)
    assert w["gust_kt"] is None and not w["calm"] and not w["variable"]
    assert d["visibility"]["metres"] == 6000
    assert [(c["code"], c["base_ft"]) for c in d["clouds"]] == [("SCT", 2000), ("BKN", 8000)]
    assert (d["temperature_c"], d["dewpoint_c"], d["pressure_hpa"]) == (31, 25, 1006)
    assert d["trend"] == "NOSIG"
    assert d["unparsed"] == []


def test_metar_prefix_and_trailing_equals_are_accepted():
    d = metar.decode("METAR vomm 291130z 24012kt 9999 NSC 31/25 Q1006=")
    assert d["station"] == "VOMM" and d["pressure_hpa"] == 1006 and d["unparsed"] == []


def test_speci_is_reported_as_special():
    d = metar.decode("SPECI VIDP 020030Z 00000KT 0150 FG VV001 08/08 Q1018")
    assert d["type"] == "SPECI"
    assert "special report" in metar.briefing(d)


def test_gust_and_varying_wind():
    d = metar.decode("VABB 150300Z 27015G25KT 240V300 2000 26/24 Q1002")
    w = d["wind"]
    assert (w["gust_kt"], w["gust_kmh"]) == (25, 46)
    assert (w["varying_from_deg"], w["varying_to_deg"]) == (240, 300)


def test_calm_and_variable_wind():
    assert metar.decode("VIDP 020030Z 00000KT 0150 08/08 Q1018")["wind"]["calm"] is True
    w = metar.decode("VOMM 291130Z VRB03KT 9999 31/25 Q1006")["wind"]
    assert w["variable"] is True and w["direction_deg"] is None


def test_wind_in_metres_per_second():
    w = metar.decode("UUEE 291130Z 18005MPS 9999 10/05 Q1010")["wind"]
    assert (w["speed_kmh"], w["speed_kt"]) == (18, 10)


def test_ist_wraps_past_midnight():
    assert metar.decode("VOMM 291900Z 24012KT 9999 28/24 Q1008")["observed"]["time_ist"] == "00:30"


def test_9999_means_ten_km_or_more():
    v = metar.decode("VOCB 291200Z 25010KT 9999 NSC 30/22 Q1009")["visibility"]
    assert v["metres"] == 10000 and v["at_least"] is True


def test_cavok():
    d = metar.decode("VOBL 291200Z 31008KT CAVOK 28/16 Q1014")
    assert d["visibility"]["cavok"] is True
    assert "Ceiling and visibility OK" in metar.briefing(d)


@pytest.mark.parametrize("raw,miles,metres,less,more", [
    ("KJFK 121851Z 10005KT 1 1/2SM BKN009 20/10 A3000", 1.5, 2414, False, False),
    ("KBOS 121854Z 05012KT M1/4SM FG VV002 M05/M06 A2980", 0.25, 402, True, False),
    ("KSFO 121856Z 28010KT P6SM FEW010 18/12 A3001", 6, 9656, False, True),
    ("KSFO 121856Z 28010KT 10SM FEW010 18/12 A3001", 10, 16093, False, False),
])
def test_statute_mile_visibility(raw, miles, metres, less, more):
    v = metar.decode(raw)["visibility"]
    assert v["statute_miles"] == miles and v["metres"] == metres
    assert v["less_than"] is less and v["at_least"] is more


def test_runway_visual_range():
    d = metar.decode("VIDP 020030Z 00000KT 0150 R28/0300V0600D R10/P1500N FG 08/08 Q1018")
    assert d["runway_visual_range"] == [
        {"runway": "28", "unit": "m", "min": 300, "max": 600, "above": False,
         "below": False, "tendency": "falling"},
        {"runway": "10", "unit": "m", "min": 1500, "max": None, "above": True,
         "below": False, "tendency": "no change"},
    ]


@pytest.mark.parametrize("token,text", [
    ("+TSRA", "thunderstorm with heavy rain"),
    ("-SHRA", "light rain showers"),
    ("VCSH", "showers in the vicinity"),
    ("TS", "thunderstorm"),
    ("BR", "mist"),
    ("HZ", "haze"),
    ("FZFG", "freezing fog"),
    ("RASN", "rain and snow"),
])
def test_weather_phenomena(token, text):
    d = metar.decode(f"VOMM 291130Z 24012KT 3000 {token} 31/25 Q1006")
    assert [wx["text"] for wx in d["weather"]] == [text]


def test_cloud_type_and_vertical_visibility():
    d = metar.decode("VABB 150300Z 27015KT 2000 FEW015CB BKN030TCU 26/24 Q1002")
    assert [c["type"] for c in d["clouds"]] == ["cumulonimbus", "towering cumulus"]
    assert metar.decode("VIDP 020030Z 00000KT 0150 FG VV001 08/08 Q1018")[
        "vertical_visibility_ft"] == 100


def test_negative_temperatures():
    d = metar.decode("UUEE 291130Z 18005MPS 9999 M02/M05 Q1010")
    assert (d["temperature_c"], d["dewpoint_c"]) == (-2, -5)


def test_altimeter_in_inches_converted_to_hpa():
    d = metar.decode("KJFK 121851Z 10005KT 10SM CLR 20/10 A2992")
    assert d["pressure_inhg"] == 29.92 and d["pressure_hpa"] == 1013


def test_trend_and_remarks_are_passed_through_raw():
    d = metar.decode("VABB 150300Z 27015KT 2000 TSRA 26/24 Q1002 TEMPO 1000 +TSRA RMK CB NE")
    assert d["trend"] == "TEMPO 1000 +TSRA"
    assert d["remarks"] == "CB NE"
    assert d["weather"][0]["code"] == "TSRA"  # trend's +TSRA isn't decoded as current weather


def test_unknown_tokens_are_reported_not_guessed():
    d = metar.decode("VOCB 291200Z 25010KT 9999 XYZ NSC 30/22 Q1009 RERA")
    assert d["unparsed"] == ["XYZ", "RERA"]
    assert "Not decoded: XYZ RERA." in metar.briefing(d)


def test_unknown_station_has_no_name():
    d = metar.decode("EGLL 291150Z 24010KT 9999 FEW030 15/09 Q1020")
    assert d["station_name"] is None
    assert metar.briefing(d).startswith("Station EGLL,")


@pytest.mark.parametrize("raw", ["", "   ", "METAR", "12 291130Z 24012KT", "VOMMX 291130Z"])
def test_invalid_input_raises(raw):
    with pytest.raises(ValueError):
        metar.decode(raw)


def test_overlong_input_raises():
    with pytest.raises(ValueError):
        metar.decode("VOMM " + "9999 " * 100)


# --- briefing() -----------------------------------------------------------------


def test_chennai_briefing():
    assert metar.briefing(metar.decode(CHENNAI)) == (
        "Chennai airport (VOMM), routine report observed at 17:00 IST (11:30 UTC on day 29"
        " of the month). Wind from the west-southwest (240°) at 22 km/h (12 kt)."
        " Visibility 6 km. Cloud: scattered at 2,000 ft, broken at 8,000 ft."
        " Temperature 31°C, dew point 25°C. Pressure (QNH) 1006 hPa."
        " No significant change expected in the next 2 hours."
    )


def test_briefing_mentions_gusts_and_weather():
    b = metar.briefing(metar.decode(
        "VABB 150300Z 27015G25KT 2000 +TSRA BR FEW015CB 26/24 Q1002"))
    assert "gusting to 46 km/h (25 kt)" in b
    assert "Weather: thunderstorm with heavy rain, mist." in b
    assert "few at 1,500 ft (cumulonimbus)" in b


# --- GET /metar/decode ------------------------------------------------------------


def test_route_returns_decoded_and_briefing():
    body = client.get("/metar/decode", params={"raw": CHENNAI}).json()
    assert body["decoded"]["station"] == "VOMM"
    assert body["briefing"] == metar.briefing(metar.decode(CHENNAI))


def test_route_rejects_invalid_metar():
    resp = client.get("/metar/decode", params={"raw": "not a metar"})
    assert resp.status_code == 422


def test_route_requires_raw():
    assert client.get("/metar/decode").status_code == 422
