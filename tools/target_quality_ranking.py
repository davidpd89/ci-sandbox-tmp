"""Read-only, explainable quality ranking for candidate accounts and posts.

No network calls, credentials, persistence, decisions to execute, or live state.
Consumers may pass native Bluesky/Mastodon/TikTok scan shortlists or explicit
normalized rows for any of the nine networks. Unknown signals stay unknown.
"""
from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata
from collections.abc import Mapping, Sequence

NETWORKS = ("bluesky", "mastodon", "x", "threads", "facebook",
            "pinterest", "reddit", "tiktok", "instagram")
_NATIVE = frozenset(("bluesky", "mastodon", "tiktok"))
_TERMS = ("fantasia", "romantasy", "fantasia juvenil", "leer", "lectura",
          "lector", "lectora", "lectores", "libro", "libros", "novela",
          "escritor", "escritora", "booktok", "bookstagram", "booktube")
_ACTIONS = frozenset(("follow", "reply", "comment", "repost"))
_WEIGHTS = {"topic": .34, "sources": .12, "activity": .14,
            "spanish": .09, "audience": .10, "reciprocity": .09,
            "outcomes": .12}
_MAX_CANDIDATES = 10000
_MAX_POSTS = 30


def _text(value):
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(c for c in value if not unicodedata.combining(c))


def _hits(value):
    words = " " + " ".join(re.findall(r"[a-z0-9]+", _text(value))) + " "
    return sum((" " + term + " ") in words for term in _TERMS)


