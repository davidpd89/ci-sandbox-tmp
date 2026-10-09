"""Regresiones de paridad de la política común de comentarios y follow.

Comprueban la función de consulta y el filtro cacheado con los mismos
datos; nunca envían mensajes ni leen registros de producción.
"""
from __future__ import annotations

import csv
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import growth_policy as gp
import relationship_policy as rp


def write_rows(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


class CommonRelationshipPolicyTests(unittest.TestCase):
    def test_grace_days_defined_only_in_common_growth_policy(self):
        self.assertEqual(rp.GRACE_DAYS, gp.NONRECIPROCAL_DAYS)
        self.assertEqual(rp.GRACE_DAYS, 7)

    def test_comment_decision_invariants_all_counts(self):
        for out in range(10):
            for incoming in range(10):
                expected = (out < rp.FIRST_STEP_COMMENTS or
                            out < rp.FIRST_STEP_COMMENTS + incoming)
                with self.subTest(out=out, incoming=incoming):
                    self.assertEqual(rp._comment_allowed_counts(out, incoming), expected)

    def test_direct_and_cached_comment_policy_agree_for_all_networks(self):
        nets = ("bluesky", "mastodon", "x", "threads",
                "facebook", "pinterest", "reddit", "tiktok")
        with tempfile.TemporaryDirectory() as tmp:
            registro = str(pathlib.Path(tmp) / "registro.csv")
            inbound_path = str(pathlib.Path(tmp) / "inbound.csv")
            for net in nets:
                for outbound in range(6):
                    for received in range(5):
                        outrows = [{"tipo": "comment", "resultado": "confirmado",
                                    "cuenta": "@Ana"}] * outbound
                        # Rechazados y likes no cuentan como comentarios enviados.
                        outrows.extend([
                            {"tipo": "like", "resultado": "confirmado", "cuenta": "Ana"},
                            {"tipo": "comment", "resultado": "fallido", "cuenta": "Ana"},
                            {"tipo": "reply", "resultado": "confirmado", "cuenta": "otra"},
                        ])
                        inrows = [{"red": net, "handle": "Ana", "tipo": "comment"}] * received
                        # Interacciones de otras redes y tipos nunca dan cupo.
                        inrows.extend([
                            {"red": net, "handle": "Ana", "tipo": "like"},
                            {"red": "otra_red", "handle": "Ana", "tipo": "comment"},
                        ])
                        write_rows(registro, ("tipo", "resultado", "cuenta"), outrows)
                        write_rows(inbound_path, ("red", "handle", "tipo"), inrows)
                        with mock.patch.object(rp, "INBOUND", inbound_path):
                            direct = rp.comment_allowed(net, "@aNa", registro, inbound_path=inbound_path)
                            cached = rp.comment_filter(net, registro)("@aNa")
                        with self.subTest(network=net, outbound=outbound, received=received):
                            self.assertEqual(direct, cached)
                            self.assertEqual(direct, outbound < 2 + received)

    def test_direct_path_does_not_read_inbound_when_first_steps_available(self):
        with mock.patch.object(rp, "outbound_comments", return_value=1):
            with mock.patch.object(rp, "inbound_counts", side_effect=AssertionError("unexpected")):
                self.assertTrue(rp.comment_allowed("reddit", "ana", "unused.csv"))


if __name__ == "__main__":
    unittest.main()
