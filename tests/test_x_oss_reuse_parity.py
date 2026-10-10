"""Contracto X de lectura-tras-ACK entre registro y deduplicador existente.

Se emplea el ejecutor vigente sincronizado del repositorio principal, no
un guard CSV paralelo. Todos los destinos/handles y fechas son sinteticos.
No se conecta a Edge ni a ninguna red.
"""
import csv
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import x_acquisition_audit as acquisition
import x_execute as executor


HEADER = ("fecha", "cuenta", "tipo", "post_resumen",
          "texto_usado", "resultado", "notas")


class XCrossComponentReplayTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = pathlib.Path(temp.name) / "registro.csv"
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerow(HEADER)

    def _persist(self, *rows):
        with mock.patch.object(executor, "REGISTRO_CSV", str(self.path)):
            executor._append_registro(list(rows))

    def _kept(self, plan):
        followed, treated = acquisition.read_history(self.path)
        return acquisition.filter_known_plan(plan, followed, treated)[0]

    def test_quote_delivery_unknown_survives_csv_and_blocks_next_scan(self):
        self._persist({
            "kind": "quote", "handle": "@lectora",
            "url": "https://twitter.com/lectora/status/00123",
            "text": "Comentario de prueba",
            "resultado": "pendiente_verificacion",
        })
        result = self._kept([
            {"kind": "reply", "url": "https://x.com/otra/status/123"},
            {"kind": "repost", "url": "https://x.com/otra/status/124"},
        ])
        self.assertEqual([r["url"] for r in result],
                         ["https://x.com/otra/status/124"])
        with self.path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows[1][5], "pendiente_verificacion")

    def test_pending_follow_and_latest_account_are_distinct(self):
        self._persist(
            {"kind": "follow", "handle": "@LECTORA",
             "resultado": "pendiente_verificacion"},
            {"kind": "like_latest", "handle": "@OTRA",
             "resultado": "pendiente_verificacion",
             "resumen": "URL incidental"},
        )
        result = self._kept([
            {"kind": "follow", "handle": "lectora"},
            {"kind": "like_latest", "handle": "otra"},
            {"kind": "follow", "handle": "tercera"},
            {"kind": "like_latest", "handle": "cuarta"},
        ])
        self.assertEqual([(r["kind"], r["handle"]) for r in result],
                         [("follow", "tercera"), ("like_latest", "cuarta")])

    def test_pre_dispatch_skip_cannot_be_fabricated_as_new_ack(self):
        self._persist(
            {"kind": "follow", "handle": "primera", "resultado": "no_intentado"},
            {"kind": "reply", "url": "https://x.com/a/status/7",
             "resultado": "parada:BotWarningDetected"},
        )
        result = self._kept([
            {"kind": "follow", "handle": "primera"},
            {"kind": "reply", "url": "https://x.com/a/status/7"},
        ])
        self.assertEqual(len(result), 2)
        with self.path.open(encoding="utf-8", newline="") as stream:
            self.assertEqual(len(list(csv.reader(stream))), 1)

    def test_observed_already_action_blocks_repeated_target(self):
        self._persist({
            "kind": "reply", "handle": "@lectora",
            "url": "https://x.com/lectora/status/42",
            "resultado": "saltado_ya_comentado",
        })
        self.assertEqual(
            self._kept([{"kind": "reply",
                         "url": "https://twitter.com/lectora/status/42"}]),
            [],
        )

    def test_missing_history_is_not_interpreted_as_empty(self):
        self.path.unlink()
        with self.assertRaises(acquisition.HistoryReadError):
            acquisition.read_history(self.path)


if __name__ == "__main__":
    unittest.main()
