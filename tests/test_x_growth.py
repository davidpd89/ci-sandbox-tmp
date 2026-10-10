"""X (06/10): reserva compartida con Threads, plan desde la reserva, lectura de cuentas/posts, rampa y filtro de perfiles; sin navegador ni red."""
import datetime
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import browser_pool as bpool
import exec_common as ec
import volume_ramp as vr
import x_build_plan as bp
import x_interact as xi
import x_pool as xp

TODAY = datetime.date(2026, 10, 6)
NOW = datetime.datetime(2026, 10, 6, 12)      # reloj fijo: sin esto los posts de prueba caducan a las 72 h reales (08/10 23:00) y el test falla solo


def post(handle, n, text, lang="es", age=3.0, repost=False, pinned=False):
    return {"handle": handle, "url": f"https://x.com/{handle}/status/{n}", "text": text, "lang": lang, "age_hours": age, "repost": repost, "pinned": pinned}


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.db = xp.connect(os.path.join(tempfile.mkdtemp(), "pool.sqlite3"))

    def test_only_spanish_niche_posts_are_offered_one_per_account(self):
        xp.record_posts(self.db, [
            post("lectora", 1, "Acabo de terminar una novela de fantasía preciosa, ¿qué libro leo ahora?"),
            post("lectora", 2, "Otra reseña de un libro de fantasía y su mapa", age=1.0),
            post("inglesa", 3, "I just finished a fantasy novel and it was great, the book is out now", lang="en"),
            post("sinnicho", 4, "Hoy hace un día precioso para pasear con los perros"),
            post("mia", 5, "Mi novela de fantasía ya está en Amazon", ),
        ], "search:test", TODAY.isoformat())
        rows = xp.pick(self.db, 10, now=datetime.datetime(2026, 10, 6, 12))
        self.assertEqual([r["handle"] for r in rows if r["handle"] == "lectora"], ["lectora"])
        handles = {r["handle"] for r in rows}
        self.assertNotIn("inglesa", handles)
        self.assertNotIn("sinnicho", handles)

    def test_own_and_pinned_posts_are_not_stored(self):
<<<<<<< HEAD
        added = xp.record_posts(self.db, [post("autorademodiaz", 1, "Mi novela de fantasía"), post("otra", 2, "Libro de fantasía fijado", pinned=True)], "feed", TODAY.isoformat())
=======
        added = xp.record_posts(self.db, [post("davidportodiaz", 1, "Mi novela de fantasía"), post("otra", 2, "Libro de fantasía fijado", pinned=True)], "feed", TODAY.isoformat())
>>>>>>> origin/research/public-reuse-parent
        self.assertEqual(added, 0)

    def test_foreign_accounts_are_never_offered_and_backfollow_goes_first(self):
        xp.record_accounts(self.db, [
            ("autora_es", "Ana", "Escritora de fantasía y lectora de novelas y libros", "profiles:fantasia", None),
            ("autor_de", "Hans", "Ich schreibe Fantasy Romane und lese gern Bücher und das ist mein Leben", "profiles:fantasia", None),
            ("amiga", "Marta", "", "backfollow", None),
        ], TODAY.isoformat())
        names = [r["handle"] for r in xp.pick_accounts(self.db, 10)]
        self.assertEqual(names[0], "amiga")
        self.assertIn("autora_es", names)
        self.assertNotIn("autor_de", names)

    def test_rich_bio_in_profile_search_becomes_a_seed(self):
        xp.record_accounts(self.db, [("editorial", "Editorial", "Editorial de libros de fantasía y novela juvenil, autores y lectores", "profiles:editorial", None)], TODAY.isoformat())
        self.assertIn("editorial", [r[0] for r in self.db.execute("SELECT handle FROM seeds")])

    def test_language_flag_prefers_the_networks_own_lang(self):
        self.assertEqual(bpool.spanish_flag("texto cualquiera", "es"), 1)
        self.assertEqual(bpool.spanish_flag("el libro que leo", "pt"), 0)
        self.assertIsNone(bpool.spanish_flag("ok", "und"))


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.db = xp.connect(os.path.join(tempfile.mkdtemp(), "pool.sqlite3"))
        rows = [post(f"lector{i}", i, f"Reseña del libro {i}: una novela de fantasía que recomiendo, ¿la habéis leído?", age=2.0) for i in range(1, 11)]
        xp.record_posts(self.db, rows, "search:test", TODAY.isoformat())
        xp.record_accounts(self.db, [(f"autora{i}", "Autora", "Escritora de novelas de fantasía y libros para lectores", "profiles:q", None) for i in range(1, 6)] + [("seguidor", "S", "", "backfollow", None)], TODAY.isoformat())

    def test_plan_has_likes_follows_and_like_latest_without_repeating_accounts(self):
        plan = bp.build_from_pool(self.db, likes=8, follows=6, known={}, today=TODAY, now=NOW)
        kinds = [a["kind"] for a in plan]
