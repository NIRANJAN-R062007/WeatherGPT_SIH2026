"""BM25 retrieval over the small IMD reference corpus (Task C, plan.md §14).

Grounds narration in category wording — colour codes, rainfall categories,
heat/cold wave criteria, wind descriptors, UV bands, glossary terms — without
ever letting a *number* from the corpus leak into an answer: the guardrail in
main.py validates every figure in the narration against the weather facts
only, so a passage's own numbers (e.g. "64.5 mm") would fail grounding and
drop the whole answer to the template. narrate.py's prompt makes this
explicit; this module only has to retrieve and format the passages.

Pure Python, no new dependency: a corpus of ~25 short entries doesn't need a
real IR library. Never raises — a retrieval bug must not break narration, so
callers wrap this anyway, but the functions here already return safely on a
missing/empty corpus.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache

import config

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# BM25 constants — standard defaults, nothing tuned for this tiny corpus.
_K1 = 1.5
_B = 0.75


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class Passage:
    id: str
    topic: str
    text: str
    keywords: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class _Doc:
    passage: Passage
    tokens: list[str]
    term_counts: dict[str, int]
    length: int


@dataclass
class _Corpus:
    docs: list[_Doc]
    df: dict[str, int]
    avg_len: float


def _load_entries(corpus_dir) -> list[dict]:
    entries: list[dict] = []
    if not corpus_dir.is_dir():
        return entries
    for path in sorted(corpus_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, list):
            entries.extend(e for e in data if isinstance(e, dict))
    return entries


@lru_cache(maxsize=1)
def _build_corpus() -> _Corpus:
    entries = _load_entries(config.RAG_CORPUS_DIR)
    docs: list[_Doc] = []
    df: dict[str, int] = {}
    total_len = 0
    for entry in entries:
        passage = Passage(
            id=entry.get("id", ""),
            topic=entry.get("topic", ""),
            text=entry.get("text", ""),
            keywords=list(entry.get("keywords") or []),
            source=entry.get("source", ""),
        )
        blob = passage.text + " " + " ".join(passage.keywords)
        tokens = _tokenize(blob)
        counts: dict[str, int] = {}
        for tok in tokens:
            counts[tok] = counts.get(tok, 0) + 1
        for tok in counts:
            df[tok] = df.get(tok, 0) + 1
        total_len += len(tokens)
        docs.append(_Doc(passage=passage, tokens=tokens, term_counts=counts, length=len(tokens)))
    avg_len = (total_len / len(docs)) if docs else 0.0
    return _Corpus(docs=docs, df=df, avg_len=avg_len)


def clear_cache() -> None:
    """Test hook: drop the cached corpus so a monkeypatched RAG_CORPUS_DIR
    (or a corpus file edit) is picked up on the next retrieve() call.
    """
    _build_corpus.cache_clear()


def _bm25_score(query_tokens: list[str], doc: _Doc, corpus: _Corpus) -> float:
    n = len(corpus.docs)
    if n == 0:
        return 0.0
    score = 0.0
    for tok in query_tokens:
        n_q = corpus.df.get(tok)
        if not n_q:
            continue
        idf = math.log(1 + (n - n_q + 0.5) / (n_q + 0.5))
        f = doc.term_counts.get(tok, 0)
        if f == 0:
            continue
        denom = f + _K1 * (1 - _B + _B * (doc.length / corpus.avg_len if corpus.avg_len else 1))
        score += idf * (f * (_K1 + 1)) / denom
    return score


# Cue words derived from facts/intent — nudge the query toward the right
# topic without hardcoding every possible fact key. Plain "temperature" is
# deliberately not a cue here: it's common enough across the heat/cold-wave
# entries that it would drown out a more specific signal like "uv" (fewer
# matching docs -> higher idf) for an ordinary, non-extreme temp_c reading.
_CUE_RULES: list[tuple[str, str]] = [
    ("rain_probability_pct", "rainfall chance of rain"),
    ("rain_so_far_mm", "rainfall rain so far"),
    ("rain_last_24h_mm", "rainfall"),
    ("wind_kmh", "wind"),
    ("uv_index", "uv index ultraviolet"),
    ("condition", ""),  # value itself gets folded in below
]

# Deliberately NOT the raw intent string — "current_weather" tokenizes to
# "current"/"weather", which coincidentally collides with unrelated corpus
# prose (e.g. "developing weather conditions" in the colour-code entries).
# These cues target vocabulary that's actually distinctive to the matching
# topic instead.
_INTENT_CUES: dict[str, str] = {
    "will_it_rain": "rainfall category",
    "rainfall_so_far_today": "rainfall category accumulated",
    "forecast": "forecast",
}


def _build_query(intent: str, facts: dict, parameter: str | None) -> str:
    parts: list[str] = [parameter or "", _INTENT_CUES.get(intent, "")]
    for key, cue in _CUE_RULES:
        if key in facts and facts[key] is not None:
            parts.append(cue)
    condition = facts.get("condition")
    if isinstance(condition, str):
        parts.append(condition)
    return " ".join(p for p in parts if p)


def retrieve(intent: str, facts: dict, parameter: str | None = None, k: int = 2) -> list[Passage]:
    """Return up to `k` passages most relevant to this intent/facts/parameter.

    Never raises: an empty or missing corpus, or an unreadable entry, just
    yields fewer (or zero) results.
    """
    try:
        corpus = _build_corpus()
        if not corpus.docs:
            return []
        query_tokens = _tokenize(_build_query(intent, facts or {}, parameter))
        if not query_tokens:
            return []
        scored = [
            (_bm25_score(query_tokens, doc, corpus), doc.passage)
            for doc in corpus.docs
        ]
        scored = [(s, p) for s, p in scored if s > 0]
        scored.sort(key=lambda sp: sp[0], reverse=True)
        return [p for _, p in scored[:k]]
    except Exception:  # never let a retrieval bug break narration
        return []


def format_context(passages: list[Passage]) -> str | None:
    if not passages:
        return None
    lines = [f"- {p.text} (source: {p.source})" for p in passages]
    return "\n".join(lines)
