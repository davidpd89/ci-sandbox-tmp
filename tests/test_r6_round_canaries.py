"""R6: canarios solo de lectura, reproducen señales de fallos reales del 08/10.

Todos los registros, locks y JSON se fabrican en tempfile. No invocar cuentas,
programador de Windows, escritorio, Edge ni tokens.
"""
import csv
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import round_canaries as canaries


NOW = dt.datetime(2026, 10, 8, 16, 30, 0)
HEADER = ["fecha", "red", "inicio", "fin", "minutos", "estado",
          "confirmadas", "saltadas", "fallos", "codigo"]


class CanaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.oper = self.root / "00_OPERATIVO"
        self.oper.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def rounds(self, *rows):
        with (self.oper / "tiempos_rondas.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(HEADER)
            for hour, network, status, confirmed, failed in rows:
                writer.writerow(["2026-10-08", network, hour, hour, 1, status,
                                 confirmed, 0, failed, 0])

    def pending(self, *, ts="2026-10-08T15:30:00", worker_pid=None):
        queue = self.oper / "_cola_respuestas"
        queue.mkdir(exist_ok=True)
        (queue / "pending.json").write_text(json.dumps({"abc": {"ts": ts, "text": "información ficticia"}}), encoding="utf-8")
        if worker_pid is not None:
            (queue / "worker.lock").write_text(str(worker_pid), encoding="utf-8")

    def breaker(self, network, *, until="2026-10-08T19:00:00", reason="rate"):
        target = self.root / f"SISTEMA_DIARIO_{network.upper()}" / "cache"
        target.mkdir(parents=True, exist_ok=True)
        (target / "breaker.json").write_text(json.dumps({
            "fails": 3, "open_until": until, "reason": reason
        }), encoding="utf-8")

    def codes(self, **kwargs):
        result = canaries.collect(self.root, now=NOW,
                                  pid_alive=kwargs.pop("pid_alive", lambda _: False))
        return {(x.get("network"), x["code"]) for x in result["alerts"]}, result

    def test_three_failed_mastodon_rounds_alert_without_leaking_text(self):
        self.rounds(
            ("15:00:00", "mastodon", "error", "{'favourite': 0}", 4),
            ("15:30:00", "mastodon", "error", "{'favourite': 0}", 1),
            ("16:00:00", "mastodon", "error", "{'favourite': 0}", 2),
        )
        codes, result = self.codes()
        self.assertIn(("mastodon", "ERRORES_SEGUIDOS"), codes)
        self.assertIn(("mastodon", "SIN_CONFIRMACIONES"), codes)
        self.assertNotIn("información ficticia", json.dumps(result, ensure_ascii=False))

    def test_partial_round_is_visible_but_not_conflated_with_error(self):
        self.rounds(("16:12:00", "bluesky", "parcial", "{'like': 39}", 2))
        codes, _ = self.codes()
        self.assertIn(("bluesky", "RONDA_PARCIAL"), codes)
        self.assertNotIn(("bluesky", "ERRORES_SEGUIDOS"), codes)

    def test_worker_dead_with_old_pending_is_alerted(self):
        self.pending(worker_pid=800000)
        codes, _ = self.codes(pid_alive=lambda _: False)
        self.assertIn((None, "TRABAJADOR_PARADO"), codes)

    def test_worker_alive_is_not_alerted(self):
        self.pending(worker_pid=123)
        codes, _ = self.codes(pid_alive=lambda pid: pid == 123)
        self.assertNotIn((None, "TRABAJADOR_PARADO"), codes)

    def test_open_platform_breaker_is_reported_without_reset(self):
        self.breaker("mastodon")
        codes, _ = self.codes()
        self.assertIn(("mastodon", "CORTACIRCUITOS_ABIERTO"), codes)
        self.assertTrue((self.root / "SISTEMA_DIARIO_MASTODON" / "cache" / "breaker.json").exists())

    def test_past_breaker_does_not_emit_active_alarm(self):
        self.breaker("mastodon", until="2026-10-08T13:00:00")
        codes, _ = self.codes()
        self.assertNotIn(("mastodon", "CORTACIRCUITOS_ABIERTO"), codes)

    def test_all_skipped_not_misclassified_as_unproductive_failure(self):
        self.rounds(
            ("15:00:00", "mastodon", "saltada", "{'like': 0}", 0),
            ("16:00:00", "mastodon", "saltada", "{'like': 0}", 0),
        )
        codes, _ = self.codes()
        self.assertNotIn(("mastodon", "SIN_CONFIRMACIONES"), codes)
        self.assertNotIn(("mastodon", "ERRORES_SEGUIDOS"), codes)

    def test_no_stale_worker_alarm_outside_service_hours(self):
        self.pending(worker_pid=800000)
        result = canaries.collect(self.root, now=NOW.replace(hour=23),
                                  pid_alive=lambda _: False)
        self.assertNotIn("TRABAJADOR_PARADO", [a["code"] for a in result["alerts"]])

    def test_corrupt_csv_does_not_disappear_as_healthy(self):
        (self.oper / "tiempos_rondas.csv").write_text("wrong,header\n1,2\n", encoding="utf-8")
        codes, _ = self.codes()
        self.assertIn((None, "REGISTRO_INVALIDO"), codes)

    def test_json_export_is_atomic_and_contains_no_posts(self):
        self.pending()
        target = self.oper / "cache" / "alertas_rondas.json"
        report = canaries.collect(self.root, now=NOW, pid_alive=lambda _: False)
        canaries.save_report(target, report)
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), report)
        self.assertFalse(any(p.name.endswith(".tmp") for p in target.parent.iterdir()))


class RealRegisterRowsTests(unittest.TestCase):
    def test_empty_confirmed_column_from_skipped_busy_and_error_rounds_is_valid(self):
        """08/10: tiempos_rondas.csv real trae `confirmadas` vacio en rondas sin resumen; antes el canario lo marcaba como REGISTRO_INVALIDO."""
        import round_canaries as rc
        for text in ("", "{}", "  "):
            self.assertEqual(rc._confirmed(text), 0, repr(text))
        self.assertEqual(rc._confirmed("{'like': 3, 'follow': 2}"), 5)
        self.assertIsNone(rc._confirmed("no es un diccionario"))


if __name__ == "__main__":
    unittest.main()
