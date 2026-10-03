"""Place-name text rules shared by the GeoNames import, the Postgres sync and
location.py, so the gazetteer file, the `cities` table and a query are all
normalised the same way.

- normalize(): NFC; Latin names lose diacritics and case ("Bilāspur" ->
  "bilaspur"); Indic names keep their vowel signs, which are letters there.
- trigrams() / similarity(): pg_trgm's similarity(), reimplemented so the
  in-memory fallback ranks exactly as Postgres does. Word characters are
  letters, digits and combining marks — what pg_trgm treats as alphanumeric
  under the en_US.utf8 locale the postgis image uses (checked on Tamil,
  Devanagari and Telugu, sql/006_cities_gazetteer.sql).
- FUZZY_SCRIPTS: where trigram matching is used at all. Telugu is left out:
  on the postgis image glibc classes the Telugu virama (U+0C4D) as a
  separator, so pg_trgm cuts a Telugu word at every conjunct ("a్b" gives
  the 4 trigrams of "a" and "b"; similarity('హ్', 'హ') = 1). The Tamil and
  Devanagari viramas are word characters there, and those scripts matched
  the Python scores here exactly. Telugu names get exact and prefix match.
"""

import re
import unicodedata

# Unicode blocks per script. Latin covers Basic Latin, Latin-1 and the
# Extended-A/B and Additional blocks GeoNames' romanisations use.
_SCRIPT_RANGES = {
    "latin": ((0x0041, 0x024F), (0x1E00, 0x1EFF)),
    "tamil": ((0x0B80, 0x0BFF),),
    "devanagari": ((0x0900, 0x097F), (0xA8E0, 0xA8FF)),
    "telugu": ((0x0C00, 0x0C7F),),
}
LANG_SCRIPT = {"en": "latin", "ta": "tamil", "hi": "devanagari", "mr": "devanagari",
               "te": "telugu"}
FUZZY_SCRIPTS = frozenset({"latin", "tamil", "devanagari"})

_JOINERS = {"‌", "‍"}  # ZWNJ / ZWJ: invisible, vary between sources


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or unicodedata.category(ch).startswith("M")


def char_script(ch: str) -> str | None:
    cp = ord(ch)
    for script, ranges in _SCRIPT_RANGES.items():
        if any(lo <= cp <= hi for lo, hi in ranges):
            return script
    return None


def script_ok(lang: str, name: str) -> bool:
    """Every letter of `name` is in `lang`'s script (digits and punctuation
    don't count either way)."""
    want = LANG_SCRIPT.get(lang)
    letters = [ch for ch in name if ch.isalpha() or unicodedata.category(ch).startswith("M")]
    return bool(want and letters) and all(char_script(ch) == want for ch in letters)


def text_script(text: str) -> str | None:
    """The script most of `text`'s letters are in, or None."""
    counts: dict[str, int] = {}
    for ch in text:
        script = char_script(ch) if (ch.isalpha() or unicodedata.category(ch)
                                     .startswith("M")) else None
        if script:
            counts[script] = counts.get(script, 0) + 1
    return max(counts, key=counts.get) if counts else None


def is_latin(text: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    return bool(letters) and all(char_script(ch) == "latin" for ch in letters)


def normalize(name: str) -> str:
    s = unicodedata.normalize("NFC", name or "")
    s = "".join(ch for ch in s if ch not in _JOINERS)
    if is_latin(s):
        s = "".join(ch for ch in unicodedata.normalize("NFKD", s)
                    if not unicodedata.combining(ch))
    s = "".join(ch if _is_word_char(ch) else " " for ch in s.casefold())
    return " ".join(s.split())


_WORD_RE = re.compile(r"\S+")


def trigrams(normalized: str) -> frozenset[str]:
    out = set()
    for word in _WORD_RE.findall(normalized):
        padded = f"  {word} "
        out.update(padded[i:i + 3] for i in range(len(padded) - 2))
    return frozenset(out)


def similarity(a: str, b: str) -> float:
    """pg_trgm similarity() of two already-normalised strings."""
    ta, tb = trigrams(a), trigrams(b)
    if not ta or not tb:
        return 0.0
    shared = len(ta & tb)
    return shared / (len(ta) + len(tb) - shared)
