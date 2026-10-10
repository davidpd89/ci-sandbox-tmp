"""Regression suite: all observations and profiles are synthetic; no sessions."""
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import audience_discovery as ad

NOW = "2026-10-10T12:00:00+00:00"
POST = "2026-10-09T12:00:00+00:00"


def actor(network, uid="7", handle="lectora"):
    if network == "bluesky":
        return {"did": "did:plc:" + uid, "handle": handle, "bio": "Leo romantasy"}
    if network == "mastodon":
        return {"id": uid, "acct": handle + "@example.org", "bio": "Leo romantasy"}
    return {"id": uid, "username": handle, "bio": "Leo romantasy"}


def event(network="bluesky", kind="comment", uid="7", handle="lectora", **kw):
    row = {"actor": actor(network, uid, handle), "event_id": "event-" + uid,
           "text": "¿Qué libro de fantasía recomiendas?"}
    row.update(kw)
    if network == "mastodon":
        row["instance"] = "mastodon.example"
    return ad.normalize(network, kind, row, surface="own_post",
                        post_key="p1", observed_at=kw.get("observed_at", NOW),
                        post_created_at=kw.get("post_created_at", POST))


class AudienceTests(unittest.TestCase):
    def setUp(self):
        self.store = ad.AudienceStore()

    def tearDown(self):
        self.store.close()

    def ingest(self, rows, network="bluesky", surface="own_post", cursor=None):
        return self.store.ingest(rows, network=network, surface=surface,
                                 seed="seed", next_cursor=cursor, now=NOW)

    def test_all_nine_networks_and_lanes(self):
        self.assertEqual(len(ad.LANES), 9)
        for network in ad.LANES:
            with self.subTest(network=network):
                kind = "comment"
                item = event(network, kind)
                self.assertEqual(item.network, network)
                self.assertTrue(item.stable_identity)
                self.assertEqual(ad.CAPABILITIES[network]["comment"] is not None, True)

    def test_unobservable_not_zero(self):
        self.assertIsNone(ad.CAPABILITIES["reddit"]["like"])
        self.assertIsNone(ad.CAPABILITIES["pinterest"]["like"])
        self.assertIsNone(ad.CAPABILITIES["tiktok"]["like"])

    def test_core_rejects_unobservable_actors_for_all_networks(self):
        for network, caps in ad.CAPABILITIES.items():
            for kind, capability in caps.items():
                if capability is None:
                    with self.subTest(network=network, kind=kind):
                        with self.assertRaisesRegex(ad.ObservationError, "fuente_no_observable"):
                            ad.normalize(network, kind, {"actor": actor(network)},
                                         surface="own_post", post_key="p",
                                         observed_at=NOW, post_created_at=POST)

    def test_first_seen_and_exact_replay(self):
        item = event()
        self.assertEqual(self.ingest([item])["new_people"], 1)
        self.assertEqual(self.ingest([item])["replays"], 1)
        self.assertEqual(len(self.store.ranked("bluesky")), 1)

    def test_like_edges_without_event_id_deduplicate(self):
        raw = {"actor": actor("bluesky"), "text": ""}
        first = ad.normalize("bluesky", "like", raw, surface="liked_by",
                             post_key="p1", observed_at=NOW, post_created_at=POST)
        self.assertIn("p1|like|", first.event_key)
        self.assertEqual(self.store.ingest([first, first], network="bluesky",
            surface="liked_by", seed="seed", next_cursor=None, now=NOW)["new_events"], 1)

    def test_comment_requires_real_event_id(self):
        with self.assertRaisesRegex(ad.ObservationError, "evento_sin_id"):
            ad.normalize("reddit", "comment", {"actor": actor("reddit")},
                         surface="comments", post_key="post", observed_at=NOW)

    def test_no_author_from_post_id(self):
        with self.assertRaisesRegex(ad.ObservationError, "actor_ausente"):
            ad.normalize("x", "repost", {"id": "a-post-id"},
                         surface="retweets", post_key="p", observed_at=NOW)

    def test_identity_rename_same_stable_id(self):
        first = event()
        later = event(handle="nuevo_nombre", observed_at="2026-10-10T12:01:00Z")
        self.ingest([first])
        self.ingest([later])
        self.assertEqual(self.store.ranked("bluesky")[0]["handle"], "nuevo_nombre")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM audience_accounts").fetchone()[0], 1)

    def test_out_of_order_profile_does_not_rollback(self):
        newer = event(handle="nuevo", observed_at="2026-10-10T12:02:00Z")
        older = event(handle="viejo", observed_at=NOW)
        self.ingest([newer])
        self.ingest([older])
        self.assertEqual(self.store.ranked("bluesky")[0]["handle"], "nuevo")

    def test_provisional_handles_not_falsely_merged(self):
        for h in ("ana", "ana2"):
            raw = {"actor": {"handle": h}, "event_id": h}
            obs = ad.normalize("instagram", "comment", raw,
                    surface="own_post", post_key="p1", observed_at=NOW,
                    post_created_at=POST)
            self.ingest([obs], network="instagram")
        self.assertEqual(len(self.store.ranked("instagram")), 2)
        self.assertTrue(all(not x["stable_identity"] for x in self.store.ranked("instagram")))

    def test_late_create_cannot_undo_newer_delete(self):
        created = event(occurred_at="2026-10-10T09:00:00Z",
                        observed_at="2026-10-10T09:00:00Z")
        deleted = event(occurred_at="2026-10-10T10:00:00Z",
                        observed_at="2026-10-10T10:00:00Z", deleted=True)
        replay = event(occurred_at="2026-10-10T09:30:00Z",
                       observed_at="2026-10-10T12:00:00Z")
        self.ingest([created])
        self.ingest([deleted])
        stats = self.ingest([replay])
        self.assertEqual(stats["replays"], 1)
        self.assertEqual(self.store.ranked("bluesky", now=NOW), [])

    def test_ranking_rechecks_post_age_after_storage(self):
        self.ingest([event()])
        self.assertEqual(len(self.store.ranked("bluesky", now=NOW)), 1)
        self.assertEqual(self.store.ranked("bluesky",
                         now="2026-10-25T00:00:00Z"), [])

    def test_mastodon_local_ids_are_instance_scoped(self):
        a = event("mastodon")
        row = {"actor": actor("mastodon"), "instance": "other.example", "event_id": "e"}
        b = ad.normalize("mastodon", "comment", row, surface="own_post",
                post_key="p1", observed_at=NOW, post_created_at=POST)
        self.assertNotEqual(a.account_key, b.account_key)

    def test_mastodon_local_post_ids_are_instance_scoped(self):
        obs = []
        for domain in ("mastodon.example", "other.example"):
            row = {"actor": {"id": "7", "acct": "lectora@" + domain},
                   "instance": domain, "event_id": "99"}
            obs.append(ad.normalize("mastodon", "comment", row,
                surface="own_post", post_key="42", observed_at=NOW,
                post_created_at=POST))
        self.assertNotEqual(obs[0].event_key, obs[1].event_key)
        self.ingest(obs, network="mastodon")
        self.assertEqual(len(self.store.ranked("mastodon")), 2)

    def test_mastodon_without_instance_is_provisional(self):
        raw = {"actor": actor("mastodon"), "event_id": "e"}
        obs = ad.normalize("mastodon", "comment", raw, surface="own_post",
                post_key="p1", observed_at=NOW, post_created_at=POST)
        self.assertFalse(obs.stable_identity)

    def test_delete_tombstone_blocks_older_replay(self):
        initial = event(occurred_at="2026-10-10T11:00:00Z")
        deleted = event(deleted=True, observed_at="2026-10-10T12:05:00Z")
        self.ingest([initial])
        self.ingest([deleted])
        self.ingest([initial])
        self.assertEqual(len(self.store.ranked("bluesky")), 0)
        self.assertEqual(self.store.db.execute(
            "SELECT active FROM audience_events").fetchone()[0], 0)

    def test_orphan_delete_tombstone_does_not_count_as_new_reader(self):
        deleted = event(deleted=True, occurred_at="2026-10-10T11:00:00Z")
        stats = self.ingest([deleted])
        self.assertEqual(stats["new_people"], 0)
        self.assertEqual(stats["new_events"], 1)
        self.assertEqual(self.store.ranked("bluesky", now=NOW), [])
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM audience_accounts").fetchone()[0], 0)

    def test_sqlite_file_concurrent_connection_writer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(pathlib.Path(directory) / "queue.db")
            first = ad.AudienceStore(path)
            second = ad.AudienceStore(path)
            first.ingest([event(uid="1")], network="bluesky",
                         surface="own_post", seed="a", next_cursor=None, now=NOW)
            second.ingest([event(uid="2")], network="bluesky",
                          surface="own_post", seed="b", next_cursor=None, now=NOW)
            self.assertEqual(len(first.ranked("bluesky", now=NOW)), 2)
            self.assertEqual(len(second.ranked("bluesky", now=NOW)), 2)
            first.close()
            second.close()

    def test_concurrent_collectors_cannot_roll_back_cursor(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(pathlib.Path(directory) / "audience.sqlite")
            first = ad.AudienceStore(path)
            second = ad.AudienceStore(path)
            try:
                first.ingest([], network="bluesky", surface="liked_by", seed="s",
                             next_cursor="A", now=NOW)
                stale_read = second.cursor("bluesky", "liked_by", "s")
                self.assertEqual(stale_read, "A")
                first.ingest([], network="bluesky", surface="liked_by", seed="s",
                             next_cursor="B", now=NOW, expected_cursor="A")
                liker = ad.normalize("bluesky", "like",
                    {"actor": actor("bluesky", "99")}, surface="liked_by",
                    post_key="p1", observed_at=NOW, post_created_at=POST)
                with self.assertRaisesRegex(ad.ObservationError, "cursor_cambiado"):
                    second.ingest([liker], network="bluesky",
                        surface="liked_by", seed="s", next_cursor="C",
                        now=NOW, expected_cursor=stale_read)
                self.assertEqual(first.cursor("bluesky", "liked_by", "s"), "B")
                self.assertEqual(first.db.execute(
                    "SELECT count(*) FROM audience_events").fetchone()[0], 0)
            finally:
                first.close()
                second.close()

    def test_stale_posts_excluded_but_recent_stored(self):
        old = event(post_created_at="2026-09-01T12:00:00Z")
        stats = self.ingest([old])
        self.assertEqual(stats["stale_posts"], 1)
        self.assertEqual(stats["new_people"], 0)

    def test_unknown_post_age_kept_but_not_action_ranked(self):
        raw = {"actor": actor("bluesky"), "event_id": "x"}
        obs = ad.normalize("bluesky", "comment", raw, surface="own_post",
                           post_key="p", observed_at=NOW)
        self.assertEqual(self.ingest([obs])["unverified_age"], 1)
        self.assertEqual(self.store.ranked("bluesky"), [])
        self.assertEqual(len(self.store.ranked("bluesky", require_verified_age=False)), 1)

    def test_strict_timezone_and_bad_input(self):
        with self.assertRaisesRegex(ad.ObservationError, "timestamp_sin_zona"):
            ad.timestamp("2026-10-10T12:00:00")
        with self.assertRaises(ad.ObservationError):
            ad.timestamp("nada")

    def test_page_atomicity_with_mixed_networks(self):
        with self.assertRaisesRegex(ad.ObservationError, "origen_cruzado"):
            self.ingest([event(), event("mastodon")])
        self.assertEqual(self.store.db.execute(
            "SELECT COUNT(*) FROM audience_events").fetchone()[0], 0)
        self.assertIsNone(self.store.cursor("bluesky", "own_post", "seed"))

    def test_page_cursor_and_resume(self):
        calls = []
        pages = {
            None: {"items": [{"actor": actor("reddit", "1"), "event_id": "c1"}],
                   "kind": "comment", "post_key": "p1",
                   "post_created_at": POST, "next_cursor": "p2"},
            "p2": {"items": [{"actor": actor("reddit", "2"), "event_id": "c2"}],
                   "kind": "comment", "post_key": "p1",
                   "post_created_at": POST, "next_cursor": None},
        }
        def fetch(cur):
            calls.append(cur)
            return pages[cur]
        first = ad.collect_pages(self.store, network="reddit", surface="comments",
            seed="seed", fetch_page=fetch, observed_at=NOW, max_pages=1)
        self.assertEqual(first["new_people"], 1)
        self.assertFalse(first["complete"])
        self.assertEqual(self.store.cursor("reddit", "comments", "seed"), "p2")
        second = ad.collect_pages(self.store, network="reddit", surface="comments",
            seed="seed", fetch_page=fetch, observed_at=NOW, max_pages=2)
        self.assertEqual(second["new_people"], 1)
        self.assertEqual(calls, [None, "p2"])
        self.assertTrue(second["complete"])

    def test_cursor_loop_raises_without_advancing(self):
        def fetch(cur):
            return {"items": [], "kind": "like", "post_key": "p",
                    "next_cursor": cur or "loop"}
        with self.assertRaisesRegex(ad.ObservationError, "cursor_ciclico"):
            ad.collect_pages(self.store, network="bluesky", surface="liked_by",
                seed="seed", fetch_page=fetch, observed_at=NOW, max_pages=3)
        self.assertEqual(self.store.cursor("bluesky", "liked_by", "seed"), "loop")

    def test_failure_on_second_page_keeps_first_checkpoint(self):
        def fetch(cur):
            if cur is not None:
                raise RuntimeError("transient")
            return {"items": [{"actor": actor("bluesky"), "event_id": "a"}],
                    "kind": "comment", "post_key": "p", "post_created_at": POST,
                    "next_cursor": "next"}
        with self.assertRaisesRegex(RuntimeError, "transient"):
            ad.collect_pages(self.store, network="bluesky", surface="own_post",
                seed="seed", fetch_page=fetch, observed_at=NOW)
        self.assertEqual(self.store.cursor("bluesky", "own_post", "seed"), "next")
        self.assertEqual(len(self.store.ranked("bluesky")), 1)

    def test_dedup_per_post_and_multi_surface_ranking(self):
        first = event(uid="7")
        rival = event(uid="8")
        self.ingest([first, rival])
        raw = {"actor": actor("bluesky", "7"), "event_id": "c3",
               "text": "Recomiendo una novela"}
        extra = ad.normalize("bluesky", "reply", raw, surface="own_post",
                             post_key="p2", observed_at=NOW, post_created_at=POST)
        self.ingest([extra])
        ranking = self.store.ranked("bluesky")
        self.assertEqual(ranking[0]["handle"], "lectora")
        self.assertEqual(ranking[0]["posts"], 2)
        self.assertEqual(ranking[0]["signals"], 2)

    def test_multiple_surface_candidates_one_person(self):
        a = event()
        self.ingest([a])
        raw = {"actor": actor("bluesky"), "event_id": "b", "text": "Libros"}
        b = ad.normalize("bluesky", "comment", raw, surface="external_post",
             post_key="p2", observed_at=NOW, post_created_at=POST)
        self.store.ingest([b], network="bluesky", surface="external_post",
             seed="seed2", next_cursor=None, now=NOW)
        self.assertEqual(len(self.store.ranked("bluesky")), 1)
        self.assertEqual(self.store.ranked("bluesky")[0]["surfaces"], 2)

    def test_one_event_two_surfaces_preserves_provenance_without_double_count(self):
        first = event()
        raw = {"actor": actor("bluesky"), "event_id": "event-7",
               "text": "¿Qué libro de fantasía recomiendas?"}
        second = ad.normalize("bluesky", "comment", raw, surface="external_post",
             post_key="p1", observed_at=NOW, post_created_at=POST)
        self.ingest([first])
        stats = self.store.ingest([second], network="bluesky",
             surface="external_post", seed="other-seed", next_cursor=None, now=NOW)
        self.assertEqual(stats["new_events"], 0)
        self.assertEqual(stats["replays"], 1)
        self.assertEqual(self.store.ranked("bluesky")[0]["signals"], 1)
        self.assertEqual(self.store.ranked("bluesky")[0]["surfaces"], 2)
        # Dos avistamientos del mismo comentario no merecen bonus de afinidad.
        self.assertEqual(self.store.ranked("bluesky")[0]["score"], 6.0)
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM audience_sightings").fetchone()[0], 2)

    def test_provisional_id_promotion_requires_same_remote_event(self):
        raw = {"actor": {"handle": "lectora"}, "event_id": "c1"}
        first = ad.normalize("instagram", "comment", raw, surface="own_post",
            post_key="p1", observed_at=NOW, post_created_at=POST)
        self.ingest([first], network="instagram")
        later = ad.normalize("instagram", "comment",
            {"actor": {"id": "123", "handle": "lectora"}, "event_id": "c1"},
            surface="external_post", post_key="p1",
            observed_at="2026-10-10T12:01:00Z", post_created_at=POST)
        self.store.ingest([later], network="instagram", surface="external_post",
             seed="seed2", next_cursor=None, now=NOW)
        people = self.store.ranked("instagram")
        self.assertEqual(len(people), 1)
        self.assertEqual(people[0]["account_key"], "id:123")
        self.assertEqual(people[0]["signals"], 1)
        self.assertEqual(people[0]["surfaces"], 2)
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM audience_accounts").fetchone()[0], 1)
        # Una captura vieja sin ID no puede despromocionar el actor ni
        # reintroducir el alias como segunda persona.
        stats = self.ingest([first], network="instagram")
        self.assertEqual(stats["replays"], 1)
        self.assertEqual(len(self.store.ranked("instagram")), 1)
        self.assertEqual(self.store.ranked("instagram")[0]["account_key"], "id:123")

    def test_conflicting_actor_for_same_event_is_atomic(self):
        first = event()
        self.ingest([first])
        conflict = ad.normalize("bluesky", "comment",
            {"actor": actor("bluesky", "999"), "event_id": "event-7"},
            surface="external_post", post_key="p1",
            observed_at="2026-10-10T12:01:00Z", post_created_at=POST)
        with self.assertRaisesRegex(ad.ObservationError, "evento_actor_conflictivo"):
            self.store.ingest([conflict], network="bluesky",
                surface="external_post", seed="other", next_cursor="cursor", now=NOW)
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM audience_sightings").fetchone()[0], 1)
        self.assertIsNone(self.store.cursor("bluesky", "external_post", "other"))

    def test_cursor_cycle_across_restarts_does_not_commit_page(self):
        calls = []
        def fetch(cur):
            calls.append(cur)
            return {"items": [], "kind": "like", "post_key": "p",
                    "next_cursor": "A" if cur != "A" else "B"}
        for _ in range(2):
            ad.collect_pages(self.store, network="bluesky", surface="liked_by",
                seed="s", fetch_page=fetch, observed_at=NOW, max_pages=1)
        with self.assertRaisesRegex(ad.ObservationError, "cursor_ciclico"):
            ad.collect_pages(self.store, network="bluesky", surface="liked_by",
                seed="s", fetch_page=fetch, observed_at=NOW, max_pages=1)
        self.assertEqual(calls, [None, "A", "B"])
        self.assertEqual(self.store.cursor("bluesky", "liked_by", "s"), "B")

    def test_cursor_history_clears_on_finished_snapshot(self):
        def fetch(cur):
            return {"items": [], "kind": "like", "post_key": "p",
                    "next_cursor": "A" if cur is None else None}
        ad.collect_pages(self.store, network="bluesky", surface="liked_by",
            seed="s", fetch_page=fetch, observed_at=NOW)
        self.assertIsNone(self.store.cursor("bluesky", "liked_by", "s"))
        self.assertFalse(self.store.seen_cursor("bluesky", "liked_by", "s", "A"))
        again = ad.collect_pages(self.store, network="bluesky", surface="liked_by",
            seed="s", fetch_page=fetch, observed_at=NOW)
        self.assertTrue(again["complete"])

    def test_newer_sparse_import_cannot_erase_verified_age_or_text(self):
        self.ingest([event()])
        raw = {"actor": actor("bluesky"), "event_id": "event-7"}
        newer = ad.normalize("bluesky", "comment", raw, surface="external_post",
            post_key="p1", observed_at="2026-10-10T12:02:00Z")
        self.store.ingest([newer], network="bluesky", surface="external_post",
            seed="s2", next_cursor=None, now=NOW)
        self.assertEqual(self.store.ranked("bluesky")[0]["signals"], 1)
        row = self.store.db.execute(
            "SELECT post_created_at,text FROM audience_events").fetchone()
        self.assertIsNotNone(row[0])
        self.assertIn("fantasía", row[1])

    def test_incomplete_roster_never_claims_complete_snapshot(self):
        result = ad.collect_pages(self.store, network="bluesky", surface="thread",
            seed="s", fetch_page=lambda _: {
                "items": [], "kind": "comment", "post_key": "p1",
                "next_cursor": None, "coverage_complete": False},
            observed_at=NOW)
        self.assertEqual(result["pages"], 1)
        self.assertFalse(result["complete"])

    def test_sqlite_reopen_persists_cursor_and_rank(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(pathlib.Path(directory) / "audience.db")
            s = ad.AudienceStore(path)
            s.ingest([event()], network="bluesky", surface="own_post",
                     seed="s", next_cursor="bookmark", now=NOW)
            s.close()
            s = ad.AudienceStore(path)
            self.assertEqual(s.cursor("bluesky", "own_post", "s"), "bookmark")
            self.assertEqual(len(s.ranked("bluesky")), 1)
            s.close()

    def test_no_cross_network_identity_collision(self):
        self.ingest([event("bluesky")])
        self.ingest([event("reddit")], network="reddit")
        self.assertEqual(len(self.store.ranked("bluesky")), 1)
        self.assertEqual(len(self.store.ranked("reddit")), 1)


if __name__ == "__main__":
    unittest.main()
