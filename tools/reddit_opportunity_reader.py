"""Reddit opportunity discovery: PRAW-backed, read-only and opt-in.

No browser, outbound request, account write or file mutation occurs on import.
Discovery emits observations for existing global ranking/ingest PRs; it NEVER
emits an executable action. The current Reddit editorial rules still prevail.

Upstream API client: praw-dev/praw, BSD-2-Clause, v8.0.3 (2026-08-12).
See docs/research/reddit-opportunities-126.md for provenance and limitations.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import unicodedata
from collections.abc import Iterable

SUBREDDITS_APPROVED = ("libros", "filosofia_en_espanol")
DEFAULT_QUERIES = (
    "fantasía", "romantasy", "libros", "recomendación",
    "novela juvenil", "lectura", "escritores",
)
_SUBREDDIT = re.compile(r"[A-Za-z0-9_]{2,21}\Z")
_POST_ID = re.compile(r"[A-Za-z0-9]{3,15}\Z")
_NAME = re.compile(r"[A-Za-z0-9_-]{2,32}\Z")
_TOPIC_TERMS = {
    "fantasia": ("fantasia", "fantasy", "dragones", "magia"),
    "romantasy": ("romantasy", "romance fantastico", "enemies to lovers"),
    "lectura": ("lectura", "leer", "libro", "libros", "novela"),
    "escritura": ("escribir", "escritor", "escritora", "escritura"),
}
_QUESTION_TERMS = ("cual", "cuales", "que leo", "recomend", "busco", "sugerid")
_MAX_ROWS = 1000


def _fold(value: str) -> str:
    value = "".join(
        c for c in unicodedata.normalize("NFD", value.casefold())
        if unicodedata.category(c) != "Mn"
    )
    return " " + re.sub(r"[^a-z0-9]+", " ", value).strip() + " "


def _contains(text: str, phrase: str) -> bool:
    return (" " + _fold(phrase).strip() + " ") in text


def text_signals(title: str, body: str = "") -> dict:
    """Evidence tags only: lexical hints are NOT verified language or intent."""
    folded = _fold((title or "") + " " + (body or ""))
    topics = sorted(
        tag for tag, terms in _TOPIC_TERMS.items()
        if any(_contains(folded, term) for term in terms)
    )
    title_folded = _fold(title or "")
    question = "?" in (title or "") or any(
        _contains(title_folded, token) for token in _QUESTION_TERMS
    )
    return {"topic_hints": topics, "question_hint": bool(question)}


def make_praw_readonly_client(*, client_id: str, client_secret: str, user_agent: str):
    """Construct PRAW's maintained OAuth read-only API client, not a writer.

    Credentials are passed explicitly and never read from .env or logged.
    No Reddit requests are made by this constructor's caller until collect().
    """
    if not all(isinstance(x, str) and x.strip() for x in
               (client_id, client_secret, user_agent)):
        raise ValueError("PRAW needs explicit client_id, client_secret and user_agent")
    try:
        import praw  # optional dependency; does not load on module import
    except ImportError as exc:
        raise RuntimeError("Install optional requirements-reddit-opportunities.txt") from exc
    credentials = {"client_id": client_id, "client_secret": client_secret,
                   "user_agent": user_agent}
    client = praw.Reddit(**credentials)
    if not client.read_only:
        raise RuntimeError("Expected a read-only Reddit client")
    return client


def _require_scope(subreddits: Iterable[str], queries: Iterable[str],
                   limit_per_query: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if (not isinstance(subreddits, (tuple, list))
        or not isinstance(queries, (tuple, list))
        or type(limit_per_query) is not int
        or not 1 <= limit_per_query <= 100):
        raise ValueError("Invalid search scope or per-query limit")
    communities = tuple(dict.fromkeys(s.casefold() for s in subreddits
                                       if isinstance(s, str) and _SUBREDDIT.fullmatch(s)))
    keywords = tuple(dict.fromkeys(q.strip() for q in queries
                                   if isinstance(q, str) and 2 <= len(q.strip()) <= 100
                                   and not any(ord(c) < 32 for c in q)))
    # Never use r/all or an unreviewed subreddit from a discovery suggestion.
    if (not communities or len(communities) != len(subreddits)
        or any(s not in SUBREDDITS_APPROVED for s in communities)
        or not keywords or len(keywords) != len(queries) or len(keywords) > 20):
        raise ValueError("Only validated subreddits and bounded unique queries accepted")
    return communities, keywords


def _observed_post(post, requested_subreddit: str, now: dt.datetime,
                   max_age_days: int) -> dict | None:
    try:
        post_id = post.id
        sub = post.subreddit.display_name
        raw_author = getattr(post, "author", None)
        author = getattr(raw_author, "name", None) if raw_author is not None else None
        raw_time = post.created_utc
        raw_title = post.title
    except (AttributeError, TypeError):
        return None
    if (not isinstance(post_id, str) or not _POST_ID.fullmatch(post_id)
        or not isinstance(sub, str) or sub.casefold() != requested_subreddit
        or not isinstance(raw_title, str) or not raw_title.strip()
        or type(raw_time) not in (float, int) or not math.isfinite(raw_time)
        or raw_time <= 0 or len(raw_title) > 2000):
        return None
    try:
        published = dt.datetime.fromtimestamp(raw_time, tz=dt.timezone.utc)
    except (OSError, OverflowError, ValueError):
        return None
    age_seconds = (now - published).total_seconds()
    if not 0 <= age_seconds <= max_age_days * 86400:
        return None
    author = author if isinstance(author, str) and _NAME.fullmatch(author) else None
    if isinstance(author, str) and author.casefold() in ("deleted", "automoderator"):
        author = None
    body = getattr(post, "selftext", "")
    if not isinstance(body, str) or body in ("[deleted]", "[removed]"):
        body = ""
    signals = text_signals(raw_title, body)
    num_comments = getattr(post, "num_comments", None)
    score = getattr(post, "score", None)
    ratio = getattr(post, "upvote_ratio", None)
    return {
        "network": "reddit", "queue": "API",
        "source": "reddit:subreddit_search",
        "subreddit": sub.casefold(), "post_id": post_id.casefold(),
        "url": f"https://www.reddit.com/r/{sub.casefold()}/comments/{post_id.casefold()}/",
        "author": author, "title": raw_title.strip(), "text": body[:4000],
        "created_utc": float(raw_time),
        "created_at": published.isoformat(),
        "observed_at": now.isoformat(),
        "language": None,  # Reddit does not expose a trustworthy native field here
        "comment_count": num_comments if type(num_comments) is int and num_comments >= 0 else None,
        "score": score if type(score) is int else None,
        "upvote_ratio": float(ratio) if type(ratio) in (int, float)
                         and math.isfinite(ratio) and 0 <= ratio <= 1 else None,
        **signals,
        "queries": [],
        "status": "manual_review_required",
        "verified_actions": [],
    }


def collect(reddit, *, as_of: dt.datetime, subreddits=SUBREDDITS_APPROVED,
            queries=DEFAULT_QUERIES, limit_per_query=25, max_age_days=7):
    """Collect bounded public submissions using injected PRAW .search().

    Never calls an action endpoint, guesses a post's language, or bypasses
    current short-answer/thread-history/community-rule preflight. Exceptions
    from PRAW propagate: a partial response is NEVER reported as complete.
    """
    if not isinstance(as_of, dt.datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if type(max_age_days) is not int or not 1 <= max_age_days <= 30:
        raise ValueError("max_age_days must be in 1..30")
    communities, keywords = _require_scope(subreddits, queries, limit_per_query)
    now = as_of.astimezone(dt.timezone.utc)
    by_id = {}
    stats = {"queries": 0, "seen": 0, "accepted": 0, "rejected": 0, "duplicates": 0}
    for sub in communities:
        subreddit = reddit.subreddit(sub)
        for query in keywords:
            stats["queries"] += 1
            # PRAW handles paging/rate-limit semantics internally. No loop past
            # server search limits; this is intentionally a bounded read.
            posts = subreddit.search(query, sort="new", time_filter="week",
                                     limit=limit_per_query)
            for post in posts:
                stats["seen"] += 1
                if stats["seen"] > _MAX_ROWS:
                    raise ValueError("Unexpectedly unbounded PRAW iterator")
                row = _observed_post(post, sub, now, max_age_days)
                if row is None:
                    stats["rejected"] += 1
                    continue
                key = (row["subreddit"], row["post_id"])
                if key in by_id:
                    previous = by_id[key]
                    # Refuse conflicting author/text/time rather than silently
                    # merge two apparently identical remote identities.
                    if any(previous[k] != row[k] for k in
                           ("author", "title", "text", "created_utc")):
                        raise ValueError(f"Conflicting Reddit observation: {key}")
                    previous["queries"].append(query)
                    stats["duplicates"] += 1
                else:
                    row["queries"].append(query)
                    by_id[key] = row
    rows = sorted(by_id.values(), key=lambda r: (-r["created_utc"], r["post_id"]))
    stats["accepted"] = len(rows)
    return {"network": "reddit", "status": "review_only", "complete": True,
            "observations": rows, "diagnostics": stats}


def to_jsonl(observations: list[dict]) -> str:
    """Offline export in the JSONL *format*; no copy from unlicensed collector."""
    if not isinstance(observations, list):
        raise ValueError("Expected observation list")
    if any(not isinstance(row, dict) or row.get("network") != "reddit"
           or row.get("status") != "manual_review_required" for row in observations):
        raise ValueError("Only review-only Reddit observations can be serialized")
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                   for row in observations)
