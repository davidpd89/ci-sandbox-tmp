"""Read-only ranking of *observed* follower snapshots by discovery source.

This is NOT a causal conversion estimate or an automated seed policy. Inputs
must be pre-deduplicated, mature, complete cohorts from a trusted collector.
The function never reads registers, calls platforms, or changes seed state.
"""
from __future__ import annotations

import datetime as dt
import math
import re
from collections import defaultdict
from collections.abc import Mapping

NETWORKS = ("bluesky", "mastodon", "x", "threads", "facebook",
            "pinterest", "reddit", "tiktok", "instagram")
# Only these networks currently have a follower-list reader in growth_attribution.
SUPPORTED_SNAPSHOTS = frozenset(("bluesky", "mastodon"))
_OPAQUE_ID_RE = re.compile(r"[0-9a-f]{24}\Z")
_MAX_ROWS = 10000


def _date(value):
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _reason(row, min_sample, min_age_days, as_of, max_snapshot_age_days):
    if not isinstance(row, Mapping):
        return "invalid_row"
    net, key = row.get("network"), row.get("source_key")
    if not isinstance(net, str) or net not in NETWORKS:
        return "invalid_network"
    if not isinstance(key, str) or not _OPAQUE_ID_RE.fullmatch(key):
        return "invalid_source_key"
    if net not in SUPPORTED_SNAPSHOTS:
        return "snapshot_adapter_unverified"
    if row.get("outcome_kind") != "follows_us_at_snapshot":
        return "outcome_not_observed"
    if row.get("unique_actors_verified") is not True:
        return "identity_unverified"
    if row.get("source_provenance_verified") is not True:
        return "provenance_unverified"
    if row.get("source_policy_approved") is not True:
        return "source_policy_unapproved"
    if row.get("follow_status_verified") is not True:
        return "follow_status_unverified"
    if row.get("snapshot_complete") is not True:
        return "snapshot_incomplete"
    n, back = row.get("eligible_unique"), row.get("following_now")
    if (type(n) is not int or type(back) is not int or
            not 0 <= n <= 1_000_000_000 or not 0 <= back <= n):
        return "invalid_denominator"
    cohort_start = _date(row.get("cohort_start"))
    cohort_end, snapshot = _date(row.get("cohort_end")), _date(row.get("snapshot_on"))
    if (cohort_start is None or cohort_end is None or snapshot is None or
            cohort_start > cohort_end or snapshot > as_of or
            (snapshot - cohort_end).days < min_age_days):
        return "immature_or_invalid_date"
    if (as_of - snapshot).days > max_snapshot_age_days:
        return "stale_snapshot"
    if n < min_sample:
        return "insufficient_sample"
    return None


def _wilson_lower(back, n, z=1.6448536269514722):
    """One-sided conservative score at nominal 95%; not a causal claim."""
    rate = back / n
    denom = 1 + z * z / n
    centre = rate + z * z / (2 * n)
    radius = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n))
    return min(rate, max(0.0, (centre - radius) / denom))


