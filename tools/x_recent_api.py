"""X API v2 recent-search -> existing X pool, without any remote writes.

Optional client: Tweepy 4.17.0 (MIT, https://github.com/tweepy/tweepy).
Pass an explicitly configured Tweepy Client to collect_recent(); no account,
secrets, network calls or changes to the production pipeline on import.

The returned rows match tools/x_pool.py.record_posts(db, posts, source).
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
from collections.abc import Mapping

X_QUERY_MAX = 512
X_RECENT_HOURS = 168
X_SOURCE = "search:x_api_recent"
FILTER = " lang:es -is:retweet"
_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}\Z", re.ASCII)
_SNOWFLAKE = re.compile(r"[0-9]{1,25}\Z", re.ASCII)
_HASHTAG = re.compile(r"#[\w]+\Z", re.UNICODE)


class InvalidXResponse(ValueError):
    """An unverifiable API response must not create candidates."""


def _value(obj, key, default=None):
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    raw = getattr(obj, "data", None)  # Tweepy Tweet/User models provide .data
    if isinstance(raw, Mapping) and key in raw:
        return raw[key]
    return getattr(obj, key, default)


def build_queries(terms, *, max_groups=8, max_per_query=5):
    """Bounded X recent-search queries; text is always quoted, never an operator.

    Invalid terms fail closed; duplicate terms are removed with Unicode NFC.
    Query count is bounded to make costs controllable outside this module.
    """
    if not isinstance(terms, (list, tuple)) or not terms:
        raise ValueError("se requiere una lista no vacía de términos")
    if (type(max_groups) is not int or type(max_per_query) is not int
            or not 1 <= max_groups <= 8 or not 1 <= max_per_query <= 16):
        raise ValueError("tamaño de consultas inválido")
    unique, seen = [], set()
    for term in terms:
        if not isinstance(term, str):
            raise ValueError("término no textual")
        if any(ord(c) < 32 for c in term):
            raise ValueError("carácter de control en consulta")
        term = unicodedata.normalize("NFC", " ".join(term.strip().split()))
        if (not 2 <= len(term) <= 100 or any(ord(c) < 32 for c in term)
                or any(c in term for c in '"\\()') or term.startswith(("-", "+"))):
            raise ValueError("término de búsqueda no seguro")
        key = term.casefold()
        if key not in seen:
            seen.add(key)
            unique.append(term if _HASHTAG.fullmatch(term) else f'"{term}"')
    queries, group = [], []
    for item in unique:
        proposal = group + [item]
        query = "(" + " OR ".join(proposal) + ")" + FILTER
        if len(proposal) > max_per_query or len(query) > X_QUERY_MAX:
            if not group:
                raise ValueError("término excede el límite de consulta")
            queries.append("(" + " OR ".join(group) + ")" + FILTER)
            group = [item]
        else:
            group = proposal
    if group:
        queries.append("(" + " OR ".join(group) + ")" + FILTER)
    if len(queries) > max_groups:
        raise ValueError("demasiadas consultas para el presupuesto")
    return queries


def _utc_datetime(value):
    if isinstance(value, str):
        try:
            value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, dt.datetime) or value.tzinfo is None:
        return None
    return value.astimezone(dt.timezone.utc)


def _snowflake(value):
    text = str(value) if not isinstance(value, bool) else ""
    return str(int(text)) if _SNOWFLAKE.fullmatch(text) and int(text) > 0 else None


def normalize_page(response, *, now=None, self_handle="davidportodiaz"):
    """Convert API JSON or Tweepy Response; reject missing author expansion.

    Only observed Spanish, non-retweeted, recent posts with genuine remote
    IDs and UTC timestamps become candidates. No guess from display names.
    """
    now = _utc_datetime(now or dt.datetime.now(dt.timezone.utc))
    if now is None:
        raise ValueError("now exige zona horaria")
    if _value(response, "errors"):
        raise InvalidXResponse("la API devolvió errores; lote descartado")
    data = _value(response, "data")
    if data is None:
        data = []
    includes = _value(response, "includes") or {}
    users = _value(includes, "users")
    if users is None:
        users = []
    if not isinstance(data, (list, tuple)) or not isinstance(users, (list, tuple)):
        raise InvalidXResponse("estructura de página inválida")
    by_id = {}
    for user in users:
        uid = _snowflake(_value(user, "id"))
        handle = _value(user, "username")
        if uid and isinstance(handle, str) and _HANDLE.fullmatch(handle):
            if uid in by_id and by_id[uid] != handle:
                raise InvalidXResponse("identidades incompatibles en expansions")
            by_id[uid] = handle
    output, seen = [], set()
    for tweet in data:
        tid = _snowflake(_value(tweet, "id"))
        author_id = _snowflake(_value(tweet, "author_id"))
        if not tid or not author_id or author_id not in by_id:
            continue
        handle = by_id[author_id]
        if handle.casefold() == self_handle.casefold():
            continue
        lang, body = _value(tweet, "lang"), _value(tweet, "text")
        if lang != "es" or not isinstance(body, str) or not body.strip():
            continue
        refs = _value(tweet, "referenced_tweets") or []
        if any(_value(r, "type") == "retweeted" for r in refs):
            continue
        posted_at = _utc_datetime(_value(tweet, "created_at"))
        if posted_at is None:
            continue
        age = (now - posted_at).total_seconds() / 3600
        if not 0 <= age <= X_RECENT_HOURS:
            continue
        if tid in seen:
            continue
        seen.add(tid)
        output.append({"handle": handle, "url": f"https://x.com/{handle}/status/{tid}",
                       "text": body.strip(), "lang": "es", "age_hours": round(age, 4),
                       "repost": False, "pinned": False, "post_id": tid,
                       "author_id": author_id, "source": X_SOURCE})
    return output


def collect_recent(client, queries, *, now=None, max_pages=1, max_results=25):
    """Use Tweepy Client.search_recent_tweets in READ-ONLY mode.

    Requires an injected authenticated client, not credentials. No retry on
    429/401/403, no infinite pagination, and no remote writes. Fail whole batch
    on errors so a partial collection cannot masquerade as a successful scan.
    """
    if not isinstance(queries, (list, tuple)) or not 1 <= len(queries) <= 8:
        raise ValueError("entre 1 y 8 consultas")
    if type(max_pages) is not int or not 1 <= max_pages <= 3:
        raise ValueError("max_pages fuera de presupuesto")
    if type(max_results) is not int or not 10 <= max_results <= 100:
        raise ValueError("max_results fuera de rango")
    if not callable(getattr(client, "search_recent_tweets", None)):
        raise TypeError("se requiere cliente de lectura Tweepy")
    posts = {}
    for query in queries:
        if (not isinstance(query, str) or len(query) > X_QUERY_MAX
                or not query.endswith(FILTER) or not query.startswith("(")):
            raise ValueError("consulta no generada/validada")
        token, tokens_seen = None, set()
        for _ in range(max_pages):
            kwargs = {"query": query, "max_results": max_results,
                      "expansions": ["author_id"],
                      "tweet_fields": ["author_id", "created_at", "lang", "referenced_tweets"],
                      "user_fields": ["username"]}
            if token:
                kwargs["next_token"] = token
            response = client.search_recent_tweets(**kwargs)
            for post in normalize_page(response, now=now):
                posts.setdefault(post["post_id"], post)
            token = _value(_value(response, "meta") or {}, "next_token")
            if not token:
                break
            if not isinstance(token, str) or token in tokens_seen:
                raise InvalidXResponse("paginación repetida o inválida")
            tokens_seen.add(token)
    return list(posts.values())


def stage_in_existing_pool(db, normalized_posts, *, today=None):
    """Opt-in: feed the existing browser_pool schema, not a parallel ledger.

    db is an explicitly supplied SQLite connection. Pool niche, spam, language,
    history and action filters remain authoritative. Never invokes an action.
    """
    import x_pool
    return x_pool.record_posts(db, normalized_posts, X_SOURCE, today=today)
