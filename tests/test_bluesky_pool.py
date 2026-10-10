import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import bluesky_pool as pool

TODAY = "2026-10-05"


def profile(handle, bio="", **extra):
    base = {"did": "did:plc:" + handle.split(".")[0], "handle": handle, "displayName": handle.split(".")[0], "description": bio}
    base.update(extra)
    return base


class FakeApi:
    """getFollowers/getFollows paginados, getProfiles, getAuthorFeed/getLikes/getRepostedBy, sin red."""

    def __init__(self, followers_by_seed, detailed=None, feeds=None, likes=None, reposts=None):
        self.followers_by_seed = followers_by_seed
        self.detailed = detailed or {}
        self.feeds = feeds or {}
        self.likes = likes or {}
        self.reposts = reposts or {}
        self.calls = []

    def __call__(self, path, params):
        self.calls.append((path, dict(params)))
        if path == "app.bsky.actor.getProfiles":
            return {"profiles": [self.detailed[did] for did in params["actors"] if did in self.detailed]}
        if path == "app.bsky.feed.getAuthorFeed":
            return {"feed": self.feeds.get(params["actor"], [])}
        if path == "app.bsky.feed.getLikes":
            return {"likes": [{"actor": p} for p in self.likes.get(params["uri"], [])]}
        if path == "app.bsky.feed.getRepostedBy":
            return {"repostedBy": self.reposts.get(params["uri"], [])}
        key = "followers" if path.endswith("getFollowers") else "follows"
        rows = self.followers_by_seed.get(params["actor"], []) if key == "followers" else []
        start = int(params.get("cursor") or 0)
        chunk = rows[start:start + pool.PAGE]
        nxt = str(start + pool.PAGE) if start + pool.PAGE < len(rows) else None
        out = {key: chunk}
        if nxt:
            out["cursor"] = nxt
        return out


class ClassifyTests(unittest.TestCase):
    def test_basic_profile_without_counters_is_not_rejected_for_activity(self):
        reject, hits, spanish, followers = pool.classify(profile("a.bsky.social", "Lectora de fantasía y novela juvenil, escribo reseñas"))
        self.assertIsNone(reject)
        self.assertTrue(spanish)
        self.assertGreaterEqual(hits, 3)
        self.assertIsNone(followers)

    def test_size_and_activity_no_longer_reject_only_the_obvious_follow_farm_does(self):
        self.assertIsNone(pool.classify(profile("b.bsky.social", "Libros", followersCount=90_000, postsCount=500))[0])      # enorme: el scan no la sigue, pero puede darle like
        self.assertIsNone(pool.classify(profile("c.bsky.social", "Libros", followersCount=10, postsCount=1))[0])
        self.assertIsNone(pool.classify(profile("d.bsky.social", "Libros", followersCount=200, followsCount=4000, postsCount=40))[0])   # lector muy activo, no granja
        self.assertEqual(pool.classify(profile("d2.bsky.social", "Libros", followersCount=20, followsCount=7000, postsCount=40))[0], "granja de follows")

    def test_only_negative_moderation_labels_reject(self):
        self.assertIsNone(pool.classify(profile("l1.bsky.social", "Libros", labels=[{"val": "bluesky-elder"}]))[0])
        self.assertIsNone(pool.classify(profile("l2.bsky.social", "Libros", labels=[{"val": "spam", "neg": True}]))[0])
        self.assertEqual(pool.classify(profile("l3.bsky.social", "Libros", labels=[{"val": "spam"}]))[0], "etiqueta spam")

    def test_spam_politics_and_adult_are_rejected(self):
        self.assertIsNotNone(pool.classify(profile("e.bsky.social", "follow back 100%, libros"))[0])
        self.assertIsNotNone(pool.classify(profile("f.bsky.social", "OnlyFans link in bio"))[0])
        self.assertIsNotNone(pool.classify(profile("g.bsky.social", "Votad al PSOE, lectora"))[0])

    def test_seed_quality_rejects_english_portuguese_and_catalan_seeds(self):
        self.assertTrue(pool.seed_quality({"bio": "Editorial independiente de narrativa, poesía y ensayo", "type": "editorial"}))
        self.assertFalse(pool.seed_quality({"bio": "Global Editorial Director at WIRED. Board member", "type": "editorial"}))
        self.assertFalse(pool.seed_quality({"bio": "Leituras que abrem caminhos! livros e mais livros", "type": "editorial"}))
        self.assertFalse(pool.seed_quality({"bio": "Editorial de llibres en català de literatura", "type": "editorial"}))


class MiningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = pool.connect(os.path.join(self.tmp.name, "pool.sqlite3"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_mining_pages_with_cursor_and_counts_distinct_seeds(self):
        fans = [profile(f"lector{i}.bsky.social", "Lector de fantasía y libros") for i in range(250)]
        api = FakeApi({"ed1.bsky.social": fans[:150], "ed2.bsky.social": fans[100:250]})
        result = pool.mine(self.db, api, ["ed1.bsky.social", "ed2.bsky.social"], pages=10, today=TODAY, pause=0)
        self.assertEqual(result["new"], 250)
        shared = self.db.execute("SELECT seeds_count FROM accounts WHERE handle='lector120.bsky.social'").fetchone()[0]
        single = self.db.execute("SELECT seeds_count FROM accounts WHERE handle='lector10.bsky.social'").fetchone()[0]
        self.assertEqual((shared, single), (2, 1))

    def test_budget_stops_mid_seed_and_cursor_resumes_next_run(self):
        fans = [profile(f"p{i}.bsky.social", "Escritor de novela") for i in range(300)]
        api = FakeApi({"ed.bsky.social": fans})
        first = pool.mine(self.db, api, ["ed.bsky.social"], pages=2, today=TODAY, pause=0)   # 1 peticion de conducta + 1 pagina de seguidores
        self.assertEqual(first["seen"], 100)
        cursor = self.db.execute("SELECT cursor, done FROM mined WHERE seed='ed.bsky.social' AND kind='followers'").fetchone()
        self.assertEqual((cursor[0], cursor[1]), ("100", 0))
        second = pool.mine(self.db, api, ["ed.bsky.social"], pages=4, today=TODAY, pause=0)
        self.assertEqual(second["new"], 200)
        followers_calls = [params for path, params in api.calls if path.endswith("getFollowers")]
        self.assertEqual(followers_calls[1].get("cursor"), "100")      # retoma donde lo dejo, no vuelve a empezar

    def test_missing_seed_is_marked_done_instead_of_retried(self):
        def api(path, params):
            raise RuntimeError("GET getFollowers fallo (400): Profile not found")
        pool.mine(self.db, api, ["gone.bsky.social"], pages=3, today=TODAY, pause=0)
        done = self.db.execute("SELECT done FROM mined WHERE seed='gone.bsky.social' AND kind='followers'").fetchone()[0]
        self.assertEqual(done, 1)

    def test_enrich_hydrates_counters_and_rejects_follow_farms(self):
        fans = [profile("granja.bsky.social", "Autor de libros de fantasía y novela"), profile("normal.bsky.social", "Lectora de fantasía y novela")]
        detailed = {
            fans[0]["did"]: dict(fans[0], followersCount=20, followsCount=9000, postsCount=900),
            fans[1]["did"]: dict(fans[1], followersCount=400, followsCount=300, postsCount=120),
        }
        api = FakeApi({"ed.bsky.social": fans}, detailed)
        pool.mine(self.db, api, ["ed.bsky.social"], pages=4, today=TODAY, pause=0)
        pool.enrich(self.db, api, limit=10)
        rows = {row[0]: row[1] for row in self.db.execute("SELECT handle, reject FROM accounts")}
        self.assertEqual(rows["granja.bsky.social"], "granja de follows")
        self.assertIsNone(rows["normal.bsky.social"])

    def test_likers_and_reposters_of_recent_seed_posts_become_behavioral_evidence(self):
        post = {"uri": "at://did:plc:ed/app.bsky.feed.post/1", "author": {"handle": "ed.bsky.social"}, "likeCount": 3, "repostCount": 1,
                "record": {"createdAt": "2026-10-04T10:00:00Z"}}
        old = {"uri": "at://did:plc:ed/app.bsky.feed.post/0", "author": {"handle": "ed.bsky.social"}, "likeCount": 9, "repostCount": 0,
               "record": {"createdAt": "2026-08-01T10:00:00Z"}}
        repost_by_seed = {"post": {"uri": "at://did:plc:x/app.bsky.feed.post/9", "author": {"handle": "otro.bsky.social"}, "likeCount": 50, "repostCount": 5,
                                   "record": {"createdAt": "2026-10-04T10:00:00Z"}}, "reason": {"$type": "reasonRepost"}}
        api = FakeApi({}, feeds={"ed.bsky.social": [{"post": post}, {"post": old}, repost_by_seed]},
                      likes={post["uri"]: [profile("liker.bsky.social", "")]}, reposts={post["uri"]: [profile("rep.bsky.social", "Leo fantasía y novelas")]})
        pool.mine(self.db, api, ["ed.bsky.social"], pages=3, today=TODAY, pause=0)
        rows = {r[0]: r[1:] for r in self.db.execute("SELECT handle, behav, first_source, last_engaged FROM accounts")}
        self.assertEqual(rows["liker.bsky.social"], (1, "seed_liker", TODAY))
        self.assertEqual(rows["rep.bsky.social"][1], "seed_reposter")
        asked = [params.get("uri") for path, params in api.calls if path.endswith("getLikes")]
        self.assertEqual(asked, [post["uri"]])         # ni el post viejo ni el repost ajeno se leen
        self.assertIn("liker.bsky.social", {r["handle"] for r in pool.top_candidates(self.db, 10, today=TODAY, mark=False)})   # sin bio pero con conducta

    def test_hubs_are_niche_accounts_whose_likers_get_mined_but_not_their_graph(self):
        hub = profile("hub.bsky.social", "Reseñas de fantasía y novela juvenil, lectora y escritora")
        pool.upsert(self.db, dict(hub, followersCount=900, followsCount=300, postsCount=400), "ed.bsky.social", "followers", TODAY)
        pool.upsert(self.db, dict(profile("pequeno.bsky.social", "Libros"), followersCount=20, followsCount=30, postsCount=4), "ed.bsky.social", "followers", TODAY)
        self.db.execute("UPDATE accounts SET enriched = 1")
        hubs = pool.load_hubs(self.db, n=5)
        self.assertEqual(hubs, ["hub.bsky.social"])
        post = {"uri": "at://did:plc:hub/app.bsky.feed.post/1", "author": {"handle": "hub.bsky.social"}, "likeCount": 4, "repostCount": 0,
                "record": {"createdAt": "2026-10-04T10:00:00Z"}}
        api = FakeApi({}, feeds={"hub.bsky.social": [{"post": post}]}, likes={post["uri"]: [profile("fan.bsky.social", "Leo fantasía")]})
        pool.mine(self.db, api, [], pages=5, today=TODAY, pause=0, hubs=hubs)
        kinds = {path for path, _ in api.calls}
        self.assertNotIn("app.bsky.graph.getFollowers", kinds)
        self.assertEqual(self.db.execute("SELECT behav FROM accounts WHERE handle='fan.bsky.social'").fetchone()[0], 1)

    def test_scan_candidates_are_persisted_without_counting_as_seeds(self):
        rows = [(profile("busq.bsky.social", "Lectora de fantasía y novela juvenil"), "post_search"),
                (profile("sinbio.bsky.social", None), "timeline")]
        rows[1][0]["description"] = None
        added = pool.record_scan_candidates(self.db, rows, TODAY)
        self.assertEqual(added, 2)  # DID+handle bastan: bio ausente se podrá enriquecer
        row = self.db.execute("SELECT seeds_count, first_source FROM accounts WHERE handle='busq.bsky.social'").fetchone()
        self.assertEqual(row, (0, "scan:post_search"))
        missing = self.db.execute(
            "SELECT did, enriched, bio FROM accounts WHERE handle='sinbio.bsky.social'"
        ).fetchone()
        self.assertEqual(missing, ("did:plc:sinbio", 0, ""))
        self.assertIn("busq.bsky.social", {r["handle"] for r in pool.top_candidates(self.db, 10, today=TODAY, mark=False)})   # bio del nicho en espanol: aprovechable

    def test_malformed_partial_profiles_are_safe_and_never_count_as_zero(self):
        invalid = [
            {"did": 123, "handle": "bad.bsky.social"},
            {"did": "did:plc:bad", "handle": ["bad.bsky.social"]},
            {"did": "not-did", "handle": "bad.bsky.social"},
            {"did": "did:plc:bad", "handle": "bad/unsafe"},
            {"did": "did:plc:", "handle": "valid.bsky.social"},
            {"did": "did:plc:bad", "handle": "bad with spaces.com"},
            {"did": "did:plc:bad", "handle": "bad_name.bsky.social"},
        ]
        self.assertEqual(pool.record_scan_candidates(
            self.db, [(profile, "scan") for profile in invalid], TODAY), 0)
        candidate = profile("partial.bsky.social", None,
                            followersCount=True, followsCount="invalid",
                            postsCount=-1, labels="bad",
                            displayName={"unexpected": "value"})
        candidate["description"] = {"invalid": "shape"}
        self.assertEqual(pool.record_scan_candidates(self.db,
                         [(candidate, "post_search")], TODAY), 1)
        self.assertEqual(self.db.execute(
            "SELECT followers, follows, posts, bio, enriched FROM accounts "
            "WHERE did='did:plc:partial'"
        ).fetchone(), (None, None, None, "", 0))

    def test_valid_did_web_and_ascii_handle_are_accepted(self):
        value = {"did": "did:web:reader.example.org",
                 "handle": "reader.example.org",
                 "description": "Lectora de fantasía"}
        self.assertEqual(pool.record_scan_candidates(self.db,
                         [(value, "post_search")], TODAY), 1)
        self.assertEqual(self.db.execute(
            "SELECT handle FROM accounts WHERE did='did:web:reader.example.org'"
        ).fetchone(), ("reader.example.org",))

    def test_first_source_is_immutable_and_touch_records_first_scan_source(self):
        fan = profile("x.bsky.social", "Lectora de fantasía y novela")
        pool.upsert(self.db, fan, "ed1.bsky.social", "followers", TODAY)
        pool.upsert(self.db, fan, "ed2.bsky.social", "liked", "2026-10-06")
        self.assertEqual(self.db.execute("SELECT first_source, first_source_at FROM accounts WHERE handle='x.bsky.social'").fetchone(), ("seed_follower", TODAY))
        pool.record_touch(self.db, {"a.bsky.social": "pool", "b.bsky.social": "post_search"}, TODAY)
        pool.record_touch(self.db, {"a.bsky.social": "jetstream_cache"}, "2026-10-09")
        self.assertEqual(pool.first_touch(self.db, ["a.bsky.social", "b.bsky.social", "c.bsky.social"]), {"a.bsky.social": "pool", "b.bsky.social": "post_search"})

    def test_basic_view_does_not_overwrite_hydrated_counters(self):
        fan = profile("x.bsky.social", "Lectora de fantasía y novela")
        pool.upsert(self.db, dict(fan, followersCount=500, followsCount=100, postsCount=50), "ed1.bsky.social", "followers", TODAY)
        pool.upsert(self.db, fan, "ed2.bsky.social", "followers", TODAY)       # la vista basica de otra semilla
        row = self.db.execute("SELECT followers, enriched, seeds_count FROM accounts WHERE handle='x.bsky.social'").fetchone()
        self.assertEqual(row, (500, 1, 2))


class OfferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = pool.connect(os.path.join(self.tmp.name, "pool.sqlite3"))
        for i, bio in enumerate(["Lectora de fantasía y novela juvenil", "Escribo relatos y poesía en español", "Fan de motos y coches"]):
            pool.upsert(self.db, profile(f"u{i}.bsky.social", bio), "ed.bsky.social", "followers", TODAY)
        pool.upsert(self.db, profile("u9.bsky.social", ""), "ed.bsky.social", "followers", TODAY)
        pool.upsert(self.db, profile("u9.bsky.social", ""), "ed2.bsky.social", "followers", TODAY)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_only_plausible_spanish_niche_accounts_are_offered(self):
        handles = {row["handle"] for row in pool.top_candidates(self.db, 10, today=TODAY, mark=False)}
        self.assertIn("u0.bsky.social", handles)
        self.assertIn("u9.bsky.social", handles)          # sin bio pero en el grafo de dos semillas
        self.assertNotIn("u2.bsky.social", handles)       # motos: sin nicho ni idioma ni segunda semilla

    def test_offered_accounts_rest_for_three_days_then_return(self):
        first = pool.top_candidates(self.db, 10, today=TODAY)
        self.assertTrue(first)
        self.assertEqual(pool.top_candidates(self.db, 10, today="2026-10-06"), [])
        again = pool.top_candidates(self.db, 10, today="2026-10-08")
        self.assertEqual({r["handle"] for r in again}, {r["handle"] for r in first})

    def test_exclude_skips_known_handles(self):
        rows = pool.top_candidates(self.db, 10, today=TODAY, mark=False, exclude={"u0.bsky.social"})
        self.assertNotIn("u0.bsky.social", {row["handle"] for row in rows})


    def test_mark_offered_by_did_is_idempotent_even_if_handle_changes(self):
        before = profile("lector.bsky.social", "Lectora de fantasía y novela")
        pool.upsert(self.db, before, "semilla.bsky.social", "followers", TODAY)
        self.db.commit()
        did = before["did"]
        self.assertEqual(pool.mark_offered(self.db, [did, did], today=TODAY), 1)
        self.assertEqual(pool.mark_offered(self.db, [did], today=TODAY), 0)
        pool.upsert(self.db, dict(before, handle="lectora.example"), "otra.bsky.social",
                    "followers", TODAY)
        self.db.commit()
        counts = self.db.execute(
            "SELECT COUNT(*), MAX(offered_count) FROM accounts WHERE did=?", (did,)
        ).fetchone()
        self.assertEqual(counts, (1, 1))
        self.assertEqual(pool.mark_offered(self.db, [did], today="2026-10-08"), 1)
        self.assertEqual(self.db.execute(
            "SELECT offered_count FROM accounts WHERE did=?", (did,)
        ).fetchone()[0], 2)

    def test_mark_offered_write_failure_rolls_back_entire_batch(self):
        # Si SQLite aborta a mitad de una tanda, el primer DID no debe
        # quedar marcado sin que el resto pueda conservar su estado.
        self.db.execute("""
            CREATE TRIGGER reject_second_offer BEFORE UPDATE OF offered_at ON accounts
            WHEN NEW.did = 'did:plc:u1'
            BEGIN SELECT RAISE(ABORT, 'synthetic disk rejection'); END
        """)
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            pool.mark_offered(self.db, ["did:plc:u0", "did:plc:u1"], today=TODAY)
        counts = self.db.execute(
            "SELECT offered_at, offered_count FROM accounts WHERE did='did:plc:u0'"
        ).fetchone()
        self.assertEqual(counts, (None, 0))

    def test_mark_offered_inside_caller_transaction_can_roll_back(self):
        did = "did:plc:u0"
        self.db.execute("BEGIN IMMEDIATE")
        self.assertEqual(pool.mark_offered(self.db, [did], today=TODAY, commit=False), 1)
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()
        self.assertEqual(self.db.execute(
            "SELECT offered_at, offered_count FROM accounts WHERE did=?", (did,)
        ).fetchone(), (None, 0))

    def test_mark_offered_commit_false_rejects_unprotected_connection(self):
        self.assertFalse(self.db.in_transaction)
        with self.assertRaisesRegex(RuntimeError, "transacción activa"):
            pool.mark_offered(self.db, ["did:plc:u0"], today=TODAY, commit=False)
        self.assertEqual(self.db.execute(
            "SELECT offered_at FROM accounts WHERE did='did:plc:u0'"
        ).fetchone(), (None,))

    def test_mark_true_cannot_select_stale_rows_during_other_claim(self):
        # Consumidor legacy (mark=True) no debe devolver filas ya reclamadas
        # por otro escáner con BEGIN IMMEDIATE, aunque pueda leer su snapshot.
        other = sqlite3.connect(os.path.join(self.tmp.name, "pool.sqlite3"),
                                timeout=0.01)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            with self.assertRaises(sqlite3.OperationalError):
                pool.top_candidates(other, 10, today=TODAY, mark=True)
            selected = pool.top_candidates(self.db, 10, today=TODAY, mark=False)
            pool.mark_offered(self.db, (row["did"] for row in selected),
                              today=TODAY, commit=False)
            self.db.commit()
            self.assertEqual(pool.top_candidates(other, 10, today=TODAY,
                                                  mark=True), [])
        finally:
            if self.db.in_transaction:
                self.db.rollback()
            other.close()

    def test_selection_without_mark_does_not_consume_reserve(self):
        first = pool.top_candidates(self.db, 10, today=TODAY, mark=False)
        second = pool.top_candidates(self.db, 10, today=TODAY, mark=False)
        self.assertEqual([r["did"] for r in first], [r["did"] for r in second])
        self.assertGreater(len(first), 0)
        self.assertEqual(pool.mark_offered(self.db, [r["did"] for r in first], today=TODAY),
                         len(first))
        self.assertFalse(pool.top_candidates(self.db, 10, today=TODAY, mark=False))

    def test_stats_report_available_accounts(self):
        info = pool.stats(self.db, today=TODAY)
        self.assertEqual(info["accounts"], 4)
        self.assertGreaterEqual(info["available_now"], 3)


if __name__ == "__main__":
    unittest.main()
