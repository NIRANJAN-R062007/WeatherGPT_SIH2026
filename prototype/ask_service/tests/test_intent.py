from cities import resolve as resolve_city
from intent import parse_intent


def test_tamil_rain_tomorrow_chennai():
    parsed = parse_intent("நாளை சென்னையில் மழை பெய்யுமா?")
    assert parsed["intent"] == "will_it_rain"
    assert resolve_city(parsed["city"]) == "chennai"
    assert parsed["day"] == "tomorrow"


def test_tamil_rain_today_madurai():
    parsed = parse_intent("இன்று மதுரையில் மழை வருமா?")
    assert parsed["intent"] == "will_it_rain"
    assert resolve_city(parsed["city"]) == "madurai"
    assert parsed["day"] == "today"


def test_tamil_rain_tonight():
    parsed = parse_intent("இன்றிரவு கோயம்புத்தூரில் மழை பெய்யுமா?")
    assert parsed["intent"] == "will_it_rain"
    assert resolve_city(parsed["city"]) == "coimbatore"
    assert parsed["day"] == "tonight"


def test_tamil_current_weather_no_rain_word_defaults_today():
    parsed = parse_intent("சென்னை வானிலை")
    assert parsed["intent"] == "current_weather"
    assert resolve_city(parsed["city"]) == "chennai"
    assert parsed["day"] == "today"


def test_english_still_works():
    parsed = parse_intent("will it rain in Chennai tomorrow")
    assert parsed["intent"] == "will_it_rain"
    assert resolve_city(parsed["city"]) == "chennai"
    assert parsed["day"] == "tomorrow"


def test_unrecognized_has_no_city():
    parsed = parse_intent("hello there")
    assert parsed["intent"] == "unrecognized"
    assert parsed["city"] is None
