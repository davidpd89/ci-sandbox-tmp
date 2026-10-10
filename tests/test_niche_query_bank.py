"""Pruebas offline del banco de búsquedas, ejecutables en Python 3.11+.

No requieren datos operativos, tokens, móvil, Edge ni acceso a internet.
"""
import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import niche_query_bank as bank
import discovery_terms as dt


class NicheBankTests(unittest.TestCase):
    def test_exactly_nine_networks_and_bounded_queries(self):
        self.assertEqual(bank.NETWORKS, {
            "x", "threads", "facebook", "pinterest", "reddit", "bluesky",
            "mastodon", "tiktok", "instagram",
        })
        for network in bank.NETWORKS:
            with self.subTest(network=network):
                rows = bank.queries(network)
                self.assertGreaterEqual(len(rows), 20)
                self.assertLessEqual(len(rows), bank.MAX_SUGGESTIONS_PER_NETWORK)
                self.assertEqual(len(rows), len(set(bank._key(x) for x in rows)))
                self.assertTrue(all(isinstance(x, str) and x.strip() and '\n' not in x for x in rows))
        self.assertEqual(bank.queries("linkedin"), [])

    def test_adapters_preserve_their_search_surfaces(self):
        self.assertTrue(any("tableros" in x for x in bank.queries("pinterest")))
        self.assertTrue(any("grupos" in x for x in bank.queries("facebook")))
        self.assertTrue(any("booktok" in x for x in bank.queries("tiktok")))
        self.assertFalse(any("tableros" in x for x in bank.queries("x")))
        self.assertTrue(all(" lang:" not in x for x in bank.queries("x")))

    def test_original_rows_first_then_niche_without_duplicates(self):
        fixture = {"x": {"busquedas": ["busco novelas romantasy en español", "mi fuente"]}}
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "data.json"
            path.write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
            with patch.object(dt, "PATH", str(path)):
                out = dt.terms("x", "busquedas", " lang:es")
                self.assertEqual(out[:2], ["busco novelas romantasy en español lang:es", "mi fuente lang:es"])
                self.assertEqual(out.count("busco novelas romantasy en español lang:es"), 1)
                self.assertIn("recomendadme fantasía juvenil lang:es", out)
                self.assertEqual(dt.terms("x", "busquedas", include_niche=False), fixture["x"]["busquedas"])

    def test_skip_matches_case_and_nfc_without_erasing_accents(self):
        with patch.object(dt, "PATH", "/not/a/real/file.json"):
            self.assertNotIn("reseña de romantasy", dt.terms("reddit", skip=(" RESEÑA  DE ROMANTASY ",)))
            self.assertNotIn("reseña de romantasy", dt.terms("reddit", skip=("resen\u0303a de romantasy",)))
            self.assertIn("reseña de romantasy", dt.terms("reddit", skip=("resena de romantasy",)))

    def test_missing_or_corrupt_catalog_keeps_queries_without_affecting_hashtags(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "data.json"
            for state in ("missing", "invalid"):
                if state == "invalid":
                    path.write_text("not json", encoding="utf-8")
                with patch.object(dt, "PATH", str(path)):
                    self.assertTrue(dt.terms("mastodon", "busquedas"))
                    self.assertEqual(dt.terms("mastodon", "hashtags"), [])
                    self.assertEqual(dt.terms("nonexistent", "busquedas"), [])

    def test_catalog_hashtags_and_other_kinds_stay_untouched(self):
        fixture = {"reddit": {"hashtags": ["#Libro", "#libro", "#año", "#ano"], "hubs": ["r/libros"]}}
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "data.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            with patch.object(dt, "PATH", str(path)):
                self.assertEqual(dt.terms("reddit", "hashtags"), ["Libro", "año", "ano"])
                self.assertEqual(dt.terms("reddit", "hubs"), ["r/libros"])

    def test_undocumented_operators_not_generated_and_cli_is_valid_json(self):
        capture = io.StringIO()
        with redirect_stdout(capture):
            self.assertEqual(bank.main(["--network", "reddit"]), 0)
        data = json.loads(capture.getvalue())
        self.assertEqual(data, {"reddit": bank.queries("reddit")})
        self.assertTrue(all("from:" not in q and "list:" not in q for q in data["reddit"]))


if __name__ == "__main__":
    unittest.main()