def _number(value, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or not 0 <= value <= maximum:
        return None
    return float(value)


def _instant(value):
    if isinstance(value, dt.datetime):
        t = value
    elif isinstance(value, str):
        try:
            t = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if t.tzinfo is None or t.utcoffset() is None:
        return None
    return t.astimezone(dt.timezone.utc)


def _now(value):
    t = _instant(value)
    if t is None:
        raise ValueError("as_of must be an aware datetime")
    return t


def _post_key(network, post):
    for field in ("uri", "post_ref", "status_id", "url"):
        value = post.get(field)
        if isinstance(value, str) and 0 < len(value) <= 2048 and value.strip():
            return network + ":" + value.strip()
        if field == "status_id" and type(value) is int and value >= 0:
            return network + ":" + str(value)
    return None


def _identity(network, row):
    if network == "bluesky":
        value = row.get("did") or row.get("handle")
    elif network == "mastodon":
        value = row.get("acct") or row.get("account_id")
        if row.get("instance") and value:
            value = str(row["instance"]) + "/" + str(value)
    else:
        value = row.get("handle") or row.get("account_id") or row.get("identity")
    if isinstance(value, str) and value.strip() and len(value) <= 320:
        value = value.strip().casefold()
    elif type(value) is int and value >= 0:
        value = str(value)
    else:
        return None
    if any(c.isspace() for c in value) or any(ord(c) < 32 for c in value):
        return None
    return network + ":" + value


def _language(row, *, post=False):
    explicit = row.get("es")
    if type(explicit) is bool:
        return 1.0 if explicit else 0.0
    raw = row.get("language") or row.get("lang")
    if isinstance(raw, str) and raw:
        return 1.0 if raw.casefold().startswith("es") else 0.0
    langs = row.get("langs")
    if isinstance(langs, (tuple, list)) and langs:
        return 1.0 if any(isinstance(x, str) and x.casefold().startswith("es")
                          for x in langs) else 0.0
    # No pretending text heuristics establish a language.
    return None


def _wilson(successes, trials):
    """One-sided Wilson lower bound (z=1.645); association, not causality."""
    z = 1.6448536269514722
    p = successes / trials
    q = z * z / trials
    return max(0.0, (p + q / 2 - z * math.sqrt(p * (1 - p) / trials +
                                             z * z / (4 * trials * trials))) / (1 + q))


def _outcome_signal(row):
    if not isinstance(row, Mapping) or row.get("verified") is not True or row.get("mature") is not True:
        return None
    trials = row.get("trials")
    if type(trials) is not int or not 10 <= trials <= 10_000_000:
        return None
    values = [row.get(key) for key in ("followbacks", "responses", "conversations", "traffic")]
    if any(type(n) is not int or not 0 <= n <= trials for n in values):
        return None
    return min(1.0, (0.4 * _wilson(values[0], trials) +
                     0.35 * _wilson(values[1], trials) +
                     0.15 * _wilson(values[2], trials) +
                     0.1 * _wilson(values[3], trials)) * 2.5)


def _components(signals, weights):
    parts = {}
    for name, weight in weights.items():
        raw = signals.get(name)
        value = _number(raw, 1)
        parts[name] = {"value": value, "weight": weight,
                       "points": round(weight * (value or 0) * 100, 3)}
    known_weight = sum(weights[k] for k, part in parts.items() if part["value"] is not None)
    return round(sum(p["points"] for p in parts.values()), 3), round(known_weight, 3), parts


def _adapt(network, row):
    profile = row.get("profile") if isinstance(row.get("profile"), Mapping) else {}
    posts = row.get("posts")
    if not isinstance(posts, (list, tuple)):
        posts = ()
    bio = row.get("bio") if isinstance(row.get("bio"), str) else profile.get("bio", "")
    followers = row.get("followers") if "followers" in row else profile.get("followers")
    sources = row.get("sources")
    source_count = (len({s for s in sources if isinstance(s, str) and s})
                    if isinstance(sources, (list, tuple, set)) else None)
    independent = row.get("independent")
    if type(independent) is int and 0 <= independent <= 10000:
        source_count = independent
    followed_by = row.get("followed_by")
    if followed_by is None and network == "tiktok":
        followed_by = row.get("relation") == "follows_me" if row.get("relation") else None
    following = row.get("following")
    if following is None and type(row.get("followed")) is bool:
        following = row["followed"]
    actions = row.get("actions")
    if not isinstance(actions, (list, tuple, set)):
        actions = ()
    return {"bio": bio, "followers": followers, "sources": source_count,
            "posts": posts[:_MAX_POSTS], "following": following,
            "followed_by": followed_by, "last_status_at": row.get("last_status_at"),
            "language": _language(row),
            "actions": sorted(set(actions) & _ACTIONS) if
                all(isinstance(a, str) for a in actions) else []}


def rank_network(network, candidates, *, as_of, outcomes=None,
                 max_post_age_days=21, community_post_age_days=45):
    """Read-only ranked account/post opportunities, no implicit action grants.

    Only provided actions are displayed. Posts require a timestamp and Spanish
    evidence; unknown language is reported but not silently claimed Spanish.
    """
    if network not in NETWORKS:
        raise ValueError("unsupported network")
    now = _now(as_of)
    if (type(max_post_age_days) is not int or not 0 <= max_post_age_days <= 365 or
        type(community_post_age_days) is not int or not 0 <= community_post_age_days <= 365):
        raise ValueError("invalid post age policy")
    if (not isinstance(candidates, (list, tuple)) or len(candidates) > _MAX_CANDIDATES):
        raise ValueError("candidates must be a bounded sequence")
    if outcomes is None:
        outcomes = {}
    if not isinstance(outcomes, Mapping):
        raise ValueError("outcomes must be a mapping")
    prepared, rejected, ids = [], [], {}
    for ordinal, row in enumerate(candidates):
        if not isinstance(row, Mapping):
            rejected.append({"index": ordinal, "reason": "invalid_row"})
            continue
        identity = _identity(network, row)
        if identity is None:
            rejected.append({"index": ordinal, "reason": "missing_identity"})
            continue
        ids.setdefault(identity, []).append((ordinal, row))
    for identity in sorted(ids):
        entries = ids[identity]
        if len(entries) != 1:
            rejected.append({"id": identity, "reason": "duplicate_identity"})
            continue
        _, raw = entries[0]
        item = _adapt(network, raw)
        bio_hits = _hits(item["bio"])
        # Do not let stale, future, invalid or foreign posts boost account affinity.
        post_hits = 0
        sources = min(1.0, item["sources"] / 4) if item["sources"] is not None else None
        audience = _number(item["followers"], 1_000_000_000)
        if audience is not None:
            audience = 1.0 if audience <= 5000 else (0.75 if audience <= 20000 else
                        (0.45 if audience <= 100000 else 0.2))
        reciprocity = item["followed_by"]
        if type(reciprocity) is bool:
            reciprocity = 1.0 if reciprocity else 0.0
        else:
            reciprocity = None
        activity_t = _instant(item["last_status_at"])
        if activity_t is not None and activity_t > now:
            activity_t = None  # A future profile date must not hide valid post activity.
        valid_posts, post_rejected = [], []
        seen_posts = set()
        for index, post in enumerate(item["posts"]):
            if not isinstance(post, Mapping):
                post_rejected.append({"index": index, "reason": "invalid_post"})
                continue
            key = _post_key(network, post)
            if key is None or key in seen_posts:
                post_rejected.append({"index": index, "reason": "missing_or_duplicate_post_key"})
                continue
            seen_posts.add(key)
            timestamp = _instant(post.get("created_at"))
            if timestamp is None:
                post_rejected.append({"id": key, "reason": "missing_post_timestamp"})
                continue
            age = (now - timestamp).total_seconds() / 86400
            limit = community_post_age_days if raw.get("lane") == "community" else max_post_age_days
            if age < 0 or age > limit:
                post_rejected.append({"id": key, "reason": "post_outside_age_window"})
                continue
            lang = _language(post, post=True)
            if lang == 0:
                post_rejected.append({"id": key, "reason": "non_spanish_post"})
                continue
            if lang == 1:
                post_hits = max(post_hits, _hits(str(post.get("text") or post.get("caption") or "")))
            activity_t = max(t for t in (activity_t, timestamp) if t is not None)
            stats = post.get("stats") if isinstance(post.get("stats"), Mapping) else {}
            engagement = stats.get("replies", post.get("replies"))
            engagement = _number(engagement, 1_000_000)
            if engagement is not None:
                engagement = min(1., math.log1p(engagement) / math.log1p(25))
            pscore, pcover, pparts = _components({
                "topic": min(1., _hits(str(post.get("text") or post.get("caption") or "")) / 3),
                "recency": max(0., 1 - age / max(1, limit + 1)),
                "engagement": engagement, "spanish": lang},
                {"topic": .42, "recency": .32, "engagement": .12, "spanish": .14})
            actions = post.get("actions")
            if not isinstance(actions, (list, tuple, set)):
                actions = ()
            valid_posts.append({"id": key, "score": pscore, "coverage": pcover,
                                "explanation": pparts, "age_days": round(age, 2),
                                "actions": sorted({a for a in actions if isinstance(a, str)} & _ACTIONS)
                                                  if lang == 1 else []})
        topical = min(1.0, (bio_hits * 1.5 + post_hits) / 4) if (item["bio"] or post_hits) else None
        activity = None
        if activity_t is not None:
            age = (now - activity_t).total_seconds() / 86400
            if age >= 0:
                activity = max(0., 1 - age / 45)
        score, coverage, reasons = _components({
            "topic": topical, "sources": sources, "activity": activity,
            "spanish": item["language"], "audience": audience,
            "reciprocity": reciprocity, "outcomes": _outcome_signal(outcomes.get(identity))}, _WEIGHTS)
        valid_posts.sort(key=lambda p: (-p["score"], -p["coverage"], p["id"]))
        opportunities = ([{"action": "follow", "score": score}]
                         if "follow" in item["actions"] and item["following"] is not True else [])
        for p in valid_posts:
            for action in p["actions"]:
                if action in ("reply", "comment", "repost"):
                    opportunities.append({"action": action, "post_id": p["id"],
                                          "score": round(.55 * score + .45 * p["score"], 3)})
        opportunities.sort(key=lambda x: (-x["score"], x["action"], x.get("post_id", "")))
        prepared.append({"id": identity, "score": score, "coverage": coverage,
                         "explanation": reasons, "posts": valid_posts,
                         "post_rejections": post_rejected, "opportunities": opportunities})
    prepared.sort(key=lambda r: (-r["score"], -r["coverage"], r["id"]))
    rejected.sort(key=lambda r: (r["reason"], r.get("id", ""), r.get("index", -1)))
    return {"network": network,
            "adapter": "native_shortlist" if network in _NATIVE else "normalized_input_only",
            "ranked": prepared, "rejected": rejected,
            "note": "observational ranking; no causal uplift or executable plan"}


def rank_all(snapshots, *, as_of, outcomes=None, **kwargs):
    """Map network->native shortlist, or network->{'shortlist': [...] }.

    Unconnected networks are represented explicitly as 'missing_input'.
    """
    if not isinstance(snapshots, Mapping) or set(snapshots) - set(NETWORKS):
        raise ValueError("invalid network snapshots")
    if outcomes is None:
        outcomes = {}
    if not isinstance(outcomes, Mapping):
        raise ValueError("invalid outcomes")
    _now(as_of)
    networks = {}
    for network in NETWORKS:
        source = snapshots.get(network)
        if source is None:
            networks[network] = {"network": network, "status": "missing_input",
                                 "ranked": [], "rejected": []}
        else:
            rows = source.get("shortlist") if isinstance(source, Mapping) else source
            if isinstance(source, Mapping) and network == "pinterest" and rows is None:
                rows = source.get("authors")
            networks[network] = {"status": "ranked", **rank_network(
                network, rows, as_of=as_of, outcomes=outcomes.get(network), **kwargs)}
    return {"as_of": _now(as_of).isoformat(), "networks": networks}


def evaluate_orders(ranked_ids, baseline_ids, heldout, *, k=10):
    """Offline P@k and nDCG@k over independently held-out binary outcomes.

    Missing labels are not negatives: rank only labelled candidates in both
    orders. A prospective time split is the caller's responsibility.
    """
    if type(k) is not int or k < 1 or k > 1000 or not isinstance(heldout, Mapping):
        raise ValueError("invalid evaluation parameters")
    if not all(isinstance(v, Mapping) for v in heldout.values()):
        raise ValueError("invalid heldout data")
    metrics = ("followback", "response", "conversation", "traffic")

    def label_value(label):
        if type(label) is bool:
            return int(label)
        if type(label) is int and label in (0, 1):
            return label
        return None

    def one(order, metric):
        # Top-k means actual exposed positions, not the first k *judged*
        # candidates after silently removing unobserved entries.
        seen, exposure = set(), []
        for key in order:
            if key in seen:
                continue
            seen.add(key)
            exposure.append(key)
            if len(exposure) >= k:
                break
        values = [label_value(heldout.get(key, {}).get(metric)) for key in exposure]
        observed = sum(v is not None for v in values)
        unjudged = len(exposure) - observed
        if not exposure or unjudged:
            return {"observed": observed, "exposed": len(exposure),
                    "unjudged": unjudged, "precision": None, "ndcg": None}
        positives = sum(label_value(row.get(metric)) == 1 for row in heldout.values())
        ideal = sum(1 / math.log2(i + 2) for i in range(min(k, positives)))
        dcg = sum(v / math.log2(i + 2) for i, v in enumerate(values))
        return {"observed": observed, "exposed": len(exposure), "unjudged": 0,
                "precision": round(sum(values) / len(exposure), 4),
                "ndcg": round(dcg / ideal, 4) if ideal else 0.}

    if (not isinstance(ranked_ids, (list, tuple)) or
        not isinstance(baseline_ids, (list, tuple))):
        raise ValueError("orders must be sequences")
    return {metric: {"candidate": one(ranked_ids, metric),
                     "baseline": one(baseline_ids, metric)}
            for metric in metrics}
