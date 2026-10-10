"""Contratos offline de 9 redes x 3 colas; no accesos a plataformas."""
from __future__ import annotations

import csv
from contextlib import closing
import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "priority-contract" / "tools"))
import relationship_planner_adapters as bridge

TODAY = dt.date(2026, 10, 10)


def pre(**changes):
    return {"checked_at": TODAY.isoformat(), "self_account": False, "blocked": False,
            "follow_state_verified": True, "already_following": False,
            "follow_eligible": True, "comment_allowed": True, "thread_verified": True,
            **changes}


def source(net, lane="WEB", **changes):
    item = {"handle": f"reader_{net}", "actor_id": f"id-{net}", "kind": "follow",
            "affinity": 0.8, "reciprocity": 0.6, "preflight": pre()}
    item.update(changes)
    return {"network": net, "lane": lane, "data": [item]}


class PlannerBridge(unittest.TestCase):
    def test_9x3_dry_lanes_actor_once(self):
        sources = [source(net, lane) for net in bridge.NETWORKS for lane in bridge.LANES]
        snapshot, diag = bridge.build_snapshot(sources, {}, [], today=TODAY)
        self.assertEqual(len(snapshot["candidates"]), 27)
        self.assertEqual(diag["prepared"], 27)
        from relationship_priority import rank_daily
        ranked = rank_daily(snapshot, today=TODAY)
        self.assertEqual(ranked["summary"]["unique_eligible"], 9)
        self.assertEqual(ranked["summary"]["selected"], 9)
        keys = [(r["network"], r["actor_id"]) for q in ranked["queues"].values() for r in q]
        self.assertEqual(len(keys), len(set(keys)))

    def test_x_never_auto_like_or_executable_plan(self):
        data = bridge.plan_dry_run([source("x", actions=["follow", "like"])],
                                   {}, [], today=TODAY, scorer=self._fake_rank)
        self.assertEqual(data["mode"], "offline_dry_run_not_executable")
        self.assertTrue(data["executor_preflight_required"])
        self.assertNotIn("like", json.dumps(data["snapshot"]))
        self.assertNotIn("text", data)
        self.assertNotIn("plan", data)

    @staticmethod
    def _fake_rank(snapshot, *, today, limits=None):
        return {"queues": {"WEB": list(snapshot["candidates"]),
                           "API": [], "MOBILE": []}}

    def test_bad_source_does_not_steal_network_budget(self):
        good = source("mastodon", "API")
        bad = {"network": "threads", "lane": "API", "data": "invalid"}
        sources = [bad, good, {"network": "wrong", "lane": "API", "data": []}]
        data, diag = bridge.build_snapshot(sources, {}, [], today=TODAY)
        self.assertEqual([x["network"] for x in data["candidates"]], ["mastodon"])
        self.assertEqual(len([x for x in diag["excluded"] if "reason" in x]), 2)

    def test_age_necropost_and_unknown_date(self):
        for date in ("2026-10-06", None, "2030-01-01", "2026-10-10T10:00:00"):
            record = source("bluesky", "API", kind="reply", target_created_at=date,
                            preflight=pre(follow_eligible=False))
            got, _ = bridge.build_snapshot([record], {}, [], today=TODAY)
            self.assertEqual(got["candidates"], [], date)
        recent = source("bluesky", "API", kind="reply", target_created_at="2026-10-09T23:00:00Z",
                        preflight=pre(follow_eligible=False))
        got, _ = bridge.build_snapshot([recent], {}, [], today=TODAY)
        self.assertTrue(got["candidates"][0]["reply_eligible"])

    def test_comment_policy_uses_confirmed_and_distinct_events(self):
        row = source("threads", "API", kind="reply", target_created_at="2026-10-10",
                     preflight=pre(follow_eligible=False))
        outbound = {"threads": [{"cuenta": "reader_threads", "fecha": "2026-10-09",
                                 "tipo": "comment", "resultado": "confirmado"}] * 2 +
                    [{"cuenta": "reader_threads", "fecha": "2026-10-09",
                      "tipo": "comment", "resultado": "intentado"}]}
        incoming = [{"network": "threads", "event_id": "100", "handle": "reader_threads",
                     "kind": "comment", "day": "2026-10-10", "author_id": "id-threads"}] * 3
        got, _ = bridge.build_snapshot([row], outbound, incoming, today=TODAY)
        self.assertEqual(got["candidates"][0]["inbound"]["comment"], 1)
        self.assertEqual(got["candidates"][0]["outbound_30d"], 2)
        self.assertTrue(got["candidates"][0]["reply_eligible"])
        got2, _ = bridge.build_snapshot([row], outbound, [], today=TODAY)
        self.assertEqual(got2["candidates"], [])

    def test_unverified_and_stale_preflights_rejected(self):
        for check in ({}, pre(checked_at="2026-10-09"),
                      pre(blocked=True), pre(self_account=True),
                      pre(follow_state_verified=False)):
            result, _ = bridge.build_snapshot(
                [source("reddit", preflight=check)], {}, [], today=TODAY)
            self.assertEqual(result["candidates"], [])

    def test_confirmed_follow_or_block_is_stronger_than_snapshot(self):
        for kind in ("follow", "block"):
            history = {"x": [{"cuenta": "reader_x", "fecha": "2026-10-10",
                               "tipo": kind, "resultado": "confirmado"}]}
            result, _ = bridge.build_snapshot([source("x")], history, [], today=TODAY)
            self.assertEqual(result["candidates"], [])

    def test_unsure_affinity_is_zero_lower_bound(self):
        result, diag = bridge.build_snapshot(
            [source("reddit", affinity="9", reciprocity="99")], {}, [], today=TODAY)
        self.assertEqual(result["candidates"][0]["affinity"], 0.0)
        self.assertIsNone(result["candidates"][0]["reciprocity"])
        self.assertTrue(any("desconocida" in x.get("note", "") for x in diag["excluded"]))

    def test_conflicting_identity_rejects_without_cross_network_collision(self):
        a = source("x", actor_id="ID-1")
        b = source("x", actor_id="ID-2")
        c = source("bluesky", actor_id="ID-1", handle="reader_x")
        result, diag = bridge.build_snapshot([a, b, c], {}, [], today=TODAY)
        self.assertEqual([r["network"] for r in result["candidates"]], ["bluesky"])
        self.assertEqual(sum(x.get("reason") == "identidad contradictoria"
                             for x in diag["excluded"]), 2)

    def test_inbound_collision_discards_event(self):
        base = {"network": "x", "event_id": "42", "kind": "comment",
                "day": "2026-10-10", "handle": "reader_x"}
        events = [base, {**base, "handle": "other"}]
        result, diag = bridge.build_snapshot([source("x")], {}, events, today=TODAY)
        self.assertEqual(diag["inbound_id_conflicts"], 1)
        self.assertEqual(result["candidates"][0]["inbound"], {})

    def test_pinterest_and_tiktok_nested_adapters(self):
        pi = {"network": "pinterest", "lane": "WEB",
              "data": {"authors": [{"handle": "p_author", "preflight": pre()}],
                       "pins": [{"author": "p_pins", "preflight": pre(follow_eligible=False),
                                 "target_created_at": "2026-10-10"}]}}
        tt = {"network": "tiktok", "lane": "MOBILE",
              "data": {"candidates": [{"handle": "t_author", "preflight": pre(), "kind": "follow",
                        "posts": [{"created_at": "2026-10-10",
                                   "preflight": pre(follow_eligible=False)}]}]}}
        result, _ = bridge.build_snapshot([pi, tt], {}, [], today=TODAY)
        self.assertEqual([x["handle"] for x in result["candidates"]],
                         ["p_author", "p_pins", "t_author", "t_author"])

    def test_manifest_is_explicit_and_readonly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.json").write_text(json.dumps(source("x")["data"]), encoding="utf-8")
            with (root / "out.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, ["cuenta", "tipo", "fecha", "resultado"])
                writer.writeheader()
            dbpath = root / "events.sqlite"
            with closing(sqlite3.connect(dbpath)) as db, db:
                db.execute("CREATE TABLE verified_inbound (network TEXT, event_id TEXT,"
                           " author_id TEXT, handle TEXT, kind TEXT, day TEXT)")
                db.execute("INSERT INTO verified_inbound VALUES (?,?,?,?,?,?)",
                           ("x", "99", "id-x", "reader_x", "follow", "2026-10-10"))
            before = dbpath.stat().st_size
            manifest = {"sources": [{"network": "x", "lane": "WEB",
                                     "path": str(root / "source.json")}],
                        "outbound_csvs": {"x": str(root / "out.csv")},
                        "verified_inbound_sqlite": str(dbpath)}
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            sources, outbound, incoming = bridge.read_manifest(root / "manifest.json")
            self.assertEqual(len(sources), 1)
            self.assertEqual(len(incoming), 1)
            self.assertEqual(outbound, {"x": []})
            self.assertEqual(dbpath.stat().st_size, before)

    def test_native_unix_seconds_and_milliseconds(self):
        epoch = int(dt.datetime(2026, 10, 9, 12, tzinfo=dt.timezone.utc).timestamp())
        for value in (epoch, str(epoch), epoch * 1000, str(epoch * 1000)):
            self.assertEqual(bridge._day(value), "2026-10-09")
            row = source("reddit", "WEB", kind="reply", post={"created_utc": value},
                         preflight=pre(follow_eligible=False))
            prepared, _ = bridge.build_snapshot([row], {}, [], today=TODAY)
            self.assertEqual(prepared["candidates"][0]["reply_target_at"], "2026-10-09")

    def test_huge_numeric_affinity_never_crashes_entire_batch(self):
        prepared, _ = bridge.build_snapshot(
            [source("reddit", affinity=10 ** 2000), source("x", affinity=0.5)],
            {}, [], today=TODAY)
        self.assertEqual(len(prepared["candidates"]), 2)
        self.assertEqual(prepared["candidates"][0]["affinity"], 0.0)
        self.assertEqual(prepared["candidates"][1]["affinity"], 0.5)

    def test_cost_read_microbenchmark_synthetic(self):
        samples = [source(net, lane, handle=f"reader_{net}_{lane}_{i}")
                   for i in range(50) for net in bridge.NETWORKS for lane in bridge.LANES]
        start = time.perf_counter()
        result, diag = bridge.build_snapshot(samples, {}, [], today=TODAY)
        elapsed = time.perf_counter() - start
        self.assertEqual(len(result["candidates"]), 1350)
        self.assertEqual(diag["sources"], 1350)
        print(f"synthetic bridge 1350 candidates read={elapsed:.3f}s", flush=True)


if __name__ == "__main__":
    unittest.main()
