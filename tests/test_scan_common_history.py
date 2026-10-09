"""El historial solo acredita acciones verdaderamente confirmadas."""
import csv
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import scan_common as sc


class HistoryTests(unittest.TestCase):
    def test_failed_reply_or_unfollow_does_not_exclude_target(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "registro.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=[
                    "tipo", "cuenta", "post_resumen", "resultado", "url"])
                writer.writeheader()
                writer.writerows([
                    {"tipo": "reply", "cuenta": "@lectora",
                     "post_resumen": "https://x.com/lectora/status/123",
                     "resultado": "fallo:timeout"},
                    {"tipo": "reply", "cuenta": "@autora",
                     "post_resumen": "Una pregunta sobre lecturas",
                     "url": "https://x.com/autora/status/987",
                     "resultado": "confirmado"},
                    {"tipo": "quote", "cuenta": "@lector",
                     "post_resumen": "https://x.com/lector/status/456",
                     "resultado": "publicado"},
                    {"tipo": "unfollow", "cuenta": "@lector",
                     "resultado": "no_intentado"},
                    {"tipo": "unfollow", "cuenta": "@bot",
                     "resultado": "confirmado"},
                    {"tipo": "reply", "cuenta": "@yarespondida",
                     "post_resumen": "https://x.com/yarespondida/status/111",
                     "resultado": "saltado_ya_comentado"},
                    {"tipo": "unfollow", "cuenta": "@yadescartada",
                     "resultado": "saltado_ya_no_seguido"},
                ])
            self.assertEqual(
                sc.already_interacted_urls(str(path)),
                {
                    "https://x.com/lector/status/456",
                    "https://x.com/autora/status/987",
                    "https://x.com/yarespondida/status/111",
                },
            )
            self.assertEqual(sc.discarded_handles(str(path)), {"bot", "yadescartada"})

    def test_empty_result_does_not_prove_interaction(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "registro.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=["tipo", "cuenta", "post_resumen", "resultado"],
                )
                writer.writeheader()
                writer.writerows([
                    {
                        "tipo": "reply",
                        "cuenta": "@sinconfirmar",
                        "post_resumen": "https://x.com/sinconfirmar/status/1",
                        "resultado": "",
                    },
                    {
                        "tipo": "unfollow",
                        "cuenta": "@sinconfirmar",
                        "post_resumen": "",
                        "resultado": "",
                    },
                ])
            self.assertEqual(sc.already_interacted_urls(str(path)), set())
            self.assertEqual(sc.discarded_handles(str(path)), set())


if __name__ == "__main__":
    unittest.main()
