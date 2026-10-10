"""Deterministic *synthetic* before/after replay. No real histories are read."""
from __future__ import annotations

import datetime as dt
import json

from target_quality_ranking import evaluate_orders, rank_network


def replay():
    now = dt.datetime(2026, 10, 10, 8, tzinfo=dt.timezone.utc)
    rows, outcomes = [], {}
    # Four topical, current Spanish-language readers are assigned deliberately
    # low native scores; four unrelated historical high-scorers are assigned
    # high native scores. This is a contract check, not claimed real lift.
    for number in range(8):
        key = f"synthetic{number}.example"
        relevant = number < 4
        rows.append({
            "handle": key, "bio": "Leo novelas de fantasía juvenil y romantasy"
            if relevant else "Noticias de tecnología",
            "followers": 500 if relevant else 100000,
            "sources": ["reading_search", "books_reply", "book_feed"]
            if relevant else ["generic_search"],
            "score": 4 if relevant else 20,  # native proxy
            "actions": ["follow"],
            "posts": [{
                "uri": "at://did:plc:synthetic/app.bsky.feed.post/" + str(number),
                "text": "Recomiendo esta novela de fantasía" if relevant else "Software empresarial",
                "created_at": "2026-10-09T08:00:00Z" if relevant else "2026-08-01T08:00:00Z",
                "es": True,
            }],
        })
        outcomes["bluesky:" + key] = {
            "followback": relevant, "response": relevant,
            "conversation": relevant, "traffic": relevant}
    ranked = rank_network("bluesky", rows, as_of=now)["ranked"]
    new_order = [item["id"] for item in ranked]
    old_order = ["bluesky:" + row["handle"] for row in
                 sorted(rows, key=lambda item: (-item["score"], item["handle"]))]
    return {"scenario": "synthetic_quality_vs_native_proxy",
            "top_k": 4, "candidate_order": new_order[:4],
            "legacy_order": old_order[:4],
            "metrics": evaluate_orders(new_order, old_order, outcomes, k=4)}


def main():
    print(json.dumps(replay(), sort_keys=True, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
