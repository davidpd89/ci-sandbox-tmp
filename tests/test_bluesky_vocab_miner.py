import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import bluesky_vocab_miner as vm
import bluesky_jetstream_collect as jc


def posts(text, authors):
    return [(f"did:{i}", text) for i in range(authors)]


class MinerTests(unittest.TestCase):
    def test_hashtags_need_distinct_authors_and_skip_known_noise_and_politics(self):
        data = posts("Terminé la saga #FantasiaEpica #BookSky", 4) + posts("#Solo2 un libro", 2) + posts("sorteo de libros #Sorteo #BookSky", 6) + \
            posts("#EleccionesPSOE y libros", 5)
        out = vm.mine(data, known_terms=set(), known_tags={"BookSky"})
        tags = [h["term"] for h in out["hashtags"]]
        self.assertIn("FantasiaEpica", tags)
        self.assertNotIn("BookSky", tags)       # ya conocida
        self.assertNotIn("Solo2", tags)         # solo 2 autores
        self.assertNotIn("Sorteo", tags)        # ruido
        self.assertFalse(any("Elecciones" in t for t in tags))

    def test_phrases_need_more_authors_and_ignore_stopword_edges(self):
        data = posts("hoy empiezo mi reto de lectura de octubre", 5) + posts("una frase poco repetida sobre dragones", 2)
        out = vm.mine(data)
        terms = [p["term"] for p in out["phrases"]]
        self.assertIn("reto lectura", terms)
        self.assertNotIn("lectura octubre de", terms)
        self.assertFalse(any("dragones" in t for t in terms))

    def test_known_terms_are_not_proposed_again(self):
        out = vm.mine(posts("mi reto de lectura", 6), known_terms={"reto de lectura"})
        self.assertNotIn("reto de lectura", [p["term"] for p in out["phrases"]])

    def test_promote_adds_to_tags_and_terms_without_duplicates_and_keeps_original(self):
        config = {"tag_queries": [{"tag": "BookSky", "query": "lectura"}], "query_families": [{"queries": ["reto de lectura"]}]}
        cands = {"hashtags": [{"term": "BookSky", "authors": 9, "posts": 9}, {"term": "FantasiaEpica", "authors": 5, "posts": 7}],
                 "phrases": [{"term": "reto de lectura", "authors": 8, "posts": 9}, {"term": "mi tbr", "authors": 6, "posts": 6}]}
        new, added = vm.promote(config, cands, 5, 5, datetime.date(2026, 10, 5))
        self.assertEqual(added, {"hashtags": ["FantasiaEpica"], "phrases": ["mi tbr"]})
        self.assertEqual(len(config["tag_queries"]), 1)                          # no muta la original
        self.assertIn("FantasiaEpica", [t["tag"] for t in new["tag_queries"]])
        self.assertEqual(sorted(new["mined_terms"]), ["FantasiaEpica", "mi tbr"])

    def test_jetstream_uses_mined_terms(self):
        config = {"query_families": [], "tag_queries": [], "mined_terms": ["Reto Lectura Otoño"]}
        self.assertIn("reto lectura otono", jc.load_terms(config))


if __name__ == "__main__":
    unittest.main()
