import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import mastodon_pool as mp

TODAY = datetime.date.today().isoformat()


def account(acct, note="", **extra):
    base = {"id": str(abs(hash(acct)) % 10 ** 9), "acct": acct, "display_name": acct, "note": f"<p>{note}</p>", "followers_count": 300, "following_count": 200,
            "statuses_count": 120, "last_status_at": TODAY, "locked": False, "bot": False}
    base.update(extra)
    return base


class FakeApi:
    def __init__(self, followers=None, statuses=None, favs=None, boosts=None):
        self.followers, self.status_rows, self.favs, self.boosts = followers or {}, statuses or {}, favs or {}, boosts or {}
        self.calls = []

    def statuses(self, account_id):
        self.calls.append(("statuses", account_id))
        return self.status_rows.get(account_id, [])

    def engagers(self, status_id, kind):
        self.calls.append(("engagers", status_id, kind))
        return (self.favs if kind == "favourites" else self.boosts).get(status_id, [])

    def neighbors(self, account_id, kind, cursor):
        self.calls.append(("neighbors", account_id, kind, cursor))
        rows = self.followers.get(account_id, []) if kind == "followers" else []
        start = int(cursor or 0)
        chunk = rows[start:start + mp.PAGE]
        nxt = str(start + mp.PAGE) if start + mp.PAGE < len(rows) else None
        return chunk, nxt


class ClassifyTests(unittest.TestCase):
    def test_complete_account_is_scored_without_extra_hydration(self):
        reject, hits, spanish, followers = mp.classify(account("a@masto.es", "Lectora de fantasía y novela juvenil"))
        self.assertIsNone(reject)
        self.assertTrue(spanish)
        self.assertGreaterEqual(hits, 3)
        self.assertEqual(followers, 300)

    def test_discards_only_the_safe_cases(self):
        self.assertEqual(mp.classify(account("b", "Libros", bot=True))[0], "bot")
        self.assertEqual(mp.classify(account("c", "Libros", last_status_at="2020-01-01"))[0], "inactiva")
        self.assertIsNotNone(mp.classify(account("d", "OnlyFans y libros"))[0])
        self.assertEqual(mp.classify(account("e", "Libros", following_count=9000, followers_count=40))[0], "granja de follows")
        self.assertIsNone(mp.classify(account("f", "Libros de fantasía", followers_count=90000))[0])      # enorme: no se descarta (puede recibir favoritos)
        self.assertEqual(mp.classify(account("g.brid.gy@bsky.brid.gy", "Libros"))[0], "cuenta puente")

    def test_seed_quality_needs_spanish_niche_audience(self):
        self.assertTrue(mp.seed_quality(account("ed@mast.lat", "Editorial independiente de narrativa, poesía y ensayo en español")))
        self.assertFalse(mp.seed_quality(account("en", "Fantasy writer and book reader, my new book is out")))
        self.assertFalse(mp.seed_quality(account("tiny", "Lectora de fantasía y novela", followers_count=10)))


class MiningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = mp.connect(os.path.join(self.tmp.name, "pool.sqlite3"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_followers_are_paged_with_cursor_and_counted_per_distinct_seed(self):
        fans = [account(f"lector{i}@masto.es", "Lector de fantasía y libros") for i in range(120)]
        api = FakeApi(followers={"1": fans[:100], "2": fans[50:120]})
        seeds = {"ed1": {"account_id": "1"}, "ed2": {"account_id": "2"}}
        result = mp.mine(self.db, api, seeds, pages=30, today=TODAY, pause=0)
        self.assertEqual(result["new"], 120)
        shared = self.db.execute("SELECT seeds_count FROM accounts WHERE acct='lector60@masto.es'").fetchone()[0]
        single = self.db.execute("SELECT seeds_count FROM accounts WHERE acct='lector10@masto.es'").fetchone()[0]
        self.assertEqual((shared, single), (2, 1))

    def test_cursor_resumes_after_the_budget_runs_out(self):
        fans = [account(f"p{i}@masto.es", "Escritor de novela") for i in range(200)]
        api = FakeApi(followers={"1": fans})
        seeds = {"ed": {"account_id": "1"}}
        mp.mine(self.db, api, seeds, pages=2, today=TODAY, pause=0)      # 1 de conducta + 1 pagina de seguidores
        self.assertEqual(self.db.execute("SELECT cursor, done FROM mined WHERE seed='ed' AND kind='followers'").fetchone(), ("80", 0))
        mp.mine(self.db, api, seeds, pages=6, today=TODAY, pause=0)
        cursors = [c[3] for c in api.calls if c[0] == "neighbors" and c[2] == "followers"]
        self.assertEqual(cursors[:2], [None, "80"])                       # retoma donde lo dejo

    def test_engagement_reads_recent_popular_statuses_only(self):
        fresh = {"id": "s1", "created_at": TODAY + "T10:00:00Z", "favourites_count": 3, "reblogs_count": 1}
        stale = {"id": "s0", "created_at": "2020-01-01T10:00:00Z", "favourites_count": 40, "reblogs_count": 0}
        quiet = {"id": "s2", "created_at": TODAY + "T10:00:00Z", "favourites_count": 0, "reblogs_count": 1}
        api = FakeApi(statuses={"1": [fresh, stale, quiet]}, favs={"s1": [account("fan@masto.es", "")]}, boosts={"s1": [account("boo@masto.es", "Leo fantasía y novelas")]})
        mp.mine(self.db, api, {"ed": {"account_id": "1"}}, pages=5, today=TODAY, pause=0)
        asked = [c[1] for c in api.calls if c[0] == "engagers"]
        self.assertEqual(set(asked), {"s1"})
        rows = {r[0]: r[1:] for r in self.db.execute("SELECT acct, behav, first_source FROM accounts")}
        self.assertEqual(rows["fan@masto.es"], (1, "seed_favouriter"))
        self.assertEqual(rows["boo@masto.es"], (1, "seed_booster"))
        self.assertIn("fan@masto.es", {r["acct"] for r in mp.top_candidates(self.db, 10, today=TODAY, mark=False)})   # sin bio pero con conducta

    def test_hidden_follower_lists_are_marked_done(self):
        class Hidden(FakeApi):
            def neighbors(self, *a):
                raise RuntimeError("403 Forbidden")
        mp.mine(self.db, Hidden(), {"x": {"account_id": "9"}}, pages=5, today=TODAY, pause=0)
        self.assertEqual(self.db.execute("SELECT done FROM mined WHERE seed='x' AND kind='followers'").fetchone()[0], 1)

    def test_hubs_only_contribute_behavior(self):
        mp.upsert(self.db, account("hub@masto.es", "Reseñas de fantasía y novela juvenil, lectora y escritora", followers_count=900), "ed", "followers", TODAY)
        self.db.commit()
        hubs = mp.load_hubs(self.db, n=3)
        self.assertEqual(hubs, ["hub@masto.es"])
        api = FakeApi()
        mp.mine(self.db, api, {}, pages=5, today=TODAY, pause=0, hubs=hubs)
        self.assertTrue(api.calls)
        self.assertTrue(all(c[0] in ("statuses", "engagers") for c in api.calls))


class OfferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = mp.connect(os.path.join(self.tmp.name, "pool.sqlite3"))
        for i, bio in enumerate(["Lectora de fantasía y novela juvenil", "Escribo relatos y poesía en español", "Fan de motos y coches"]):
            mp.upsert(self.db, account(f"u{i}@masto.es", bio), "ed", "followers", TODAY)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_only_plausible_accounts_are_offered_and_rest_for_three_days(self):
        first = {r["acct"] for r in mp.top_candidates(self.db, 10, today=TODAY)}
        self.assertEqual(first, {"u0@masto.es", "u1@masto.es"})
        tomorrow = (datetime.date.fromisoformat(TODAY) + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(mp.top_candidates(self.db, 10, today=tomorrow), [])
        later = (datetime.date.fromisoformat(TODAY) + datetime.timedelta(days=4)).isoformat()
        self.assertTrue(mp.top_candidates(self.db, 10, today=later))

    def test_first_touch_is_immutable(self):
        mp.record_touch(self.db, {"a@x": "pool"}, TODAY)
        mp.record_touch(self.db, {"a@x": "hashtag_timeline"}, TODAY)
        self.assertEqual(mp.first_touch(self.db, ["a@x"]), {"a@x": "pool"})

    def test_scan_candidates_persist_without_counting_as_seeds(self):
        added = mp.record_scan_candidates(self.db, [(account("busq@masto.es", "Lectora de fantasía y novela"), "hashtag_timeline")], TODAY)
        self.assertEqual(added, 1)
        self.assertEqual(self.db.execute("SELECT seeds_count, first_source FROM accounts WHERE acct='busq@masto.es'").fetchone(), (0, "scan:hashtag_timeline"))

    def test_seeds_are_built_from_own_following_and_search(self):
        seeds = mp.build_seeds([account("ed@mast.lat", "Editorial independiente de narrativa y poesía en español")], [account("en", "Fantasy writer and book reader")], today=TODAY)
        self.assertEqual(set(seeds), {"ed@mast.lat"})
        self.assertEqual(seeds["ed@mast.lat"]["origin"], "siguiendo")


if __name__ == "__main__":
    unittest.main()


class CommonTests(unittest.TestCase):
    def test_both_pools_share_the_same_first_touch_and_cursor_implementation(self):
        import bluesky_pool as bpool
        import pool_common as pc
        self.assertIs(mp.first_touch, pc.first_touch)
        self.assertIs(bpool.first_touch, pc.first_touch)
        self.assertIs(mp.set_cursor, pc.set_cursor)
