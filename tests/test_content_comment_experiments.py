"""Regresiones deterministas offline del motor de experimentos de la PR #80."""
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import content_comment_experiments as ce

EARLY = "2026-01-01T10:00:00+00:00"
DAY7 = "2026-01-08T10:00:00+00:00"
DAY14 = "2026-01-15T10:00:00+00:00"


class ExperimentEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name) / "experiments.db"
        self.store = ce.ExperimentStore(self.path)
        self.addCleanup(self.store.close)
        self.store.register("apertura", seed="public-test-seed")

    def assign(self, unit="unit_001", network="x", queue="WEB", name="apertura"):
        return self.store.assign(name, network, unit, queue)

    def exposure(self, unit="unit_001", network="x", queue="WEB",
                 event="exposure_001", name="apertura", timestamp=EARLY):
        return self.store.expose(event, name, network, unit, queue, timestamp)

    def outcome(self, unit="unit_001", network="x", queue="WEB",
                event="outcome_001", name="apertura", timestamp=DAY7,
                converted=True, source="confirmed_snapshot"):
        return self.store.outcome(event, name, network, unit, queue, timestamp,
                                  converted, source)

    def test_all_networks_and_all_queues_have_one_generic_contract(self):
        for idx, net in enumerate(sorted(ce.NETWORKS)):
            unit = f"synthetic_{idx}"
            q = sorted(ce.QUEUES)[idx % 3]
            arm = self.assign(unit, net, q)
            self.assertIn(arm, ce.INITIAL_EXPERIMENTS["apertura"][1])
            self.assertEqual(self.assign(unit, net, q), arm)
            self.assertTrue(self.exposure(unit, net, q, f"exposure_{idx}"))
            self.assertTrue(self.outcome(unit, net, q, f"outcome_{idx}"))
        report = self.store.report(draws=512)
        self.assertEqual(len(report["studies"]), 9)
        for study in report["studies"]:
            self.assertEqual(study["coverage"], {
                "assigned": 1, "exposed": 1, "mature": 1, "unexposed": 0,
                "pending_maturity": 0})
            self.assertFalse(report["causal_claim_approved"])

    def test_registration_and_assignments_immutable_across_restarts(self):
        first = self.assign()
        self.store.register("apertura", seed="public-test-seed")
        with self.assertRaises(ValueError):
            self.store.register("apertura", seed="changed")
        with ce.ExperimentStore(self.path) as reopened:
            self.assertEqual(reopened.assign("apertura", "x", "unit_001", "WEB"), first)
            with self.assertRaises(ValueError):
                reopened.assign("apertura", "x", "unit_001", "API")

    def test_exposure_requires_assignment_and_confirmation(self):
        with self.assertRaises(ValueError):
            self.exposure()
        self.assign()
        with self.assertRaises(ValueError):
            self.store._record(event_id="bad", name="apertura", network="x",
                               unit_id="unit_001", queue="WEB", kind="exposure",
                               occurred_at=EARLY, source="pending")
        self.assertTrue(self.exposure())
        self.assertFalse(self.exposure())
        with self.assertRaises(ValueError):
            self.exposure(event="another_exposure")

    def test_outcome_requires_exposure_maturity_and_boolean(self):
        self.assign()
        with self.assertRaises(ValueError):
            self.outcome()
        self.exposure()
        with self.assertRaises(ValueError):
            self.outcome(timestamp="2026-01-07T10:00:00+00:00")
        with self.assertRaises(ValueError):
            self.outcome(converted=1)
        with self.assertRaises(ValueError):
            self.outcome(source="inferred")
        self.assertTrue(self.outcome(converted=False))
        self.assertFalse(self.outcome(converted=False))
        with self.assertRaises(ValueError):
            self.outcome(converted=True)
        with self.assertRaises(ValueError):
            self.outcome(event="outcome_002", converted=False)

    def test_event_id_global_conflict_and_atomic_rollback(self):
        self.assign()
        self.exposure()
        with self.assertRaises(ValueError):
            self.outcome(event="exposure_001")
        self.assertEqual(self.store.report(draws=256)["studies"][0]["coverage"]["mature"], 0)
        self.assertTrue(self.outcome(event="outcome_001"))

    def test_persist_no_handles_or_text_or_secrets_and_no_duplicate_overcount(self):
        self.assign()
        self.exposure()
        self.outcome()
        with self.assertRaises(ValueError):
            self.assign("@persona")
        with self.assertRaises(ValueError):
            self.assign("https://profile.example")
        rows = self.store.db.execute("SELECT subject FROM assignments").fetchall()
        self.assertEqual(len(rows[0]["subject"]), 64)
        self.assertNotIn("unit_001", repr([tuple(x) for x in rows]))
        self.assertEqual(self.store.report(draws=256)["studies"][0]["variants"][
            self.assign()]["successes"], 1)

    def test_no_network_mixing_same_unit_id(self):
        arm_x = self.assign()
        arm_t = self.assign(network="threads")
        self.assertIn(arm_x, ce.INITIAL_EXPERIMENTS["apertura"][1])
        self.assertIn(arm_t, ce.INITIAL_EXPERIMENTS["apertura"][1])
        self.assertEqual(len(self.store.report(draws=256)["studies"]), 2)
        # Una unidad en Threads se expone correctamente con evento distinto.
        self.assertTrue(self.exposure(network="threads", event="event_threads"))

    def test_empty_and_partial_exposures_remain_outside_denominator(self):
        self.assign("u1")
        self.assign("u2")
        self.exposure("u1", event="ex1")
        row = self.store.report(draws=256)["studies"][0]
        self.assertEqual(row["coverage"], {"assigned": 2, "exposed": 1,
                                           "mature": 0, "unexposed": 1,
                                           "pending_maturity": 1})
        self.assertEqual(row["status"], "insufficient_outcomes")

    def test_context_is_comment_only_and_14_day_window(self):
        self.store.register("contexto", seed="context-seed")
        arm = self.assign("context_1", "bluesky", "API", "contexto")
        self.assertIn(arm, ("detalle_observable", "cita_verificada"))
        self.exposure("context_1", "bluesky", "API", "exp_context", "contexto")
        with self.assertRaises(ValueError):
            self.outcome("context_1", "bluesky", "API", "out_context", "contexto")
        self.outcome("context_1", "bluesky", "API", "out_context", "contexto", DAY14)
        study = next(x for x in self.store.report(draws=256)["studies"]
                     if x["experiment"] == "contexto")
        self.assertEqual((study["metric"], study["window_days"]),
                         ("reply_received", 14))

    def test_four_editorial_experiments_are_distinct(self):
        for name, definition in ce.INITIAL_EXPERIMENTS.items():
            if name != "apertura":
                self.store.register(name, seed="synthetic")
            self.assign("candidate", "pinterest", "API", name)
            study = next(x for x in self.store.report(draws=256)["studies"]
                         if x["experiment"] == name)
            self.assertEqual(study["metric"], definition[2])
            self.assertEqual(set(study["variants"]), set(definition[1]))

    def test_timestamps_reject_naive_non_utc_and_malformed(self):
        self.assign()
        for bad in ("2026-01-01", "2026-01-01T10:00:00",
                    "2026-01-01T12:00:00+02:00", "nonsense", None):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                self.exposure(event="bad_event", timestamp=bad)
        self.assertTrue(self.exposure(timestamp="2026-01-01T10:00:00Z"))

    def test_estimates_deterministic_with_small_sample_and_no_winner_action(self):
        arm_to_unit = {}
        for i in range(100):
            unit = f"trial_{i}"
            arm = self.assign(unit)
            arm_to_unit.setdefault(arm, unit)
            if len(arm_to_unit) == 2:
                break
        self.assertEqual(len(arm_to_unit), 2)
        for i, (arm, unit) in enumerate(arm_to_unit.items()):
            self.exposure(unit, event=f"exp_{i}")
            self.outcome(unit, event=f"result_{i}", converted=i == 1)
        first = self.store.report(draws=1024)
        second = self.store.report(draws=1024)
        self.assertEqual(first, second)
        self.assertEqual(first["studies"][0]["status"], "exploratory_only")
        self.assertFalse(first["adaptive"])
        self.assertTrue(0 <= first["studies"][0]["p_second_better_exploratory"] <= 1)
        self.assertIn("Sin atribución validada", self.store.markdown())

    def test_reject_bad_identifiers_seed_and_outcomes_without_mutation(self):
        for name in ("inventado", "", "apertura\n"):
            with self.assertRaises(ValueError):
                self.store.register(name, seed="seed")
        for seed in ("", "no válido", "@not_public"):
            with self.assertRaises(ValueError):
                self.store.register("pregunta", seed=seed)
        for bad in ("unknown", "", None):
            with self.assertRaises(ValueError):
                self.assign(network=bad)
        with self.assertRaises(ValueError):
            self.store.report(draws=0)
        self.assertEqual(self.store.report(draws=256)["studies"], [])

    def test_readonly_dashboard_refuses_mutations_even_of_existing_schema(self):
        self.assign("safe_1")
        before = self.path.stat().st_size
        with ce.ExperimentStore(self.path, read_only=True) as reader:
            self.assertEqual(reader.report(draws=256)["studies"][0]["coverage"]["assigned"], 1)
            for action in (
                lambda: reader.register("pregunta", seed="new"),
                lambda: reader.assign("apertura", "x", "new_unit", "WEB"),
                lambda: reader.expose("ev", "apertura", "x", "safe_1", "WEB", EARLY),
            ):
                with self.assertRaises(ValueError):
                    action()
        self.assertEqual(self.path.stat().st_size, before)

    def test_readonly_open_non_database_does_not_initialize_schema(self):
        random_file = pathlib.Path(self.temp.name) / "not-a-database.txt"
        random_file.write_text("original content", encoding="utf-8")
        with self.assertRaises(sqlite3.DatabaseError):
            with ce.ExperimentStore(random_file, read_only=True) as reader:
                reader.report(draws=256)
        self.assertEqual(random_file.read_text(encoding="utf-8"), "original content")

    def test_schema_sqlite_and_cli_offline(self):
        self.assign()
        script = pathlib.Path(ce.__file__)
        result = subprocess.run(
            [sys.executable, str(script), "--db", str(self.path), "--format", "json"],
            capture_output=True, text=True, check=True, timeout=15)
        output = json.loads(result.stdout)
        self.assertEqual(output["studies"][0]["coverage"]["assigned"], 1)
        self.assertFalse(output["causal_claim_approved"])
        missing = pathlib.Path(self.temp.name) / "not_existing.db"
        bad = subprocess.run([sys.executable, str(script), "--db", str(missing)],
                             capture_output=True, text=True, timeout=15)
        self.assertNotEqual(bad.returncode, 0)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
