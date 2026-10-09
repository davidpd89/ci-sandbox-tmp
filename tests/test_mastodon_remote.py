"""Mastodon: estados en espanol de instancias hispanohablantes (06/10); sin red."""
import datetime
import os
import pathlib
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: None
requests_stub.post = lambda *a, **k: None
requests_stub.delete = lambda *a, **k: None
x_stub = types.ModuleType("x_interact")
x_stub._check_spanish_orthography = lambda text: None
sys.modules.setdefault("requests", requests_stub)
sys.modules.setdefault("x_interact", x_stub)

import mastodon_pool as mp
import mastodon_remote as mr

TODAY = datetime.date(2026, 10, 6)


def status(sid, text, *, language="es", acct="ana", days=1, **extra):
    base = {"id": str(sid), "url": f"https://masto.es/@{acct}/{sid}", "content": f"<p>{text}</p>", "language": language, "visibility": "public", "sensitive": False,
            "spoiler_text": "", "in_reply_to_id": None, "reblog": None, "tags": [], "account": {"acct": acct, "bot": False},
            "created_at": (TODAY - datetime.timedelta(days=days)).isoformat() + "T10:00:00.000Z"}
    base.update(extra)
    return base


NICHE_TEXT = "Acabo de terminar una novela de fantasía y ya estoy buscando mi próxima lectura de libros"


class KeepTests(unittest.TestCase):
    def test_spanish_niche_recent_public_original_posts_are_kept(self):
        self.assertIsNotNone(mr.keep(status(1, NICHE_TEXT), TODAY))

    def test_everything_else_is_dropped(self):
        cases = {
            "english": status(2, "I just finished a fantasy novel and I am looking for my next book to read", language="en"),
            "sin nicho": status(3, "Hoy hace un día precioso en Madrid y me voy a pasear por el parque con mi perro"),
            "antiguo": status(4, NICHE_TEXT, days=40),
            "respuesta": status(5, NICHE_TEXT, in_reply_to_id="9"),
            "boost": status(6, NICHE_TEXT, reblog={"id": "1"}),
            "privado": status(7, NICHE_TEXT, visibility="unlisted"),
            "sensible": status(8, NICHE_TEXT, sensitive=True),
            "bot": status(9, NICHE_TEXT, account={"acct": "bot", "bot": True}),
            "corto": status(10, "Libros"),
        }
        for name, st in cases.items():
            self.assertIsNone(mr.keep(st, TODAY), name)


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = mp.connect(os.path.join(self.tmp.name, "pool.sqlite3"))
        mr.ensure(self.db)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_record_dedupes_by_url_and_qualifies_the_account_with_the_host(self):
        rows = [status(1, NICHE_TEXT, acct="ana"), status(1, NICHE_TEXT, acct="ana"), status(2, NICHE_TEXT + " otra vez", acct="bea", days=3)]
        self.assertEqual(mr.record(self.db, "masto.es", rows, TODAY), 2)
        picked = mr.pick(self.db, 5, today=TODAY)
        self.assertEqual({r["acct"] for r in picked}, {"ana@masto.es", "bea@masto.es"})
        self.assertEqual(picked[0]["acct"], "ana@masto.es")           # el mas reciente primero a igualdad de nicho

    def test_one_post_per_account_and_known_accounts_are_excluded(self):
        mr.record(self.db, "masto.es", [status(1, NICHE_TEXT, acct="ana"), status(2, NICHE_TEXT + " dos", acct="ana"), status(3, NICHE_TEXT + " tres", acct="bea")], TODAY)
        self.assertEqual(len(mr.pick(self.db, 5, today=TODAY)), 2)
        self.assertEqual([r["acct"] for r in mr.pick(self.db, 5, exclude_accts={"ana@masto.es"}, today=TODAY)], ["bea@masto.es"])

    def test_registry_names_without_host_exclude_remote_accounts(self):
        mr.record(self.db, "masto.es", [status(1, NICHE_TEXT, acct="ana"), status(2, NICHE_TEXT + " dos", acct="bea")], TODAY)
        self.assertEqual([r["acct"] for r in mr.pick(self.db, 5, exclude_bare={"ana"}, today=TODAY)], ["bea@masto.es"])

    def test_resolved_posts_are_not_offered_again(self):
        mr.record(self.db, "masto.es", [status(1, NICHE_TEXT, acct="ana")], TODAY)
        mr.mark(self.db, "https://masto.es/@ana/1", "resolved")
        self.assertEqual(mr.pick(self.db, 5, today=TODAY), [])

    def test_a_closed_instance_does_not_stop_the_others(self):
        def getter(url, params):
            if "cerrada.example" in url:
                raise RuntimeError("422")
            return [status(7, NICHE_TEXT, acct="eva")]

        result = mr.mine(self.db, hosts=["cerrada.example", "masto.es"], pages=1, tags_per_host=1, today=TODAY, sleep=lambda s: None, getter=getter)
        self.assertEqual(result["masto.es"] >= 1, True)
        self.assertEqual(result["cerrada.example"], 0)
        self.assertTrue(any("cerrada.example" in e for e in result["_errores"]))

    def test_paging_follows_max_id(self):
        seen = []

        def getter(url, params):
            seen.append(params.get("max_id"))
            return [{"id": str(100 - len(seen))}]

        mr.fetch_timeline("masto.es", None, pages=3, sleep=lambda s: None, getter=getter)
        self.assertEqual(seen, [None, "99", "98"])


class DirectoryTests(unittest.TestCase):
    def test_niche_directory_accounts_become_posts_read_from_their_own_instance(self):
        tmp = tempfile.TemporaryDirectory()
        db = mp.connect(os.path.join(tmp.name, "pool.sqlite3"))
        try:
            calls = []

            def getter(url, params):
                calls.append(url)
                if url.endswith("/directory"):
                    return [{"id": "11", "acct": "lectora", "note": "<p>Libros, novelas de fantasía y lecturas</p>", "display_name": "Lectora", "followers_count": 300, "following_count": 200,
                             "statuses_count": 80, "last_status_at": TODAY.isoformat()},
                            {"id": "12", "acct": "futbolero", "note": "<p>Fútbol y cervezas</p>", "display_name": "Futbolero", "followers_count": 50, "following_count": 80,
                             "statuses_count": 80, "last_status_at": TODAY.isoformat()},
                            {"id": "13", "acct": "elbot", "note": "<p>Libros y novelas</p>", "display_name": "Bot", "bot": True, "statuses_count": 5}]
                if url.endswith("/accounts/11/statuses"):
                    return [status(21, NICHE_TEXT, acct="lectora")]
                raise AssertionError(url)

            result = mr.mine_directory(db, hosts=["masto.es"], today=TODAY, sleep=lambda s: None, getter=getter)
            self.assertEqual(result["masto.es"], 1)
            self.assertEqual([u for u in calls if "/statuses" in u], ["https://masto.es/api/v1/accounts/11/statuses"])    # solo la cuenta del nicho
            self.assertEqual([r["acct"] for r in mr.pick(db, 5, today=TODAY)], ["lectora@masto.es"])
        finally:
            db.close()
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
