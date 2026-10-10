"""Offline chronological replay of discovery-source ranking; never schedules actions.

Training cohorts and later holdout cohorts must be independently verified upstream.
The result is descriptive prevalence at snapshots, NOT incremental conversion or
causal uplift. No I/O, credentials, accounts, API, state, or hidden current time.
"""
from __future__ import annotations

import datetime as dt

from discovery_ranking import NETWORKS, SUPPORTED_SNAPSHOTS, rank_cohorts


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def compare_rankings(train, holdout, *, train_as_of, holdout_as_of,
                     min_sample=40, top_k=1):
    """Compare Wilson+minimum-sample with naive rate on chronological holdout.

    Both strategies are evaluated on the SAME disjoint holdout cohorts.
    A missing/invalid holdout for ANY baseline candidate invalidates that
    network's comparison, instead of silently evaluating only survivors.
    No estimator corrects observational selection bias or multiple testing.
    """
    if (type(train_as_of) is not dt.date or type(holdout_as_of) is not dt.date
            or holdout_as_of <= train_as_of
            or type(min_sample) is not int or min_sample < 2
            or type(top_k) is not int or not 1 <= top_k <= 100):
        raise ValueError("invalid replay parameters")

    # The baseline is intentionally the UNGUARDED raw observed rate.
    # The conservative strategy only ranks verified mature cohorts.
    raw = rank_cohorts(train, min_sample=1, as_of=train_as_of)
    guarded = rank_cohorts(train, min_sample=min_sample, as_of=train_as_of)
    future = rank_cohorts(holdout, min_sample=1, as_of=holdout_as_of)
    if raw["rejected_without_network"] or future["rejected_without_network"]:
        raise ValueError("cohorts with unknown network cannot enter replay")
    out = {}
    for net in NETWORKS:
        if net not in SUPPORTED_SNAPSHOTS:
            out[net] = {"status": "snapshot_not_instrumented",
                        "raw_rate_at_k": None, "conservative_at_k": None,
                        "difference": None}
            continue
        candidates = raw["networks"][net]["ranked"]
        reviewed = guarded["networks"][net]["ranked"]
        targets = {r["source_key"]: r for r in future["networks"][net]["ranked"]}
        # Fail comparison if the training or holdout cohort set contains any
        # rejected/duplicated data for this network. A malformed sample is
        # missing information, not evidence of zero outcome.
        if (raw["networks"][net]["unranked"]
                or future["networks"][net]["unranked"]):
            status = "invalid_or_incomplete_cohort"
        elif not candidates:
            status = "no_train_cohorts"
        elif not reviewed:
            status = "no_mature_train_cohorts"
        elif len(candidates) < top_k or len(reviewed) < top_k:
            status = "insufficient_candidates_for_k"
        elif any(r["source_key"] not in targets for r in candidates):
            status = "missing_holdout"
        else:
            # Require a genuinely later exposure window, not merely a newer
            # read of the same followers list or an identical training cohort.
            train_cutoff = max(_date(r["snapshot_on"]) for r in candidates)
            if any(_date(targets[r["source_key"]]["cohort_start"]) <= train_cutoff
                   or _date(targets[r["source_key"]]["cohort_start"]) <= train_as_of
                   for r in candidates):
                status = "overlapping_or_nonchronological_holdout"
            else:
                status = "evaluated"
        if status != "evaluated":
            out[net] = {"status": status, "train_sources": len(candidates),
                        "eligible_sources": len(reviewed),
                        "raw_rate_at_k": None, "conservative_at_k": None,
                        "difference": None}
            continue

        # Identical eligibility and holdout for both strategies, and stable
        # token-only tie breaks. Small training samples stay in naive baseline.
        naive_top = sorted(candidates, key=lambda r:
                           (-r["observed_rate"], -r["eligible_unique"],
                            r["source_key"]))[:top_k]
        guarded_top = reviewed[:top_k]

        def performance(rows):
            # Macro-average: each selected SOURCE is one observation; this is
            # not a count of unique followers across overlapping sources.
            return sum(targets[r["source_key"]]["observed_rate"]
                       for r in rows) / len(rows)

        baseline = performance(naive_top)
        conservative = performance(guarded_top)
        out[net] = {
            "status": status,
            "train_sources": len(candidates),
            "eligible_sources": len(reviewed),
            "baseline_source_keys": [r["source_key"] for r in naive_top],
            "conservative_source_keys": [r["source_key"] for r in guarded_top],
            "raw_rate_at_k": baseline,
            "conservative_at_k": conservative,
            "difference": conservative - baseline,
        }
    return {
        "metric": "holdout_observed_follows_us_at_snapshot_not_causal",
        "baseline": "unguarded_raw_rate",
        "candidate": "wilson_lower_with_min_sample",
        "top_k": top_k,
        "train_as_of": train_as_of.isoformat(),
        "holdout_as_of": holdout_as_of.isoformat(),
        "networks": out,
    }
