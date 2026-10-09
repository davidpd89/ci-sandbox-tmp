"""La rotación nunca repite una semilla dentro de la sesión."""
import datetime
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import scan_common as sc


class SeedRotationTest(unittest.TestCase):
    def test_no_repeat_if_only_one_fresh(self):
        with tempfile.TemporaryDirectory() as td:
            file = pathlib.Path(td) / "seeds.csv"
            file.write_text("fecha,post_url\n" + datetime.date.today().isoformat() + ",A\n", encoding="utf-8")
            with patch.object(sc.random.Random, "shuffle", lambda self, items: None):
                chosen = sc.pick_seeds(file, ["B", "A", "B", "C"], n=3, id_field="post_url")
            self.assertEqual(chosen, ["B", "C", "A"])
            self.assertEqual(len(chosen), len(set(chosen)))

    def test_selection_does_not_record_cooldown_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            file = pathlib.Path(td) / "seeds.csv"
            chosen = sc.pick_seeds(file, ["post-1"], id_field="post_url")
            self.assertEqual(chosen, ["post-1"])
            self.assertFalse(file.exists())

    def test_explicit_record_is_idempotent_for_same_day_key(self):
        with tempfile.TemporaryDirectory() as td:
            file = pathlib.Path(td) / "seeds.csv"
            with patch.object(sc.random.Random, "shuffle", lambda self, items: None):
                self.assertEqual(
                    sc.pick_seeds(
                        file, ["A", "A"], n=2, id_field="post_url", record=True
                    ),
                    ["A"],
                )
                self.assertEqual(
                    sc.pick_seeds(
                        file, ["A"], n=1, id_field="post_url", record=True
                    ),
                    ["A"],
                )
            self.assertEqual(
                file.read_text(encoding="utf-8").splitlines(),
                ["fecha,post_url", f"{datetime.date.today().isoformat()},A"],
            )

    def test_failed_fetch_does_not_consume_seed_cooldown(self):
        with tempfile.TemporaryDirectory() as td:
            file = pathlib.Path(td) / "seeds.csv"
            chosen = sc.pick_seeds(file, ["A"], n=1, id_field="post_url", record=False)
            self.assertEqual(chosen, ["A"])
            self.assertFalse(file.exists())
            # Solo la descarga exitosa modifica el CSV.
            sc.record_successful_seed(file, "A", id_field="post_url")
            self.assertIn(",A", file.read_text(encoding="utf-8"))
            with patch.object(sc.random.Random, "shuffle", lambda self, items: None):
                self.assertEqual(
                    sc.pick_seeds(file, ["A", "B"], n=1, id_field="post_url", record=False),
                    ["B"]
                )

    def test_tuple_keys_and_short_pool(self):
        with tempfile.TemporaryDirectory() as td:
            file = pathlib.Path(td) / "seeds.csv"
            selected = sc.pick_seeds(file, [("u1", "a"), ("u1", "duplicate")], n=3,
                                     id_field="uri", key_fn=lambda x: x[0])
            self.assertEqual(len(selected), 1)
            self.assertEqual(selected[0][0], "u1")

    def test_record_successful_seed_is_idempotent_same_day(self):
        with tempfile.TemporaryDirectory() as td:
            file = pathlib.Path(td) / "seeds.csv"
            self.assertTrue(sc.record_successful_seed(
                file, "A", id_field="post_url", date="2026-09-28"
            ))
            self.assertFalse(sc.record_successful_seed(
                file, "A", id_field="post_url", date="2026-09-28"
            ))
            lines = file.read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, ["fecha,post_url", "2026-09-28,A"])

    def test_corrupt_seed_csv_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            file = pathlib.Path(td) / "seeds.csv"
            file.write_text("wrong,header\n2026-09-28,A\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "faltan columnas"):
                sc.pick_seeds(
                    file, ["A", "B"], n=1, id_field="post_url", record=False
                )

            file.write_text(
                "fecha,post_url\nfecha-mala,A\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "fecha"):
                sc.pick_seeds(
                    file, ["A", "B"], n=1, id_field="post_url", record=False
                )


if __name__ == "__main__":
    unittest.main()
