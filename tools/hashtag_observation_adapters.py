"""Read-only observation adapters for nine social collectors (Python 3.11).

SPDX-License-Identifier: MIT
No network, browser, mobile, filesystem or social-action imports.
Native payloads must be supplied by a trusted read-only collector. Identity
remains in memory; only aggregate results are intended for persistence.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import re
import unicodedata
from typing import Mapping, Any

NETWORKS = frozenset(("x", "threads", "facebook", "pinterest", "reddit",
                      "bluesky", "mastodon", "tiktok", "instagram"))
QUEUES = frozenset(("WEB", "API", "MOBILE"))
# These are *field contracts*, not guesses made from a search query or URL.
# Fallbacks support common API and already-normalised collector snapshots.
FIELDS = {
    "x": (("id_str", "rest_id", "id", "post_id"),
          ("user.id_str", "user.id", "author_id"),
          ("full_text", "text"), ("created_at", "createdAt")),
    "threads": (("id", "post_id"), ("user_id", "user.id", "author_id"),
                ("text", "caption"), ("timestamp", "created_at")),
    "facebook": (("id", "post_id"), ("from.id", "author_id"),
                 ("message", "text"), ("created_time", "created_at")),
    "pinterest": (("id", "post_id"), ("creator.id", "owner.id", "author_id"),
                  ("description", "text"), ("created_at", "created_time")),
    "reddit": (("name", "post_id"), ("author_fullname", "author_id", "author.name", "author"),
               ("selftext", "text"), ("created_utc", "created_at")),
    "bluesky": (("uri", "post.uri", "post_id"),
                ("author.did", "post.author.did", "author_id"),
                ("record.text", "post.record.text", "text"),
                ("record.createdAt", "post.record.createdAt", "created_at")),
    "mastodon": (("url", "uri", "post_id"),
                 ("account.url", "author_id"),
                 ("content", "text"), ("created_at",)),
    "tiktok": (("id", "aweme_id", "post_id"),
               ("author.uid", "author.id", "author_id"),
               ("desc", "caption", "text"),
               ("createTime", "create_time", "created_at")),
    "instagram": (("id", "pk", "post_id"),
                  ("user.id", "owner.id", "author_id"),
                  ("caption.text", "caption", "text"),
                  ("timestamp", "taken_at", "created_at")),
}
# Native hashtags only. Search terms, subreddit names and post URLs are
# never attributed as hashtags. #63 separately extracts literal #tags in text.
NATIVE_TAGS = {
    "x": (), "threads": (), "facebook": (), "pinterest": ("tags",),
    "reddit": (), "bluesky": ("record.tags", "post.record.tags"),
    "mastodon": ("tags",), "tiktok": ("challenges", "textExtra"),
    "instagram": ("hashtags",),
}
TAG_VALID = re.compile(r"[^\W\d_][\w]{1,47}\Z", re.UNICODE)
MAX_BATCH = 10000
MAX_TEXT = 10000


def _path(row, dotted):
    value = row
    for key in dotted.split("."):
        if not isinstance(value, Mapping) or key not in value:
            return None
        value = value[key]
    return value


def _first(row, choices):
    for name in choices:
        value = _path(row, name)
        if value is not None and value != "":
            return value
    return None


def _id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("missing stable identity")
    result = str(value).strip()
    if not result or len(result) > 256:
        raise ValueError("missing stable identity")
    return result


def _time(value, *, epoch=False):
    if epoch and isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            result = datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, ValueError, OSError) as exc:
            raise ValueError("invalid epoch") from exc
    elif isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            if not epoch:  # X timestamps may use RFC 2822.
                try:
                    result = parsedate_to_datetime(value)
                except (TypeError, ValueError, IndexError) as exc:
                    raise ValueError("invalid timestamp") from exc
            else:
                raise ValueError("invalid timestamp")
    else:
        raise ValueError("invalid timestamp")
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp without timezone")
    return result.astimezone(timezone.utc)


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("p", "div", "br", "li") and not self.suppressed:
            self.parts.append(" ")
        if tag in ("script", "style"):
            self.suppressed += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.suppressed:
            self.suppressed -= 1
        if tag in ("p", "div", "li") and not self.suppressed:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.suppressed:
            self.parts.append(data)


def _text(raw, network):
    if isinstance(raw, Mapping) and network == "instagram":
        raw = raw.get("text")
    if isinstance(raw, bool) or not isinstance(raw, str) or len(raw) > MAX_TEXT:
        raise ValueError("text missing or too long")
    if network == "mastodon" and "<" in raw:
        parser = _PlainText()
        parser.feed(raw)
        raw = "".join(parser.parts).strip()
    return unicodedata.normalize("NFC", raw)


def _tag(value):
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFC", value.strip().lstrip("#")).casefold()
    return value if TAG_VALID.fullmatch(value) else ""


def _tags(network, row):
    raw = []
    for name in NATIVE_TAGS[network]:
        items = _path(row, name)
        if not isinstance(items, (list, tuple)):
            continue
        for item in items[:100]:
            if isinstance(item, str):
                raw.append(item)
            elif isinstance(item, Mapping):
                key = ("hashtagName" if name == "textExtra" else
                       "title" if name == "challenges" else "name")
                candidate = item.get(key)
                if isinstance(candidate, str):
                    raw.append(candidate)
    if network == "bluesky":
        for parent in ("record.facets", "post.record.facets"):
            facets = _path(row, parent)
            if not isinstance(facets, (list, tuple)):
                continue
            for facet in facets[:100]:
                if not isinstance(facet, Mapping):
                    continue
                features = facet.get("features")
                if not isinstance(features, (list, tuple)):
                    continue
                for feature in features[:10]:
                    if (isinstance(feature, Mapping)
                            and feature.get("$type") == "app.bsky.richtext.facet#tag"
                            and isinstance(feature.get("tag"), str)):
                        raw.append(feature.get("tag"))
    return sorted({x for v in raw if (x := _tag(v))})


def _normalize(network, source, row, now, max_age):
    if not isinstance(row, Mapping):
        raise ValueError("row is not a mapping")
    fields = FIELDS[network]
    post = _id(_first(row, fields[0]))
    author = _id(_first(row, fields[1]))
    if network == "mastodon":
        # A server-local status ID is not globally unique in the Fediverse.
        if not post.startswith(("https://", "http://")) or not author.startswith(("https://", "http://")):
            raise ValueError("mastodon requires globally scoped URLs")
    raw = _first(row, fields[2])
    if network == "reddit":
        title = row.get("title")
        if isinstance(title, str) and title:
            raw = title + (" " + raw if isinstance(raw, str) and raw else "")
    text = _text(raw, network)
    when = _time(_first(row, fields[3]), epoch=network in ("reddit", "tiktok", "instagram"))
    if when > now:
        raise ValueError("future")
    if now - when > timedelta(days=max_age):
        raise ValueError("stale")
    return {"network": network, "source": source, "post_id": post,
            "author_id": author, "created_at": when.isoformat(), "text": text,
            "tags": _tags(network, row)}


class ObservationCollector:
    """Bounded in-memory bridge for WEB/API/MOBILE data, with no side effects.

    Call add_posts separately per read-only producer; to_engine_rows returns
    transient identity-bearing rows for #63 and must NEVER be persisted.
    """
    def __init__(self, *, now, max_age_days=14, max_unique_posts=50000,
                 max_conflicts=50000, max_feedback=50000,
                 max_feedback_conflicts=50000, max_sources_per_post=100):
        self.now = _time(now)
        if not isinstance(max_age_days, int) or isinstance(max_age_days, bool) or not 1 <= max_age_days <= 14:
            raise ValueError("backfill must remain within 14 days")
        if (type(max_unique_posts) is not int
                or not 1 <= max_unique_posts <= 200000):
            raise ValueError("invalid in-memory post budget")
        if (type(max_conflicts) is not int or not 100 <= max_conflicts <= 200000):
            raise ValueError("invalid conflicts budget")
        if (type(max_feedback) is not int or not 100 <= max_feedback <= 200000):
            raise ValueError("invalid feedback budget")
        if (type(max_feedback_conflicts) is not int or not 100 <= max_feedback_conflicts <= 200000):
            raise ValueError("invalid feedback conflicts budget")
        if (type(max_sources_per_post) is not int or not 1 <= max_sources_per_post <= 1000):
            raise ValueError("invalid max sources budget")

        self.max_age_days = max_age_days
        self.max_unique_posts = max_unique_posts
        self.max_conflicts = max_conflicts
        self.max_feedback = max_feedback
        self.max_feedback_conflicts = max_feedback_conflicts
        self.max_sources_per_post = max_sources_per_post

        self._posts = {}
        self._conflicts = set()
        self._feedback = {}
        self._feedback_events = {}
        self._feedback_conflicts = set()
        self.counts = Counter()
        self.by_network_queue = Counter()

    @staticmethod
    def _scope(network, queue, source, rows):
        if network not in NETWORKS or queue not in QUEUES:
            raise ValueError("unsupported network/queue")
        if not isinstance(source, str) or not source.strip() or len(source) > 80:
            raise ValueError("source required")
        if not isinstance(rows, (list, tuple)) or len(rows) > MAX_BATCH:
            raise ValueError("bounded list of rows required")
        return f"{queue}:{source.strip()}"

    def add_posts(self, network, queue, source, rows):
        origin = self._scope(network, queue, source, rows)
        for raw in rows:
            self.counts["input"] += 1
            self.by_network_queue[(network, queue, "input")] += 1
            try:
                item = _normalize(network, origin, raw, self.now, self.max_age_days)
            except (ValueError, TypeError, OverflowError) as exc:
                reason = str(exc)
                key = reason if reason in ("stale", "future") else "invalid"
                self.counts[key] += 1
                self.by_network_queue[(network, queue, key)] += 1
                continue
            key = (network, item["post_id"])
            if key in self._conflicts:
                self.counts["conflicts"] += 1
                continue
            existing = self._posts.get(key)
            if existing:
                # Keep only genuinely identical readings, independent of source.
                if any(existing[k] != item[k] for k in ("author_id", "created_at", "text")):
                    self._posts.pop(key)
                    if len(self._conflicts) < self.max_conflicts:
                        self._conflicts.add(key)
                    self.counts["conflicts"] += 1
                    continue
                existing["tags"] = sorted(set(existing["tags"]) | set(item["tags"]))
                if len(existing["sources"]) < self.max_sources_per_post:
                    existing["sources"].add(origin)
                self.counts["duplicates"] += 1
            else:
                if len(self._posts) >= self.max_unique_posts:
                    self.counts["capacity_skipped"] += 1
                    self.by_network_queue[(network, queue, "capacity_skipped")] += 1
                    continue
                item["sources"] = {origin}
                self._posts[key] = item
                self.by_network_queue[(network, queue, "accepted")] += 1

    def to_engine_rows(self):
        """Ephemeral only; NOT an export format. One row per observed source."""
        rows = []
        for key in sorted(self._posts):
            item = self._posts[key]
            for origin in sorted(item["sources"]):
                rows.append({k: list(item[k]) if k == "tags" else item[k] for k in ("network", "post_id",
                             "author_id", "created_at", "text", "tags")}
                            | {"source": origin})
        return rows

    def add_feedback(self, network, queue, source, rows):
        """Idempotent by (network, tag, event_id), even across queues and windows.

        No denominator => no feedback. Do not derive engaged from likes/views.
        Calls represent explicit confirmed attribution from upstream.
        """
        self._scope(network, queue, source, rows)
        for row in rows:
            self.counts["feedback_input"] += 1
            try:
                if not isinstance(row, Mapping):
                    raise ValueError
                label = _tag(row.get("tag"))
                event = _id(row.get("event_id"))
                window = _time(row.get("window"))
                if window > self.now or self.now - window > timedelta(days=self.max_age_days):
                    raise ValueError
                vals = tuple(row[k] for k in ("eligible", "engaged", "replies", "followers"))
                if (not label or any(type(v) is not int or v < 0 for v in vals)
                        or vals[1] > vals[0] or (vals[0] == 0 and any(vals[1:]))):
                    raise ValueError
            except (ValueError, KeyError, TypeError, OverflowError):
                self.counts["feedback_invalid"] += 1
                continue

            event_key = (network, label, event)
            key = (network, label, window.isoformat(), event)

            if event_key in self._feedback_conflicts:
                self.counts["feedback_conflicts"] += 1
                continue

            if event_key in self._feedback_events:
                prev_window, prev_vals = self._feedback_events[event_key]
                if prev_window == window.isoformat() and prev_vals == vals:
                    self.counts["feedback_duplicates"] += 1
                else:
                    # Conflict across windows or values for same event_id
                    prev_key = (network, label, prev_window, event)
                    self._feedback.pop(prev_key, None)
                    self._feedback_events.pop(event_key, None)
                    if len(self._feedback_conflicts) < self.max_feedback_conflicts:
                        self._feedback_conflicts.add(event_key)
                    self.counts["feedback_conflicts"] += 1
            else:
                if len(self._feedback) >= self.max_feedback:
                    self.counts["capacity_skipped"] += 1
                    continue
                self._feedback[key] = vals
                self._feedback_events[event_key] = (window.isoformat(), vals)

    def feedback_aggregates(self):
        """Safe to export: no event identifiers, source or per-post payload."""
        totals = defaultdict(lambda: [0, 0, 0, 0])
        for (network, label, _window, _event), values in self._feedback.items():
            target = totals[network, label]
            for index, value in enumerate(values):
                target[index] += value
        return [{"network": n, "tag": t, "eligible": v[0], "engaged": v[1],
                 "replies": v[2], "followers": v[3]}
                for (n, t), v in sorted(totals.items())]

    def aggregate_report(self):
        """Exportable diagnostics contain neither identities nor raw post text."""
        return {"schema": 1, "counts": dict(sorted(self.counts.items())),
                "unique_posts": len(self._posts),
                "coverage": [
                    {"network": network, "queue": queue,
                     "input": self.by_network_queue[(network, queue, "input")],
                     "accepted": self.by_network_queue[(network, queue, "accepted")],
                     "invalid": self.by_network_queue[(network, queue, "invalid")],
                     "stale": self.by_network_queue[(network, queue, "stale")],
                     "future": self.by_network_queue[(network, queue, "future")],
                     "capacity_skipped": self.by_network_queue[(network, queue, "capacity_skipped")]}
                    for network in sorted(NETWORKS) for queue in sorted(QUEUES)]}


def ingest_collector_payload(collector: ObservationCollector, network: str,
                            queue: str, source: str, raw_rows: list[dict]) -> int:
    """Convenience helper to ingest posts from read-only scanner into a collector.

    Returns the count of accepted posts for this batch.
    """
    before = collector.aggregate_report()["unique_posts"]
    collector.add_posts(network, queue, source, raw_rows)
    after = collector.aggregate_report()["unique_posts"]
    return max(0, after - before)


def to_snapshot_kwargs(collector: ObservationCollector) -> dict[str, Any]:
    """Prepares kwargs for PR #63 build_snapshot(rows=..., feedback=...)."""
    return {
        "rows": collector.to_engine_rows(),
        "feedback": collector.feedback_aggregates(),
    }