def rank_cohorts(cohorts, *, min_sample=40, min_age_days=3,
                 exploration_fraction=0.2, scan_slots=None, as_of=None,
                 max_snapshot_age_days=7, exploration_cursor=None):
    """Rank eligible cohorts separately per network; reserve exploration slots.

    Input: one independently verified cohort for each (network, source_key).
    Duplicate keys fail closed. Observations can overlap across source keys:
    sums of cohorts ARE NOT unique users or incremental followers.
    scan_slots is optional hypothetical read budget; output never schedules it.
    A caller must supply a per-network, persisted exploration_cursor to select
    any exploration candidates. This function does NOT persist that cursor.
    """
    if as_of is None:
        as_of = dt.date.today()
    if (not isinstance(as_of, dt.date) or isinstance(as_of, dt.datetime) or
            type(max_snapshot_age_days) is not int or max_snapshot_age_days < 0 or
            type(min_sample) is not int or min_sample < 1 or
            type(min_age_days) is not int or min_age_days < 0 or
            type(exploration_fraction) not in (int, float) or
            not math.isfinite(exploration_fraction) or
            not 0 <= exploration_fraction <= 1):
        raise ValueError("invalid ranking parameters")
    if not isinstance(cohorts, (list, tuple)) or len(cohorts) > _MAX_ROWS:
        raise ValueError("cohorts must be a bounded sequence")
    if scan_slots is not None:
        if (not isinstance(scan_slots, Mapping) or
                set(scan_slots) - set(NETWORKS) or
                any(type(v) is not int or not 0 <= v <= 10000 for v in scan_slots.values()) or
                any(net not in SUPPORTED_SNAPSHOTS and slots > 0
                    for net, slots in scan_slots.items())):
            raise ValueError("invalid read-only scan budget")
    if exploration_cursor is not None:
        if (scan_slots is None or not isinstance(exploration_cursor, Mapping) or
                set(exploration_cursor) - set(SUPPORTED_SNAPSHOTS) or
                set(exploration_cursor) - set(scan_slots) or
                any(type(v) is not int or v < 0 or v > 1000000
                    for v in exploration_cursor.values())):
            raise ValueError("exploration cursor requires verified read budget")
    buckets = defaultdict(list)
    unranked = {n: [] for n in NETWORKS}
    rejected_without_network = 0
    for row in cohorts:
        if not isinstance(row, Mapping):
            rejected_without_network += 1
            continue
        net = row.get("network")
        if not isinstance(net, str) or net not in NETWORKS:
            rejected_without_network += 1
            continue
        key = row.get("source_key")
        # Group plausible source keys BEFORE validation so an invalid duplicate
        # cannot be silently ignored in favor of a valid entry.
        if isinstance(key, str) and _OPAQUE_ID_RE.fullmatch(key):
            buckets[(net, key)].append(row)
        else:
            unranked[net].append({"source_key": None, "reason": "invalid_source_key"})
    ranked = {n: [] for n in NETWORKS}
    for (net, key), rows in buckets.items():
        if len(rows) > 1:
            unranked[net].append({"source_key": key, "reason": "duplicate_source_cohort"})
            continue
        row = rows[0]
        reason = _reason(row, min_sample, min_age_days, as_of, max_snapshot_age_days)
        if reason:
            unranked[net].append({"source_key": key, "reason": reason})
            continue
        n, back = row["eligible_unique"], row["following_now"]
        ranked[net].append({"source_key": key, "eligible_unique": n,
                            "following_now": back, "observed_rate": back / n,
                            "lower_bound": _wilson_lower(back, n),
                            "cohort_start": row["cohort_start"],
                            "cohort_end": row["cohort_end"], "snapshot_on": row["snapshot_on"]})
    out = {}
    for net in NETWORKS:
        frames = {(r["cohort_start"], r["cohort_end"], r["snapshot_on"]) for r in ranked[net]}
        if len(frames) > 1:
            # Different exposure windows cannot be fairly ordered together.
            unranked[net].extend(
                {"source_key": r["source_key"], "reason": "incomparable_cohort_windows"}
                for r in ranked[net])
            ranked[net] = []
        ranked[net].sort(key=lambda x: (-x["lower_bound"], -x["eligible_unique"], x["source_key"]))
        unranked[net].sort(key=lambda x: (x["reason"], x["source_key"] or ""))
        slots = scan_slots.get(net) if scan_slots is not None else None
        explore = min(slots, math.ceil(slots * exploration_fraction)) if slots is not None else None
        eligible_small = [r["source_key"] for r in unranked[net]
                          if r["reason"] == "insufficient_sample"]
        cursor = exploration_cursor.get(net) if exploration_cursor is not None else None
        exploration_candidates = None
        if cursor is not None and explore is not None:
            # Deterministic cyclic preview; rotation state MUST live upstream.
            if eligible_small:
                start = cursor % len(eligible_small)
                rotation = eligible_small[start:] + eligible_small[:start]
                exploration_candidates = rotation[:explore]
            else:
                exploration_candidates = []
        out[net] = {"capability": ("reader_in_code_access_unverified" if net in SUPPORTED_SNAPSHOTS
                                   else "not_instrumented"),
                    "ranked": ranked[net], "unranked": unranked[net],
                    "exploration_slots_reserved": explore,
                    "exploration_cursor_required": explore is not None and cursor is None,
                    "exploration_candidates": exploration_candidates,
                    "ranking_slots_available": slots - explore if slots is not None else None}
    return {"metric": "observed_followers_at_snapshot_not_incremental_conversion",
            "min_sample": min_sample, "min_age_days": min_age_days,
            "as_of": as_of.isoformat(),
            "rejected_without_network": rejected_without_network,
            "networks": out}
