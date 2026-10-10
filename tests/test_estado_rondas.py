"""Contrato offline de la PR #86: sin red, credenciales, locks reales ni escritura operativa."""
import csv
from datetime import datetime, timedelta
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import estado_rondas as panel


class EstadoRondasTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = datetime(2026, 10, 9, 14, 30, tzinfo=panel.MADRID)
        self.oper = self.root / "00_OPERATIVO"
        self.oper.mkdir()

    def rounds(self, rows):
        path = self.oper / "tiempos_rondas.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["fecha", "red", "inicio", "fin", "minutos", "estado", "confirmadas", "saltadas", "fallos", "codigo"])
            w.writerows(rows)
        return path

    def kpis(self, root, day):
        return {"networks": {n: {"confirmed_rows": 0, "confirmed_by_kind": {},
                                 "followers_net": None, "outbound_coverage": "registro_legacy_sin_ids"}
                             for n in panel.NETWORKS}}

    def build(self, **kwargs):
        return panel.build(self.root, now=self.now, kpi_builder=self.kpis,
                           canaries_collector=lambda root, now: {"alerts": []}, **kwargs)

    def test_nine_networks_absence_not_zero(self):
        report = self.build()
        self.assertEqual(len(report["networks"]), 9)
        for net in panel.NETWORKS:
            self.assertEqual(report["networks"][net]["status"], "sin_datos")
            self.assertIsNone(report["networks"][net]["rounds"])
        self.assertEqual(len(report["networks"]["instagram"]["history"]), 14)

    def test_round_states_error_paused_and_confirmations(self):
        self.rounds([["2026-10-09", "bluesky", "11:00:00", "11:10:00", "10", "ok", "{'like': 2}", 0, 0, 0],
                     ["2026-10-09", "bluesky", "12:00:00", "12:10:00", "10", "error", "{}", 0, 2, 1],
                     ["2026-10-09", "instagram", "13:00:00", "13:10:00", "10", "saltada", "{}", 1, 0, 0]])
        report = self.build()
        self.assertEqual(report["networks"]["bluesky"]["rounds"], 1)
        self.assertEqual(report["networks"]["bluesky"]["status"], "error")
        self.assertEqual(report["networks"]["instagram"]["status"], "aviso")
        self.assertEqual(report["networks"]["bluesky"]["history"][-1]["total"], 2)

    def test_invalid_row_does_not_invent_success(self):
        self.rounds([["2026-10-09", "bluesky", "10:00:00", "10:30:00", "1", "ok", "__import__('os')", 0, 0, 0]])
        report = self.build()
        self.assertTrue(any(a["code"] == "REGISTRO_RONDAS_INVALIDO" for a in report["alerts"]))
        self.assertEqual(report["networks"]["bluesky"]["status"], "sin_datos")

    def test_redacted_alerts_do_not_leak_private_text(self):
        dangerous = 'RUTA_C\\Users\\privado_token@correo.es'
        report = panel.build(self.root, now=self.now, kpi_builder=self.kpis,
                             canaries_collector=lambda root, now: {"alerts": [
                                 {"network": "bluesky", "severity": "alta", "code": "CORTACIRCUITOS_ABIERTO", "reason": dangerous},
                                 {"network": "x", "code": dangerous, "reason": dangerous}]})
        html = panel.render_html(report)
        self.assertNotIn(dangerous, html)
        self.assertIn("CORTACIRCUITOS_ABIERTO", html)
        self.assertNotIn("<script", html)
        self.assertIn("Content-Security-Policy", html)

    def test_canaries_receive_naive_local_time_as_their_contract_requires(self):
        seen = []
        def collector(root, now):
            seen.append(now)
            # round_canaries._read_recent resta datetimes naive construidos del CSV.
            self.assertIsNone(now.tzinfo)
            self.assertEqual(now.hour, 14)
            return {"alerts": []}
        panel.build(self.root, now=self.now, kpi_builder=self.kpis,
                    canaries_collector=collector)
        self.assertEqual(len(seen), 1)

    def test_html_generation_changes_no_input(self):
        path = self.rounds([["2026-10-09", "x", "12:00:00", "12:05:00", "5", "ok", "1", 0, 0, 0]])
        before = path.read_bytes()
        target = self.oper / "ESTADO_RONDAS.html"
        panel.write_html(target, panel.render_html(self.build()))
        self.assertEqual(path.read_bytes(), before)
        self.assertTrue(target.read_text(encoding="utf-8").startswith("<!doctype html>"))
        self.assertEqual(set(p.name for p in self.oper.iterdir()), {"tiempos_rondas.csv", "ESTADO_RONDAS.html"})

    def test_relative_hist_and_comparison_ignores_days_without_rows(self):
        self.rounds([["2026-10-02", "x", "10:00:00", "10:01:00", "1", "ok", "{'like': 4}", 0, 0, 0],
                     ["2026-10-07", "x", "11:00:00", "11:01:00", "1", "ok", "{'like': 6}", 0, 0, 0]])
        report = self.build()
        self.assertEqual(report["networks"]["x"]["mean7_round_confirmed"], 5)
        self.assertEqual(report["networks"]["x"]["history"][0]["total"], None)

    def test_timing_fixture_below_five_seconds(self):
        rows = []
        for n in panel.NETWORKS:
            for i in range(100):
                rows.append(["2026-10-09", n, "10:00:00", "10:01:00", "1", "ok", "{'like': 1}", 0, 0, 0])
        self.rounds(rows)
        start = time.perf_counter()
        html = panel.render_html(self.build())
        self.assertLess(time.perf_counter() - start, 5)
        self.assertEqual(html.count('<tr><th>'), 10)

    def test_kpi_kinds_not_remote_ack_and_unknowns(self):
        def partial(root, day):
            report = self.kpis(root, day)
            report["networks"]["x"] = {"confirmed_rows": 3,
                "confirmed_by_kind": {"like": 1, "follow": 1, "reply": 1},
                "followers_net": 4, "outbound_coverage": "registro_legacy_sin_ids"}
            return report
        report = panel.build(self.root, now=self.now, kpi_builder=partial,
            canaries_collector=lambda root, now: {"alerts": []})
        self.assertEqual(report["networks"]["x"]["kinds"], {"follows": 1, "likes": 1, "textos": 1})
        self.assertIn("NO ACK remoto", panel.render_text(report))



    def test_recovered_round_is_not_stuck_red(self):
        self.rounds([
            ["2026-10-09", "x", "10:00:00", "10:05:00", "5", "error", "{}", 0, 2, 1],
            ["2026-10-09", "x", "11:00:00", "11:05:00", "5", "ok", "{'like': 2}", 0, 0, 0],
        ])
        report = self.build()
        self.assertEqual(report["networks"]["x"]["status"], "aviso")
        self.assertEqual(report["networks"]["x"]["history"][-1]["status"], "aviso")
        self.assertEqual(report["networks"]["x"]["errors"], 2)
        self.assertEqual(report["networks"]["x"]["round_errors"], 1)

    def test_skipped_round_is_not_platform_pause(self):
        self.rounds([["2026-10-09", "instagram", "13:00:00", "13:10:00", 10,
                      "saltada", "{}", 1, 0, 0]])
        report = self.build()
        self.assertEqual(report["networks"]["instagram"]["status"], "aviso")
        self.assertEqual(report["networks"]["instagram"]["history"][-1]["status"], "aviso")

    def test_absent_csv_never_claims_zero_failures_or_skips(self):
        row = self.build()["networks"]["x"]
        self.assertIsNone(row["errors"])
        self.assertIsNone(row["skipped"])
        self.assertIsNone(row["busy"])
        self.assertIsNone(row["history"][-1]["total"])

    def test_extra_csv_fields_cannot_be_accepted_as_valid(self):
        self.rounds([["2026-10-09", "x", "10:00:00", "10:05:00", "5", "ok", "1", 0, 0, 0, "malformed"]])
        report = self.build()
        self.assertTrue(any(a["code"] == "REGISTRO_RONDAS_INVALIDO" for a in report["alerts"]))
        self.assertIsNone(report["networks"]["x"]["rounds"])

    def test_alert_codes_are_explicitly_allowlisted(self):
        report = panel.build(self.root, now=self.now, kpi_builder=self.kpis,
            canaries_collector=lambda root, now: {"alerts": [
              {"network":"x", "severity":"alta", "code":"PRIVATE_PHONE_1234567"},
              {"network":"x", "severity":"alta", "code":"BREAKER_REVISION_MANUAL"},
              {"network":"x", "severity":"media", "code":"FALLO_PLAN_REPETIDO"}]})
        html = panel.render_html(report)
        self.assertNotIn("PRIVATE_PHONE_1234567", html)
        self.assertIn("CANARIO_NO_RECONOCIDO", html)
        self.assertIn('class="alert-alta"', html)
        self.assertEqual(report["networks"]["x"]["status"], "pausada")
        self.assertIn(".pausada,.error{background:#fee2e2}", html)

    def test_alert_list_is_bounded(self):
        report = panel.build(self.root, now=self.now, kpi_builder=self.kpis,
            canaries_collector=lambda root, now: {"alerts": [
                 {"network":"x", "severity":"alta", "code":"SIN_CONFIRMACIONES"}] * 1000})
        self.assertLessEqual(len(report["alerts"]), 41)

    def test_csv_with_bad_row_must_mark_metrics_nd(self):
        self.rounds([["2026-10-09", "x", "12:00:00", "12:05:00", 5, "ok", "3", 0, 0, 0],
                     ["2026-10-09", "x", "13:00:00", "13:05:00", 5, "ok", "not-an-action-count", 0, 0, 0]])
        row = self.build()["networks"]["x"]
        self.assertIsNone(row["rounds"])
        self.assertIsNone(row["errors"])
        self.assertIsNone(row["last"])
        self.assertEqual(row["history"][-1]["status"], "sin_datos")

    def test_out_of_order_and_future_rounds_are_ignored(self):
        self.rounds([["2026-10-09", "x", "15:00:00", "15:05:00", 5, "ok", "99", 0, 0, 0],
                     ["2026-10-09", "x", "14:00:00", "14:05:00", 5, "ok", "2", 0, 0, 0]])
        row = self.build()["networks"]["x"]
        self.assertEqual(row["history"][-1]["total"], 2)
        self.assertEqual(row["rounds"], 1)


    def test_seven_day_trend_uses_same_daily_cutoff(self):
        self.rounds([[
            "2026-10-08", "x", "09:00:00", "09:01:00", 1, "ok", "10", 0, 0, 0],
            ["2026-10-08", "x", "21:00:00", "21:01:00", 1, "ok", "100", 0, 0, 0],
            ["2026-10-09", "x", "10:00:00", "10:01:00", 1, "ok", "10", 0, 0, 0]])
        report = self.build()["networks"]["x"]
        self.assertEqual(report["mean7_round_confirmed"], 10)
        self.assertEqual(report["trend_rounds"], 0)


    def test_cli_text_does_not_create_html_or_mutate_input(self):
        import io
        from contextlib import redirect_stdout
        before = self.rounds([["2026-10-09", "x", "10:00:00", "10:05:00", 5,
                               "ok", "3", 0, 0, 0]]).read_bytes()
        target = self.oper / "ESTADO_RONDAS.html"
        output = io.StringIO()
        with mock.patch.object(panel.kpi_report, "build_report", side_effect=self.kpis), \
             mock.patch("round_canaries.collect", return_value={"alerts": []}), \
             redirect_stdout(output):
            rc = panel.main(["texto", "--root", str(self.root), "--red", "x"])
        self.assertEqual(rc, 0)
        self.assertIn("x", output.getvalue())
        self.assertNotIn("bluesky", output.getvalue())
        self.assertFalse(target.exists())
        self.assertEqual((self.oper / "tiempos_rondas.csv").read_bytes(), before)

    def test_failed_atomic_html_replace_preserves_previous_output(self):
        dest = self.oper / "ESTADO_RONDAS.html"
        dest.write_text("old", encoding="utf-8")
        with mock.patch.object(panel.os, "replace", side_effect=OSError("locked")):
            with self.assertRaises(OSError):
                panel.write_html(dest, "new")
        self.assertEqual(dest.read_text(encoding="utf-8"), "old")
        self.assertEqual([p.name for p in self.oper.iterdir()], [dest.name])


    def test_partial_round_failures_are_counted_without_mixing_units(self):
        self.rounds([["2026-10-09", "x", "10:00:00", "10:05:00", 5, "parcial",
                      "{'like': 2}", 5, 3, 1],
                     ["2026-10-09", "x", "11:00:00", "11:05:00", 5, "saltada",
                      "{}", 12, 0, 0],
                     ["2026-10-09", "x", "12:00:00", "12:05:00", 5, "ocupada",
                      "{}", 0, 0, 0]])
        item = self.build()["networks"]["x"]
        self.assertEqual(item["errors"], 3)
        self.assertEqual(item["round_errors"], 0)
        self.assertEqual((item["skipped"], item["busy"]), (1, 1))


    def test_tiktok_follow_only_cooldown_does_not_mark_all_writes_blocked(self):
        import tiktok_safety as safe
        def guard(path, *, now, kind):
            self.assertIn(str(self.root), str(path))
            if kind == "follow":
                raise safe.SafetyBlocked("only follow")
        with mock.patch.object(safe, "require_writable", side_effect=guard):
            row = self.build()["networks"]["tiktok"]
        self.assertEqual(row["status"], "aviso")
        self.assertIn("TIKTOK_SEGUIR_EN_DESCANSO", row["alerts"])

    def test_tiktok_total_manual_hold_marks_paused(self):
        import tiktok_safety as safe
        with mock.patch.object(safe, "require_writable", side_effect=safe.SafetyBlocked):
            row = self.build()["networks"]["tiktok"]
        self.assertEqual(row["status"], "pausada")
        self.assertIn("TIKTOK_ESCRITURA_BLOQUEADA", row["alerts"])

    def test_tiktok_corrupt_guard_is_high_severity_not_clean_status(self):
        import tiktok_safety as safe
        with mock.patch.object(safe, "require_writable", side_effect=safe.SafetyStateError):
            row = self.build()["networks"]["tiktok"]
        self.assertEqual(row["status"], "error")
        self.assertIn("TIKTOK_ESTADO_SEGURIDAD_INVALIDO", row["alerts"])

if __name__ == "__main__":
    unittest.main()