<<<<<<< HEAD
        self.assertGreaterEqual(kinds.count("like"), 5)
        self.assertGreaterEqual(kinds.count("like_latest"), 1)
        self.assertLessEqual(kinds.count("follow"), 6)
        self.assertIn(("follow", "seguidor"), [(a["kind"], a["handle"]) for a in plan])      # el follow-back va primero
        likes = [a["url"] for a in plan if a["kind"] == "like"]
        self.assertEqual(len(likes), len(set(likes)))

    def test_recent_accounts_and_done_urls_are_skipped(self):
        known = {"lector1": TODAY.isoformat(), "lector2": (TODAY - datetime.timedelta(days=30)).isoformat()}
        plan = bp.build_from_pool(self.db, likes=20, follows=0, known=known, done_urls={"https://x.com/lector3/status/3"}, today=TODAY, now=NOW)
        handles = {a.get("handle") for a in plan}
        self.assertNotIn("lector1", handles)      # tocada hoy
        self.assertIn("lector2", handles)         # tocada hace 30 dias: vuelve a ser elegible
        self.assertNotIn("lector3", handles)      # post ya tratado

    def test_merge_keeps_one_follow_per_account_and_one_like_per_url(self):
        first = [{"kind": "follow", "handle": "a"}, {"kind": "like", "url": "u1", "handle": "a"}]
        second = [{"kind": "follow", "handle": "A"}, {"kind": "like", "url": "u1", "handle": "a"}, {"kind": "like_latest", "handle": "b"}, {"kind": "like_latest", "handle": "B"}]
        merged = bp.merge(first, second)
        self.assertEqual([m["kind"] for m in merged], ["follow", "like", "like_latest"])
=======
        self.assertEqual(kinds.count("like"), 0)           # sin auto-like en X
        self.assertEqual(kinds.count("like_latest"), 0)
        self.assertLessEqual(kinds.count("follow"), 6)
        self.assertIn(("follow", "seguidor"), [(a["kind"], a["handle"]) for a in plan])      # el follow-back va primero
        follows = [a["handle"].casefold() for a in plan if a["kind"] == "follow"]
        self.assertEqual(len(follows), len(set(follows)))

    def test_recent_accounts_and_done_urls_are_skipped(self):
        known = {"lector1": TODAY.isoformat(), "lector2": (TODAY - datetime.timedelta(days=30)).isoformat()}
        plan = bp.build_from_pool(self.db, likes=20, follows=20, known=known, done_urls={"https://x.com/lector3/status/3"}, today=TODAY, now=NOW)
        handles = {a.get("handle") for a in plan}
        self.assertNotIn("lector1", handles)      # tocada hoy
        # lector2 (conocida desde hace 30 dias) ya no recibe like; el follow sigue la politica de `known`
        self.assertNotIn("lector3", handles)      # post ya tratado

    def test_merge_keeps_one_follow_per_account_and_one_like_per_url(self):
        first = [{"kind": "follow", "handle": "a"}, {"kind": "like", "url": "u1", "handle": "a"}]      # los likes se descartan
        second = [{"kind": "follow", "handle": "A"}, {"kind": "like", "url": "u1", "handle": "a"}, {"kind": "like_latest", "handle": "b"}, {"kind": "like_latest", "handle": "B"}]
        merged = bp.merge(first, second)
        self.assertEqual([m["kind"] for m in merged], ["follow"])
