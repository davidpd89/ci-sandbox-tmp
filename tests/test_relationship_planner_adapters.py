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


def proof(net, *, start="2020-01-01", through="2026-10-10"):
    return {net: {"status": "complete", "from": start,
                  "account_since": "2020-01-01", "through": through}}


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
        if importlib.util.find_spec("relationship_priority") is None:
            self.skipTest("dependencia #71 ausente en base; CI103 la comprueba fijada por SHA")
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
        got, _ = bridge.build_snapshot([recent], {"bluesky": []}, [], today=TODAY,
                                       outbound_coverage=proof("bluesky"))
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
        got, _ = bridge.build_snapshot([row], outbound, incoming, today=TODAY,
                                       outbound_coverage=proof("threads"))
        self.assertEqual(got["candidates"][0]["inbound"]["comment"], 1)
        self.assertEqual(got["candidates"][0]["outbound_30d"], 2)
        self.assertTrue(got["candidates"][0]["reply_eligible"])
        got2, _ = bridge.build_snapshot([row], outbound, [], today=TODAY,
                                        outbound_coverage=proof("threads"))
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
              "data": {"authors": [{"handle": "p_author", "kind": "follow", "preflight": pre()}],
                       "pins": [{"author": "p_pins", "kind": "comment", "preflight": pre(follow_eligible=False),
                                 "target_created_at": "2026-10-10"}]}}
        tt = {"network": "tiktok", "lane": "MOBILE",
              "data": {"candidates": [{"handle": "t_author", "preflight": pre(), "kind": "follow",
                        "posts": [{"created_at": "2026-10-10", "kind": "reply",
                                   "preflight": pre(follow_eligible=False)}]}]}}
        result, _ = bridge.build_snapshot([pi, tt], {"pinterest": [], "tiktok": []}, [],
                                          today=TODAY, outbound_coverage={
                                              **proof("pinterest"), **proof("tiktok")})
        self.assertEqual([x["handle"] for x in result["candidates"]],
                         ["p_author", "p_pins", "t_author", "t_author"])

    def test_nested_native_containers_never_fabricate_actions(self):
        # Autores/pines y posts son estructuras de descubrimiento, no permisos.
        pinterest = {"network": "pinterest", "lane": "WEB",
                     "data": {"authors": [{"handle": "author", "preflight": pre()}],
                              "pins": [{"author": "pin_author",
                                        "target_created_at": "2026-10-10",
                                        "preflight": pre()}]}}
        tiktok = {"network": "tiktok", "lane": "MOBILE",
                  "data": {"candidates": [{"handle": "tt", "kind": "follow",
                                          "preflight": pre(),
                                          "posts": [{"created_at": "2026-10-10",
                                                     "preflight": pre()}]}]}}
        prepared, _ = bridge.build_snapshot([pinterest, tiktok], {}, [], today=TODAY)
        self.assertEqual([(r["network"], r["handle"]) for r in prepared["candidates"]],
                         [("tiktok", "tt")])
        # La acción declarada por un autor tampoco puede heredarse por un post.
        tiktok["data"]["candidates"][0]["actions"] = ["follow"]
        prepared, _ = bridge.build_snapshot([tiktok], {}, [], today=TODAY)
        self.assertEqual(len(prepared["candidates"]), 1)

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
            prepared, _ = bridge.build_snapshot([row], {"reddit": []}, [], today=TODAY,
                                                outbound_coverage=proof("reddit"))
            self.assertEqual(prepared["candidates"][0]["reply_target_at"], "2026-10-09")

    def test_huge_numeric_affinity_never_crashes_entire_batch(self):
        prepared, _ = bridge.build_snapshot(
            [source("reddit", affinity=10 ** 2000), source("x", affinity=0.5)],
            {}, [], today=TODAY)
        self.assertEqual(len(prepared["candidates"]), 2)
        self.assertEqual(prepared["candidates"][0]["affinity"], 0.0)
        self.assertEqual(prepared["candidates"][1]["affinity"], 0.5)

    def test_missing_source_and_bad_registry_do_not_abort_other_networks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "valid.json").write_text(json.dumps(source("x")["data"]), encoding="utf-8")
            (root / "invalid.csv").write_text("cuenta,fecha,tipo\nalpha,2026-10-10,follow\n",
                                               encoding="utf-8")
            config = {"sources": [
                {"network": "x", "lane": "WEB", "path": str(root / "valid.json")},
                {"network": "threads", "lane": "API", "path": str(root / "missing.json")},
                {"network": "reddit", "lane": "WEB", "path": str(root / "valid.json")}],
                "outbound_csvs": {"reddit": str(root / "invalid.csv")}}
            (root / "manifest.json").write_text(json.dumps(config), encoding="utf-8")
            sources, outbound, inbound = bridge.read_manifest(root / "manifest.json")
            self.assertEqual(outbound, {})
            prepared, diag = bridge.build_snapshot(sources, outbound, inbound, today=TODAY)
            self.assertEqual([item["network"] for item in prepared["candidates"]], ["x"])
            self.assertEqual(len([x for x in diag["excluded"] if "reason" in x]), 2)

    def test_missing_or_partial_outbound_does_not_offer_reply(self):
        # Los flags de preflight no acreditan cobertura del histórico entero.
        rows = [source(net, kind="reply", target_created_at="2026-10-10",
                       preflight=pre(follow_eligible=False))
                for net in bridge.NETWORKS]
        outbound = {net: [] for net in bridge.NETWORKS}
        complete = proof("threads")
        missing = bridge.build_snapshot(rows, outbound, [], today=TODAY)[0]
        self.assertEqual(missing["candidates"], [])
        partial = {"x": {"status": "complete", "from": "2026-10-09",
                         "account_since": "2020-01-01", "through": "2026-10-10"}}
        snapshot, diag = bridge.build_snapshot(
            rows, outbound, [], today=TODAY, outbound_coverage={**complete, **partial})
        self.assertEqual([r["network"] for r in snapshot["candidates"]], ["threads"])
        self.assertEqual(diag["outbound_coverage"]["x"], "unknown_or_incomplete")
        # Ninguna certificación es válida sin fichero exportado.
        snapshot, _ = bridge.build_snapshot([rows[1]], {}, [], today=TODAY,
                                            outbound_coverage=complete)
        self.assertEqual(snapshot["candidates"], [])

    def test_inbound_30day_cutoff_and_stale_volume_nine_networks(self):
        events = []
        cutoff = (TODAY - dt.timedelta(days=29)).isoformat()
        old = (TODAY - dt.timedelta(days=30)).isoformat()
        for net in bridge.NETWORKS:
            for i in range(75):
                events.append({"network": net, "event_id": f"old-{i}",
                               "handle": f"reader_{net}", "author_id": f"id-{net}",
                               "kind": "like", "day": old})
            for day, suffix in ((cutoff, "edge"), (TODAY.isoformat(), "now")):
                event = {"network": net, "event_id": suffix,
                         "handle": f"reader_{net}", "author_id": f"id-{net}",
                         "kind": "comment", "day": day}
                events.extend([event] * 3)  # múltiples colectores, un evento
        snapshot, diag = bridge.build_snapshot(
            [source(net) for net in bridge.NETWORKS], {}, events, today=TODAY)
        self.assertEqual(diag["inbound_id_conflicts"], 0)
        self.assertEqual(len(snapshot["candidates"]), 9)
        for row in snapshot["candidates"]:
            self.assertEqual(row["inbound"], {"comment": 2})
            self.assertEqual(row["last_inbound_at"], TODAY.isoformat())
        old_only = [{"network": "x", "event_id": "veryold", "handle": "reader_x",
                     "author_id": "id-x", "kind": "like", "day": old}]
        snapshot, _ = bridge.build_snapshot([source("x")], {}, old_only, today=TODAY)
        self.assertNotIn("inbound", snapshot["candidates"][0])
        self.assertIsNone(snapshot["candidates"][0]["last_inbound_at"])

    def test_lane_limits_use_current_common_scorer(self):
        from relationship_priority import rank_daily
        snapshot, _ = bridge.build_snapshot(
            [source("x", "WEB"), source("x", "API")], {}, [], today=TODAY)
        ranked = rank_daily(snapshot, today=TODAY,
                            limits={"WEB": 0, "API": 1, "MOBILE": 0})
        self.assertEqual(len(ranked["queues"]["API"]), 1)
        self.assertEqual(ranked["queues"]["WEB"], [])

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
