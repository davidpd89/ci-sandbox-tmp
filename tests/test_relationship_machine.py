"""Pruebas offline sin cuentas/credenciales de la máquina común de relaciones."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
import pathlib
import random
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import relationship_machine as rm

BASE = datetime(2026, 10, 1, tzinfo=timezone.utc)
KINDS = tuple(sorted(rm.KINDS))


def ev(kind, n, *, net="bluesky", person="sujeto-01", lane="API", eid=None):
    return rm.Event(net, person, eid or f"{n}-{kind}", kind, lane,
                    (BASE + timedelta(minutes=n)).isoformat())


class PureStateTests(unittest.TestCase):
    def test_normal_nine_stage_journey(self):
        seq = ("discovered", "qualified", "follow_confirmed",
               "followback_confirmed", "activity_confirmed", "loyalty_confirmed",
               "inactivity_confirmed", "reactivation_confirmed", "closed_confirmed")
        state = None
        for i, kind in enumerate(seq):
            state = rm.step(state, kind, ev(kind, i).occurred_at)
            self.assertEqual(state.state, rm.STATES[i])
            self.assertEqual(state.version, i + 1)
        self.assertTrue(state.following and state.follows_me)

    def test_cannot_infer_reciprocity_or_loyalty(self):
        state = rm.step(None, "discovered", ev("discovered", 0).occurred_at)
        for kind in ("follow_confirmed", "followback_confirmed", "activity_confirmed",
                     "loyalty_confirmed", "reactivation_confirmed"):
            with self.subTest(kind=kind), self.assertRaises(rm.TransitionError):
                rm.step(state, kind, ev(kind, 1).occurred_at)
        state = rm.step(state, "qualified", ev("qualified", 1).occurred_at)
        state = rm.step(state, "follow_confirmed", ev("follow_confirmed", 2).occurred_at)
        with self.assertRaises(rm.TransitionError):
            rm.step(state, "activity_confirmed", ev("activity_confirmed", 3).occurred_at)

    def test_unfollow_retry_then_follow_again(self):
        kinds = ("discovered", "qualified", "follow_confirmed",
                 "unfollow_confirmed", "retry_approved", "follow_confirmed",
                 "followback_confirmed", "closed_confirmed")
        state = None
        for i, kind in enumerate(kinds):
            state = rm.step(state, kind, ev(kind, i).occurred_at)
        self.assertEqual(state.state, "cerrado")
        for kind in KINDS:
            with self.subTest(kind=kind), self.assertRaises(rm.TransitionError):
                rm.step(state, kind, ev(kind, 50).occurred_at)

    def test_cannot_reactivate_after_unfollow_without_mutuality(self):
        state = None
        for i, kind in enumerate(("discovered", "qualified", "follow_confirmed",
                                  "followback_confirmed", "unfollow_confirmed")):
            state = rm.step(state, kind, ev(kind, i).occurred_at)
        self.assertFalse(state.following)
        with self.assertRaises(rm.TransitionError):
            rm.step(state, "reactivation_confirmed", ev("reactivation_confirmed", 6).occurred_at)
        state = rm.step(state, "retry_approved", ev("retry_approved", 7).occurred_at)
        self.assertEqual(state.state, "candidato")

    def test_lost_followback_then_refollowback(self):
        state = None
        for i, kind in enumerate(("discovered", "qualified", "follow_confirmed",
                                  "followback_confirmed", "activity_confirmed",
                                  "followback_lost", "followback_confirmed",
                                  "activity_confirmed")):
            state = rm.step(state, kind, ev(kind, i).occurred_at)
        self.assertEqual(state.state, "activo")
        self.assertTrue(state.follows_me)

    def test_unordered_rejected_timezone_naive_rejected(self):
        state = rm.step(None, "discovered", ev("discovered", 10).occurred_at)
        with self.assertRaises(rm.OutOfOrderEvent):
            rm.step(state, "qualified", ev("qualified", 1).occurred_at)
        with self.assertRaises(ValueError):
            rm.step(state, "qualified", "2026-10-01T01:01:00")
        with self.assertRaises(ValueError):
            rm.step(state, "qualified", "mal")

    def test_property_based_random_event_sequences(self):
        """6000 secuencias generadas: ningún estado inválido ni promoción sin evidencia."""
        rng = random.Random(6072026)
        for _ in range(6000):
            state = None
            history = []
            for minute in range(rng.randrange(1, 32)):
                kind = rng.choice(KINDS)
                when = ev(kind, minute).occurred_at
                try:
                    new = rm.step(state, kind, when)
                except rm.TransitionError:
                    continue
                self.assertIn(new.state, rm.STATES)
                self.assertEqual(new.version, len(history) + 1)
                if new.state in ("reciproco", "activo", "fiel", "reactivado"):
                    self.assertTrue(new.following and new.follows_me)
                history.append((kind, when))
                state = new
            replayed = None
            for kind, when in history:
                replayed = rm.step(replayed, kind, when)
            self.assertEqual(replayed, state)

    def test_mermaid_covers_every_state_and_is_stable(self):
        diagram = rm.mermaid_diagram()
        self.assertEqual(diagram, rm.mermaid_diagram())
        self.assertTrue(diagram.startswith("stateDiagram-v2\n"))
        for state in rm.STATES:
            self.assertIn(state, diagram)


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(pathlib.Path(self.temp.name) / "synthetic.sqlite")
        self.store = rm.RelationshipStore(self.path)

    def apply_path(self, net="bluesky", person="anon", lane="API"):
        seq = ("discovered", "qualified", "follow_confirmed",
               "followback_confirmed", "activity_confirmed", "loyalty_confirmed")
        return [self.store.apply(ev(kind, i, net=net, person=person, lane=lane))
                for i, kind in enumerate(seq)]

    def test_restore_and_verified_replay(self):
        results = self.apply_path()
        self.assertTrue(all(d.applied for d in results))
        self.assertEqual(results[-1].after, "fiel")
        store2 = rm.RelationshipStore(self.path)
        self.assertEqual(store2.snapshot("bluesky", "anon").version, 6)
        self.assertEqual(len(store2.history("bluesky", "anon")), 6)
        self.assertTrue(store2.verify_replay("bluesky", "anon"))

    def test_exact_duplicate_idempotence_after_later_events(self):
        a, b = ev("discovered", 0), ev("qualified", 1)
        self.store.apply(a)
        self.store.apply(b)
        result = self.store.apply(a)
        self.assertFalse(result.applied)
        self.assertEqual(result.after, "descubierto")
        self.assertEqual(self.store.snapshot("bluesky", "sujeto-01").state, "candidato")
        self.assertEqual(len(self.store.history("bluesky", "sujeto-01")), 2)

    def test_same_id_with_different_content_is_rejected(self):
        a = ev("discovered", 0)
        self.store.apply(a)
        for variation in (
            rm.Event(a.network, a.account, a.event_id, "qualified", a.lane, a.occurred_at),
            rm.Event(a.network, a.account, a.event_id, a.kind, "WEB", a.occurred_at),
            rm.Event(a.network, a.account, a.event_id, a.kind, a.lane, ev("discovered", 1).occurred_at),
        ):
            with self.subTest(variation=variation), self.assertRaises(rm.TransitionError):
                self.store.apply(variation)
        self.assertEqual(len(self.store.history(a.network, a.account)), 1)

    def test_rejected_transition_leaves_no_event_or_version(self):
        a = ev("discovered", 0)
        self.store.apply(a)
        with self.assertRaises(rm.TransitionError):
            self.store.apply(ev("loyalty_confirmed", 1))
        self.assertEqual(self.store.snapshot(a.network, a.account).version, 1)
        self.assertEqual(len(self.store.history(a.network, a.account)), 1)

    def test_rollbacks_on_failure_in_projection(self):
        with mock.patch.object(rm, "step", side_effect=RuntimeError("synthetic crash")):
            with self.assertRaises(RuntimeError):
                self.store.apply(ev("discovered", 0))
        self.assertEqual(self.store.history("bluesky", "sujeto-01"), [])
        self.assertIsNone(self.store.snapshot("bluesky", "sujeto-01"))

    def test_concurrent_distinct_accounts_do_not_lose_rows(self):
        def worker(n):
            for i, kind in enumerate(("discovered", "qualified", "follow_confirmed")):
                self.store.apply(ev(kind, i, person=f"anon-{n}"))
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(worker, range(30)))
        for n in range(30):
            self.assertEqual(self.store.snapshot("bluesky", f"anon-{n}").version, 3)
            self.assertTrue(self.store.verify_replay("bluesky", f"anon-{n}"))

    def test_concurrent_same_event_is_exactly_once(self):
        event = ev("discovered", 0)
        with ThreadPoolExecutor(max_workers=6) as pool:
            decisions = list(pool.map(self.store.apply, [event] * 20))
        self.assertEqual(sum(x.applied for x in decisions), 1)
        self.assertEqual(len(self.store.history(event.network, event.account)), 1)

    def test_network_and_queue_isolation(self):
        for net in rm.NETWORKS:
            for lane in rm.LANES:
                person = f"anon-{lane}"
                self.apply_path(net, person, lane)
                self.assertTrue(self.store.verify_replay(net, person))
        self.assertEqual(len(rm.NETWORKS) * len(rm.LANES), 27)
        self.assertIsNone(self.store.snapshot("bluesky", "not-present"))

    def test_replay_detects_projection_corruption(self):
        self.apply_path()
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute("UPDATE relation_state SET following=0 WHERE network='bluesky'")
        self.assertFalse(self.store.verify_replay("bluesky", "anon"))

    def test_unknown_network_lane_and_identity_rejected(self):
        for bad in (
            rm.Event("other", "anon", "x", "discovered", "API", BASE.isoformat()),
            rm.Event("x", "", "x", "discovered", "API", BASE.isoformat()),
            rm.Event("x", "anon", "x", "discovered", "UNKNOWN", BASE.isoformat()),
            rm.Event("x", "anon", "x", "unrecognized", "WEB", BASE.isoformat()),
            rm.Event("x", "anon", "x\n", "discovered", "WEB", BASE.isoformat()),
            rm.Event("x", " anon", "id", "discovered", "WEB", BASE.isoformat()),
            rm.Event("x", "anon", "id ", "discovered", "WEB", BASE.isoformat()),
            rm.Event("x", None, "id", "discovered", "WEB", BASE.isoformat()),
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.store.apply(bad)


    def test_event_history_row_tamper_detected_even_if_projection_is_valid(self):
        self.apply_path()
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute("UPDATE relation_events SET after_state='cerrado' "
                           "WHERE network='bluesky' AND version=2")
        self.assertFalse(self.store.verify_replay("bluesky", "anon"))

    def test_corrupt_historical_timestamp_is_a_failed_verification(self):
        self.apply_path()
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute("UPDATE relation_events SET occurred_at='not-a-time' "
                           "WHERE network='bluesky' AND version=2")
        self.assertFalse(self.store.verify_replay("bluesky", "anon"))

    def test_in_memory_database_requires_real_file_for_restart(self):
        with self.assertRaises(ValueError):
            rm.RelationshipStore(":memory:")


class ProducerAdapterTests(unittest.TestCase):
    def test_all_networks_and_lanes_only_confirmed_outcomes(self):
        for network in rm.NETWORKS:
            for lane in rm.LANES:
                with self.subTest(net=network, lane=lane):
                    self.assertIsNone(rm.settled_action_event(
                        network=network, account="fake", event_id="demo",
                        action="follow", outcome="fallido", lane=lane,
                        occurred_at=BASE.isoformat()))
                    event = rm.settled_action_event(
                        network=network, account="fake", event_id="demo",
                        action="follow", outcome="confirmado", lane=lane,
                        occurred_at=BASE.isoformat())
                    self.assertEqual(event.kind, "follow_confirmed")
                    self.assertEqual(event.lane, lane)

    def test_observations_require_independent_verification(self):
        kwargs = dict(network="bluesky", account="fake", event_id="x",
                      action="followback", outcome="verified", lane="API",
                      occurred_at=BASE.isoformat())
        with self.assertRaises(rm.TransitionError):
            rm.settled_action_event(**kwargs)
        self.assertEqual(
            rm.settled_action_event(**kwargs, independently_verified=True).kind,
            "followback_confirmed")
        with self.assertRaises(ValueError):
            rm.settled_action_event(**{**kwargs, "action": "not_a_real_action"})


class LegacyContractTests(unittest.TestCase):
    def test_confirmed_legacy_follows_only_no_inferred_reciprocity(self):
        rows = [
            {"fecha": "2026-10-01", "cuenta": "anon", "tipo": "follow", "resultado": "fallido"},
            {"fecha": "2026-10-02", "cuenta": "anon", "tipo": "follow", "resultado": "confirmado"},
            {"fecha": "2026-10-03", "cuenta": "anon", "tipo": "reply", "resultado": "confirmado"},
            {"fecha": "2026-10-04", "cuenta": "anon", "tipo": "unfollow", "resultado": "confirmado"},
        ]
        result = rm.audit_legacy_rows("threads", rows)
        self.assertEqual(result["verified"], 2)
        self.assertEqual(result["states"], {"anon": "inactivo"})
        self.assertEqual(result["anomalies"], [])

    def test_orphaned_unfollow_is_diagnosed_not_invented(self):
        result = rm.audit_legacy_rows("mastodon", [
            {"fecha": "2026-10-01", "cuenta": "fake@example.net",
             "tipo": "unfollow", "resultado": "confirmado"},
            {"fecha": "mal", "cuenta": "another", "tipo": "follow", "resultado": "confirmado"},
        ])
        self.assertEqual(result["verified"], 0)
        self.assertEqual([x["row"] for x in result["anomalies"]], [1, 2])
        self.assertEqual(result["states"], {})

    def test_legacy_uses_existing_normalization_across_handle_aliases(self):
        rows = [
            {"fecha": "2026-10-01", "cuenta": "@ANA", "tipo": "follow",
             "resultado": "confirmado"},
            {"fecha": "2026-10-02", "cuenta": "ana", "tipo": "unfollow",
             "resultado": "confirmado"},
        ]
        result = rm.audit_legacy_rows("instagram", rows)
        self.assertEqual(result["states"], {"ana": "inactivo"})
        self.assertEqual(result["anomalies"], [])

    def test_diagnose_duplicate_and_stale_producer(self):
        result = rm.audit_legacy_rows("x", [
            {"fecha": "2026-10-02", "cuenta": "fake", "tipo": "follow", "resultado": "confirmado"},
            {"fecha": "2026-10-03", "cuenta": "fake", "tipo": "follow", "resultado": "confirmado"},
            {"fecha": "2026-10-01", "cuenta": "fake", "tipo": "unfollow", "resultado": "confirmado"},
        ])
        self.assertEqual(result["verified"], 1)
        self.assertEqual(len(result["anomalies"]), 2)

if __name__ == "__main__":
    unittest.main()
