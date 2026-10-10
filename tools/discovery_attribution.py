"""Discovery provenance (PR #49). Pure, read-only; no ledger, migrations or API calls.

This is NOT the GPT reply-context provenance (#79). Source labels in old scans
are partial observations, never proof of a particular seed/query for a candidate.
Opaque identifiers require a caller-provided HMAC key (not stored in this repo).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping

NETWORKS = frozenset({
    "bluesky", "mastodon", "x", "threads", "facebook",
    "pinterest", "reddit", "tiktok",
})
STATE_ADAPTERS = frozenset({"bluesky", "mastodon", "tiktok"})
SAFE_REASON = frozenset({
    "niche_match", "reciprocity", "search_match", "author_follow",
    "editorial", "unknown",
})
_KIND = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _norm(value):
    """Canonicalise WITHOUT destroying accents, IDs or punctuation."""
    if not isinstance(value, str):
        return ""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _token(value, key, namespace):
    """Return an opaque stable token only when the caller supplies a secret.

    Unkeyed digests of public handles/queries are vulnerable to dictionary
    attacks. Never serialize raw third-party identities as fallback.
    """
    value = _norm(value)
    if not value or not isinstance(key, bytes) or len(key) < 16:
        return None
    return hmac.new(key, (namespace + "\0" + value).encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def _source_type(raw):
    if not isinstance(raw, str):
        return "unknown"
    prefix = _norm(raw).split(":", 1)[0].replace("-", "_")
    return prefix if _KIND.fullmatch(prefix) else "unknown"


def _timestamp(raw):
    if not isinstance(raw, str) or not raw:
        return None
    try:
        value = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return value.isoformat() if value.tzinfo is not None and value.utcoffset() is not None else None


def observation(*, network, source_type, source_key=None, seed=None, query=None,
                observation_time=None, candidate_id=None, selection_reason=None,
                hmac_key=None):
    """Full opt-in observation, explicitly supplied at collection time.

    Each token is domain-separated and network-scoped. No seed/query is
    inferred from a URL, a post ID, a reply, or a legacy source string.
    """
    if network not in NETWORKS:
        raise ValueError("network no soportada")
    kind = _source_type(source_type)
    reason = selection_reason if selection_reason in SAFE_REASON else "unknown"
    return {
        "network": network,
        "source_type": kind,
        "source_key": _token(source_key, hmac_key, network + "/source"),
        "seed": _token(seed, hmac_key, network + "/seed"),
        "query": _token(query, hmac_key, network + "/query"),
        "observation_time": _timestamp(observation_time),
        "candidate_id": _token(candidate_id, hmac_key, network + "/candidate"),
        "selection_reason": reason,
        "provenance_missing": (
            kind == "unknown" or not _norm(source_key)
            or not _norm(candidate_id) or _timestamp(observation_time) is None
            or _token(source_key, hmac_key, network + "/source") is None
            or _token(candidate_id, hmac_key, network + "/candidate") is None
        ),
    }


def state_summary(network, state, *, hmac_key=None):
    """Summarise ACTUAL scan state without inventing per-candidate query links.

    The existing shortlist contains source *labels* and, on Mastodon,
    first-touch. It does NOT carry an unambiguous seed/query -> candidate edge.
    Query metrics are separate observations, not a join on similarly named text.
    All output is aggregated or HMAC-pseudonymised; no handles, URLs or text.
    """
    if network not in NETWORKS:
        raise ValueError("network no soportada")
    if network not in STATE_ADAPTERS:
        return {"network": network, "capability": "unsupported",
                "reason": "sin contrato de shortlist verificado",
                "candidate_count": None, "sources": [], "queries": []}
    if not isinstance(state, Mapping):
        return {"network": network, "capability": "missing",
                "reason": "estado ausente o no válido",
                "candidate_count": None, "sources": [], "queries": []}
    shortlist = state.get("shortlist")
    if not isinstance(shortlist, list):
        return {"network": network, "capability": "missing",
                "reason": "shortlist ausente",
                "candidate_count": None, "sources": [], "queries": []}

    groups = defaultdict(set)
    first_groups = defaultdict(set)
    unknown_ids, unknown_source = 0, 0
    all_ids = set()
    unstable_ids = set()
    first_touch_ids = set()
    for index, row in enumerate(shortlist):
        if not isinstance(row, Mapping):
            unknown_ids += 1
            continue
        if network == "mastodon":
            identity = (str(row.get("instance") or "") + "/" + str(row.get("account_id") or "")
                        if row.get("instance") and row.get("account_id") else _norm(row.get("acct")))
            stable = bool(row.get("instance") and row.get("account_id"))

        else:
            # Bluesky shortlist does not currently expose DID; TikTok offers handle.
            identity = _norm(row.get("handle"))
            stable = False
        if not identity or identity == "/":
            unknown_ids += 1
            continue
        internal = (network, identity)
        if not stable:
            unstable_ids.add(internal)
        all_ids.add(internal)
        if network == "mastodon" and _norm(row.get("first_source")):
            first_touch_ids.add(internal)
            first_groups[_source_type(row["first_source"])].add(internal)
        sources = row.get("sources")
        if not isinstance(sources, (list, tuple, set)):
            sources = []
        labels = {(_source_type(source), _token(source, hmac_key, network + "/source"))
                  for source in sources if isinstance(source, str)}
        labels = {pair for pair in labels if pair[0] != "unknown"}
        if not labels:
            unknown_source += 1
            groups[("unknown", None)].add(internal)
        else:
            for label in labels:
                groups[label].add(internal)

    source_rows = [{"source_type": name, "candidate_count_unique": len(ids),
                    "source_key": token, "query": None, "seed": None,
                    "query_cost": None}
                   for (name, token), ids in sorted(groups.items())]
    first_touch_rows = [{"source_type": name, "candidate_count_unique": len(ids)}
                        for name, ids in sorted(first_groups.items())]
    query_rows = []
    raw_metrics = state.get("source_metrics")
    if isinstance(raw_metrics, Mapping):
        for label, values in sorted(raw_metrics.items(), key=lambda p: str(p[0])):
            if not isinstance(label, str) or not isinstance(values, Mapping):
                continue
            surface, sep, key = label.partition(":")
            # Never claim a source is tied to a particular candidate.
            if not sep or not _norm(key):
                continue
            counts = {}
            for dst, src in (("fetched", "fetched"), ("accepted", "accepted"),
                             ("new_reported", "new_handles")):
                value = values.get(src, values.get("new_accounts") if dst == "new_reported" else None)
                counts[dst] = value if type(value) is int and value >= 0 else None
            query_rows.append({"surface": _source_type(surface),
                               "query": _token(key, hmac_key, network + "/query"),
                               "query_cost": None, **counts})
    observed_on = state.get("date")
    try:
        if not isinstance(observed_on, str) or dt.date.fromisoformat(observed_on).isoformat() != observed_on:
            observed_on = None
    except ValueError:
        observed_on = None
    budget = state.get("budget")
    budget_used = budget.get("used") if isinstance(budget, Mapping) else None
    if type(budget_used) is not int or budget_used < 0:
        budget_used = None
    return {
        "network": network,
        "capability": "partial",
        "reason": "estado legacy: seed/query no vinculados a candidato",
        "observed_on": observed_on,
        "observation_time": None,
        "candidate_count": len(all_ids),
        "candidate_id_missing": unknown_ids,
        "candidate_id_unstable": len(unstable_ids),
        "candidate_source_missing": unknown_source,
        "first_touch_recorded": len(first_touch_ids) if network == "mastodon" else None,
        "first_touch_by_type": first_touch_rows if network == "mastodon" else None,
        "sources": source_rows,
        "queries": query_rows,
        "read_cost_total": budget_used,
        "query_cost_available": False,
        "provenance_missing": True,
    }


def safe_state_summary(*args, **kwargs):
    """Telemetria: un fallo aqui nunca debe romper un scan de produccion."""
    try:
        return state_summary(*args, **kwargs)
    except Exception as exc:        # noqa: BLE001
        return {"capability": "error", "reason": type(exc).__name__}
