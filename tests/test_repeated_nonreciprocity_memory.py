"""Regresiones de memoria histórica. No hay credenciales ni acciones externas."""
import csv
import datetime as dt
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import relationship_memory as mem
import relationship_policy as rp

TODAY = dt.date(2026, 10, 10)


def row(account, kind, date, *, notes="", result="confirmado"):
    return {"cuenta": account, "tipo": kind, "fecha": date, "notas": notes, "resultado": result}


def cycle(account, start, end):
    return [row(account, "follow+like", start),
            row(account, "unfollow", end, notes="cleanup:no devuelve el follow")]


class HistoricalMemoryTests(unittest.TestCase):
    def test_cooldown_expires_exactly_and_deprioritizes(self):
        events = mem.events_from_rows(cycle("@LECTOR", "2026-09-01", "2026-09-02"), "x")
        self.assertEqual(mem.decision(events, "x", "lector", today=dt.date(2026, 9, 22))["status"], "cooldown")
        d = mem.decision(events, "x", "@lector", today=dt.date(2026, 9, 23))
        self.assertEqual((d["status"], d["failures"], d["rank_delta"]), ("eligible", 1, -1.5))
        self.assertEqual(d["retry_on"], dt.date(2026, 9, 23))
        self.assertEqual(d["evidence"], "registro.csv:3")

    def test_adaptive_second_attempt_then_exhaustion(self):
        rows = cycle("a", "2026-08-01", "2026-08-02") + cycle("a", "2026-09-01", "2026-09-02")
        events = mem.events_from_rows(rows, "threads")
        self.assertEqual(mem.decision(events, "threads", "a", today=TODAY)["status"], "cooldown")
        self.assertEqual(mem.decision(events, "threads", "a", today=dt.date(2026, 10, 14))["status"], "eligible")
        rows += cycle("a", "2026-10-15", "2026-10-16")
        events = mem.events_from_rows(rows, "threads")
        self.assertEqual(mem.decision(events, "threads", "a", today=dt.date(2026, 10, 17))["status"], "exhausted")
        self.assertEqual(mem.decision(events, "threads", "a", today=dt.date(2027, 1, 14),
                                      policy=mem.Policy(ban_days=90))["status"], "eligible")

    def test_no_duplicate_cycles_failed_or_future(self):
        rows = cycle("a", "2026-08-01", "2026-08-02")
        rows += [rows[-1], row("a", "unfollow", "2026-08-03", notes="no devuelve", result="fallo")]
        rows += cycle("a", "2026-10-20", "2026-10-22")
        self.assertEqual(mem.decision(mem.events_from_rows(rows, "mastodon"),
                                      "mastodon", "a", today=TODAY)["failures"], 1)
        orphans = [row("b", "unfollow", "2026-09-01", notes="no devuelve") for _ in range(3)]
        self.assertEqual(mem.decision(mem.events_from_rows(orphans, "x"),
                                      "x", "b", today=TODAY)["failures"], 1)

    def test_legacy_orphans_from_distinct_dates_remain_three_attempts(self):
        # Históricos anteriores sólo guardaban el unfollow, sin follow previo.
        rows = [row("a", "unfollow", day, notes="no devuelve")
                for day in ("2026-07-01", "2026-08-01", "2026-09-01")]
        state = mem.decisions_from_rows(rows, "x", today=TODAY)["a"]
        self.assertEqual((state["failures"], state["status"]), (3, "exhausted"))

    def test_reciprocity_requires_verified_event_and_permanent_survives(self):
        rows = cycle("a", "2026-08-01", "2026-08-02") + [row("a", "followback", "2026-09-01")]
        self.assertEqual(mem.decisions_from_rows(rows, "facebook", today=TODAY)["a"]["failures"], 1)
        rows.append(row("a", "reciprocated", "2026-09-02"))
        self.assertEqual(mem.decisions_from_rows(rows, "facebook", today=TODAY)["a"]["failures"], 0)
        rows.append(row("a", "block", "2026-09-03"))
        self.assertEqual(mem.decisions_from_rows(rows, "facebook", today=TODAY)["a"]["status"], "permanent")

    def test_verified_followback_events_from_neighboring_prs_reset_memory(self):
        # #57 usa followback_observed y #60 followback_confirmed.
        for kind in ("followback_observed", "followback_confirmed"):
            with self.subTest(kind=kind):
                rows = cycle("a", "2026-08-01", "2026-08-02")
                rows.append(row("a", kind, "2026-09-01", result="pendiente"))
                self.assertEqual(mem.decisions_from_rows(rows, "x", today=TODAY)["a"]["failures"], 1)
                rows[-1]["resultado"] = "confirmado"
                self.assertEqual(mem.decisions_from_rows(rows, "x", today=TODAY)["a"]["failures"], 0)

    def test_permanent_decision_preserves_block_evidence(self):
        rows = [row("a", "block", "2026-08-01")] + cycle(
            "a", "2026-09-01", "2026-09-02")
        decision = mem.decisions_from_rows(rows, "x", today=TODAY)["a"]
        self.assertEqual(decision["status"], "permanent")
        self.assertEqual(decision["evidence"], "registro.csv:2")

    def test_invalid_skipped_or_undated_legacy(self):
        rows = [row("bot", "unfollow", "", result="saltado_ya_no_seguido"),
                row("dudosa", "unfollow", "2026-09-01", notes="no devuelve",
                    result="saltado_ya_no_seguido"),
                row("ninguna", "follow", "2026-09-01", result="fallo"),
                row("https://example.com", "block", "2026-09-01")]
        states = mem.decisions_from_rows(rows, "x", today=TODAY)
        self.assertEqual(states["bot"]["status"], "permanent")
        self.assertNotIn("dudosa", states)
        self.assertNotIn("ninguna", states)
        self.assertNotIn("https://example.com", states)

    def test_network_isolation_handles_and_validation(self):
        x = mem.events_from_rows(cycle("@ANA", "2026-09-01", "2026-09-02"), "x")
        self.assertEqual(mem.decision(x, "bluesky", "ana", today=TODAY)["failures"], 0)
        self.assertNotEqual(mem.norm("@ana@example.com"), mem.norm("@ana@example.net"))
        for args in ({"multiplier": 0}, {"max_failures": 0}, {"cap_days": 1}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                mem.Policy(**args)
        with self.assertRaises(ValueError):
            mem.events_from_rows([], "desconocida")

    def test_sqlite_import_is_idempotent_atomic_and_cross_network(self):
        with tempfile.TemporaryDirectory() as folder:
            db, src = pathlib.Path(folder) / "memory.db", pathlib.Path(folder) / "registro.csv"
            def write(rows):
                with src.open("w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=["fecha", "cuenta", "tipo", "notas", "resultado"])
                    writer.writeheader()
                    writer.writerows(rows)
            write(cycle("a", "2026-09-01", "2026-09-02"))
            memory = mem.RelationshipMemory(db)
            self.assertEqual(memory.import_csv("x", src), 2)
            self.assertEqual(memory.import_csv("x", src), 2)
            self.assertEqual(len(memory.events("x")), 2)
            memory.replace_source("mastodon", "legacy", mem.events_from_rows(
                cycle("a", "2026-09-01", "2026-09-02"), "mastodon"))
            with self.assertRaises(ValueError):
                memory.replace_source("x", "registro.csv", memory.events("mastodon"))
            self.assertEqual(len(memory.events("x")), 2)
            src.write_text("cuenta,tipo\na,unfollow\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                memory.import_csv("x", src)
            self.assertEqual(len(memory.events("x")), 2)
            write([row("b", "block", "2026-10-01")])
            memory.import_csv("x", src)
            self.assertEqual(memory.lookup("x", "a", today=TODAY)["failures"], 0)
            self.assertEqual(memory.lookup("x", "b", today=TODAY)["status"], "permanent")
            self.assertEqual(memory.lookup("mastodon", "a", today=TODAY)["failures"], 1)

    def test_integration_discovery_parity_for_nine_networks(self):
        for network in mem.NETWORKS:
            with self.subTest(network=network), tempfile.TemporaryDirectory() as folder:
                src = pathlib.Path(folder) / f"SISTEMA_DIARIO_{network.upper()}" / "registro.csv"
                src.parent.mkdir()
                with src.open("w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=["fecha", "cuenta", "tipo", "notas", "resultado"])
                    writer.writeheader()
                    writer.writerows(cycle("a", "2026-09-01", "2026-09-02") +
                                    [row("b", "block", "2026-09-01")])
                with mock.patch.object(rp, "SETTINGS", str(pathlib.Path(folder) / "no_config.json")):
                    self.assertEqual(rp.blocked_accounts(str(src), TODAY), {"b"})
                    self.assertEqual(rp.follow_memory_ranking(str(src), TODAY), {"a": -1.5})

    def test_synthetic_volume_and_conversion_proxy(self):
        """Etiquetas inventadas: prueba del embudo, NO atribución real."""
        cases = []
        for i in range(4):
            cases.append((str(i), [], i < 2))
        for i in range(3):
            cases.append((f"one{i}", cycle(f"one{i}", "2026-09-10", "2026-09-15"), i == 0))
        for i in range(2):
            rows = (cycle(f"two{i}", "2026-08-01", "2026-08-02") +
                    cycle(f"two{i}", "2026-09-10", "2026-09-15"))
            cases.append((f"two{i}", rows, False))
        for i in range(2):
            rows = (cycle(f"three{i}", "2026-07-01", "2026-07-02") +
                    cycle(f"three{i}", "2026-08-01", "2026-08-02") +
                    cycle(f"three{i}", "2026-09-10", "2026-09-15"))
            cases.append((f"three{i}", rows, False))
        cases.append(("permanent", [row("permanent", "block", "2026-09-01")], False))
        old, new = [], []
        for handle, rows, converted in cases:
            events = mem.events_from_rows(rows, "x")
            old_state = mem.decision(events, "x", handle, today=TODAY,
                                     policy=mem.Policy(multiplier=1))
            new_state = mem.decision(events, "x", handle, today=TODAY)
            if old_state["allowed"]:
                old.append(converted)
            if new_state["allowed"]:
                new.append(converted)
        self.assertEqual((len(old), sum(old)), (9, 3))
        self.assertEqual((len(new), sum(new)), (7, 3))

    def test_bulk_projection_processes_each_event_once_per_account(self):
        # Una entrada por cuenta: evita la regresión cuadrática en discovery.
        rows = [row(f"reader{i}", "unfollow", "2026-09-01", notes="no devuelve")
                for i in range(500)]
        processed = []
        original = mem.decision

        def observe(events, network, account, **kwargs):
            processed.extend(events)
            self.assertTrue(all(event.account == account for event in events))
            return original(events, network, account, **kwargs)

        with mock.patch.object(mem, "decision", side_effect=observe):
            states = mem.decisions_from_rows(rows, "bluesky", today=TODAY)
        self.assertEqual(len(states), 500)
        self.assertEqual(len(processed), 500)
        self.assertTrue(all(state["failures"] == 1 for state in states.values()))

    def test_network_override_and_invalid_config_fallback(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            src = pathlib.Path(folder) / "SISTEMA_DIARIO_BLUESKY" / "registro.csv"
            src.parent.mkdir()
            with src.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["fecha", "cuenta", "tipo", "notas", "resultado"])
                writer.writeheader()
                writer.writerows(cycle("a", "2026-09-01", "2026-09-02"))
            config = pathlib.Path(folder) / "config.json"
            today = dt.date(2026, 9, 8)
            with mock.patch.object(rp, "SETTINGS", str(config)):
                config.write_text(json.dumps({"memoria_reciprocidad": {"initial_days": 5}}), encoding="utf-8")
                self.assertEqual(rp.blocked_accounts(str(src), today), set())
                config.write_text(json.dumps({"memoria_reciprocidad": {"initial_days": 5},
                    "redes": {"bluesky": {"memoria_reciprocidad": {"initial_days": 15}}}}),
                    encoding="utf-8")
                self.assertEqual(rp.blocked_accounts(str(src), today), {"a"})
                config.write_text(json.dumps({"memoria_reciprocidad": {"initial_days": "invalido"}}),
                                  encoding="utf-8")
                self.assertEqual(rp.blocked_accounts(str(src), today), {"a"})

    def test_configurable_retention_and_cooldown(self):
        events = mem.events_from_rows(cycle("a", "2026-09-01", "2026-09-02"), "x")
        state = mem.decision(events, "x", "a", today=TODAY, policy=mem.Policy(lookback_days=2))
        self.assertEqual(state["failures"], 0)
        state = mem.decision(events, "x", "a", today=dt.date(2026, 9, 2),
                             policy=mem.Policy(initial_days=0))
        self.assertEqual(state["status"], "eligible")


if __name__ == "__main__":
    unittest.main()
