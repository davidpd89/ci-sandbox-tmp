"""Fixtures 100 % sintéticos; no se importan ejecutores ni credenciales."""
import csv
from datetime import date
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import kpi_report as k


class KPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.day = date(2026, 10, 9)

    def write(self, net, file, rows, *, bom=False):
        path = self.root / f"SISTEMA_DIARIO_{net.upper()}" / file
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
            csv.writer(f).writerows(rows)
        return path

    def sample(self, status="confirmado", kind="like", notes=""):
        return ["2026-10-09", "@lector", kind, "https://ejemplo.es/1", "", status, notes]

    def test_eight_networks_absent_is_not_zero(self):
        result = k.build_report(self.root, self.day)
        self.assertEqual(tuple(result["networks"]), k.NETWORKS)
        self.assertTrue(all(r["confirmed_rows"] is None for r in result["networks"].values()))
        self.assertTrue(all(r["followers_net"] is None for r in result["networks"].values()))

    def test_headerless_legacy_confirmed_does_not_infer_queued(self):
        self.write("bluesky", "registro_interacciones.csv", [self.sample(), self.sample("publicado", "reply")])
        r = k.build_report(self.root, self.day)["networks"]["bluesky"]
        self.assertEqual(r["confirmed_rows"], 2)
        self.assertEqual(r["confirmed_by_kind"], {"like": 1, "reply": 1})
        self.assertIsNone(r["denominators"]["attempted"])
        self.assertIsNone(r["denominators"]["queued"])
        self.assertEqual(r["confirmed_by_source"], {"sin_atribucion": 2})

    def test_pending_is_not_confirmation_and_omissions_are_not_attempts(self):
        self.write("threads", "registro_interacciones.csv", [self.sample("pendiente_verificacion"), self.sample("saltado_ya_like"), self.sample("fallo:timeout"), self.sample("enviado")])
        r = k.build_report(self.root, self.day)["networks"]["threads"]
        self.assertEqual((r["confirmed_rows"], r["pending_unknown_rows"], r["omitted_logged_rows"], r["failed_logged_rows"], r["unclassified_rows"]), (0, 1, 1, 1, 1))

    def test_identical_retry_rows_not_counted_twice(self):
        row = self.sample()
        self.write("x", "registro_interacciones.csv", [row, row, row])
        r = k.build_report(self.root, self.day)["networks"]["x"]
        self.assertEqual(r["confirmed_rows"], 1)
        self.assertEqual(r["duplicate_identical_rows"], 2)

    def test_different_targets_are_distinct(self):
        row = self.sample()
        another = self.sample()
        another[3] = "https://ejemplo.es/2"
        self.write("facebook", "registro_interacciones.csv", [row, another])
        self.assertEqual(k.build_report(self.root, self.day)["networks"]["facebook"]["confirmed_rows"], 2)

    def test_headerless_reddit_type_is_fourth_column(self):
        self.write("reddit", "registro_interacciones.csv", [["2026-10-09", "r/libros", "https://reddit.com/r/libros/x", "comentario", "Hola", "confirmado", ""]])
        r = k.build_report(self.root, self.day)["networks"]["reddit"]
        self.assertEqual(r["confirmed_by_kind"], {"comentario": 1})

    def test_named_headers_and_bom_source_attribution(self):
        self.write("mastodon", "registro_interacciones.csv", [["fecha", "cuenta", "tipo", "post_resumen", "texto", "resultado", "notas", "fuente"], self.sample(notes="") + ["seed_ñ"]], bom=True)
        r = k.build_report(self.root, self.day)["networks"]["mastodon"]
        self.assertEqual(r["confirmed_by_source"], {"seed_ñ": 1})

    def test_extra_legacy_columns_are_malformed_not_confirmed(self):
        self.write("x", "registro_interacciones.csv", [self.sample() + ["unexpected"]])
        r = k.build_report(self.root, self.day)["networks"]["x"]
        self.assertIsNone(r["confirmed_rows"])
        self.assertEqual(r["malformed_rows"], 1)
        self.assertEqual(r["outbound_coverage"], "registro_parcial_filas_invalidas")

    def test_bad_row_keeps_only_observed_positive_lower_bound(self):
        self.write("x", "registro_interacciones.csv", [
            self.sample(), ["2026-10-09", "cuenta"], self.sample("fallo:timeout", "reply")
        ])
        r = k.build_report(self.root, self.day)["networks"]["x"]
        self.assertEqual(r["confirmed_rows"], 1)
        self.assertEqual(r["failed_logged_rows"], 1)
        self.assertIsNone(r["pending_unknown_rows"])
        self.assertEqual(r["outbound_coverage"], "registro_parcial_filas_invalidas")

    def test_invalid_named_header_is_unknown_not_zero(self):
        header = ["fecha", "cuenta", "tipo", "post_resumen", "texto", "notas", "fuente"]
        self.write("x", "registro_interacciones.csv", [header, self.sample() + ["seed"]])
        r = k.build_report(self.root, self.day)["networks"]["x"]
        self.assertIsNone(r["confirmed_rows"])
        self.assertEqual(r["outbound_coverage"], "cabecera_invalida")

    def test_duplicate_named_header_is_rejected(self):
        header = ["fecha", "cuenta", "tipo", "post_resumen", "texto",
                  "resultado", "resultado", "notas"]
        row = self.sample() + ["extra"]
        self.write("x", "registro_interacciones.csv", [header, row])
        r = k.build_report(self.root, self.day)["networks"]["x"]
        self.assertIsNone(r["confirmed_rows"])
        self.assertEqual(r["outbound_coverage"], "cabecera_invalida")

    def test_current_official_named_aliases_are_accepted(self):
        header = ["fecha", "cuenta", "tipo", "post_resumen",
                  "texto_usado", "resultado", "notas"]
        self.write("x", "registro_interacciones.csv", [header, self.sample()])
        reddit_header = ["fecha", "subreddit", "hilo_url", "tipo",
                         "texto_usado", "resultado", "notas"]
        reddit_row = ["2026-10-09", "r/libros", "https://reddit.com/r/libros/x",
                      "comentario", "Hola", "confirmado", ""]
        self.write("reddit", "registro_interacciones.csv",
                   [reddit_header, reddit_row])
        networks = k.build_report(self.root, self.day)["networks"]
        self.assertEqual(networks["x"]["confirmed_rows"], 1)
        self.assertEqual(networks["reddit"]["confirmed_rows"], 1)

    def test_lineage_only_explicit_never_guess(self):
        self.write("pinterest", "registro_interacciones.csv", [self.sample(notes="buena fuente:seed-a"), [*self.sample(notes="motivo | fuente=semilla_1")]])
        r = k.build_report(self.root, self.day)["networks"]["pinterest"]
        self.assertEqual(r["confirmed_by_source"], {"semilla_1": 1, "sin_atribucion": 1})

    def test_bad_row_and_out_of_window(self):
        self.write("x", "registro_interacciones.csv", [["basura"], ["2026-10-08", "a", "like", "x", "", "confirmado", ""], self.sample()])
        r = k.build_report(self.root, self.day)["networks"]["x"]
        self.assertEqual(r["malformed_rows"], 1)
        self.assertEqual(r["confirmed_rows"], 1)

    def test_csv_decode_error_is_missing_not_zero(self):
        p = self.write("x", "registro_interacciones.csv", [self.sample()])
        p.write_bytes(b"\xff\xfe")
        r = k.build_report(self.root, self.day)["networks"]["x"]
        self.assertIsNone(r["confirmed_rows"])
        self.assertEqual(r["outbound_coverage"], "UnicodeDecodeError")

    def test_permission_error_is_not_zero(self):
        from unittest import mock
        with mock.patch.object(k, "_rows", side_effect=lambda path: ([], "PermissionError")):
            r = k.build_report(self.root, self.day)["networks"]["bluesky"]
        self.assertEqual(r["outbound_coverage"], "PermissionError")
        self.assertIsNone(r["incoming_comment_account_days"])

    def test_timezone_crosses_midnight(self):
        self.write("x", "registro_interacciones.csv", [["2026-10-08T23:30:00Z", "a", "like", "x", "", "confirmado", ""]])
        r = k.build_report(self.root, self.day)["networks"]["x"]
        self.assertEqual(r["confirmed_rows"], 1)

    def test_dst_fall_back_offsets(self):
        self.assertEqual(k._local_day("2026-10-24T23:30:00Z"), date(2026, 10, 25))
        self.assertEqual(k._local_day("2026-10-25T01:30:00Z"), date(2026, 10, 25))
        self.assertEqual(k._local_day("2026-03-28T23:30:00Z"), date(2026, 3, 29))

    def test_followers_delta_and_stale(self):
        self.write("tiktok", "metricas.csv", [["2026-10-08", "1.234", "2"], ["2026-10-09", "1.240", "3"]])
        r = k.build_report(self.root, self.day)["networks"]["tiktok"]
        self.assertEqual(r["followers_net"], 6)
        self.assertEqual(r["followers_coverage"], "dos_snapshots_locales")

    def test_reddit_karma_is_not_relabelled_as_followers(self):
        self.write("reddit", "metricas.csv", [
            ["fecha", "karma_visible", "notas"],
            ["2026-10-08", "100", ""],
            ["2026-10-09", "105", ""],
        ])
        r = k.build_report(self.root, self.day)["networks"]["reddit"]
        self.assertIsNone(r["followers_net"])
        self.assertEqual(r["followers_coverage"], "sin_columna_seguidores")

    def test_corrupt_large_follower_number_does_not_abort_other_networks(self):
        self.write("x", "metricas.csv", [
            ["fecha", "seguidores"], ["2026-10-08", "100"],
            ["2026-10-09", "9" * 6000],
        ])
        self.write("threads", "metricas.csv", [
            ["fecha", "seguidores"], ["2026-10-08", "20"],
            ["2026-10-09", "22"],
        ])
        nets = k.build_report(self.root, self.day)["networks"]
        self.assertIsNone(nets["x"]["followers_net"])
        self.assertEqual(nets["x"]["followers_coverage"], "sin_snapshot_del_dia")
        self.assertEqual(nets["threads"]["followers_net"], 2)

    def test_datetime_day_is_converted_to_madrid_before_report(self):
        import datetime as dt
        report = k.build_report(self.root, dt.datetime(
            2026, 10, 8, 23, 30, tzinfo=dt.timezone.utc))
        self.assertEqual(report["day"], "2026-10-09")

    def test_named_followers_column_is_used_by_semantics(self):
        self.write("x", "metricas.csv", [
            ["fecha", "posts", "seguidores", "notas"],
            ["2026-10-08", "200", "100", ""],
            ["2026-10-09", "201", "104", ""],
        ])
        r = k.build_report(self.root, self.day)["networks"]["x"]
        self.assertEqual(r["followers_net"], 4)

    def test_follower_baseline_uses_latest_date_even_if_csv_unsorted(self):
        self.write("x", "metricas.csv", [["2026-10-08", "100"], ["2026-10-07", "20"], ["2026-10-09", "105"]])
        r = k.build_report(self.root, self.day)["networks"]["x"]
        self.assertEqual(r["followers_net"], 5)

    def test_no_old_baseline_and_no_rounded_number(self):
        self.write("facebook", "metricas.csv", [["2026-09-01", "234"], ["2026-10-09", "1.2k"]])
        r = k.build_report(self.root, self.day)["networks"]["facebook"]
        self.assertIsNone(r["followers_net"])
        self.assertEqual(r["followers_coverage"], "sin_snapshot_del_dia")

    def test_old_baseline_is_not_daily_gain(self):
        self.write("facebook", "metricas.csv", [["2026-09-01", "234"], ["2026-10-09", "244"]])
        r = k.build_report(self.root, self.day)["networks"]["facebook"]
        self.assertIsNone(r["followers_net"])
        self.assertEqual(r["followers_coverage"], "snapshot_previo_obsoleto")

    def test_inbound_only_own_network_and_comment(self):
        p = self.root / "00_OPERATIVO" / "inbound_interacciones.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows([["fecha", "red", "handle", "tipo"], ["2026-10-09", "bluesky", "A", "comment"], ["2026-10-09", "bluesky", "A", "comment"], ["2026-10-09", "bluesky", "A", "like"], ["2026-10-09", "tiktok", "B", "comment"]])
        result = k.build_report(self.root, self.day)["networks"]
        self.assertEqual(result["bluesky"]["incoming_comment_account_days"], 1)
        self.assertIsNone(result["tiktok"]["incoming_comment_account_days"])
        self.assertEqual(result["tiktok"]["incoming_coverage"], "sin_cosecha_instrumentada")
        self.assertIsNone(result["reddit"]["incoming_comment_account_days"])
        self.assertEqual(result["x"]["outbound_coverage"], "ausente")

    def test_corrupt_inbound_row_never_masquerades_as_zero(self):
        p = self.root / "00_OPERATIVO" / "inbound_interacciones.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerows([
                ["fecha", "red", "handle", "tipo"],
                ["2026-10-09", "bluesky", "cuenta"],
                ["2026-10-09", "bluesky", "otra", "like"],
            ])
        r = k.build_report(self.root, self.day)["networks"]["bluesky"]
        self.assertIsNone(r["incoming_comment_account_days"])
        self.assertEqual(r["incoming_coverage"], "registro_inbound_parcial")

    def test_unattributable_inbound_row_is_not_silent(self):
        p = self.root / "00_OPERATIVO" / "inbound_interacciones.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerows([
                ["fecha", "red", "handle", "tipo"],
                ["2026-10-09", "", "cuenta", "comment"],
            ])
        r = k.build_report(self.root, self.day)["networks"]["mastodon"]
        self.assertIsNone(r["incoming_comment_account_days"])
        self.assertEqual(r["incoming_coverage"], "registro_inbound_parcial")

    def test_render_does_not_serialize_none_as_zero(self):
        text = k.render_markdown(k.build_report(self.root, self.day))
        self.assertIn("ND", text)
        self.assertIn("No son ACK remotos", text)
        self.assertNotIn("0/ND", text)

    def test_cli_readonly_no_files_written(self):
        before = set(self.root.rglob("*"))
        run = subprocess.run([sys.executable, str(Path(k.__file__)), "--root", str(self.root), "--day", "2026-10-09", "--json"], capture_output=True, text=True, check=True)
        self.assertIn('"schema_version": 1', run.stdout)
        self.assertEqual(set(self.root.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
