"""Backtest sintético temporal, sin ficheros ni sesiones de redes.

Los resultados son ilustrativos, NO conversiones observadas. Evalua
precision@10 etiquetada, cobertura y estabilidad de ranking entre dias.
"""
from __future__ import annotations

import datetime as dt
import json

import relationship_priority as priority

DATE = dt.date(2026, 10, 10)
NETWORKS = ("x", "threads", "facebook", "pinterest", "reddit",
            "bluesky", "mastodon", "tiktok", "instagram")
LANES = ("WEB", "API", "MOBILE")


def cohort():
    rows = []
    for i, network in enumerate(NETWORKS):
        for j in range(24):
            lane = LANES[i % len(LANES)]
            # Cohorte ficticia: la probabilidad futura depende de afinidad y
            # conversaciones, no de los likes. El score no lee converted.
            affinity = (j % 12) / 11
            comments = 3 if j % 12 >= 7 else 0
            likes = (23 - j) % 18
            converted = affinity >= 0.55 and comments >= 3
            rows.append({
                "network": network, "handle": f"ficcion{i:02d}_{j:02d}",
                "lane": lane, "affinity": affinity,
                "inbound": {"comment": comments, "like": likes,
                            "repost": 1 if comments else 0},
                "last_inbound_at": "2026-10-08",
                "last_outbound_at": "2026-09-30",
                "reply_target_at": "2026-10-08",
                "reply_eligible": comments > 0,
                "thread_verified": comments > 0,
                "follow_eligible": True, "visit_eligible": True,
                "converted": converted,
            })
    return {"candidates": rows}


def precision(rows, k=10):
    observed = rows[:k]
    return round(sum(item["converted"] for item in observed) / len(observed), 3) if observed else None


def run():
    snapshot = cohort()
    limits = {lane: 10 for lane in LANES}
    output = priority.rank_daily(snapshot, today=DATE, limits=limits)
    evaluation = priority.evaluate_synthetic(snapshot, output)
    by_key = {(r["network"], r["handle"]): r for r in snapshot["candidates"]}
    baseline = {}
    for lane in LANES:
        rows = [r for r in snapshot["candidates"] if r["lane"] == lane]
        # Control histórico simple: ordenar por volumen de likes.
        rows.sort(key=lambda r: (-r["inbound"]["like"], r["network"], r["handle"]))
        baseline[lane] = precision(rows)
    later = priority.rank_daily(snapshot, today=DATE + dt.timedelta(days=1), limits=limits)
    stability = {}
    diversity = {}
    for lane in LANES:
        before = {(r["network"], r["handle"]) for r in output["queues"][lane]}
        after = {(r["network"], r["handle"]) for r in later["queues"][lane]}
        stability[lane] = round(len(before & after) / len(before | after), 3) if before | after else None
        diversity[lane] = len({r["network"] for r in output["queues"][lane]})
    return {"fixture": "SINTETICO_NO_REAL", "candidates": len(snapshot["candidates"]),
            "date": DATE.isoformat(), "at_10": evaluation,
            "baseline_likes_precision": baseline,
            "network_coverage_by_lane": diversity,
            "day_plus_one_jaccard": stability}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
