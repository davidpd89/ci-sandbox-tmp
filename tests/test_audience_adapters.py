"""Offline API/export adapters contract tests with synthetic records only."""
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import audience_adapters as adapters
import audience_discovery as core

NOW = "2026-10-10T12:00:00Z"
POST = "2026-10-10T10:00:00Z"


class AdaptersTests(unittest.TestCase):
    def wrap(self, network, kind, payload, **kw):
        return adapters.adapt_page(network, kind, payload, post_key="p", post_created_at=POST, **kw)

    def test_bluesky_getlikes_with_cursor(self):
        p = self.wrap("bluesky", "like", {"likes": [
            {"actor": {"did": "did:plc:abc", "handle": "nueva.bsky.social"},
             "createdAt": "2026-10-10T11:00:00Z"}], "next_cursor": "c2"})
        self.assertEqual(p["next_cursor"], "c2")
        obs = core.normalize("bluesky", "like", p["items"][0], surface="liked_by",
            post_key="p", observed_at=NOW, post_created_at=POST)
        self.assertTrue(obs.stable_identity)
        self.assertEqual(obs.kind, "like")

    def test_bluesky_native_cursor_and_precedence(self):
        native = self.wrap("bluesky", "like", {"likes": [], "cursor": "bsky-next"})
        self.assertEqual(native["next_cursor"], "bsky-next")
        explicit = self.wrap("bluesky", "like", {"likes": [], "cursor": "native",
                                                  "next_cursor": "normalized"})
        self.assertEqual(explicit["next_cursor"], "normalized")

    def test_bluesky_getpostthread_nested_replies_and_placeholder(self):
        payload = {"thread": {"post": {
            "uri": "at://did:plc:root/app.bsky.feed.post/root",
            "author": {"did": "did:plc:root", "handle": "author.bsky.social"}},
            "replies": [
                {"$type": "app.bsky.feed.defs#threadViewPost",
                 "post": {"uri": "at://did:plc:one/app.bsky.feed.post/c1",
                          "author": {"did": "did:plc:one", "handle": "reader.bsky.social"},
                          "record": {"text": "Leo romantasy",
                                     "createdAt": "2026-10-10T11:30:00Z"}},
                 "replies": [
                     {"$type": "app.bsky.feed.defs#blockedPost"},
                     {"post": {"uri": "at://did:plc:two/app.bsky.feed.post/c2",
                               "author": {"did": "did:plc:two", "handle": "reader2.bsky.social"},
                               "record": {"text": "Recomiendo fantasía"}}}
                 ]},
                {"$type": "app.bsky.feed.defs#notFoundPost"}
            ]}}
        p = self.wrap("bluesky", "comment", payload)
        self.assertEqual(len(p["items"]), 2)
        self.assertEqual(p["unavailable"], 2)
        self.assertFalse(p["coverage_complete"])
        blocked = self.wrap("bluesky", "comment", {
            "thread": {"$type": "app.bsky.feed.defs#blockedPost"}})
        self.assertEqual(blocked["items"], [])
        self.assertFalse(blocked["coverage_complete"])
        self.assertEqual(p["items"][0]["event_id"], "at://did:plc:one/app.bsky.feed.post/c1")
        self.assertEqual(p["items"][1]["event_id"], "at://did:plc:two/app.bsky.feed.post/c2")
        normalized = [core.normalize("bluesky", "comment", x,
            surface="thread", post_key="p", observed_at=NOW,
            post_created_at=POST) for x in p["items"]]
        self.assertTrue(all(x.stable_identity for x in normalized))
        self.assertNotIn("id:did:plc:root", [x.account_key for x in normalized])

    def test_mastodon_native_descendants(self):
        p = self.wrap("mastodon", "comment", {"ancestors": [],
            "descendants": [{"id": "99", "account": {"id": "7", "acct": "reader"},
                             "content": "Una novela", "created_at": NOW}]},
            source_instance="mastodon.example")
        self.assertEqual(len(p["items"]), 1)
        normalized = core.normalize("mastodon", "comment", p["items"][0],
            surface="context", post_key="p", observed_at=NOW, post_created_at=POST)
        self.assertEqual(normalized.account_key, "id:mastodon.example:7")

    def test_reddit_nested_replies_and_unexpanded_morecomments(self):
        p = self.wrap("reddit", "comment", {"comments": [
            {"id": "c1", "author": "ana", "author_fullname": "t2_a",
             "replies": [{"id": "c2", "author": "bea", "author_fullname": "t2_b"}]}]})
        self.assertEqual([x["event_id"] for x in p["items"]], ["c1", "c2"])
        with self.assertRaisesRegex(core.ObservationError, "reddit_morecomments_sin_expandir"):
            self.wrap("reddit", "comment", {"comments": [
                {"id": "c1", "author": "ana", "replies": [{"kind": "more"}]}]})

    def test_mastodon_favourited_by_instance(self):
        p = self.wrap("mastodon", "like",
            {"items": [{"id": "21", "acct": "lectora@example.com"}],
             "paging": {"cursors": {"after": "page2"}, "next": "https://example/?token=x"}},
            source_instance="mastodon.example")
        self.assertEqual(p["next_cursor"], "page2")
        obs = core.normalize("mastodon", "like", p["items"][0], surface="favourited_by",
            post_key="p", observed_at=NOW, post_created_at=POST)
        self.assertEqual(obs.account_key, "id:mastodon.example:21")

    def test_reddit_comment_author_fullname(self):
        p = self.wrap("reddit", "comment", {"comments": [
            {"id": "t1", "author": "lector", "author_fullname": "t2_123",
             "body": "Me encantó la fantasía", "created_utc": 1791633600}]})
        item = core.normalize("reddit", "comment", p["items"][0], surface="comments",
            post_key="p", observed_at=NOW, post_created_at=POST)
        self.assertEqual(item.account_key, "id:t2_123")
        self.assertEqual(item.event_key, "p|comment|t1")

    def test_instagram_browser_export_with_comment_id(self):
        p = self.wrap("instagram", "comment", {"comments": [
            {"handle": "lectora", "author_id": "1234", "comment_id": "3456",
             "comment_text": "Me encantó ese libro"}]})
        item = core.normalize("instagram", "comment", p["items"][0],
            surface="seed_comments", post_key="p", observed_at=NOW, post_created_at=POST)
        self.assertEqual(item.account_key, "id:1234")
        self.assertTrue(item.stable_identity)

    def test_tiktok_mobile_export(self):
        p = self.wrap("tiktok", "reply", {"comments": [
            {"handle": "booktok", "comment_id": "t1", "comment_text": "Romantasy"}]})
        item = core.normalize("tiktok", "reply", p["items"][0],
            surface="video_comment", post_key="p", observed_at=NOW, post_created_at=POST)
        self.assertFalse(item.stable_identity)

    def test_tiktok_research_anonymous_author_is_rejected(self):
        with self.assertRaisesRegex(core.ObservationError, "actor_ausente"):
            self.wrap("tiktok", "comment",
                      {"comments": [{"id": "123", "text": "libros"}]})

    def test_pinterest_pin_metrics_do_not_expose_people(self):
        with self.assertRaisesRegex(core.ObservationError, "export_sin_lista"):
            self.wrap("pinterest", "comment", {"comment_count": 6, "reaction": 12})

    def test_facebook_graph_comments_data(self):
        p = self.wrap("facebook", "comment", {"data": [
            {"id": "c1", "from": {"id": "u17", "name": "Lectora"},
             "message": "Novelas de fantasía"}]})
        self.assertEqual(p["items"][0]["event_id"], "c1")
        self.assertEqual(p["items"][0]["actor"]["id"], "u17")

    def test_threads_replies_data(self):
        p = self.wrap("threads", "reply", {"data": [
            {"id": "r", "from": {"id": "u", "username": "lector"},
             "text": "Libro recomendado"}]})
        self.assertEqual(len(p["items"]), 1)

    def test_x_repost_users_and_no_auto_action(self):
        p = self.wrap("x", "repost", {"users": [
            {"id": "42", "screen_name": "letrillas"}]})
        x = core.normalize("x", "repost", p["items"][0], surface="repost_users",
            post_key="p", observed_at=NOW, post_created_at=POST)
        self.assertEqual(x.account_key, "id:42")
        self.assertEqual(x.kind, "repost")

    def test_missing_comment_id_is_not_fabricated(self):
        with self.assertRaisesRegex(core.ObservationError, "comentario_sin_id"):
            self.wrap("instagram", "comment",
                      {"comments": [{"handle": "lectora", "comment": "hola"}]})

    def test_unsupported_signal_and_bad_cursors(self):
        with self.assertRaisesRegex(core.ObservationError, "fuente_no_observable"):
            self.wrap("reddit", "like", {"items": []})
        with self.assertRaisesRegex(core.ObservationError, "cursor_tipo_invalido"):
            self.wrap("bluesky", "like", {"likes": [], "next_cursor": {"bad": 1}})

    def test_empty_explicit_list_is_legitimate(self):
        p = self.wrap("bluesky", "like", {"likes": []})
        self.assertEqual(p["items"], [])
        self.assertIsNone(p["next_cursor"])

    def test_atomic_adapter_validation(self):
        with self.assertRaisesRegex(core.ObservationError, "actor_ausente"):
            self.wrap("reddit", "comment", {"comments": [
                {"id": "a", "author": "lector"},
                {"id": "b", "body": "anónimo"}]})


if __name__ == "__main__":
    unittest.main()
