"""Loader for data/i18n/glossary.json — the five-language vocabulary for IMD
warning colour codes (word + meaning) and warning categories. The API serves
this text (GET /glossary, and inside GET /warnings via imd_warnings.public)
so every surface renders the same words instead of carrying its own copy —
plan.md §3.1: one decoder, five outputs; never five decoders.

Read once at import. Like i18n.py's table check at the bottom of that file,
a missing/malformed file, an entry without all of SUPPORTED_LANGUAGES, or a
missing required id fails loudly here, not during a demo.
"""

import json
import re
from pathlib import Path

import config
from i18n import SUPPORTED_LANGUAGES

_PATH = config.DATA_DIR / "i18n" / "glossary.json"

# IMD's four-level scale, in legend order (least to most severe).
COLOURS = ("green", "yellow", "orange", "red")

# Ids the functions below dereference directly. Other category_* ids are
# looked up by convention (see category_label) and may legitimately be absent.
_REQUIRED_IDS = (
    tuple(f"colour_{c}" for c in COLOURS)
    + tuple(f"colour_word_{c}" for c in COLOURS)
    + ("category_no_warning",)
)


def _load(path: Path) -> dict[str, dict[str, dict]]:
    """Parse and validate the glossary file: {id: {lang: {text, native_qa}}},
    minus the "_meta" block. Raises (FileNotFoundError / json's ValueError /
    RuntimeError) rather than returning a partial table."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = {k: v for k, v in raw.items() if not k.startswith("_")}
    for entry_id, langs in entries.items():
        if not isinstance(langs, dict):
            raise RuntimeError(f"glossary entry {entry_id!r} must map lang -> {{text, native_qa}}")
        missing = set(SUPPORTED_LANGUAGES) - set(langs)
        if missing:
            raise RuntimeError(
                f"glossary entry {entry_id!r} is missing language entries: {sorted(missing)}"
            )
        for lang, entry in langs.items():
            text = entry.get("text") if isinstance(entry, dict) else None
            if not isinstance(text, str) or not text.strip() \
                    or not isinstance(entry.get("native_qa"), bool):
                raise RuntimeError(
                    f"glossary entry {entry_id!r}/{lang} needs non-empty text and boolean native_qa"
                )
    absent = [i for i in _REQUIRED_IDS if i not in entries]
    if absent:
        raise RuntimeError(f"glossary is missing required entries: {absent}")
    return entries


_ENTRIES = _load(_PATH)


def text(entry_id: str, lang: str) -> str:
    """Entry text in `lang`, English for a language the glossary doesn't carry
    (same fallback as imd_warnings' headline labels). An unknown id is a
    KeyError — every id the code uses is checked at import."""
    entry = _ENTRIES[entry_id]
    return (entry.get(lang) or entry["en"])["text"]


def entries(lang: str) -> dict[str, dict]:
    """Every entry in `lang` as {id: {"text", "native_qa"}} — the /glossary
    payload. native_qa is passed through so a client can mark unreviewed
    translations; nothing renders it yet."""
    return {entry_id: dict(langs.get(lang) or langs["en"]) for entry_id, langs in _ENTRIES.items()}


def legend(lang: str) -> list[dict]:
    """The four colour rows in COLOURS order: canonical colour key, the
    localised colour word, and what the colour means."""
    return [
        {"colour": c, "label": text(f"colour_word_{c}", lang), "meaning": text(f"colour_{c}", lang)}
        for c in COLOURS
    ]


def category_label(category: str | None, lang: str) -> str:
    """Localised label for a warning feed's `category` value, via the
    category_<slug> convention documented in glossary.json's _meta (null ->
    category_no_warning). A category the glossary doesn't know comes back
    verbatim: the feed's own text, never a guess (plan.md §2 principle 4)."""
    if category is None:
        return text("category_no_warning", lang)
    entry_id = "category_" + re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_")
    if entry_id not in _ENTRIES:
        return category
    return text(entry_id, lang)
