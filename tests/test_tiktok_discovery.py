import pathlib
import random
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import tiktok_discovery as d

CONFIG = {
    "niche_terms": ["libro", "libros", "novela", "booktok", "escritora", "editorial"],
    "spam_terms": ["kdp", "ghostwriting", "crypto"],
    "scoring": {},
}


def row(**kw):
    base = d.make_row("ana_libros", source="user_search", name="Ana", bio="")
    base.update(kw)
    return base


class ScoringTests(unittest.TestCase):
    def test_identity_beats_nothing_and_follows_me_needs_base_signal(self):
        strong = row(name="Ana Escritora de novela", relation="follows_me", followers=900)
        weak_bot = row(name="Servicios", bio="", relation="follows_me", followers=900)
        self.assertGreater(d.score_row(strong, CONFIG), 8)
        self.assertLess(d.score_row(weak_bot, CONFIG), 4)

    def test_english_and_huge_accounts_are_penalised(self):
        es = row(name="Lectora de libros", followers=1000)
        en = row(name="The books reader", followers=1000)
        huge = row(name="Lectora de libros", followers=900_000)
        self.assertGreater(d.score_row(es, CONFIG), d.score_row(en, CONFIG))
        self.assertGreater(d.score_row(es, CONFIG), d.score_row(huge, CONFIG))

    def test_spam_politics_self_and_existing_relations_are_rejected(self):
        self.assertFalse(d.validate_row(row(name="Amazon KDP formatting libros"), CONFIG))
        self.assertFalse(d.validate_row(row(handle="autorademoescritor"), CONFIG))
        self.assertFalse(d.validate_row(row(name="libros", relation="following"), CONFIG))
        self.assertTrue(d.validate_row(row(name="Lectora de libros"), CONFIG))


class MemoryTests(unittest.TestCase):
    def test_seen_roundtrip_and_new_flag(self):
        seen = {}
        self.assertTrue(d.touch_seen(seen, "Ana", "user_search", "2026-10-05"))
        self.assertFalse(d.touch_seen(seen, "ana", "video_search:comment", "2026-10-06"))
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "seen.csv"
            d.save_seen(seen, str(path))
            loaded = d.load_seen(str(path))
        self.assertEqual(loaded["ana"]["times_seen"], "2")
        self.assertTrue(d.recently_seen(loaded, "ANA", "2026-10-07", 3))
        self.assertFalse(d.recently_seen(loaded, "ANA", "2026-10-20", 3))

    def test_rotation_uses_common_ranking_unused_first_and_metrics_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp, "m.csv"))
            d.append_metrics([
                {"fecha": "2026-10-01", "surface": "user_search", "query": "b", "rows": 20, "valid": 18, "new": 15},
                {"fecha": "2026-10-01", "surface": "user_search", "query": "c", "rows": 20, "valid": 1, "new": 0},
            ], path, run_id="r1")
            stats = d.load_stats(path)
        picked = d.pick_queries(["a", "b", "c"], "user_search", stats, 3)
        self.assertEqual(picked[0], "a")           # nunca usada
        self.assertEqual(picked[1], "b")           # más rentable que "c"


class SeedPoolTests(unittest.TestCase):
    def test_pool_learns_only_strong_niche_accounts_with_audience(self):
        cfg = {"scoring": {"seed_min_score": 6, "seed_min_followers": 1500}}
        rows = [
            {"handle": "libreria_x", "name": "Librería X", "score": 8, "followers": 5000},
            {"handle": "tiny_libros", "name": "Libros", "score": 9, "followers": 40},
            {"handle": "random", "name": "Cocina", "score": 9, "followers": 90000},
            {"handle": "low", "name": "Editorial Baja", "score": 2, "followers": 9000},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp, "pool.csv"))
            d.update_seed_pool(rows, cfg, path)
            self.assertEqual(d.load_seed_pool(path), ["libreria_x"])


if __name__ == "__main__":
    unittest.main()
