import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import instagram_commenters_scan as cs
import instagram_build_plan as bp

HEADER = """quilaknabooks
QuilaknaBooks 📚📖💕
700 publicaciones
9339 seguidores
3421 seguidos
Bookstagram 🌸🌿
Novela romántica
quilaknabooks
hquintana1972 sigue esta cuenta
Seguir
Mensaje
NdeNovela"""


class ParseTests(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(cs.parse_count("9339"), 9339)
        self.assertEqual(cs.parse_count("17,2 mil"), 17200)
        self.assertEqual(cs.parse_count("561 mil"), 561000)
        self.assertEqual(cs.parse_count("1.234"), 1234)
        self.assertEqual(cs.parse_count("1,2 M"), 1_200_000)
        self.assertIsNone(cs.parse_count("abc"))

    def test_profile_header(self):
        prof = cs.parse_profile(HEADER)
        self.assertEqual((prof["posts"], prof["followers"], prof["following"]), (700, 9339, 3421))
        self.assertTrue(prof["bio"].startswith("Bookstagram"))
        self.assertNotIn("Seguir", prof["bio"])


class EvaluateTests(unittest.TestCase):
    base = {"followers": 800, "following": 600, "posts": 120, "bio": "Lectora de fantasía y café. Reseñas de libros"}

    def test_small_spanish_reader_is_accepted(self):
        score, why = cs.evaluate("ana_lee", self.base, "Qué ganas de leerlo", button="follow")
        self.assertEqual(why, "")
        self.assertGreater(score, 15)

    def test_big_accounts_followed_private_english_and_dating_are_rejected(self):
        cases = [
            ({**self.base, "followers": 20000}, "follow", "hola"),
            (self.base, "following", "hola"),
            (self.base, "privada", "hola"),
            ({**self.base, "bio": "Book lover. Reading and coffee, love my life", }, "follow", "so good"),
            ({**self.base, "bio": "Hablemos por ig, sexo y más"}, "follow", "hola"),
            ({**self.base, "following": 30}, "follow", "hola"),
            ({**self.base, "bio": "Tienda online de libros, sorteo y descuento"}, "follow", "hola"),
        ]
        for profile, button, comment in cases:
            score, why = cs.evaluate("x_user", profile, comment, button=button)
            self.assertNotEqual(why, "", (profile, button))

    def test_known_or_discarded_handles_are_skipped(self):
        self.assertNotEqual(cs.evaluate("ana", self.base, "", button="follow", known={"ana"})[1], "")
        self.assertNotEqual(cs.evaluate("ana", self.base, "", button="follow", discarded={"ana"})[1], "")

    def test_commenters_parsing(self):
        text = "angel_mg\nplanetadelibros\nSeguir\nCaption\nPara ti\nquilaknabooks\n \n2 d\nQué maravilla 😍\nResponder\n" \
               "blaancawritess\n \n2 d\nMi corazón\n1 Me gusta\nResponder\nVer las 1 respuestas\nplanetadelibros\nautor\n"
<<<<<<< HEAD
        out = cs._commenters(text, ["quilaknabooks", "blaancawritess", "planetadelibros"], "planetadelibros", "autorademodiaz")
=======
        out = cs._commenters(text, ["quilaknabooks", "blaancawritess", "planetadelibros"], "planetadelibros", "davidportodiaz")
>>>>>>> origin/research/public-reuse-parent
        self.assertEqual([h for h, _ in out], ["quilaknabooks", "blaancawritess"])
        self.assertIn("maravilla", out[0][1])


class SeedTests(unittest.TestCase):
    def test_pick_seeds_rotates_by_last_scanned_then_yield(self):
        seeds = {"a": {"last_scanned": "2026-10-04", "yield": 9}, "b": {"last_scanned": None, "yield": None},
                 "c": {"last_scanned": "2026-10-01", "yield": 5}, "d": {"last_scanned": "2026-10-01", "yield": 8}}
        self.assertEqual(cs.pick_seeds(seeds, 3), ["b", "d", "c"])

    def test_seeds_with_no_yield_are_parked(self):
        seeds = {"tienda": {"last_scanned": "2026-10-01", "yield": 2}, "a": {"last_scanned": "2026-10-04", "yield": 9},
                 "b": {"last_scanned": "2026-10-03", "yield": 7}, "c": {"last_scanned": "2026-10-02", "yield": 4}}
        self.assertEqual(cs.pick_seeds(seeds, 3), ["c", "b", "a"])

    def test_builtin_seeds_are_always_present(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            book = cs.load_seeds(os.path.join(d, "nada.json"))
        self.assertTrue(set(cs.SEEDS) <= set(book))

    def test_seed_acceptance(self):
        self.assertTrue(cs.seed_ok("editorial_x", "Editorial independiente de fantasía", 12000)[0])
        self.assertFalse(cs.seed_ok("pequena", "Editorial de libros", 300)[0])          # sin comentarios
        self.assertFalse(cs.seed_ok("gigante", "Libros", 9_000_000)[0])                 # ruido
        self.assertFalse(cs.seed_ok("pizzeria", "Las mejores pizzas de Madrid", 20000)[0])
        self.assertFalse(cs.seed_ok("editorial_x", "Editorial", 12000, known={"editorial_x"})[0])

    def test_day_queries_rotate(self):
        import datetime
        a = cs.day_seed_queries(datetime.date(2026, 10, 5))
        b = cs.day_seed_queries(datetime.date(2026, 10, 6))
        self.assertEqual(len(a), cs.SEED_QUERIES_PER_DAY)
        self.assertNotEqual(a, b)


class PlanTests(unittest.TestCase):
    def test_best_ten_unique(self):
        cands = [{"handle": f"u{i}", "score": 20 + i, "niche": True, "followers": 100, "source": "@x"} for i in range(15)]
        cands.append({"handle": "U14", "score": 99, "niche": True, "bio": "", "comment": ""})
        plan = bp.build(cands)
        self.assertEqual(len(plan), 10)
        self.assertEqual(plan[0]["handle"], "U14")
        self.assertTrue(all(p["kind"] == "follow" for p in plan))

    def test_non_niche_commenters_are_dropped(self):
        cands = [{"handle": "viajera", "score": 30, "niche": False, "bio": "Mujer viajera", "comment": "bonito"},
                 {"handle": "lectora", "score": 19, "niche": True, "bio": "Lectora", "comment": "me encanta"}]
        self.assertEqual([p["handle"] for p in bp.build(cands)], ["lectora"])


if __name__ == "__main__":
    unittest.main()
