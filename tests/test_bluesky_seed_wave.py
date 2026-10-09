import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import bluesky_seed_wave as sw


def prof(handle="ana.bsky.social", bio="Lectora de fantasía y reseñas de libros", followers=800, following=500, posts=120, viewer=None, name=""):
    return {"handle": handle, "description": bio, "followersCount": followers, "followsCount": following, "postsCount": posts,
            "viewer": viewer or {}, "displayName": name}


class ClassifyTests(unittest.TestCase):
    def test_types(self):
        self.assertEqual(sw.classify("Editorial independiente de fantasía y ciencia ficción"), "editorial")
        self.assertEqual(sw.classify("Librería de barrio en Madrid"), "libreria")
        self.assertEqual(sw.classify("Reseñas de libros y bookstagram"), "resenador")
        self.assertEqual(sw.classify("Escritora de novela juvenil"), "autor")
        self.assertEqual(sw.classify("Club de lectura de fantasía"), "club")
        self.assertIsNone(sw.classify("Fotógrafo y viajero"))
        self.assertEqual(sw.classify("Máster de juegos de rol y D&D en Madrid"), "rol")
        self.assertEqual(sw.classify("Ilustradora y autora de cómic"), "comic")


class SeedTests(unittest.TestCase):
    def test_accepts_real_spanish_publisher_and_rejects_the_rest(self):
        ok = prof("ed.bsky.social", "Editorial independiente de narrativa y fantasía en español", 5400)
        self.assertEqual(sw.seed_ok(ok)[0], "editorial")
        for bad in (prof(bio="Editorial", followers=40), prof(bio="Editorial publisher of the best books and love", followers=9000),
                    prof(bio="Editorial de política y activismo militante", followers=9000), prof(bio="Fotógrafo", followers=9000),
                    prof(bio="Editorial de libros", followers=9000, posts=2)):
            self.assertIsNone(sw.seed_ok(bad)[0], bad)
        self.assertIsNone(sw.seed_ok(ok, known={"ed.bsky.social"})[0])

    def test_pick_seeds_rotates_and_parks_barren_ones(self):
        seeds = {"a": {"last_scanned": "2026-10-04", "yield": 9}, "b": {"last_scanned": None, "yield": None},
                 "c": {"last_scanned": "2026-10-01", "yield": 0}, "d": {"last_scanned": "2026-10-01", "yield": 8},
                 "e": {"last_scanned": "2026-10-02", "yield": 5}}
        self.assertEqual(sw.pick_seeds(seeds, 3), ["b", "d", "e"])

    def test_day_queries_rotate(self):
        a = sw.day_queries(datetime.date(2026, 10, 5))
        b = sw.day_queries(datetime.date(2026, 10, 6))
        self.assertEqual(len(a), sw.SEED_QUERIES_PER_DAY)
        self.assertNotEqual(a, b)


class CommenterTests(unittest.TestCase):
    def test_small_spanish_reader_scores_and_filters_work(self):
        score, why = sw.commenter_ok(prof(), "Qué ganas de leerlo")
        self.assertEqual(why, "")
        self.assertGreater(score, 18)
        cases = [prof(viewer={"following": "at://x"}), prof(followers=90000), prof(following=10),
                 prof(posts=1), prof(bio="Hablemos por ig, sexo y más"), prof(bio="Reading and coffee, the best books and love my life"),
                 prof(viewer={"blocking": "at://x"})]
        for p in cases:
            self.assertNotEqual(sw.commenter_ok(p, "hola")[1], "", p)

    def test_plan_pairs_follow_with_like_and_adds_seed_follows(self):
        cands = [{"handle": "a", "score": 20, "source": "editorial:x", "url": "https://bsky.app/profile/a/post/1"},
                 {"handle": "b", "score": 25, "source": "autor:y", "url": "https://bsky.app/profile/b/post/2"},
                 {"handle": "B", "score": 24, "source": "autor:y", "url": ""}]
        plan = sw.build_plan(cands, [{"handle": "ed.bsky.social", "type": "editorial"}], max_follows=2)
        self.assertEqual([(p["handle"], p["kind"]) for p in plan],
                         [("b", "follow"), ("b", "like"), ("a", "follow"), ("a", "like"), ("ed.bsky.social", "follow")])


if __name__ == "__main__":
    unittest.main()
