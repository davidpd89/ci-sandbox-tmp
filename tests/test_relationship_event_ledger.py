"""Offline contract tests for the read-only relationship history migration."""
import csv
from contextlib import closing
import pathlib
import sqlite3
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from relationship_event_ledger import (
    NETWORKS, QUEUES, RelationshipLedger, import_legacy_csv,
    legacy_outcome, legacy_time,
)


def event(network="bluesky", queue="API", subject="@Ana", kind="follow",
          outcome="confirmed", source_id="evt-1", occurred_at="2026-10-01T10:00:00Z", **extras):
    return {
        "network": network, "queue": queue, "subject": subject, "kind": kind,
        "outcome": outcome, "source": "synthetic", "source_id": source_id,
        "occurred_at": occurred_at, **extras,
    }


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / "relationships.sqlite"
        self.ledger = RelationshipLedger(self.path)

    def test_idempotent_replay_and_conflict(self):
        e = event()
        self.assertTrue(self.ledger.append(e))
        self.assertFalse(self.ledger.append(e))
        self.assertEqual(self.ledger.count(), 1)
        with self.assertRaisesRegex(ValueError, "changed"):
            self.ledger.append({**e, "outcome": "uncertain"})
        self.assertEqual(self.ledger.count(), 1)

    def test_append_only_guard_and_isolated_action_ledger(self):
        self.ledger.append(event())
        with closing(sqlite3.connect(self.path)) as conn:
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("UPDATE relationship_events SET outcome='failed'")
            with self.assertRaises(sqlite3.DatabaseError):
                conn.execute("DELETE FROM relationship_events")
            self.assertFalse(conn.execute(
                "SELECT name FROM sqlite_master WHERE name='actions'").fetchall())
        operational = pathlib.Path(self.tmp.name) / "actions.sqlite"
        with closing(sqlite3.connect(operational)) as conn:
            conn.execute("CREATE TABLE actions (kind TEXT)")
        with self.assertRaisesRegex(ValueError, "separate DB"):
            RelationshipLedger(operational)
        with closing(sqlite3.connect(operational)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM actions").fetchone()[0], 0)
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0], "delete")

    def test_multi_network_three_queues_and_identity_isolation(self):
        queues = ("WEB", "API", "MOBILE")
        for index, network in enumerate(sorted(NETWORKS)):
            self.assertTrue(self.ledger.append(event(
                network=network, queue=queues[index % len(queues)], source_id=f"row-{index}"
            )))
        self.assertEqual(self.ledger.count(), 9)
        self.assertEqual(len(self.ledger.history("x", "ana")), 1)
        self.assertEqual(len(self.ledger.history("mastodon", "@ANA")), 1)
        self.assertEqual(len(self.ledger.history("instagram", "@ana")), 1)

    def test_reserved_source_id_is_network_scoped(self):
        self.ledger.append(event(network="x"))
        self.ledger.append(event(network="threads"))
        self.assertEqual(self.ledger.count(), 2)
        self.assertEqual(len(self.ledger.history("x", "ana")), 1)

    def test_source_identifiers_preserve_case_in_urls(self):
        self.ledger.append(event(subject="https://example.invalid/Post/A", source_id="case-A"))
        self.ledger.append(event(subject="https://example.invalid/Post/a", source_id="case-a"))
        self.assertEqual(len(self.ledger.history("bluesky", "https://example.invalid/Post/A")), 1)

    def test_utc_normalization_and_no_inferred_timezone(self):
        self.ledger.append(event(occurred_at="2026-10-01T12:00:00+02:00"))
        row = self.ledger.history("bluesky", "ana")[0]
        self.assertEqual(row["occurred_at"], "2026-10-01T10:00:00.000000+00:00")
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.ledger.append(event(source_id="bad", occurred_at="2026-10-01T10:00:00"))
        with self.assertRaises(ValueError):
            self.ledger.append(event(source_id="bad", occurred_at="not-a-date"))
        self.assertEqual(self.ledger.count(), 1)

    def test_validation_and_no_mutations_after_invalid_event(self):
        invalid = [
            {"network": "other"}, {"queue": "BROWSER"}, {"kind": "dm"},
            {"outcome": "present"}, {"subject": ""}, {"source_id": ""},
            {"precision": "hour"}, {"correlation_id": ""},
            {"kind": "followback", "outcome": "confirmed"},
        ]
        for index, changes in enumerate(invalid):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    sample = event(source_id=f"invalid-{index}")
                    sample.update(changes)
                    self.ledger.append(sample)
        self.assertEqual(self.ledger.count(), 0)

    def test_existing_schema_version_refusal(self):
        other = pathlib.Path(self.tmp.name) / "newer.sqlite"
        with closing(sqlite3.connect(other)) as conn:
            conn.execute("PRAGMA user_version=99")
        with self.assertRaisesRegex(ValueError, "version"):
            RelationshipLedger(other)

    def test_concurrent_same_identity_writes_once(self):
        winners = []
        errors = []
        def run():
            try:
                winners.append(RelationshipLedger(self.path).append(event()))
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=run) for _ in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(winners.count(True), 1)
        self.assertEqual(winners.count(False), 11)
        self.assertEqual(self.ledger.count(), 1)

    def test_batch_atomic_when_later_event_invalid(self):
        valid = event(source_id="a")
        invalid = event(source_id="b", occurred_at="2026-10-01T10:00:00")
        with self.assertRaises(ValueError):
            self.ledger.append_many([valid, invalid])
        self.assertEqual(self.ledger.count(), 0)

    def test_batch_atomic_when_later_event_conflicts(self):
        self.ledger.append(event(source_id="original"))
        good = event(source_id="fresh")
        conflict = event(source_id="original", outcome="failed")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.ledger.append_many([good, conflict])
        self.assertEqual(self.ledger.count(), 1)
        self.assertEqual(self.ledger.history("bluesky", "ana")[0]["outcome"], "confirmed")

    def test_batch_load_500_records_and_replay(self):
        records = [event(subject=f"autor-{i}", source_id=f"bulk-{i}") for i in range(500)]
        self.assertEqual(self.ledger.append_many(records), {"inserted": 500, "replayed": 0})
        self.assertEqual(self.ledger.append_many(records), {"inserted": 0, "replayed": 500})
        self.assertEqual(self.ledger.count(), 500)

    def test_in_memory_connection(self):
        mem = RelationshipLedger(":memory:")
        self.assertTrue(mem.append(event()))
        self.assertFalse(mem.append(event()))
        self.assertEqual(mem.count(), 1)
        self.assertEqual(len(mem.history("bluesky", "ana")), 1)

    def test_snapshot_partial_does_not_invent_absence(self):
        self.ledger.append(event())
        partial = self.ledger.reconcile_followers(
            network="bluesky", queue="API", snapshot_id="partial-1",
            observed_at="2026-10-06T12:00:00Z", tracked=["ana", "bea"],
            followers=["bea"], complete=False,
        )
        self.assertEqual(partial, {"inserted": 1, "replayed": 0, "unknown": 1})
        stats = self.ledger.conversion("bluesky", as_of="2026-10-07T00:00:00Z")
        self.assertEqual(stats["unknown"], 1)
        self.assertIsNone(stats["observed_conversion_rate"])

    def test_snapshot_complete_confirmed_positive_negative_and_replay(self):
        for subject, index in [("ana", 1), ("bea", 2), ("cora", 3)]:
            self.ledger.append(event(subject=subject, source_id=str(index)))
        kwargs = {
            "network": "bluesky", "queue": "API", "snapshot_id": "full-v1",
            "observed_at": "2026-10-05T10:00:00Z", "tracked": ["ana", "bea", "cora"],
            "followers": ["ana", "cora"], "complete": True,
        }
        self.assertEqual(self.ledger.reconcile_followers(**kwargs)["inserted"], 3)
        self.assertEqual(self.ledger.reconcile_followers(**kwargs)["replayed"], 3)
        stats = self.ledger.conversion("bluesky", as_of="2026-10-06T12:00:00Z")
        self.assertEqual(
            [stats[k] for k in ("eligible", "observed", "positive", "negative", "unknown")],
            [3, 3, 2, 1, 0],
        )
        self.assertAlmostEqual(stats["observed_conversion_rate"], 2/3)
        with self.assertRaisesRegex(ValueError, "changed"):
            self.ledger.reconcile_followers(**{**kwargs, "followers": ["bea"]})

    def test_followback_snapshot_must_be_timezone_aware(self):
        with self.assertRaises(ValueError):
            self.ledger.reconcile_followers(
                network="mastodon", queue="API", snapshot_id="bad",
                observed_at="2026-10-07T12:00:00", tracked=["ana"],
                followers=["ana"], complete=True,
            )

    def test_age_gate_unfollow_and_latest_observation(self):
        self.ledger.append(event())
        self.ledger.append(event(kind="followback", outcome="present", source_id="s1",
                                 occurred_at="2026-10-03T12:00:00Z"))
        self.ledger.append(event(kind="followback", outcome="absent", source_id="s2",
                                 occurred_at="2026-10-06T12:00:00Z"))
        self.assertEqual(self.ledger.conversion(
            "bluesky", as_of="2026-10-07T12:00:00Z")["negative"], 1)
        self.ledger.append(event(kind="unfollow", source_id="unfollow",
                                 occurred_at="2026-10-07T13:00:00Z"))
        self.assertEqual(self.ledger.conversion(
            "bluesky", as_of="2026-10-08T12:00:00Z")["eligible"], 0)
        self.ledger.append(event(kind="follow", source_id="follow-new",
                                 occurred_at="2026-10-09T12:00:00Z"))
        self.assertEqual(self.ledger.conversion(
            "bluesky", as_of="2026-10-10T12:00:00Z")["eligible"], 0)
        self.assertEqual(self.ledger.conversion(
            "bluesky", as_of="2026-10-12T12:00:00Z")["unknown"], 1)

    def test_duplicate_follow_confirmation_does_not_reset_maturity_or_snapshot(self):
        self.ledger.append(event(source_id="follow-1"))
        self.ledger.append(event(kind="followback", outcome="present", source_id="snapshot",
                                 occurred_at="2026-10-04T12:00:00Z"))
        self.ledger.append(event(source_id="follow-2",
                                 occurred_at="2026-10-06T12:00:00Z"))
        stats = self.ledger.conversion("bluesky", as_of="2026-10-07T12:00:00Z")
        self.assertEqual(stats["eligible"], 1)
        self.assertEqual(stats["positive"], 1)

    def test_uncertain_and_observed_are_not_confirmed_follows(self):
        self.ledger.append(event(outcome="uncertain", source_id="uncertain"))
        self.ledger.append(event(outcome="observed", subject="bea", source_id="observed"))
        self.assertEqual(self.ledger.conversion(
            "bluesky", as_of="2026-10-10T12:00:00Z")["eligible"], 0)

    def test_legacy_outcome_distinguishes_unknown(self):
        self.assertEqual(legacy_outcome("confirmado"), "confirmed")
        self.assertEqual(legacy_outcome("saltado_ya_seguido"), "observed")
        self.assertEqual(legacy_outcome("saltado_preflight_post_antiguo"), "skipped")
        self.assertEqual(legacy_outcome("confirmado_pendiente_verificacion"), "uncertain")
        self.assertEqual(legacy_outcome("texto_desconocido"), "unverified")
        self.assertEqual(legacy_time("2026-10-01")[1], "day")
        with self.assertRaises(ValueError):
            legacy_time("2026-10-01 12:34:56")

    def test_offline_csv_nine_networks_replay_and_pii_minimization(self):
        path = pathlib.Path(self.tmp.name) / "sample.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=(
                "fecha", "cuenta", "tipo", "resultado", "texto_usado", "url"))
            writer.writeheader()
            writer.writerow({"fecha": "2026-10-01", "cuenta": "@Ñandú",
                             "tipo": "follow+reply", "resultado": "confirmado",
                             "texto_usado": "texto privado de fixture", "url": "at://post/1"})
            writer.writerow({"fecha": "2026-10-02", "cuenta": "@Otro",
                             "tipo": "dm", "resultado": "confirmado"})
        for index, network in enumerate(sorted(NETWORKS)):
            q = sorted(QUEUES)[index % len(QUEUES)]
            stats = import_legacy_csv(self.ledger, path, network=network,
                                      queue=q, source_id="export-v1")
            self.assertEqual(stats, {"inserted": 2, "replayed": 0, "ignored": 1})
            self.assertEqual(import_legacy_csv(
                self.ledger, path, network=network, queue=q, source_id="export-v1"
            )["replayed"], 2)
        self.assertEqual(self.ledger.count(), 18)
        self.assertEqual(len(self.ledger.history("reddit", "ñandú")), 2)
        with closing(sqlite3.connect(self.path)) as conn:
            saved = str(conn.execute("SELECT * FROM relationship_events").fetchall())
            self.assertNotIn("texto privado de fixture", saved)

    def test_csv_mutation_same_version_refused(self):
        path = pathlib.Path(self.tmp.name) / "legacy.csv"
        path.write_text("fecha,cuenta,tipo,resultado\n2026-10-01,ana,follow,confirmado\n",
                        encoding="utf-8")
        args = dict(network="threads", queue="API", source_id="immutable-v1")
        self.assertEqual(import_legacy_csv(self.ledger, path, **args)["inserted"], 1)
        path.write_text("fecha,cuenta,tipo,resultado\n2026-10-01,ana,follow,fallo\n",
                        encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            import_legacy_csv(self.ledger, path, **args)
        self.assertEqual(self.ledger.count(), 1)


if __name__ == "__main__":
    unittest.main()
