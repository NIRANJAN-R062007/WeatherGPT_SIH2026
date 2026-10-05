"""TFA-3: shared slot parsing and ask-back for travel and farming.

Turns what a user typed into the slots a collector needs (facts.py) — travel:
`origin`, `destination`, `day` (+ optional `mode` and `via`, the stops on a
multi-leg route, TFA-6); farming: `crop`, `district` —
and, when a required one is missing, the single follow-up question to ask. A
missing slot is asked for, never guessed (plan.md §2 principle 3).

Slots only ever hold *canonical* values — a city key from `data/cities.json`, a
crop key from `CROPS`, a day name. Free text the user typed is never copied
into a slot: a place or crop we don't have is reported in `unsupported` (as a
letters-only, length-capped word, so it is safe to echo back) and asked about
again. That keeps this input from reaching a prompt as an injection surface
(plan.md R12, TFA-15).

Parsing is rules, not an LLM: city names in all five languages come from the
registry, and the role cues (from / to, and the Indic postpositions) are
patterns. It is stateless — a caller keeps `slots` and the `asking` slot
between turns and passes them back as `have=` / `asking=`, so a bare reply
("Madurai") fills the slot that was asked about.

Every non-English string and cue below is a first draft, marked
`# TODO: native_qa` like the rest of the repo's unreviewed translations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import cities

TRAVEL = "travel"
FARMING = "farming"

# Ask order. Required slots only — `mode` is optional and never asked for.
REQUIRED: dict[str, tuple[str, ...]] = {
    TRAVEL: ("origin", "destination", "day"),
    FARMING: ("crop", "district"),
}
_CITY_SLOTS = {"origin", "destination", "district"}

# TFA-6: most stops a route may name (the `via` slot); facts.py makes each a role.
MAX_STOPS = 2

DAYS = ("today", "tomorrow", "day_after_tomorrow")  # what advisory/facts.py can fetch

# Crops we can recognise by name, with their aliases. TODO(TFA-9): the sourced
# crop file becomes the source of truth for which crops exist; until then this
# is only a vocabulary so a crop word resolves to a key — a crop not here is
# reported as unsupported, not passed on as text. Non-English names are drafts.
CROPS: dict[str, tuple[str, ...]] = {
    "groundnut": ("groundnut", "groundnuts", "peanut", "peanuts",
                  "நிலக்கடலை", "मूंगफली", "వేరుశెనగ", "भुईमूग", "शेंगदाणे"),  # TODO: native_qa
    "rice": ("rice", "paddy", "நெல்", "அரிசி", "धान", "चावल",
             "వరి", "బియ్యం", "भात", "तांदूळ"),  # TODO: native_qa
    "wheat": ("wheat", "கோதுமை", "गेहूं", "గోధుమ", "गहू"),  # TODO: native_qa
    "maize": ("maize", "corn", "மக்காச்சோளம்", "मक्का", "మొక్కజొన్న", "मका"),  # TODO: native_qa
    "cotton": ("cotton", "பருத்தி", "कपास", "పత్తి", "कापूस"),  # TODO: native_qa
    "sugarcane": ("sugarcane", "கரும்பு", "गन्ना", "చెరకు", "ऊस"),  # TODO: native_qa
    "ragi": ("ragi", "finger millet", "கேழ்வரகு", "रागी", "రాగి", "नाचणी"),  # TODO: native_qa
}

# --- cues ---------------------------------------------------------------------
# Role of a city in a route, from the words just before it (English) or the
# postposition right after it (Indic languages attach it to the name).
_PRE_ORIGIN = re.compile(
    r"(?:\bfrom|\bleaving|\bout\s+of|\bdeparting\s+from|\bstarting\s+(?:from|in|at))\s*$", re.I)
_PRE_DEST = re.compile(
    r"(?:\bto|\btowards?|\breach(?:ing)?|\bvisit(?:ing)?|\barriv\w*\s+(?:in|at)|\bgo(?:ing)?\s+to)\s*$",
    re.I)
_POST_ORIGIN = re.compile(
    r"^\S{0,3}?(?:லிருந்து|இருந்து)"      # ta  TODO: native_qa
    r"|^\s*से(?!\w)"                    # hi  TODO: native_qa  (not \b: े is a combining mark)
    r"|^\s*(?:నుండి|నుంచి)"              # te  TODO: native_qa
    r"|^\s*(?:हून|पासून)")               # mr  TODO: native_qa
_POST_DEST = re.compile(
    r"^(?:க்கு|கு|ைக்கு)"                # ta  TODO: native_qa
    r"|^\s*(?:तक|को)(?!\w)|^\s*जा"      # hi  TODO: native_qa
    r"|^\s*(?:కు|కి|వెళ్)"               # te  TODO: native_qa
    r"|^\s*(?:ला|पर्यंत)")                # mr  TODO: native_qa

# TFA-6: a stop on the route ("via Madurai", "changing at Delhi"). English only so
# far; an Indic stop cue is not recognised yet, so such a city is not a stop.
_PRE_VIA = re.compile(
    r"(?:\bvia|\bthrough|\bstopping\s+(?:at|in)|\bstop(?:over)?\s+(?:at|in)"
    r"|\bchang(?:e|ing)\s+(?:at|in)|\bconnecting\s+(?:at|in|through))\s*$", re.I)
# "via Madurai and Kochi": a city right after a stop, joined by "and" or a comma.
_VIA_JOIN = re.compile(r"\s*(?:,|and|&)\s*", re.I)
_VIA_PLACE = re.compile(
    r"\b(?:via|through)\s+([A-Za-z][A-Za-z\- ]{1,29}?)"
    r"(?=\s+(?:from|to|by|on|and|today|tomorrow|tonight)\b|[?.!,]|$)", re.I)

_ROUTE_SEP = re.compile(r"\s*(?:-|–|—|→|->|=>)\s*")

# A place named after a route word that isn't in the registry ("to Goa").
_PLACE_AFTER = re.compile(
    r"\b(from|to|towards?|reach|visit)\s+([A-Za-z][A-Za-z\- ]{1,29}?)"
    r"(?=\s+(?:from|to|by|on|via|in|for|today|tomorrow|tonight)\b|[?.!,]|$)", re.I)
_DISTRICT_PLACE_AFTER = re.compile(
    r"\b(?:in|at|near|around)\s+([A-Za-z][A-Za-z\- ]{1,29}?)"
    r"(?=\s+(?:this|next|now|today|tomorrow|tonight|for|to)\b|[?.!,]|$)", re.I)
_CROP_AFTER = re.compile(
    r"\b(?:sow(?:ing)?|plant(?:ing)?|grow(?:ing)?|cultivat\w+)\s+(?:the\s+)?"
    r"([A-Za-z][A-Za-z\- ]{1,24}?)"
    r"(?=\s+(?:in|at|near|around|this|next|now|today|tomorrow|crop)\b|[?.!,]|$)", re.I)
# Words that follow "to" / "sow" but are not a place or a crop.
_NOT_A_NAME = frozenset(
    "the a an my me our it this that go going travel travelling traveling reach visit fly drive "
    "do be get know check see plan take make find work sow plant grow some any what when how "
    "today tomorrow tonight there here home work office airport station".split())

_MODES = (
    ("flight", re.compile(r"\b(?:fly|flying|flight|flights|plane|airline)\b", re.I)),
    ("train", re.compile(r"\b(?:train|trains|rail|railway)\b", re.I)),
    ("road", re.compile(r"\b(?:drive|driving|road|car|bus|bike)\b", re.I)),
    ("ferry", re.compile(r"\b(?:ferry|boat|ship|cruise)\b", re.I)),
)
MODES = tuple(mode for mode, _ in _MODES)  # what `parse` can put in the `mode` slot

# "day after tomorrow" must be tried before "tomorrow" (it contains it). For
# travel, which looks forward, Hindi "कल" is taken as tomorrow.
_DAY_CUES = (
    ("day_after_tomorrow", re.compile(
        r"\bday\s+after\s+tomorrow\b|\bovermorrow\b|நாளை\s*மறுநாள்|परसों|ఎల్లుండి|परवा", re.I)),
    ("tomorrow", re.compile(r"\btomorrow\b|நாளை|\bकल\b|రేపు|उद्या", re.I)),
    ("today", re.compile(r"\btoday\b|\btonight\b|இன்று|\bआज\b|ఈ\s*రోజు|ఈరోజు", re.I)),
)
# A date we can't fetch: weekday names, "next week", "12 Oct". Reported, not clamped.
_FAR_DAY = re.compile(
    r"\b(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)(?:day)?\b"
    r"|\bnext\s+(?:week|month)\b|\bweekend\b"
    r"|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\b", re.I)


@dataclass
class SlotResult:
    """What was understood and what is still needed.

    `slots` holds canonical values only. `missing` lists the required slots not
    filled, in ask order; `unsupported` maps a slot to the (sanitised) word the
    user used that we don't have; `assumed` names a slot filled by the one
    deliberate default (a lone uncued city is taken as the destination) so the
    answer can say so.
    """

    kind: str
    slots: dict = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    unsupported: dict = field(default_factory=dict)
    assumed: list[str] = field(default_factory=list)
    # TFA-6: stops named but not used — a place we don't have, or one past
    # MAX_STOPS — so the answer can say they were not checked.
    ignored_stops: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def asking(self) -> str | None:
        """The slot the next question is about — pass back as `asking=`."""
        return self.missing[0] if self.missing else None


# --- parsing ------------------------------------------------------------------


def _clean_name(raw: str) -> str | None:
    """A word safe to echo back (letters, spaces, hyphens), or None if it is a
    function word rather than a name."""
    name = re.sub(r"\s+", " ", raw).strip(" -").lower()
    if not name or name.split()[0] in _NOT_A_NAME or name in _NOT_A_NAME:
        return None
    return name


def _crop_in(text: str) -> str | None:
    s = text.lower()
    best: tuple[int, str] | None = None
    for key, names in CROPS.items():
        for name in names:
            pattern = re.escape(name.lower())
            if name.isascii():
                pattern = rf"(?<![a-z]){pattern}(?![a-z])"
            m = re.search(pattern, s)
            if m and (best is None or m.start() < best[0]):
                best = (m.start(), key)
    return best[1] if best else None


def _day_in(text: str) -> tuple[str | None, str | None]:
    """`(day, unsupported)`: the one supported day named, or the unsupported
    one. Two different days named ("today or tomorrow") is ambiguous: neither."""
    found = {day for day, rx in _DAY_CUES if rx.search(text)}
    if "tomorrow" in found and "day_after_tomorrow" in found:
        found.discard("tomorrow")  # the longer phrase contains the shorter one
    if len(found) == 1:
        return found.pop(), None
    if not found:
        far = _FAR_DAY.search(text)
        if far:
            return None, re.sub(r"[^a-z0-9 ]", "", far.group().lower())[:20]
    return None, None


def _mode_in(text: str) -> str | None:
    found = {mode for mode, rx in _MODES if rx.search(text)}
    return found.pop() if len(found) == 1 else None  # two modes named: don't pick


def _stops(text: str, found: list) -> tuple[list[str], list]:
    """`(stop keys, the other mentions)`: the cities `text` names as stops, in
    order, and the mentions left for origin/destination."""
    stops: list[str] = []
    rest = []
    prev_stop_end = None
    for key, start, end in found:
        before = text[:start]
        joined = prev_stop_end is not None and _VIA_JOIN.fullmatch(text[prev_stop_end:start])
        if _PRE_VIA.search(before.lower()) or joined:
            if key not in stops:
                stops.append(key)
            prev_stop_end = end
        else:
            rest.append((key, start, end))
            prev_stop_end = None
    return stops, rest


def _route_roles(text: str, asking: str | None, have: dict) -> tuple[dict, list[str]]:
    """`(roles, assumed)`: origin/destination city keys from the mentions in
    `text`. Cues decide; a leftover city next to a cued one takes the other
    role; a lone uncued city fills the asked slot, else the one missing slot,
    else is assumed to be the destination (and flagged as assumed)."""
    roles: dict = {}
    assumed: list[str] = []
    stops, found = _stops(text, cities.mentions(text, travel=True))
    if stops:
        roles["via"] = stops
    uncued: list[str] = []
    for key, start, end in found:
        before, after = text[:start].lower(), text[end:]
        if _POST_ORIGIN.match(after) or _PRE_ORIGIN.search(before):
            roles.setdefault("origin", key)
        elif _POST_DEST.match(after) or _PRE_DEST.search(before):
            roles.setdefault("destination", key)
        else:
            uncued.append(key)

    # "Chennai to Madurai": the cue sits only on the second city.
    for key in list(uncued):
        if len(found) == 2 and "destination" in roles and "origin" not in roles:
            roles["origin"] = key
            uncued.remove(key)
        elif len(found) == 2 and "origin" in roles and "destination" not in roles:
            roles["destination"] = key
            uncued.remove(key)

    if len(uncued) == 2 and not roles:
        # "Chennai – Madurai" / "Chennai -> Madurai": a bare dash or arrow between two cities
        (a, _, a_end), (b, b_start, _) = [m for m in found if m[0] in uncued][:2]
        if _ROUTE_SEP.fullmatch(text[a_end:b_start]) and a != b:
            roles["origin"], roles["destination"] = a, b
    elif len(uncued) == 1 and not roles:
        key = uncued[0]
        missing_cities = [s for s in ("origin", "destination") if s not in have]
        if asking in ("origin", "destination"):
            roles[asking] = key
        elif len(missing_cities) == 1:
            roles[missing_cities[0]] = key
        else:
            roles["destination"] = key
            assumed.append("destination")
    return roles, assumed


def parse(kind: str, text: str, *, have: dict | None = None,
          asking: str | None = None) -> SlotResult:
    """Fill the slots `kind` needs from `text`, on top of `have` (slots from
    earlier turns). `asking` is the slot the last question was about, so a bare
    reply fills it. Anything not understood stays missing."""
    if kind not in REQUIRED:
        raise ValueError(f"unknown advisory kind {kind!r}")
    text = text or ""
    have = dict(have or {})
    result = SlotResult(kind, slots={k: v for k, v in have.items() if v})

    if kind == TRAVEL:
        roles, assumed = _route_roles(text, asking, have)
        for slot, other in (("origin", "destination"), ("destination", "origin")):
            if roles.get(slot) and roles[slot] == (roles.get(other) or have.get(other)):
                roles.pop(slot)  # "Chennai to Chennai" is not a trip: ask again
        stops = roles.pop("via", [])
        result.slots.update(roles)
        result.assumed = [s for s in assumed if s in roles]
        if stops:
            ends = {result.slots.get("origin"), result.slots.get("destination")}
            stops = [k for k in stops if k not in ends]  # the trip's own ends are not stops
            result.ignored_stops += stops[MAX_STOPS:]
            if stops[:MAX_STOPS]:
                result.slots["via"] = ",".join(stops[:MAX_STOPS])
        for m in _VIA_PLACE.finditer(text):
            name = _clean_name(m.group(1))
            if name and not cities.resolve(name, travel=True):
                result.ignored_stops.append(name)

        day, far = _day_in(text)
        if day:
            result.slots["day"] = day
        elif far:
            result.unsupported["day"] = far
        mode = _mode_in(text)
        if mode:
            result.slots["mode"] = mode
        for slot in ("origin", "destination"):
            if slot not in result.slots:
                _unsupported_place(text, slot, result)
    else:
        mentioned = list(dict.fromkeys(k for k, _, _ in cities.mentions(text)))
        if len(mentioned) == 1:
            result.slots["district"] = mentioned[0]
        elif len(mentioned) > 1 and "district" not in have:
            result.slots.pop("district", None)  # two places named: ask which, don't pick
        crop = _crop_in(text)
        if crop:
            result.slots["crop"] = crop
        elif "crop" not in result.slots:
            m = _CROP_AFTER.search(text)
            name = _clean_name(m.group(1)) if m else None
            if name:
                result.unsupported["crop"] = name
        if "district" not in result.slots and not mentioned:
            m = _DISTRICT_PLACE_AFTER.search(text)
            name = _clean_name(m.group(1)) if m else None
            if name:
                result.unsupported["district"] = name

    result.missing = [s for s in REQUIRED[kind] if s not in result.slots]
    result.unsupported = {s: v for s, v in result.unsupported.items() if s in result.missing}
    return result


def _unsupported_place(text: str, slot: str, result: SlotResult) -> None:
    """Note a place named for `slot` that the registry doesn't have ("to Goa")."""
    wanted = {
        "origin": ("from",),
        "destination": ("to", "towards", "toward", "reach", "visit"),
    }[slot]
    for m in _PLACE_AFTER.finditer(text):
        if m.group(1).lower() not in wanted:
            continue
        name = _clean_name(m.group(2))
        if name and not cities.resolve(name, travel=True):
            result.unsupported.setdefault(slot, name)
            return


