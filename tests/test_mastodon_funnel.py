"""Embudo del scan de Mastodon (05/10): reserva persistente, huecos de la shortlist, filtros de idioma y antiguedad, atribucion first-touch."""
import datetime as dt
import os
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: None
requests_stub.post = lambda *a, **k: None
requests_stub.delete = lambda *a, **k: None
x_stub = types.ModuleType("x_interact")
x_stub._check_spanish_orthography = lambda text: None
sys.modules.setdefault("requests", requests_stub)
sys.modules.setdefault("x_interact", x_stub)

import mastodon_interact as m
import mastodon_growth_scan as gs
import mastodon_build_plan as bp
import mastodon_pool as pool

TODAY = dt.date(2026, 9, 29)


def account(acct, ident="1", **extra):
    return {"id": ident, "acct": acct, "username": acct.split("@", 1)[0], "display_name": acct, "note": "Lectora de fantasía y novelas",
            "followers_count": 30, "following_count": 40, "statuses_count": 100, **extra}


def status(ident, acct="lectora@mastodon.social", text="Estoy leyendo fantasía juvenil y me está encantando mucho", **extra):
    return {"id": str(ident), "url": f"https://mastodon.social/@{acct.split('@')[0]}/{ident}", "uri": f"https://mastodon.social/users/{acct.split('@')[0]}/statuses/{ident}",
            "visibility": "public", "content": f"<p>{text}</p>", "created_at": "2026-09-29T10:00:00Z", "replies_count": 2, "favourites_count": 4, "reblogs_count": 1,
            "account": account(acct, "1"), "tags": [{"name": "Bookstodon"}], **extra}


