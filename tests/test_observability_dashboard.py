"""Contratos offline del dashboard: fixtures exclusivamente sinteticos."""
import csv
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import observability_dashboard as dash

NOW = dt.datetime(2026, 10, 10, 12, 30)


def csv_file(path, headers, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(records)


def fixture(root):
    csv_file(root / "00_OPERATIVO" / "tiempos_rondas.csv",
             ["fecha", "red", "inicio", "fin", "minutos", "estado",
              "confirmadas", "saltadas", "fallos", "codigo"], [
                 {"fecha": "2026-10-10", "red": "x", "minutos": "3.5", "estado": "parcial",
                  "confirmadas": "{'follow': 4}", "fallos": "1"},
                 {"fecha": "2026-10-10", "red": "x", "minutos": "1.5", "estado": "ocupada",
                  "confirmadas": "{}", "fallos": "0"},
                 {"fecha": "2026-10-09", "red": "bluesky", "minutos": "0.1", "estado": "ok",
                  "confirmadas": "{'like': 3}", "fallos": "0"},
                 {"fecha": "2026-09-01", "red": "x", "minutos": "100", "estado": "error"},
                 {"fecha": "2026-10-09", "red": "secretnet", "minutos": "3", "estado": "ok"},
             ])
    csv_file(root / "SISTEMA_DIARIO_X" / "registro_interacciones.csv",
             ["fecha", "cuenta", "tipo", "resultado", "texto_usado"], [
                 {"fecha": "2026-10-10", "cuenta": "@privatehandle", "tipo": "reply",
                  "resultado": "confirmado", "texto_usado": "token SECRET_EXAMPLE"},
                 {"fecha": "2026-10-10", "cuenta": "@privatehandle", "tipo": "follow",
                  "resultado": "incierto:revisar"},
                 {"fecha": "2026-10-10", "cuenta": "@another", "tipo": "like",
                  "resultado": "saltado_perfil"},
                 {"fecha": "2026-10-09", "cuenta": "@another", "tipo": "follow",
                  "resultado": "fallo_api"},
                 {"fecha": "2026-09-30", "cuenta": "@another", "tipo": "reply",
                  "resultado": "confirmado"},
             ])
    cache = root / "SISTEMA_DIARIO_X" / "cache"
    cache.mkdir(parents=True)
    (cache / "breaker.json").write_text(
        json.dumps({"fails": 3, "reason": "token literal privado", "open_until": "2026-10-10T15:00:00"}),
        encoding="utf-8",
    )
    (cache / "mech_2026-10-10_1012.log").write_text(
        "[TIEMPO_ETAPA] phase=scan script=foo.py inicio=2026-10-10T10:00:00 "
        "fin=2026-10-10T10:00:05 segundos=5.0 exit=0\n"
        "handle privado SECRET_EXAMPLE\n"
        "[TIEMPO_ETAPA] phase=scan script=foo.py inicio=2026-10-10T10:00:06 "
        "fin=2026-10-10T10:00:16 segundos=10.0 exit=1\n", encoding="utf-8"
    )
    folder = root / "00_OPERATIVO" / "_cola_respuestas"
    folder.mkdir(parents=True)
    (folder / "pending.json").write_text(json.dumps({
        "opaque1": {"network": "x", "text": "PRIVATE_FULL_POST", "ts": "2026-10-10T12:20:00"},
        "opaque2": {"network": "tiktok", "text": "SECRET_EXAMPLE", "ts": "2026-10-10T12:20:00"},
    }), encoding="utf-8")


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name) / "source"
        self.root.mkdir()
        fixture(self.root)

    def test_nine_networks_and_independent_queue_summary(self):
        report = dash.collect(self.root, as_of=NOW)
        self.assertEqual(len(report["networks"]), 9)
        self.assertEqual(report["queues"]["WEB"]["rounds_observed"], 2)
        self.assertEqual(report["queues"]["API"]["rounds_observed"], 1)
        self.assertIsNone(report["queues"]["MOBILE"]["rounds_observed"])
        self.assertEqual(report["queues"]["WEB"]["confirmed_records_observed"], 1)
        self.assertEqual(report["queues"]["WEB"]["open_breakers"], 1)
        self.assertEqual(report["networks"]["reddit"]["queue"], "WEB")
        self.assertEqual(report["networks"]["tiktok"]["queue"], "MOBILE")
        self.assertEqual(report["queues"]["WEB"]["networks_with_alerts"], 1)

    def test_outcomes_not_conflated_and_no_double_count_from_rounds(self):
        report = dash.collect(self.root, as_of=NOW)
        x = report["networks"]["x"]
        self.assertEqual(x["actions"]["confirmed_records"], 1)
        self.assertEqual(x["actions"]["pending_verification"], 1)
        self.assertEqual(x["actions"]["failed_records"], 1)
        self.assertEqual(x["actions"]["skipped_records"], 1)
        self.assertEqual(x["rounds"]["total"], 2)
        self.assertEqual(x["rounds"]["states"]["parcial"], 1)
        self.assertEqual(x["rounds"]["states"]["ocupada"], 1)
        self.assertEqual(x["rounds"]["mean_minutes"], 2.5)
        self.assertEqual(x["pending_replies"], 1)
        self.assertEqual(x["alerts"], ["breaker_abierto", "rondas_parciales", "acciones_sin_verificar"])
        self.assertEqual(report["networks"]["tiktok"]["pending_replies"], 1)

    def test_phase_timings_bounded_and_sensitive_log_text_not_exported(self):
        report = dash.collect(self.root, as_of=NOW)
        phases = report["networks"]["x"]["phases"]
        self.assertEqual(phases["scan"], {"samples": 2, "mean_seconds": 7.5, "p95_seconds": 10.0})
        serialized = json.dumps(report, ensure_ascii=False) + dash.render_html(report)
        for secret in ("PRIVATE_FULL_POST", "SECRET_EXAMPLE", "privatehandle",
                       "token literal privado", "foo.py", "secretnet"):
            self.assertNotIn(secret, serialized)
        self.assertNotIn("<script", serialized)
        self.assertIn("Confirmadas", serialized)

    def test_no_data_is_not_zero_and_present_empty_file_is_zero(self):
        report = dash.collect(self.root, as_of=NOW)
        self.assertIsNone(report["networks"]["instagram"]["actions"])
        self.assertIsNone(report["networks"]["instagram"]["rounds"])
        self.assertEqual(report["networks"]["instagram"]["pending_replies"], 0)
        self.assertEqual(report["networks"]["instagram"]["alerts"], [])
        csv_file(self.root / "SISTEMA_DIARIO_INSTAGRAM" / "registro_interacciones.csv",
                 ["fecha", "cuenta", "tipo", "resultado"], [])
        report = dash.collect(self.root, as_of=NOW)
        self.assertEqual(report["networks"]["instagram"]["actions"]["confirmed_records"], 0)
        self.assertEqual(report["networks"]["instagram"]["actions"]["by_day"]["2026-10-10"], 0)

    def test_historical_network_without_recent_rounds_is_observed_zero(self):
        rounds = self.root / "00_OPERATIVO" / "tiempos_rondas.csv"
        with rounds.open("a", encoding="utf-8") as f:
            f.write("2026-09-01,tiktok,10:00,10:01,1,ok,{},0,0,0\n")
        report = dash.collect(self.root, as_of=NOW)
        self.assertEqual(report["networks"]["tiktok"]["rounds"]["total"], 0)
        self.assertEqual(report["queues"]["MOBILE"]["rounds_observed"], 0)

    def test_invalid_breaker_and_corrupted_reply_queue_are_unknown(self):
        breaker = self.root / "SISTEMA_DIARIO_X" / "cache" / "breaker.json"
        breaker.write_text('{"fails": -1, "reason": "leak"}', encoding="utf-8")
        pending = self.root / "00_OPERATIVO" / "_cola_respuestas" / "pending.json"
        pending.write_text('{"secret":', encoding="utf-8")
        report = dash.collect(self.root, as_of=NOW)
        self.assertEqual(report["networks"]["x"]["breaker"]["status"], "invalido")
        self.assertIsNone(report["networks"]["x"]["pending_replies"])
        self.assertIn("cola_respuestas", report["networks"]["x"]["missing_sources"])
        self.assertFalse(report["coverage"]["reply_queue"])

    def test_expired_pending_is_not_counted_and_source_remains_unchanged(self):
        pending = self.root / "00_OPERATIVO" / "_cola_respuestas" / "pending.json"
        data = json.loads(pending.read_text(encoding="utf-8"))
        data["old"] = {"network": "x", "text": "PRIVATE_OLD", "ts": "2026-10-01T10:00:00"}
        pending.write_text(json.dumps(data), encoding="utf-8")
        before = pending.read_bytes()
        report = dash.collect(self.root, as_of=NOW)
        self.assertEqual(report["networks"]["x"]["pending_replies"], 1)
        self.assertEqual(pending.read_bytes(), before)

    def test_breaker_expiry_is_not_open(self):
        breaker = self.root / "SISTEMA_DIARIO_X" / "cache" / "breaker.json"
        breaker.write_text(json.dumps({"fails": 1, "open_until": "2026-10-09T12:00:00"}), encoding="utf-8")
        report = dash.collect(self.root, as_of=NOW)
        self.assertEqual(report["networks"]["x"]["breaker"]["status"], "cerrado")

    def test_official_breaker_timezone_offsets_and_manual_hold(self):
        path = self.root / "SISTEMA_DIARIO_X" / "cache" / "breaker.json"
        def set_breaker(value):
            path.write_text(json.dumps(value), encoding="utf-8")
            return dash.collect(self.root, as_of=NOW)
        # circuit_breaker._record_unlocked guarda timestamps Madrid con offset.
        report = set_breaker({"fails": 1, "open_until": "2026-10-10T15:00:00+02:00"})
        self.assertEqual(report["networks"]["x"]["breaker"]["status"], "abierto")
        self.assertEqual(report["queues"]["WEB"]["open_breakers"], 1)
        report = set_breaker({"fails": 1, "open_until": "2026-10-10T12:29:00+02:00"})
        self.assertEqual(report["networks"]["x"]["breaker"]["status"], "cerrado")
        # Una retencion manual no expira cuando open_until es null o pasado.
        report = set_breaker({"fails": 1, "open_until": None, "manual_hold": True,
                              "manual_hold_reason": "edge_ack_uncertain"})
        self.assertEqual(report["networks"]["x"]["breaker"]["status"], "revision_manual")
        self.assertIn("retencion_manual", report["networks"]["x"]["alerts"])
        self.assertEqual(report["queues"]["WEB"]["open_breakers"], 1)
        report = set_breaker({"fails": 1, "open_until": "bad timestamp"})
        self.assertEqual(report["networks"]["x"]["breaker"]["status"], "invalido")
        report = set_breaker({"fails": 1})
        self.assertEqual(report["networks"]["x"]["breaker"]["status"], "invalido")
        path.write_text("{broken", encoding="utf-8")
        self.assertEqual(dash.collect(self.root, as_of=NOW)["networks"]["x"]["breaker"]["status"], "invalido")

    def test_bad_csv_numeric_values_ignored_and_no_crash(self):
        rounds = self.root / "00_OPERATIVO" / "tiempos_rondas.csv"
        csv_file(rounds, ["fecha", "red", "minutos", "estado"],
                 [{"fecha": "2026-10-10", "red": "x", "minutos": "-1", "estado": "error"},
                  {"fecha": "2026-10-10", "red": "x", "minutos": "nan", "estado": "ok"},
                  {"fecha": "bad", "red": "x", "minutos": "2", "estado": "ok"},
                  {"fecha": "2026-10-10", "red": "x", "minutos": "inf", "estado": "ok"}])
        report = dash.collect(self.root, as_of=NOW)
        self.assertEqual(report["networks"]["x"]["rounds"]["total"], 3)
        self.assertIsNone(report["networks"]["x"]["rounds"]["mean_minutes"])

    def test_headerless_or_wrong_schema_is_unknown_not_zero(self):
        registry = self.root / "SISTEMA_DIARIO_X" / "registro_interacciones.csv"
        csv_file(registry, ["foo"], [{"foo": "PRIVATE"}])
        round_path = self.root / "00_OPERATIVO" / "tiempos_rondas.csv"
        csv_file(round_path, ["foo"], [{"foo": "PRIVATE"}])
        report = dash.collect(self.root, as_of=NOW)
        self.assertIsNone(report["networks"]["x"]["actions"])
        self.assertIsNone(report["networks"]["x"]["rounds"])
        self.assertFalse(report["coverage"]["round_csv"])

    def test_cli_writes_only_sanitized_artifacts(self):
        output = pathlib.Path(self.tmp.name) / "export"
        result = dash.main(["--root", str(self.root), "--output", str(output),
                            "--as-of", "2026-10-10T12:30", "--days", "2"])
        self.assertEqual(result, 0)
        data = json.loads((output / "dashboard.json").read_text(encoding="utf-8"))
        page = (output / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(data["days"], 2)
        self.assertEqual(data["schema_version"], 1)
        self.assertIn("<!doctype html>", page)
        self.assertEqual(sorted(p.name for p in output.iterdir()), ["dashboard.html", "dashboard.json"])

    def test_rejects_invalid_window_and_preserves_output(self):
        with self.assertRaises(ValueError):
            dash.collect(self.root, as_of=NOW, days=0)
        with self.assertRaises(ValueError):
            dash.collect(self.root, as_of=NOW, days=32)


if __name__ == "__main__":
    unittest.main()
