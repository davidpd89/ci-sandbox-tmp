import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import facebook_build_plan as plan
import facebook_pool as fpool


class FacebookPoolPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = fpool.connect(os.path.join(self.tmp.name, "pool.sqlite3"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def _record(self, rows, source="search:test"):
        return fpool.record_posts(self.db, rows, source)

    def test_pool_is_persistent_and_counts_new(self):
        rows = [("Editorial Fantasía", "https://facebook.com/p/1", "Nueva novela de fantasía juvenil: lectura recomendada para lectores")]
        self.assertEqual(self._record(rows), 1)
        self.assertEqual(self._record(rows), 0)
        self.assertEqual(fpool.stats(self.db)["posts"], 1)

    def test_own_page_never_recorded(self):
        self.assertEqual(self._record([("Autora Demo Escritor", "https://facebook.com/p/9", "Mi novela de fantasía, una lectura juvenil")]), 0)

    def test_off_topic_religious_post_is_not_planned(self):
        self._record([("Lectura del día católica", "https://facebook.com/p/2", "Lectura del día: evangelio y libro de oración, lectura para lectores")])
        self.assertEqual(plan.build_from_pool(self.db, 5), [])

    def test_needs_at_least_one_niche_term(self):
        self._record([("Cuenta X", "https://facebook.com/p/3", "Buenas tardes a todos, feliz jueves")])
        self.assertEqual(plan.build_from_pool(self.db, 5), [])
        self._record([("Cuenta Y", "https://facebook.com/p/4", "Buenas tardes a todos, hoy empiezo una lectura nueva")])
        self.assertEqual(len(plan.build_from_pool(self.db, 5)), 1)

    def test_book_post_is_planned_and_marked_once(self):
        self._record([("Reseñas con Alma", "https://facebook.com/p/4", "Reseña de una novela de fantasía juvenil: gran lectura para lectores de sagas")])
        first = plan.build_from_pool(self.db, 5)
        self.assertEqual([i["permalink"] for i in first], ["https://facebook.com/p/4"])
        self.assertIn(first[0]["kind"], ("like_external", "comment_external"))
        self.assertEqual(plan.build_from_pool(self.db, 5), [])      # ya marcado como 'planned'

    def test_intent_post_gets_bank_comment_and_plain_post_gets_like(self):
        self._record([("Lectora Ana", "https://facebook.com/p/6", "Estoy leyendo una novela de fantasía juvenil buenísima, lectura de sagas"),
                      ("Club Libros", "https://facebook.com/p/7", "Club de lectura de novela y fantasía: reunión este jueves, libros y lectores")])
        out = {i["permalink"]: i for i in plan.build_from_pool(self.db, 5)}
        self.assertEqual(out["https://facebook.com/p/6"]["kind"], "comment_external")
        self.assertTrue(out["https://facebook.com/p/6"]["bank"] and out["https://facebook.com/p/6"]["text"])
        self.assertEqual(out["https://facebook.com/p/7"]["kind"], "like_external")

    def test_max_comments_zero_means_only_likes(self):
        self._record([("Lectora Ana", "https://facebook.com/p/8", "Estoy leyendo una novela de fantasía juvenil buenísima, lectura de sagas")])
        self.assertEqual([i["kind"] for i in plan.build_from_pool(self.db, 5, max_comments=0)], ["like_external"])

    def test_recent_authors_excluded(self):
        self._record([("Reseñas con Alma", "https://facebook.com/p/5", "Reseña de una novela de fantasía juvenil: gran lectura para lectores de sagas")])
        self.assertEqual(plan.build_from_pool(self.db, 5, exclude_handles={"reseñas con alma"}), [])

    def test_recent_authors_reads_registry_window(self):
        path = os.path.join(self.tmp.name, "registro.csv")
        today = datetime.date(2026, 10, 20)
        with open(path, "w", encoding="utf-8") as stream:
            stream.write("2026-10-18,Autor Reciente,like_external,u,,confirmado,x\n2026-09-01,Autor Antiguo,like_external,u,,confirmado,x\n")
        self.assertEqual(plan.recent_authors(path, today), {"autor reciente"})


if __name__ == "__main__":
    unittest.main()