class FunnelTests(unittest.TestCase):
    def collector(self):
        c = gs.Collector(gs._load_config(gs.CONFIG_PATH), today=TODAY, write_metrics=False, run_id="test")
        c.own, c.own_id = "davidportodiaz", "david"
        return c

    def item_and_post(self, c, st):
        c.add_status(st, "post_search", "q")
        item = c.candidates[st["account"]["acct"].casefold()]
        post = c.posts[st["id"]]
        return item, post

    def test_non_spanish_statuses_get_no_actions_even_from_accounts_that_follow_us(self):
        """06/10 (David): nos orientamos al espanol; quien nos sigue en otro idioma no pasa nada, pero no se le da favorito."""
        c = self.collector()
        item, post = self.item_and_post(c, status("1", language="en", text="My fantasy book is out today and I love reading it so much"))
        for lane in ("acquisition", "community"):
            self.assertEqual(gs._post_actions(item, post, lane, TODAY, c.config), [])
        item["followed_by"] = True
        self.assertEqual(gs._post_actions(item, post, "community", TODAY, c.config), [])

    def test_spanish_language_field_and_heuristic(self):
        c = self.collector()
        _, es = self.item_and_post(c, status("2", language="es"))
        self.assertIn("favourite", gs._post_actions({}, es, "acquisition", TODAY, c.config))
        _, none = self.item_and_post(c, status("3", acct="otra@mastodon.social", language=None, text="Estoy leyendo una novela de fantasía que me gusta mucho"))
        self.assertTrue(gs._spanish_post(none))

    def test_old_statuses_are_not_favourited_for_new_readers(self):
        c = self.collector()
        item, post = self.item_and_post(c, status("4", language="es", created_at="2026-08-30T10:00:00Z"))       # 30 dias
        self.assertNotIn("favourite", gs._post_actions(item, post, "acquisition", TODAY, c.config))            # adquisicion: <=21
        self.assertIn("favourite", gs._post_actions(item, post, "community", TODAY, c.config))                  # comunidad: <=45

    def test_shortlist_gaps_get_their_statuses_with_a_cap(self):
        c = self.collector()
        c.config["budgets"]["vet_gap_profiles"] = 2
        c.config["budgets"]["shortlist_profiles"] = 10
        for i in range(4):
            c.add_account(account(f"sin{i}@mastodon.social", str(100 + i), note="Escribo novelas de fantasía y leo mucho"), "pool", "x")
        fetched = []

        def fake_statuses(account_id, **kw):
            fetched.append(account_id)
            return [status(900 + int(account_id), acct=f"sin{int(account_id) - 100}@mastodon.social", language="es")]

        with patch.object(m, "account_statuses", side_effect=fake_statuses):
            gs._vet_shortlist_gaps(c)
        self.assertEqual(len(fetched), 2)
        self.assertEqual(sum(1 for i in c.candidates.values() if i["posts"]), 2)

    def test_pool_offers_accounts_and_skips_known_and_self(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = pool.connect(os.path.join(tmp, "p.sqlite3"))
            for acct in ("nueva@masto.es", "conocida@masto.es", "davidportodiaz"):
                pool.upsert(db, account(acct, "5", note="Lectora de fantasía y novela juvenil", last_status_at=dt.date.today().isoformat()), "ed", "followers", "2026-09-29")
            db.commit()
            db.close()
            c = self.collector()
            c.config["budgets"]["pool_candidates"] = 10
            c.known["conocida@masto.es"] = "2026-09-01"
            original = pool.connect
            with patch.object(pool, "connect", lambda path=None: original(os.path.join(tmp, "p.sqlite3"))):
                gs._consume_pool(c)
        self.assertIn("nueva@masto.es", c.candidates)
        self.assertIn("pool", c.candidates["nueva@masto.es"]["sources"])
        self.assertNotIn("davidportodiaz", c.candidates)
        self.assertNotIn("conocida@masto.es", c.candidates)

    def test_first_touch_source_survives_a_later_discovery_order(self):
        def shortlist_source(order):
            c = self.collector()
            c.config["budgets"]["shortlist_profiles"] = 5
            c.config["budgets"]["vet_gap_profiles"] = 0
            first = account("primera@masto.es", "7")
            for source in order:
                c.add_account(first, source, "k")
            with patch.object(m, "_get", return_value=[]), patch.object(gs, "_refresh_cached_viewer_state", lambda *a, **k: None):
                result = gs._build_output(c)
            return next(row for row in result["shortlist"] if row["acct"] == "primera@masto.es")["first_source"]

        self.assertEqual(shortlist_source(["pool", "hashtag"]), "pool")
        self.assertEqual(shortlist_source(["hashtag", "pool"]), "pool")           # otro dia llega antes por hashtag: la primera vez fue el pool

    def test_builder_carries_account_id_and_first_touch_in_the_motive(self):
        scan = {"auto_plan": [], "follow_pool": [], "shortlist": [{
            "id": "M001", "acct": "a@masto.es", "account_id": "77", "first_source": "pool", "lane": "acquisition", "sources": ["pool"], "actions": ["follow"],
            "posts": [{"id": "M001-P1", "status_id": "5", "url": "https://masto.es/@a/5", "sources": ["author_status"], "actions": ["favourite"]}]}]}
        plan = bp.build(scan, {"actions": [{"candidate": "M001", "kind": "follow"}, {"post": "M001-P1", "kind": "favourite"}]})
        follow = next(a for a in plan if a["kind"] == "follow")
        self.assertEqual(follow["account_id"], "77")
        self.assertTrue(all(":src=pool" in a["motivo"] for a in plan))


if __name__ == "__main__":
    unittest.main()


class HashtagCursorTests(unittest.TestCase):
    """Consulta F (GPT): cada ronda releia la cabeza del timeline; ahora hay cursores persistentes (cabeza + retrospectiva)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "p.sqlite3")
        original = pool.connect
        patcher = patch.object(pool, "connect", lambda path=None: original(self.db_path))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def collector(self):
        c = gs.Collector(gs._load_config(gs.CONFIG_PATH), today=TODAY, write_metrics=False, run_id="t")
        c.config["budgets"].update({"hashtag_pages": 3, "hashtag_backfill_pages": 2})
        return c

    @staticmethod
    def feed(newest, count=40):
        """Timeline simulado: ids descendentes; hashtag_page(max_id=...) devuelve los 40 siguientes mas antiguos."""
        def page(tag, *, limit=40, max_id=None, min_id=None):
            top = int(max_id) - 1 if max_id else newest
            rows = [{"id": str(i)} for i in range(top, max(top - count, 0), -1)]
            return rows, (str(rows[-1]["id"]) if rows else None)
        return page

    def test_first_run_reads_the_head_and_stores_cursors(self):
        c = self.collector()
        with patch.object(m, "hashtag_page", side_effect=self.feed(1000)) as page:
            rows = gs._hashtag_rows(c, "Libros")
        self.assertEqual(len(rows), 120)                      # sin cursor: hashtag_pages paginas hacia atras
        self.assertEqual(page.call_count, 3)
        db = pool.connect()
        self.assertEqual(pool.get_cursor(db, "hashtag", "libros"), ("1000", "881"))
        db.close()

    def test_next_run_reads_only_new_statuses_and_goes_back_in_time(self):
        c = self.collector()
        with patch.object(m, "hashtag_page", side_effect=self.feed(1000)):
            first = {r["id"] for r in gs._hashtag_rows(c, "Libros")}
        with patch.object(m, "hashtag_page", side_effect=self.feed(1010)):          # llegaron 10 estados nuevos
            second = {r["id"] for r in gs._hashtag_rows(c, "Libros")}
        self.assertIn("1010", second)
        self.assertIn("880", second)                                                # retrospectiva: lo que antes no se leyo
        overlap = first & second
        self.assertLess(len(overlap), 40)                                           # casi nada se relee (solo el enlace de la cabeza)
        db = pool.connect()
        newest, oldest = pool.get_cursor(db, "hashtag", "libros")
        db.close()
        self.assertEqual(newest, "1010")
        self.assertLess(int(oldest), 881)

    def test_cursor_never_moves_the_wrong_way(self):
        db = pool.connect()
        pool.set_cursor(db, "hashtag", "x", "500", "100")
        pool.set_cursor(db, "hashtag", "x", "400", "300")
        self.assertEqual(pool.get_cursor(db, "hashtag", "x"), ("500", "100"))
        db.close()