>>>>>>> origin/research/public-reuse-parent

    def test_done_urls_reads_confirmed_registry_rows(self):
        path = os.path.join(tempfile.mkdtemp(), "reg.csv")
        with open(path, "w", encoding="utf-8", newline="") as stream:
            stream.write("fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n")
            stream.write("2026-10-05,@a,like,https://x.com/a/status/1/,,confirmado,\n")
            stream.write("2026-10-05,@b,like,https://x.com/b/status/2,,fallo,\n")
        self.assertEqual(bp.done_urls(path), {"https://x.com/a/status/1"})


class InteractParsingTests(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(xi.parse_count("1.234 Followers"), 1234)
        self.assertEqual(xi.parse_count("1,2 mil Seguidores"), 1200)
        self.assertEqual(xi.parse_count("3.4K Followers"), 3400)
        self.assertEqual(xi.parse_count("2 M Followers"), 2_000_000)
        self.assertIsNone(xi.parse_count("sin cifra"))

    def test_user_cell_name_and_bio(self):
        self.assertEqual(xi.parse_user_cell("foo", "Foo Bar\n@foo\nFollows you\nLectora de fantasía\nFollowing"), ("foo", "Foo Bar", "Lectora de fantasía"))

    def test_weighted_length_counts_links_as_23(self):
<<<<<<< HEAD
        link = "https://autorademodiaz.com/herramientas/variedad-lexica/herramienta-muy-larga-de-url"
=======
        link = "https://davidportodiaz.com/herramientas/variedad-lexica/herramienta-muy-larga-de-url"
>>>>>>> origin/research/public-reuse-parent
        xi._check_length("a" * 250 + " " + link)          # 251 + 23 = 274 <= 280
        with self.assertRaises(ValueError):
            xi._check_length("a" * 270 + " " + link)

    def test_extract_posts_filters_ads_and_builds_permalinks(self):
        class Page:
            def evaluate(self, js, limit):
                return [{"href": "/Autora/status/10", "datetime": "2026-10-06T10:00:00.000Z", "text": "Un libro", "lang": "es", "social": "", "ad": False},
                        {"href": "/Anuncio/status/11", "datetime": None, "text": "Compra", "lang": "es", "social": "", "ad": True},
                        {"href": "/Otra/status/12", "datetime": None, "text": "RT", "lang": "es", "social": "Ana reposted", "ad": False},
                        {"href": None, "text": "sin enlace", "ad": False}]
        posts = xi.extract_posts(Page())
        self.assertEqual([p["url"] for p in posts], ["https://x.com/Autora/status/10", "https://x.com/Otra/status/12"])
        self.assertTrue(posts[1]["repost"])


class RampAndVetTests(unittest.TestCase):
    def test_x_stages_grow_and_pauses_shrink(self):
        stages = vr.stages("x")
        self.assertEqual([s["daily"] for s in stages], sorted(s["daily"] for s in stages))
        self.assertEqual([s["pause"] for s in stages], sorted((s["pause"] for s in stages), reverse=True))
        self.assertTrue(all(s["pause"][0] >= 10 for s in stages))

    def test_x_advances_on_healthy_days_and_regresses_on_warnings(self):
        healthy = {"rate_limited": 0, "ui_warnings": 0, "unique_ratio": 0.9, "not_found_rate": 0.01, "attempted": 60, "done_today": 100, "target": 150, "hours_elapsed": 23}
        self.assertEqual(vr.decide(healthy, 1, 1, network="x")[0], "advance")
        self.assertEqual(vr.decide({**healthy, "ui_warnings": 1}, 9, 3, network="x")[0], "regress")

    def test_shared_vet_rejects_giants_foreign_and_political_profiles(self):
        self.assertIsNone(ec.follow_vet({"followers": 300, "bio": "Escribo novelas de fantasía y leo mucho", "name": "Lector"}))
        self.assertIn("enorme", ec.follow_vet({"followers": 90000, "bio": "Escritora"}))
        self.assertIn("ingles", ec.follow_vet({"followers": 300, "bio": "Fantasy writer and book reader, my new book is out today"}))
        self.assertIsNotNone(ec.follow_vet({"followers": 300, "bio": "Ich schreibe Fantasy Romane und lese gern Bücher und das ist mein Leben"}))


if __name__ == "__main__":
    unittest.main()
