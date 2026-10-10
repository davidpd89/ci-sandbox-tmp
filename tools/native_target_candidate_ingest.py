"""Read-only adapters for native target observations -> PR #66 candidate contract.

This module does not read files, launch browsers, call APIs, mutate state or
grant actions. Source data is supplied by callers; missing facts stay unknown.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from collections.abc import Mapping
from urllib.parse import parse_qs, urlsplit

NETWORKS = ("x", "threads", "facebook", "reddit", "pinterest", "instagram")
QUEUES = ("WEB", "API", "MOBILE")
# Verified in the official scanner at the commit documented in the research report.
NATIVE_CAPTURE = {
    "x": "persisted_json",
    "threads": "persisted_json",
    "facebook": "persisted_json",
    "pinterest": "persisted_json",
    "reddit": "memory_only",
    "instagram": "memory_only",
}
MAX_OBSERVATIONS = 10000
MAX_POSTS_PER_ACCOUNT = 30
_ALLOWED_ACTIONS = frozenset(("follow", "reply", "comment", "repost"))
_BAD_HANDLES = frozenset(("?", "unknown", "none", "deleted", "[deleted]", "null"))
_HANDLE = re.compile(r"[a-z0-9_][a-z0-9_.-]{0,99}", re.I)
_DIGITS = re.compile(r"[0-9]{1,30}")
_SHORTCODE = re.compile(r"[A-Za-z0-9_-]{3,100}")
_POST_PATTERN = {
    "x": re.compile(r"/([A-Za-z0-9_]{1,15})/status/([0-9]{1,30})/?$"),
    "threads": re.compile(r"/@([A-Za-z0-9_.]{1,100})/post/([A-Za-z0-9_-]{3,100})/?$"),
    "pinterest": re.compile(r"/pin/([0-9]{1,30})/?$"),
    "instagram": re.compile(r"/(p|reel)/([A-Za-z0-9_-]{3,100})/?$"),
    "reddit": re.compile(r"/(?:r/[A-Za-z0-9_]+/)?comments/([A-Za-z0-9]{3,15})(?:/[^?#]*)?/?$"),
}
_HOSTS = {
    "x": ("x.com", "twitter.com"),
    "threads": ("threads.net", "www.threads.net", "threads.com"),
    "facebook": ("facebook.com", "www.facebook.com", "m.facebook.com"),
    "reddit": ("reddit.com", "www.reddit.com", "old.reddit.com"),
    "pinterest": ("pinterest.com", "www.pinterest.com", "es.pinterest.com"),
    "instagram": ("instagram.com", "www.instagram.com"),
}


def _valid_handle(value):
    if not isinstance(value, str):
        return None
    value = value.strip().lstrip("@").casefold()
    return value if _HANDLE.fullmatch(value) and value not in _BAD_HANDLES else None


def _id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    value = str(value).strip()
    if (not value or value.casefold() in {"unknown", "none", "null", "undefined", "deleted", "n/a", "na"}
        or len(value) > 128 or any(c.isspace() or ord(c) < 33 for c in value)):
        return None
    return value if re.fullmatch(r"[A-Za-z0-9_.:-]+", value) else None


def _when(value, *, epoch=False):
    if isinstance(value, bool):
        return None
    if epoch and isinstance(value, (int, float)):
        try:
            if math.isfinite(value) and 0 <= value <= 253402300799:
                return dt.datetime.fromtimestamp(value, tz=dt.timezone.utc)
        except (ValueError, OverflowError, OSError):
            pass
        return None
    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(dt.timezone.utc)


def _language(obs):
    """Only explicit, observed language fields, not query hints or text inference."""
    value = obs.get("language") or obs.get("lang")
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip().lower()
    return value if re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", value) else None


def _is_spanish(value):
    """Only `es` and `es-*`, never `est` (Estonian)."""
    return value == "es" or (isinstance(value, str) and value.startswith("es-"))


def _permalink(network, value):
    """Canonical, network-scoped remote post keys; never scan ordinals."""
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        p = urlsplit(value)
        if p.scheme != "https" or p.username or p.password or p.port or p.hostname not in _HOSTS[network]:
            return None
        path = p.path
        if network == "facebook":
            # Real Facebook hashtag readers also expose /videos/ and
            # /posts/ URLs; groups may use textual slugs, not just IDs.
            if re.fullmatch(r"/(?:[A-Za-z0-9_.-]+/(?:posts|videos)/(?:[0-9]+|pfbid[A-Za-z0-9]+)|groups/[A-Za-z0-9_.-]+/(?:posts|permalink)/[0-9]+)/?", path):
                return "https://www.facebook.com" + path.rstrip("/")
            if path in ("/story.php", "/permalink.php"):
                qs = parse_qs(p.query, strict_parsing=False)
                if (len(qs.get("story_fbid", [])) == 1 and len(qs.get("id", [])) == 1
                    and all(_DIGITS.fullmatch(qs[k][0]) for k in ("story_fbid", "id"))):
                    return ("https://www.facebook.com" + path + "?story_fbid="
                            + qs["story_fbid"][0] + "&id=" + qs["id"][0])
            return None
        match = _POST_PATTERN[network].fullmatch(path)
        if not match:
            return None
        if network == "x":
            return "https://x.com/" + match.group(1).lower() + "/status/" + match.group(2)
        if network == "threads":
            return "https://www.threads.net/@" + match.group(1).lower() + "/post/" + match.group(2)
        if network == "reddit":
            return "https://www.reddit.com/comments/" + match.group(1).lower()
        if network == "pinterest":
            return "https://www.pinterest.com/pin/" + match.group(1)
        return "https://www.instagram.com/" + match.group(1) + "/" + match.group(2)
    except (ValueError, TypeError):
        return None


def _observations(network, snapshot):
    if network == "pinterest" and isinstance(snapshot, Mapping):
        authors, pins = snapshot.get("authors"), snapshot.get("pins")
        if not isinstance(authors, list) or not isinstance(pins, list):
            raise ValueError("pinterest snapshot requires authors and pins lists")
        # Preserve all Pin metadata while ensuring author/handle, source, and text are set.
        res_pins = []
        for p in pins:
            if isinstance(p, Mapping):
                pin_row = dict(p)
                if "handle" not in pin_row and "author" in pin_row:
                    pin_row["handle"] = pin_row["author"]
                if "source" not in pin_row and "query" in pin_row:
                    pin_row["source"] = pin_row["query"]
                if "text" not in pin_row:
                    pin_row["text"] = " ".join(str(p.get(k) or "") for k in ("title", "desc"))
                pin_row["_pin"] = True
                res_pins.append(pin_row)
        return list(authors) + res_pins
    if not isinstance(snapshot, (list, tuple)):
        raise ValueError("snapshot must be a sequence of native observations")
    if network == "instagram":
        converted = []
        for row in snapshot:
            if isinstance(row, (tuple, list)) and len(row) == 5:
                source, handle, text, permalink, kind = row
                converted.append({"source": source, "handle": handle,
                                  "text": text, "permalink": permalink, "kind": kind})
            else:
                converted.append(row)
        return converted
    return list(snapshot)


def _handle(network, row):
    if network == "facebook":
        # facebook_scan 'autor' is unverified display text; not a stable ID.
        return _valid_handle(row.get("handle"))
    if network == "reddit":
        return _valid_handle(row.get("author") or row.get("handle"))
    return _valid_handle(row.get("handle") or (row.get("author") if network == "pinterest" else None))


def _account_identity(network, row):
    stable = _id(row.get("account_id")) or _id(row.get("user_id"))
    handle = _handle(network, row)
    if stable:
        return "id:" + stable, handle, stable
    if network == "facebook" or not handle:
        return None, handle, None
    return "handle:" + handle, handle, None


def _native_rows(network, rows):
    if network == "facebook":
        for row in rows:
            if isinstance(row, Mapping):
                yield {**row, "source": row.get("tag") or row.get("source"),
                       "url": row.get("permalink") or row.get("url")}
            else:
                yield row
    else:
        yield from rows


def normalize_candidates(network, snapshot, *, as_of, queue="WEB",
                         max_post_age_days=21, community_post_age_days=45,
                         lane="acquisition"):
    """Return {'shortlist': ranker-compatible rows, 'diagnostics': ..., ...}.

    The caller owns provenance and snapshot completeness. Nothing here assumes a
    scan covers all posts/users; absent fields are never backfilled from query,
    scan date, post ordering, suggested action kind or follower guesses.
    """
    if network not in NETWORKS:
        raise ValueError("unknown network")
    if queue not in QUEUES:
        raise ValueError("unknown queue")
    now = _when(as_of)
    if now is None:
        raise ValueError("as_of must be timezone-aware")
    if (lane not in ("acquisition", "community")
        or type(max_post_age_days) is not int or not 0 <= max_post_age_days <= 365
        or type(community_post_age_days) is not int or not 0 <= community_post_age_days <= 365):
        raise ValueError("invalid age policy or lane")
    if snapshot is None:
        return {"network": network, "queue": queue, "status": "unsupported",
                "capture": NATIVE_CAPTURE[network], "shortlist": [],
                "diagnostics": [{"reason": "missing_snapshot"}],
                "complete": None}
    rows = _observations(network, snapshot)
    if len(rows) > MAX_OBSERVATIONS:
        raise ValueError("snapshot exceeds configured bounded size")
    diagnostics, grouped = [], {}
    handle_to_key = {}
    for i, original in enumerate(_native_rows(network, rows)):
        if not isinstance(original, Mapping):
            diagnostics.append({"index": i, "reason": "invalid_observation"})
            continue
        row = original
        if row.get("queue", queue) != queue:
            diagnostics.append({"index": i, "reason": "queue_mismatch"})
            continue
        key, handle, stable = _account_identity(network, row)
        if key is None:
            diagnostics.append({"index": i, "reason": "missing_stable_account_identity"})
            continue

        # Check if an existing account key was created solely by handle ("handle:...") and now we have a stable ID for the same handle
        if stable and handle and handle in handle_to_key:
            prev_key = handle_to_key[handle]
            if prev_key != key and prev_key.startswith("handle:") and prev_key in grouped:
                # Merge handle-keyed account into ID-keyed account
                prev_acc = grouped.pop(prev_key)
                if key not in grouped:
                    grouped[key] = prev_acc
                    grouped[key]["account_id"] = stable
                else:
                    curr = grouped[key]
                    if curr["bio"] is None: curr["bio"] = prev_acc["bio"]
                    if curr["followers"] is None: curr["followers"] = prev_acc["followers"]
                    curr["sources"].update(prev_acc["sources"])
                    curr["actions"].update(prev_acc["actions"])
                    if curr["language"] is None: curr["language"] = prev_acc["language"]
                    if curr["following"] is None: curr["following"] = prev_acc["following"]
                    if curr["followed_by"] is None: curr["followed_by"] = prev_acc["followed_by"]
                    for p_url, p_data in prev_acc["posts"].items():
                        if p_url not in curr["posts"]:
                            curr["posts"][p_url] = p_data
                    curr["conflicting_posts"].update(prev_acc["conflicting_posts"])
                handle_to_key[handle] = key

        # In each network, a verified platform ID survives handle changes.
        account = grouped.setdefault(key, {
            "account_id": stable, "handle": handle, "bio": None,
            "followers": None, "sources": set(), "posts": {},
            "conflicting_posts": set(),
            "language": None, "following": None, "followed_by": None,
            "actions": set(), "lane": lane,
        })
        if handle:
            handle_to_key[handle] = key
        if stable and handle and account["handle"] not in (None, handle):
            diagnostics.append({"index": i, "reason": "handle_rename_for_stable_id"})
        if handle:
            account["handle"] = handle
        bio = row.get("bio")
        if isinstance(bio, str) and bio.strip() and account["bio"] is None:
            account["bio"] = bio[:2000]
        followers = row.get("followers")
        if type(followers) is int and 0 <= followers <= 1_000_000_000:
            if account["followers"] is None:
                account["followers"] = followers
            elif account["followers"] != followers:
                diagnostics.append({"index": i, "reason": "conflicting_follower_snapshots"})
        for field in ("source", "tag"):
            src = row.get(field)
            if isinstance(src, str) and 0 < len(src.strip()) <= 200:
                account["sources"].add(src.strip())
        sources = row.get("sources")
        if isinstance(sources, (list, tuple)):
            account["sources"].update(s.strip() for s in sources
                                       if isinstance(s, str) and 0 < len(s.strip()) <= 200)
        # A post language does not prove the account/profile language.
        # Profile language can come from row profile_language, profile.language, or profile-level language/lang field on author profile observations.
        profile = row.get("profile") if isinstance(row.get("profile"), Mapping) else {}
        is_pin_row = bool(row.get("_pin"))
        is_post_row = is_pin_row or bool(row.get("url") or row.get("permalink") or row.get("created_at") or row.get("created_utc"))
        raw_prof_lang = row.get("profile_language") or profile.get("language")
        if not raw_prof_lang and not is_post_row:
            raw_prof_lang = row.get("language") or row.get("lang")
        profile_lang = _language({"language": raw_prof_lang})
        if profile_lang is not None and account["language"] is None:
            account["language"] = profile_lang
        for rel in ("following", "followed_by"):
            if type(row.get(rel)) is bool:
                account[rel] = row[rel]
        # 'kind' means scanner preference, not observed permission/capability.
        explicit = row.get("verified_actions")
        if isinstance(explicit, (list, tuple)):
            account["actions"].update(a for a in explicit if isinstance(a, str)
                                      and a in _ALLOWED_ACTIONS)
        posts = row.get("posts")
        candidates = posts if isinstance(posts, (list, tuple)) else [row]
        for post in candidates:
            if not isinstance(post, Mapping):
                diagnostics.append({"index": i, "reason": "invalid_post"})
                continue
            url = _permalink(network, post.get("permalink") or post.get("url"))
            if url is None:
                if post.get("url") or post.get("permalink"):
                    diagnostics.append({"index": i, "reason": "invalid_post_permalink"})
                continue
            # Explicit remote author identity must match the account on any network.
            post_author_id = _id(post.get("author_id"))
            if stable and post_author_id and post_author_id != stable:
                diagnostics.append({"index": i, "reason": "post_author_mismatch"})
                continue
            # Check that X and Threads post permalinks do not contradict an
            # author handle (URL is author evidence; not display text).
            if network in ("x", "threads") and handle:
                url_handle = url.split("/")[3].lstrip("@").casefold()
                claimed_post_handle = _valid_handle(post.get("handle"))
                # Historical links can show the old handle only when a
                # trusted immutable author id links them to this account.
                id_matches = bool(stable and post_author_id == stable)
                if ((handle != url_handle or
                     (claimed_post_handle and claimed_post_handle != handle))
                    and not id_matches):
                    diagnostics.append({"index": i, "reason": "post_author_mismatch"})
                    continue
            raw_date = post.get("created_at")
            # Bare "timestamp" is ambiguous: it can be scan time, not post time.
            if raw_date is None and post.get("timestamp_provenance") == "post_published":
                raw_date = post.get("timestamp")
            if network == "reddit" and raw_date is None:
                raw_date = post.get("created_utc")
            timestamp = _when(raw_date, epoch=(network == "reddit"))
            if timestamp is None:
                diagnostics.append({"index": i, "reason": "missing_post_timestamp"})
                continue
            age = (now - timestamp).total_seconds() / 86400
            max_age = community_post_age_days if lane == "community" else max_post_age_days
            if not 0 <= age <= max_age:
                diagnostics.append({"index": i, "reason": "post_outside_age_window"})
                continue
            post_lang = _language(post)
            if post_lang is None:
                diagnostics.append({"index": i, "reason": "unknown_post_language"})
            if post_lang is not None and not _is_spanish(post_lang):
                diagnostics.append({"index": i, "reason": "non_spanish_post"})
                continue
            text = post.get("text") or post.get("title")
            if not isinstance(text, str):
                text = ""
            known = {"url": url, "created_at": timestamp.isoformat(),
                     "text": text[:2000], "language": post_lang,
                     "actions": [a for a in (post.get("verified_actions") or ())
                                 if isinstance(a, str) and a in _ALLOWED_ACTIONS]
                     if isinstance(post.get("verified_actions"), (tuple, list)) and
                        _is_spanish(post_lang) else []}
            # No fake reply counts or engagement stats.
            replies = post.get("replies")
            if replies is None and network == "reddit":
                replies = post.get("comment_count")
            if type(replies) is int and 0 <= replies <= 1_000_000:
                known["stats"] = {"replies": replies}
            existing = account["posts"].get(url)
            if url in account["conflicting_posts"]:
                continue
            if existing and existing["created_at"] != known["created_at"]:
                account["posts"].pop(url, None)
                account["conflicting_posts"].add(url)
                diagnostics.append({"index": i, "reason": "conflicting_post_timestamps"})
                continue
            if existing is None or (existing["language"] is None and known["language"] is not None):
                account["posts"][url] = known
    shortlist = []
    for key, account in sorted(grouped.items()):
        # If stable id exists, avoid the ranker's handle-first fallback.
        value = {
            "bio": account["bio"], "followers": account["followers"],
            "sources": sorted(account["sources"]) if account["sources"] else None,
            "posts": sorted(account["posts"].values(), key=lambda p: (p["created_at"], p["url"]),
                            reverse=True)[:MAX_POSTS_PER_ACCOUNT],
            "language": account["language"], "following": account["following"],
            "followed_by": account["followed_by"], "lane": lane,
            "actions": sorted(account["actions"]),
        }
        if account["account_id"]:
            value["account_id"] = account["account_id"]
            value["observed_handle"] = account["handle"]
        else:
            value["handle"] = account["handle"]
        shortlist.append(value)
    return {"network": network, "queue": queue, "status": "normalized_offline",
            "capture": NATIVE_CAPTURE[network], "shortlist": shortlist,
            "complete": None,  # No native collector certifies complete pages.
            "diagnostics": diagnostics}


def normalize_all(snapshots, *, as_of, queues=None, **kwargs):
    """Six-network entrypoint; missing producers remain visibly unsupported."""
    if not isinstance(snapshots, Mapping) or set(snapshots) - set(NETWORKS):
        raise ValueError("invalid network snapshots")
    if queues is not None and (not isinstance(queues, Mapping)
                               or set(queues) - set(NETWORKS)):
        raise ValueError("invalid queues")
    return {network: normalize_candidates(
        network, snapshots.get(network), as_of=as_of,
        queue=(queues or {}).get(network, "WEB"), **kwargs)
        for network in NETWORKS}


def rank_with_66(normalized, ranker, *, as_of, **kwargs):
    """Explicit dependency injection: module #66 is not on this PR's branch.

    Post #66 integration, pass target_quality_ranking.rank_all. No monkeypatch,
    no production routing or automatic calls to executors.
    """
    if not isinstance(normalized, Mapping):
        raise ValueError("expected normalized network mapping")
    snapshots = {}
    for network, record in normalized.items():
        if network not in NETWORKS or not isinstance(record, Mapping):
            raise ValueError("invalid normalized record")
        if record.get("status") == "normalized_offline":
            snapshots[network] = {"shortlist": record["shortlist"]}
    return ranker(snapshots, as_of=as_of, **kwargs)
