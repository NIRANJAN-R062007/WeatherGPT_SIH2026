"""Check the sourced crop file against its own quotes (plan.md §8 TFA-10, §11.7).

    python scripts/check_crops.py                  # data/crops/crops.json
    python scripts/check_crops.py path/to/crops.json
    python scripts/check_crops.py --fetch          # ... and each quote against its page

Every value the file gives must trace to a source, so this rejects:

- an entry for a crop the slot parser doesn't know (advisory/slots.py CROPS), a
  region that is neither a registered district nor a state slug, or a crop and
  region given twice;
- a field without a `source` or an https `url`, even when its value is null, and a
  non-null value without a verbatim `quote`;
- a value of the wrong shape (the same check advisory/crops.py applies on read);
- a number the quote does not contain: each sowing month by name or abbreviation
  ("June", "Jun"), each end of `temp_range_c`, and `max_rain_probability_pct`.

A quote may join several passages of one page with " ... " (table cells are joined
with " | " in page order). With --fetch, each passage must also appear in the text
of the page at `url`, compared with whitespace and "|" collapsed. That needs the
network, so it is off by default and CI runs without it.

Exit status 1 when anything is rejected, with one line per problem.
"""

import argparse
import calendar
import html
import json
import re
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "services" / "orchestrator"))

import cities  # noqa: E402
from advisory import crops, slots  # noqa: E402

DEFAULT_PATH = crops.PATH
PASSAGE_SEP = " ... "
_NUMBER = re.compile(r"(?<![\d.])\d+(?:\.\d+)?")
_MONTH_WORDS = {m: {calendar.month_name[m].lower(), calendar.month_abbr[m].lower()}
                for m in range(1, 13)}
_MONTH_WORDS[9].add("sept")


def _numbers(text: str) -> set[float]:
    return {float(n) for n in _NUMBER.findall(text)}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", text.lower()))


def _regions() -> set[str]:
    return set(cities.CITIES) | {s for s in map(crops.state_slug, cities.CITIES) if s}


def _unquoted(field: str, value, quote: str) -> list[str]:
    """The parts of `value` the quote doesn't contain."""
    if field == "sowing_months":
        words = _words(quote)
        return [calendar.month_name[m] for m in value if not _MONTH_WORDS[m] & words]
    numbers = _numbers(quote)
    wanted = [value["min"], value["max"]] if field == "temp_range_c" else [value]
    return [f"{n:g}" for n in wanted if float(n) not in numbers]


def check_value(field: str, given) -> list[str]:
    if not isinstance(given, dict):
        return ["missing: give the field, with value null when the source has none"]
    out = []
    if not str(given.get("source") or "").strip():
        out.append("no source")
    if not str(given.get("url") or "").startswith("https://"):
        out.append("no https url")
    value = given.get("value")
    if value is None:
        return out
    quote = str(given.get("quote") or "").strip()
    if not quote:
        return [*out, "no quote for a value"]
    if not crops._valid(field, value):
        return [*out, f"malformed value {value!r}"]
    missing = _unquoted(field, value, quote)
    if missing:
        out.append(f"not in the quote: {', '.join(missing)}")
    return out


def check(doc: dict) -> list[str]:
    """Every problem in a parsed crop file, one line each; [] when it is clean."""
    entries = doc.get("entries") if isinstance(doc, dict) else None
    if not isinstance(entries, list):
        return ["file: no `entries` list"]
    regions, seen, out = _regions(), set(), []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            out.append(f"entries[{i}]: not an object")
            continue
        name = f"{entry.get('crop')}/{entry.get('region')}"
        if entry.get("crop") not in slots.CROPS:
            out.append(f"{name}: unknown crop (not in advisory/slots.py CROPS)")
        if entry.get("region") not in regions:
            out.append(f"{name}: unknown region (not a district key or state slug)")
        if (entry.get("crop"), entry.get("region")) in seen:
            out.append(f"{name}: given twice")
        seen.add((entry.get("crop"), entry.get("region")))
        if not isinstance(entry.get("reviewed"), bool):
            out.append(f"{name}: `reviewed` must be true or false")
        values = entry.get("values") if isinstance(entry.get("values"), dict) else {}
        for field in crops.FIELDS:
            out += [f"{name} {field}: {p}" for p in check_value(field, values.get(field))]
    return out


def page_text(raw: str) -> str:
    """A page's visible text, whitespace and table bars collapsed (as quotes are)."""
    raw = re.sub(r"(?s)<(script|style)\b.*?</\1>", " ", raw)
    return _collapse(html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def _collapse(text: str) -> str:
    return re.sub(r"[\s|]+", " ", text).strip()


def fetch(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "WeatherGPT crop check"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (https only)
        return response.read().decode("utf-8", errors="replace")


def check_pages(doc: dict, get=fetch) -> list[str]:
    """Each quote passage against the text of its page; `get(url)` returns the HTML."""
    pages: dict[str, str | None] = {}
    out = []
    for entry in doc.get("entries", []):
        name = f"{entry.get('crop')}/{entry.get('region')}"
        for field, given in (entry.get("values") or {}).items():
            url, quote = (given or {}).get("url"), (given or {}).get("quote")
            if not url or not quote:
                continue
            if url not in pages:
                try:
                    pages[url] = page_text(get(url))
                except OSError as e:
                    pages[url] = None
                    out.append(f"{url}: could not fetch ({e})")
            if pages[url] is None:
                continue
            for passage in quote.split(PASSAGE_SEP):
                if _collapse(passage) not in pages[url]:
                    out.append(f"{name} {field}: quote not on the page: {passage[:60]!r}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    parser.add_argument("--fetch", action="store_true",
                        help="also check each quote against the text of its page")
    args = parser.parse_args(argv)
    try:
        doc = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"{args.path}: unreadable ({e})")
        return 1
    problems = check(doc) + (check_pages(doc) if args.fetch else [])
    for p in problems:
        print(p)
    count = len(doc.get("entries", [])) if isinstance(doc, dict) else 0
    print(f"{args.path}: {count} entries, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
