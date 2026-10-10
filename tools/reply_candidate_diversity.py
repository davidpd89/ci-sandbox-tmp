"""Offline candidate diversity selector. No network, credentials or publishing.

Candidates MUST have undergone independent contextual/human approval first.
Novelty is only a tie-breaker between such approved candidates; never use
lexical overlap with the original post to claim semantic relevance.

CLI: python tools/reply_candidate_diversity.py input.json
Input: [{"network":"x","candidates":[{"text":"...", "context_approved":true}],
         "recent":["..."]}]. Output: selection indexes and aggregated metrics,
never user text. The caller must independently validate provenance/preflight
before any action, including when this module returns a selection.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

from vendor.distinct_n_compat import distinct_n_pooled, ngrams

# Nine primary networks; reddit_micro is a narrower format of Reddit.
# Values for eight networks mirror reply_writer.py at 2026-10-10;
# Instagram is a proposed, OFFLINE-only cap (not an active executor).
NETWORK_LIMITS = {
    "x": (200, 32),
    "threads": (230, 36),
    "facebook": (230, 36),
    "pinterest": (110, 16),
    "reddit": (170, 28),
    "bluesky": (200, 32),
    "mastodon": (230, 36),
    "tiktok": (90, 14),
    "instagram": (90, 14),
    "reddit_micro": (62, 9),
}
WORD = re.compile(r"[^\W_]+", re.UNICODE)
DISALLOWED = re.compile(r"https?://|www\.|@\w+|#\w+|\n|\r|\x00", re.I)
MAX_CANDIDATES = 16
MAX_RECENT = 250


def tokens(value: str) -> list[str]:
    if not isinstance(value, str):
        raise ValueError("texto debe ser cadena")
    folded = unicodedata.normalize("NFKD", value.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return WORD.findall(folded)


def _normalized(value: str) -> str:
    return " ".join(tokens(value))


def _similarity(left: list[str], right: list[str], n: int) -> float:
    a, b = set(ngrams(left, n)), set(ngrams(right, n))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _novelty(words: list[str], history: list[list[str]]) -> float:
    if not history:
        return 1.0
    return 1.0 - max(0.30 * _similarity(words, other, 1)
                     + 0.70 * _similarity(words, other, 2) for other in history)


def _valid_shape(text: str, network: str) -> bool:
    char_max, word_max = NETWORK_LIMITS[network]
    words = tokens(text)
    return (2 <= len(words) <= word_max and len(text) <= char_max
            and not DISALLOWED.search(text) and not text.startswith(" ")
            and not text.endswith(" "))


def select_approved(network: str, candidates: list[dict], recent: list[str] | None = None,
                    *, validator=None) -> dict:
    """Return only index + diagnostics, not user text.

    'context_approved is True' means an independent review approved factual
    relevance. Fail closed if absent/False (boolean identity is intentional).
    Optional 'validator(text, network, recent)' delegates live-system rules;
    callers must use it before proposing a candidate for publication.
    """
    if network not in NETWORK_LIMITS:
        raise ValueError("red no admitida")
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise ValueError("candidatos inválidos o demasiados")
    if recent is None:
        recent = []
    if not isinstance(recent, list) or len(recent) > MAX_RECENT or any(not isinstance(t, str) for t in recent):
        raise ValueError("historial inválido")
    if validator is not None and not callable(validator):
        raise ValueError("validador inválido")

    history = [tokens(t) for t in recent]
    seen = {_normalized(t) for t in recent}
    scored: list[tuple[float, int]] = []
    accepted_words: list[list[str]] = []
    rejected = {"contexto_no_aprobado": 0, "formato": 0, "repeticion": 0,
                "preflight": 0, "entrada_invalida": 0}
    for i, candidate in enumerate(candidates):
        if not isinstance(candidate, dict) or not isinstance(candidate.get("text"), str):
            rejected["entrada_invalida"] += 1
            continue
        if candidate.get("context_approved") is not True:
            rejected["contexto_no_aprobado"] += 1
            continue
        text = candidate["text"]
        if not _valid_shape(text, network):
            rejected["formato"] += 1
            continue
        norm = _normalized(text)
        if norm in seen:
            rejected["repeticion"] += 1
            continue
        if validator is not None:
            # Adapter for reply_writer.valid_reply: returns (ok, reason).
            verdict = validator(text, network, tuple(recent))
            if not isinstance(verdict, tuple) or not verdict or verdict[0] is not True:
                rejected["preflight"] += 1
                continue
        words = tokens(text)
        scored.append((_novelty(words, history), i))
        accepted_words.append(words)
        seen.add(norm)  # reject duplicate candidates in same batch

    best = sorted(scored, key=lambda item: (-item[0], item[1]))
    return {"network": network, "selected_index": best[0][1] if best else None,
            "eligible": len(best), "total": len(candidates), "rejected": rejected,
            "distinct_1": round(distinct_n_pooled(accepted_words, 1), 4),
            "distinct_2": round(distinct_n_pooled(accepted_words, 2), 4),
            "max_novelty": round(best[0][0], 4) if best else None,
            "requires_external_preflight": True}


def evaluate_cases(cases: list[dict], *, validator=None) -> list[dict]:
    if not isinstance(cases, list) or len(cases) > 300:
        raise ValueError("casos inválidos")
    results = []
    for item in cases:
        if not isinstance(item, dict):
            raise ValueError("caso inválido")
        results.append(select_approved(item.get("network"), item.get("candidates"),
                                       item.get("recent"), validator=validator))
    return results


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Uso: reply_candidate_diversity.py input.json", file=sys.stderr)
        return 2
    path = Path(argv[0])
    if path.stat().st_size > 300_000:
        raise ValueError("entrada demasiado grande")
    with path.open(encoding="utf-8") as stream:
        cases = json.load(stream, parse_constant=lambda _x: (_ for _ in ()).throw(ValueError("NaN")))
    print(json.dumps({"schema": 1, "cases": evaluate_cases(cases)},
                     ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
