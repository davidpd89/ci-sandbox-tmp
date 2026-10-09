"""R7: la ruta de fichas X debe respetar los posts del banco X.

La #114 protegía banco -> fichas; faltaba la ruta inversa.
Todas las llamadas a publicación/red son mocks, sin Edge ni credenciales.
"""
import datetime as dt
import os
import tempfile
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import content_publisher as cp
import x_bank_publish as xb

NOW = dt.datetime(2026, 10, 8, 18, 0)
ITEM = {
    "md_path": "/f/uno/publicacion.md", "carpeta": "/f/uno",
    "fecha_hora": NOW - dt.timedelta(days=1),
    "texto": "Una ficha de un libro", "estado": "lista",
    "media": [], "blockers": [], "red": "x", "meta": {},
}


class CrossPublisherCooldownTests(unittest.TestCase):
    def do_run(self, network="x", bank_rows=(), *, other=None, now=NOW):
        sent = []
        messages = []
        config = {"enabled": {"x": True, "bluesky": True},
                  "max_overdue_days": 14}
        with mock.patch.object(cp, "load_config", return_value=config), \
             mock.patch.object(cp.cq, "pending_parse_issues", return_value=[]), \
             mock.patch.object(cp, "eligible", return_value=([dict(ITEM)], [])), \
             mock.patch.object(cp, "last_auto_publication", return_value=other), \
             mock.patch.object(xb, "read_log", return_value=list(bank_rows)) as bank_read, \
             mock.patch.object(cp.cq, "mark_done") as marked, \
             mock.patch.object(cp, "_log") as recorded:
            url = cp.run(network, apply=True, now=now, out=messages.append,
                         publishers={network: lambda item: sent.append(item) or "https://x.com/1"},
                         verify=lambda *_: None)
        return url, sent, messages, marked.call_count, recorded.call_count, bank_read.call_count

    def test_x_ficha_waits_when_bank_posted_one_hour_ago(self):
        result, sent, msgs, marked, logged, checked = self.do_run(bank_rows=[
            {"id": "b1", "when": NOW - dt.timedelta(hours=1)}
        ])
        self.assertIsNone(result)
        self.assertEqual((sent, marked, logged), ([], 0, 0))
        self.assertGreaterEqual(checked, 1)
        self.assertTrue(any("banco" in m.lower() for m in msgs))

    def test_x_ficha_can_publish_after_six_hours(self):
        result, sent, _, marked, logged, _ = self.do_run(bank_rows=[
            {"id": "b1", "when": NOW - dt.timedelta(hours=7)}
        ])
        self.assertEqual(result, "https://x.com/1")
        self.assertEqual((len(sent), marked, logged), (1, 1, 1))

    def test_x_ficha_waits_when_bank_post_recorded_in_future(self):
        result, sent, _, marked, logged, _ = self.do_run(bank_rows=[
            {"id": "b1", "when": NOW + dt.timedelta(minutes=5)}
        ])
        self.assertIsNone(result)
        self.assertEqual((sent, marked, logged), ([], 0, 0))

    def test_far_future_bank_row_is_warned_and_ignored(self):
        result, sent, msgs, marked, logged, checked = self.do_run(bank_rows=[
            {"id": "reloj_roto", "when": NOW + dt.timedelta(days=2)}
        ])
        self.assertEqual(result, "https://x.com/1")
        self.assertEqual((len(sent), marked, logged), (1, 1, 1))
        self.assertTrue(any("futuro" in m.lower() for m in msgs))

    def test_real_x_bank_csv_header_and_datetime_are_consumed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "posts_banco.csv")
            xb.record({"id": "b-real", "text": "Una pregunta de lectura"},
                      "https://x.com/demo/status/1",
                      now=NOW - dt.timedelta(hours=1), path=path)
            with open(path, encoding="utf-8") as stream:
                self.assertEqual(stream.readline().strip(), "fecha_hora,id,texto,url")
            rows = xb.read_log(path)
            self.assertEqual(rows[0]["when"], NOW - dt.timedelta(hours=1))
            result, sent, _, marked, logged, checked = self.do_run(bank_rows=rows)
            self.assertIsNone(result)
            self.assertEqual((sent, marked, logged), ([], 0, 0))
            self.assertGreaterEqual(checked, 1)

    def test_bluesky_does_not_consult_x_bank(self):
        result, sent, _, marked, logged, reads = self.do_run(
            network="bluesky", bank_rows=[{"when": NOW}])
        self.assertEqual(result, "https://x.com/1")
        self.assertEqual((len(sent), marked, logged, reads), (1, 1, 1, 0))

    def test_x_ficha_still_respects_own_six_hour_cooldown(self):
        result, sent, _, _, _, _ = self.do_run(
            bank_rows=[], other=NOW - dt.timedelta(hours=1))
        self.assertIsNone(result)
        self.assertEqual(sent, [])

    def test_x_own_ficha_four_hours_ago_preserves_three_hour_interval(self):
        result, sent, msgs, marked, logged, reads = self.do_run(
            bank_rows=[], other=NOW - dt.timedelta(hours=4))
        self.assertEqual(result, "https://x.com/1")
        self.assertEqual((len(sent), marked, logged), (1, 1, 1))
        self.assertEqual(reads, 1)  # sigue verificando el banco por separado

    def test_x_own_ficha_six_hours_ago_allows_publication(self):
        result, sent, _, marked, logged, _ = self.do_run(
            bank_rows=[], other=NOW - dt.timedelta(hours=6))
        self.assertEqual(result, "https://x.com/1")
        self.assertEqual((len(sent), marked, logged), (1, 1, 1))

    def test_other_network_preserves_three_hour_cooldown(self):
        result, sent, _, marked, logged, _ = self.do_run(
            network="bluesky", bank_rows=[],
            other=NOW - dt.timedelta(hours=4))
        self.assertEqual(result, "https://x.com/1")
        self.assertEqual((len(sent), marked, logged), (1, 1, 1))


    def test_dst_spring_forward_does_not_shorten_bank_gap(self):
        date = dt.datetime(2026, 3, 29, 6, 30)  # Madrid: 02:00 -> 03:00
        result, sent, messages, marked, logged, _ = self.do_run(
            now=date,
            bank_rows=[{"id": "b1", "when": dt.datetime(2026, 3, 29, 0, 30)}])
        self.assertIsNone(result)
        self.assertEqual((sent, marked, logged), ([], 0, 0))
        self.assertTrue(any("banco" in m.lower() for m in messages))

    def test_dst_spring_forward_does_not_shorten_own_ficha_gap(self):
        # 00:30 CET -> 03:30 CEST solo transcurren 2 h reales.
        date = dt.datetime(2026, 3, 29, 3, 30)
        result, sent, _, marked, logged, _ = self.do_run(
            now=date, other=dt.datetime(2026, 3, 29, 0, 30))
        self.assertIsNone(result)
        self.assertEqual((sent, marked, logged), ([], 0, 0))

    def test_dst_spring_forward_allows_after_six_real_hours(self):
        date = dt.datetime(2026, 3, 29, 7, 30)
        result, sent, _, marked, logged, _ = self.do_run(
            now=date, other=dt.datetime(2026, 3, 29, 0, 30))
        self.assertEqual(result, "https://x.com/1")
        self.assertEqual((len(sent), marked, logged), (1, 1, 1))



if __name__ == "__main__":
    unittest.main()
