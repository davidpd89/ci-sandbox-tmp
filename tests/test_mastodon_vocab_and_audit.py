import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import mastodon_vocab_loader as ml
import mastodon_self_audit as au

CONFIG = {"query_families": [{"name": "lectores", "queries": ["libro recomendado"]}], "hashtags": ["Libros", "Bookstodon"],
          "account_queries": ["editorial libros"], "niche_terms": ["libro", "reseña", "reseña", "novela"]}
VOCAB = {"families": {"lectores": ["Libro recomendado", "necesito un libro"], "gpt_tropes": ["slow burn"]}, "hashtags": ["BookSky", "FantasySky", "Leer", "libros"],
         "seed_actor_queries": ["Hispacon", "editorial libros"]}


class VocabTests(unittest.TestCase):
    def test_merge_adds_only_what_is_missing_and_skips_bluesky_only_tags(self):
        new, added = ml.merge(CONFIG, VOCAB)
        self.assertEqual(added["families"], 1)
        self.assertEqual(added["queries"], 2)                       # «Libro recomendado» ya estaba (sin distinguir mayusculas)
        tags = new["hashtags"]
        self.assertNotIn("BookSky", tags)
        self.assertNotIn("FantasySky", tags)
        self.assertIn("Leer", tags)
        self.assertEqual(sum(1 for t in tags if t.casefold() == "libros"), 1)
        self.assertEqual(new["account_queries"], ["editorial libros", "Hispacon"])
        self.assertEqual(sum(1 for t in new["niche_terms"] if t == "reseña"), 1)     # el duplicado de la lista original desaparece

    def test_merge_is_idempotent(self):
        once, _ = ml.merge(CONFIG, VOCAB)
        twice, added = ml.merge(once, VOCAB)
        self.assertEqual(once, twice)
        self.assertEqual(sum(added.values()), 0)

    def test_real_local_vocab_when_available_is_idempotent(self):
        """Integración optativa con el vocabulario GPT local no versionado.

        Se ejecuta automáticamente cuando el fichero existe en el PC.
        En CI se omite con un motivo explícito, sin sustituir el fixture offline.
        """
        import json
        if not os.path.isfile(ml.VOCAB):
            self.skipTest("vocabulario GPT local ausente; probar en PC con archivo real")
        with open(ml.CONFIG, encoding="utf-8") as stream:
            actual_config = json.load(stream)
        with open(ml.VOCAB, encoding="utf-8") as stream:
            actual_vocab = json.load(stream)
        self.assertIsInstance(actual_vocab, dict)
        self.assertIsInstance(actual_vocab.get("families"), dict)
        self.assertTrue(actual_vocab["families"], "el vocabulario real no contiene familias")
        original = json.dumps(actual_config, sort_keys=True, ensure_ascii=False)
        once, _ = ml.merge(actual_config, actual_vocab)
        twice, changes = ml.merge(once, actual_vocab)
        self.assertEqual(once, twice)
        self.assertEqual(sum(changes.values()), 0)
        self.assertEqual(json.dumps(actual_config, sort_keys=True, ensure_ascii=False), original)

    def test_real_config_accepts_representative_vocab_idempotently(self):
        import json
        with open(ml.CONFIG, encoding="utf-8") as stream:
            config = json.load(stream)
        new, _ = ml.merge(config, VOCAB)
        again, added = ml.merge(new, VOCAB)
        self.assertEqual(new, again)
        self.assertEqual(sum(added.values()), 0)


BASE = {"target": 1000, "stage": 1, "hours_elapsed": 20, "done_today": 900, "plan": 300, "cap": 400, "unique_ratio": 0.8, "rate_limited": 0, "forbidden": 0,
        "followback_n": 80, "followback_rate": 0.25, "exhausted": [], "reply_notes": [], "follow_ratio": 3.0, "pool": {"available_now": 5000},
        "shortlist_no_posts": 0.02, "plan_quality": {"favourites": 200, "spanish": 0.99, "niche_post": 0.6}, "plan_failures": 0}


class AuditTests(unittest.TestCase):
    def test_a_healthy_day_has_no_gaps(self):
        self.assertEqual(au.gaps(BASE), [])

    def test_each_problem_is_flagged_with_an_action(self):
        cases = {
            "volumen": {"done_today": 100},
            "OFERTA": {"plan": 50},
            "objetivos unicos": {"unique_ratio": 0.3},
            "429": {"rate_limited": 2},
            "403": {"forbidden": 3},
            "follow-back": {"followback_rate": 0.05},
            "EJECUCION": {"plan_failures": 1},
            "RESERVA": {"pool": {"available_now": 200}},
            "sin ningun estado": {"shortlist_no_posts": 0.5},
            "CALIDAD del plan: solo 70 %": {"plan_quality": {"favourites": 100, "spanish": 0.7, "niche_post": 0.6}},
            "llevan un termino del nicho": {"plan_quality": {"favourites": 100, "spanish": 0.99, "niche_post": 0.1}},
            "siguiendo/seguidores": {"follow_ratio": 5.0},
            "concentracion": {"top_source": "hashtag", "top_source_share": 0.6},
        }
        for needle, change in cases.items():
            found = au.gaps({**BASE, **change})
            self.assertTrue(any(needle in gap for gap, _ in found), (needle, found))
            self.assertTrue(all(action for _, action in found))


if __name__ == "__main__":
    unittest.main()