# --- ask-back -----------------------------------------------------------------

# One question per slot, in each language. All non-English drafts: TODO native_qa.
_QUESTIONS: dict[str, dict[str, str]] = {
    "origin": {
        "en": "Where are you travelling from?",
        "hi": "आप कहाँ से यात्रा कर रहे हैं?",  # TODO: native_qa
        "ta": "நீங்கள் எங்கிருந்து பயணம் செய்கிறீர்கள்?",  # TODO: native_qa
        "te": "మీరు ఎక్కడి నుండి ప్రయాణిస్తున్నారు?",  # TODO: native_qa
        "mr": "तुम्ही कुठून प्रवास करत आहात?",  # TODO: native_qa
    },
    "destination": {
        "en": "Where do you want to go?",
        "hi": "आप कहाँ जाना चाहते हैं?",  # TODO: native_qa
        "ta": "நீங்கள் எங்கே செல்ல விரும்புகிறீர்கள்?",  # TODO: native_qa
        "te": "మీరు ఎక్కడికి వెళ్లాలనుకుంటున్నారు?",  # TODO: native_qa
        "mr": "तुम्हाला कुठे जायचे आहे?",  # TODO: native_qa
    },
    "day": {
        "en": "Which day are you travelling: today, tomorrow or the day after tomorrow?",
        "hi": "आप किस दिन यात्रा करेंगे: आज, कल या परसों?",  # TODO: native_qa
        "ta": "எந்த நாளில் பயணம் செய்கிறீர்கள்: இன்று, நாளை அல்லது நாளை மறுநாள்?",  # TODO: native_qa
        "te": "ఏ రోజు ప్రయాణిస్తారు: ఈ రోజు, రేపు లేదా ఎల్లుండి?",  # TODO: native_qa
        "mr": "कोणत्या दिवशी प्रवास करणार: आज, उद्या की परवा?",  # TODO: native_qa
    },
    "crop": {
        "en": "Which crop do you want to sow?",
        "hi": "आप कौन सी फसल बोना चाहते हैं?",  # TODO: native_qa
        "ta": "எந்தப் பயிரை விதைக்க விரும்புகிறீர்கள்?",  # TODO: native_qa
        "te": "మీరు ఏ పంట విత్తాలనుకుంటున్నారు?",  # TODO: native_qa
        "mr": "तुम्हाला कोणते पीक पेरायचे आहे?",  # TODO: native_qa
    },
    "district": {
        "en": "Which district are you in? Name the nearest city.",
        "hi": "आप किस जिले में हैं? सबसे नज़दीकी शहर का नाम बताइए।",  # TODO: native_qa
        "ta": "நீங்கள் எந்த மாவட்டத்தில் இருக்கிறீர்கள்? "  # TODO: native_qa
        "அருகிலுள்ள நகரத்தின் பெயரைச் சொல்லுங்கள்.",
        "te": "మీరు ఏ జిల్లాలో ఉన్నారు? దగ్గరలోని నగరం పేరు చెప్పండి.",  # TODO: native_qa
        "mr": "तुम्ही कोणत्या जिल्ह्यात आहात? जवळच्या शहराचे नाव सांगा.",  # TODO: native_qa
    },
}
# Said first when the user named something we don't have. {name} is the
# sanitised word; {options} the names we do have, in the user's language.
_NOT_COVERED: dict[str, str] = {
    "en": "I don't have {name} yet. I cover: {options}.",
    "hi": "मेरे पास अभी {name} की जानकारी नहीं है। "  # TODO: native_qa
    "मैं इनके बारे में बता सकता हूँ: {options}।",
    "ta": "{name} பற்றிய தகவல் இன்னும் என்னிடம் இல்லை. "  # TODO: native_qa
    "இவற்றைப் பற்றி சொல்ல முடியும்: {options}.",
    "te": "{name} గురించి నా వద్ద ఇంకా సమాచారం లేదు. "  # TODO: native_qa
    "నేను వీటి గురించి చెప్పగలను: {options}.",
    "mr": "माझ्याकडे अजून {name} ची माहिती नाही. "  # TODO: native_qa
    "मी यांची माहिती देऊ शकतो: {options}.",
}
_NOT_COVERED_DAY: dict[str, str] = {
    "en": "I can only look up to the day after tomorrow.",
    "hi": "मैं केवल परसों तक की जानकारी दे सकता हूँ।",  # TODO: native_qa
    "ta": "நாளை மறுநாள் வரை மட்டுமே என்னால் சொல்ல முடியும்.",  # TODO: native_qa
    "te": "నేను ఎల్లుండి వరకు మాత్రమే చెప్పగలను.",  # TODO: native_qa
    "mr": "मी फक्त परवापर्यंतची माहिती देऊ शकतो.",  # TODO: native_qa
}
_NOT_COVERED_CROP: dict[str, str] = {
    "en": "I don't have {name} yet. I cover: {options}.",
    **{k: v for k, v in _NOT_COVERED.items() if k != "en"},
}
_LANGS = ("en", "hi", "ta", "te", "mr")


def _options(slot: str, lang: str) -> str:
    if slot == "crop":
        return ", ".join(CROPS)  # crop names stay as keys until TFA-9 gives localised ones
    places = cities.CITIES if slot == "district" else cities.TRAVEL_CITIES
    return ", ".join(cities.display_name(k, lang) for k in places)


def ask_back(result: SlotResult, lang: str = "en") -> str | None:
    """The one follow-up question for what is still missing, or None when the
    slots are complete. If the user named something we don't have, that comes
    first. An unknown `lang` is answered in English."""
    slot = result.asking
    if slot is None:
        return None
    lang = lang if lang in _LANGS else "en"
    parts: list[str] = []
    name = result.unsupported.get(slot)
    if name and slot == "day":
        parts.append(_NOT_COVERED_DAY[lang])
    elif name:
        template = (_NOT_COVERED_CROP if slot == "crop" else _NOT_COVERED)[lang]
        parts.append(template.format(name=name.title(), options=_options(slot, lang)))
    parts.append(_QUESTIONS[slot][lang])
    return " ".join(parts)
