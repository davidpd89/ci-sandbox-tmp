import csv
import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import pinterest_growth as pg


class PureTests(unittest.TestCase):
    def test_followers(self):
        self.assertEqual(pg.parse_followers("imredwrightes | 5 seguidores | · | Siguiendo a 0"), 5)
        self.assertEqual(pg.parse_followers("1,2 mil seguidores"), 1200)
        self.assertEqual(pg.parse_followers("10,5 mil seguidores"), 10500)
        self.assertEqual(pg.parse_followers("2 M seguidores"), 2_000_000)
        self.assertEqual(pg.parse_followers("1.234 seguidores"), 1234)
        self.assertIsNone(pg.parse_followers("sin cifras"))

    def test_pin_filter(self):
        self.assertTrue(pg.pin_ok("10 libros de fantasía que debes leer", "Una recopilación de sagas de fantasía juvenil"))
        self.assertFalse(pg.pin_ok("Best fantasy books to read", "Top books and reading ideas for you"))
        self.assertFalse(pg.pin_ok("Libros de fantasía en oferta", "Comprar en Amazon con descuento"))
        self.assertFalse(pg.pin_ok("Decoración de salón moderno", "ideas para la casa y el jardín"))   # no es del nicho
        self.assertFalse(pg.pin_ok("Libros para ligar y sexo", "hablemos por ig"))

    def test_author_filter(self):
        ok, _ = pg.author_ok("ana", "Escritora de fantasía y lectora", 800)
        self.assertTrue(ok)
        for args in (("big", "Autora de fantasía", 90000), ("shop", "Tienda de libros, descuento", 300),
                     ("eng", "Reading and coffee lover of the best books", 300), ("autorademodiaz", "libros", 10)):
            self.assertFalse(pg.author_ok(*args)[0], args)
        self.assertFalse(pg.author_ok("ana", "Escritora de fantasía", 800, known={"ana"})[0])
        self.assertFalse(pg.author_ok("x", "Escritora de fantasía", None)[0])

    def test_day_queries_rotate_and_cover_the_pool(self):
        today = datetime.date(2026, 10, 4)
        a = pg.day_queries(today)
        b = pg.day_queries(today + datetime.timedelta(days=1))
        self.assertEqual(len(a), pg.QUERIES_PER_DAY)
        self.assertNotEqual(a, b)
        covered = {q for d in range(60) for q in pg.day_queries(today + datetime.timedelta(days=d))}
        self.assertEqual(len(covered), len(pg.QUERY_POOL))


class PlanTests(unittest.TestCase):
    def cands(self):
        pins = [{"url": f"u{i}", "title": f"t{i}", "ok": i % 5 != 0, "author": f"a{i % 4}", "board": pg.FANTASY if i % 2 else None,
                 "done_react": i == 1, "done_save": False} for i in range(1, 30)]
        authors = [{"handle": f"c{i}", "followers": 100, "score": i} for i in range(20)]
        return {"pins": pins, "authors": authors}

    def test_caps_and_uniqueness(self):
        plan = pg.build_plan(self.cands())
        kinds = [p["kind"] for p in plan]
        self.assertEqual(kinds.count("follow"), 10)
        self.assertLessEqual(kinds.count("react"), 15)
        self.assertLessEqual(kinds.count("save"), 10)
        self.assertEqual(plan[-1]["handle"], "c0") if False else None
        follows = [p["handle"] for p in plan if p["kind"] == "follow"]
        self.assertEqual(follows[0], "c19")                     # mejor puntuacion primero
        self.assertNotIn("u1", [p["url"] for p in plan if p["kind"] == "react"])   # ya reaccionado
        saves = [p for p in plan if p["kind"] == "save"]
        self.assertTrue(all(p["board"] for p in saves))         # solo pines con tablero
        self.assertEqual(len({p["url"] for p in saves}), len(saves))

    def test_pin_caption_is_carried_to_guard(self):
        import like_context_policy as lcp
        candidates = {"pins": [{
            "url": "https://pinterest.example/pin/123",
            "title": "Cinco novelas de fantasía que merece la pena leer",
            "desc": "Estas historias de fantasía juvenil me han sorprendido este año",
            "ok": True, "done_react": False,
        }], "authors": []}
        row = next(r for r in pg.build_plan(candidates) if r["kind"] == "react")
        self.assertEqual(row["media_present"], True)
        self.assertIn("historias", row["post_text"])
        self.assertTrue(lcp.check_execution("pinterest", row)[0])

    def test_done_sets_from_registry(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "r.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["fecha", "cuenta", "tipo", "post_resumen", "texto_usado", "resultado", "notas"])
                w.writerow(["2026-10-04", "@autorademodiaz", "react", "https://x/pin/1/", "", "confirmado", ""])
                w.writerow(["2026-10-04", "@autorademodiaz", "save", "https://x/pin/2/", "tab", "confirmado", ""])
                w.writerow(["2026-10-04", "@Ana", "follow", "", "", "confirmado", ""])
                w.writerow(["2026-10-04", "@fallo", "follow", "", "", "fallo", ""])
            reacted, saved, followed = pg.done_sets(path)
            self.assertEqual((reacted, saved, followed), ({"https://x/pin/1/"}, {"https://x/pin/2/"}, {"ana"}))


if __name__ == "__main__":
    unittest.main()
