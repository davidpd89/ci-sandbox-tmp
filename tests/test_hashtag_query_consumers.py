"""Contrato offline de consumo de consultas: 9 redes, 3 colas, sin cuentas."""
import ast
import datetime as dt
from pathlib import Path
import random
import unittest
from urllib.parse import quote, unquote

from tools import hashtag_query_consumers as hqc


NETWORKS = tuple(hqc.NETWORK_QUEUE)
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (
    "x_scan.py", "threads_scan.py", "facebook_scan.py",
    "pinterest_growth.py", "reddit_scan.py", "bluesky_scan.py",
    "bluesky_growth_scan.py", "mastodon_scan.py",
    "mastodon_growth_scan.py", "tiktok_growth_scan.py",
    "instagram_scan.py",
)


def provider(network, kind):
    if kind == "hashtags":
        return ["#año", "#ano", "#año", "bad space", ""]
    return ["fantasía juvenil", "lectura ñ", "fantasía juvenil", "", 8]


class ConsumerParityTests(unittest.TestCase):
    def test_all_nine_networks_and_queues(self):
        self.assertEqual(set(NETWORKS), {
            "x", "threads", "facebook", "pinterest", "reddit",
            "bluesky", "mastodon", "tiktok", "instagram"})
        self.assertEqual(set(hqc.NETWORK_QUEUE.values()), {"WEB", "API", "MOBILE"})

    def test_fresh_terms_per_network_without_erasing_seeds(self):
        for network in NETWORKS:
            with self.subTest(network=network):
                seeds = ["lectores", "escritores"]
                old, new = hqc.combine(network, "busquedas", seeds, reader=provider)
                self.assertEqual(len(old), 2)
                self.assertEqual(len(new), 2)
                self.assertTrue(any("fantasía juvenil" in q for q in new))
                self.assertTrue(any("lectores" in q for q in old))
                self.assertEqual(len(set(q.casefold() for q in old + new)), 4)
                self.assertEqual(seeds, ["lectores", "escritores"])

    def test_fresh_stale_corrupt_empty_snapshots(self):
        # #63 valida schema y caducidad, este contrato solo consume su salida.
        snapshots = [
            ("fresh", ["recién leído"]),
            ("expired", []),
            ("corrupt", {"unexpected": "object"}),
            ("empty", []),
        ]
        for network in NETWORKS:
            for name, payload in snapshots:
                with self.subTest(network=network, state=name):
                    old, fresh = hqc.combine(
                        network, "busquedas", ["semilla"],
                        reader=lambda n, k, p=payload: p)
                    self.assertEqual(len(old), 1)
                    self.assertEqual(len(fresh), int(name == "fresh"))

    def test_provider_exceptions_degrade_to_static(self):
        for exc in (OSError, ValueError, KeyError, TypeError):
            def broken(network, kind, error=exc):
                raise error("fixture sintético")
            a, b = hqc.combine("x", "busquedas", ["lectura"], reader=broken)
            self.assertEqual(len(a), 1)
            self.assertEqual(b, [])

    def test_network_isolation(self):
        def isolated(network, kind):
            return [network + "_único"]
        for network in NETWORKS:
            _, terms = hqc.combine(network, "busquedas", [], reader=isolated)
            self.assertEqual(len(terms), 1)
            self.assertIn(network, terms[0])
            self.assertFalse(any(other + "_" in terms[0]
                                 for other in NETWORKS if other != network))

    def test_hashtags_unicode_and_format(self):
        for network in hqc.TAG_NETWORKS:
            with self.subTest(network=network):
                old, new = hqc.combine(network, "hashtags",
                                       ["#niño"], reader=provider)
                self.assertEqual(len(old), 1)
                self.assertEqual(len(new), 2)
                self.assertNotEqual(new[0].casefold(), new[1].casefold())
                self.assertIn("año", new[0])
                self.assertIn("ano", new[1])
                for item in old + new:
                    encoded = quote(item, safe="")
                    self.assertEqual(unquote(encoded), item)
                    self.assertIn("%23", encoded)
        self.assertEqual(hqc.format_term("reddit", "hashtags", "#año"), "")

    def test_x_lang_es_once_and_dedupe_final(self):
        old, fresh = hqc.combine(
            "x", "busquedas", ["fantasía lang:es", "fantasía",
                              "novela lang:es"],
            reader=lambda n, k: ["fantasía", "otra", "otra lang:es"])
        self.assertEqual(old, ["fantasía lang:es", "novela lang:es"])
        self.assertEqual(fresh, ["otra lang:es"])
        self.assertEqual(
            hqc.format_term("x", "hashtags", "#año"), "#año lang:es")

    def test_nfc_equivalent_but_no_ascii_folding_for_hashtags(self):
        a, fresh = hqc.combine(
            "bluesky", "hashtags", ["año", "nin\u0303o"],
            reader=lambda n, k: ["an\u0303o", "niño", "ano"])
        self.assertEqual(len(a), 2)
        self.assertEqual(fresh, ["#ano"])

    def test_rotation_preserves_budget_and_exploration(self):
        for network in NETWORKS:
            for budget in (0, 1, 2, 3, 6):
                for tick in range(12):
                    with self.subTest(network=network, budget=budget, tick=tick):
                        terms = hqc.select(
                            network, "busquedas", ["semilla A", "semilla B",
                            "semilla C"], budget=budget, tick=tick,
                            reader=provider)
                        self.assertLessEqual(len(terms), budget)
                        self.assertEqual(len(terms), len(set(map(str.casefold, terms))))
                        if budget >= 2:
                            self.assertTrue(any("semilla" in x for x in terms))
                            self.assertTrue(any("fantasía" in x or "lectura ñ" in x
                                                for x in terms))
            seen = set()
            for tick in range(16):
                seen.update(hqc.select(network, "busquedas",
                                      ["semilla"], budget=1, tick=tick,
                                      reader=provider))
            self.assertTrue(any("semilla" in term for term in seen))
            self.assertTrue(any("fantasía" in term for term in seen))

    def test_budget_and_missing_reader_guard(self):
        with self.assertRaises(ValueError):
            hqc.select("x", "busquedas", [], budget=-1, tick=0)
        with self.assertRaises(ValueError):
            hqc.select("x", "busquedas", [], budget=1, tick="lunes")
        with self.assertRaises(ValueError):
            hqc.combine("otra_red", "busquedas", [], reader=provider)
        self.assertEqual(hqc.rotate([], 9, 0), [])

    def test_native_configs_pure_idempotent(self):
        samples = {
            "bluesky": {"query_families": [{"name": "old", "queries": ["semilla"]}],
                        "tag_queries": [{"tag": "lectura", "query": "lectura"}],
                        "coverage": {"post_queries_per_family": 1}},
            "mastodon": {"query_families": [{"name": "old", "queries": ["semilla"]}],
                         "hashtags": ["lectura"], "coverage": {"hashtags_per_round": 2}},
            "tiktok": {"actor_queries": ["semilla"],
                       "video_queries": ["semilla"],
                       "budgets": {"user_search_queries": 2, "video_search_queries": 2}},
        }
        import copy
        for network, config in samples.items():
            with self.subTest(network=network):
                before = copy.deepcopy(config)
                merged = hqc.extend_native_config(network, config, reader=provider)
                again = hqc.extend_native_config(network, merged, reader=provider)
                self.assertEqual(merged, again)
                self.assertEqual(config, before)
                self.assertEqual(merged.get("budgets", merged.get("coverage")),
                                 before.get("budgets", before.get("coverage")))
                self.assertIn("fantasía juvenil", str(merged))
                self.assertIn("año", str(merged))
                self.assertNotIn("lexical_expansion", str(before))

    def test_malformed_and_control_characters(self):
        for invalid in ("", " # ", "a b", "0hola", "a\x00b", "x" * 140):
            self.assertEqual(hqc.format_term("mastodon", "hashtags", invalid), "")
        self.assertEqual(hqc.format_term("threads", "busquedas", "  libros   niños "),
                         "libros niños")

    def test_repeatable_property_stress(self):
        rng = random.Random(101)
        for network in NETWORKS:
            for _ in range(70):
                seeds = [rng.choice(["uno", "dos", "tres", "año", "ano"])
                         for _ in range(rng.randrange(1, 20))]
                result = hqc.select(
                    network, "busquedas", seeds,
                    budget=rng.randrange(0, 8), tick=rng.randrange(1000),
                    reader=lambda n, k: ["uno", "día", "día", "tarde"])
                self.assertEqual(len(result), len(set(map(str.casefold, result))))

    def test_actual_consumer_source_wiring_and_syntax(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                content = (ROOT / "tools" / script).read_text(encoding="utf-8")
                ast.parse(content)
                self.assertIn("hashtag_query_consumers", content)
        self.assertEqual(len(SCRIPTS), 11)

    def test_url_encoding_is_transport_responsibility(self):
        for network in NETWORKS:
            query = hqc.format_term(network, "busquedas", "qué leer, niño")
            encoded = quote(query, safe="")
            self.assertEqual(unquote(encoded), query)
            self.assertIn("%C3%B1", encoded)


if __name__ == "__main__":
    unittest.main()
