import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import bluesky_vocab_loader as vl

CONFIG = {"query_families": [{"name": "lectura_general", "queries": ["club de lectura", "libro recomendado"]}],
          "tag_queries": [{"tag": "BookSky", "query": "lectura"}], "feed_queries": ["books"], "starter_pack_queries": ["libros"]}
VOCAB = {"families": {"gpt_x": ["Club de Lectura", "mini reseña", "mi tbr"], "lectura_general": ["wrap up"]},
         "hashtags": ["booksky", "FantasySky"], "feed_queries": ["Books", "booksky"], "starter_pack_queries": ["libros", "rol español"],
         "jetstream_extra_terms": ["📚💙", "booksky"]}


class MergeTests(unittest.TestCase):
    def test_merge_adds_only_new_items_and_never_mutates_the_original(self):
        new, added = vl.merge(CONFIG, VOCAB)
        self.assertEqual(len(CONFIG["query_families"]), 1)
        fam = {f["name"]: f["queries"] for f in new["query_families"]}
        self.assertEqual(fam["gpt_x"], ["mini reseña", "mi tbr"])        # "Club de Lectura" ya existia (sin distinguir mayusculas)
        self.assertIn("wrap up", fam["lectura_general"])
        self.assertEqual([t["tag"] for t in new["tag_queries"]], ["BookSky", "FantasySky"])   # booksky ya estaba
        self.assertEqual(new["feed_queries"], ["books", "booksky"])
        self.assertEqual(new["starter_pack_queries"], ["libros", "rol español"])
        self.assertIn("📚💙", new["mined_terms"])
        self.assertEqual(added["tags"], 1)
        self.assertEqual(added["queries"], 3)

    def test_idempotent(self):
        once, _ = vl.merge(CONFIG, VOCAB)
        twice, added = vl.merge(once, VOCAB)
        self.assertEqual(once, twice)
        self.assertEqual(sum(added.values()), 0)


if __name__ == "__main__":
    unittest.main()
