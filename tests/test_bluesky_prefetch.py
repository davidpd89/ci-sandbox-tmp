"""Precarga en lote de viewer/cid/did (bluesky_interact.prefetch) y su uso por like/follow; sin red."""
import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import bluesky_interact as b

URIS = [f"at://did:plc:x/app.bsky.feed.post/{i}" for i in range(30)]


class PrefetchTests(unittest.TestCase):
    def setUp(self):
        b._PREFETCH.clear()

    def test_posts_and_profiles_are_fetched_in_batches_of_25(self):
        calls = []

        def fake_get(base, path, params, auth=True, **kw):
            calls.append((path, len(params.get("uris") or params.get("actors") or [])))
            if path.endswith("getPosts"):
                return {"posts": [{"uri": u, "cid": "c" + u[-2:], "viewer": {}} for u in params["uris"]]}
            return {"profiles": [{"did": "did:plc:" + a, "handle": a + ".bsky.social", "viewer": {"following": None}} for a in params["actors"]]}

        with patch.object(b, "_get", side_effect=fake_get):
            b.prefetch(uris=URIS, handles=["uno", "dos"])
        self.assertEqual(calls, [("app.bsky.feed.getPosts", 25), ("app.bsky.feed.getPosts", 5), ("app.bsky.actor.getProfiles", 2)])
        self.assertIsNotNone(b._prefetched(("post", URIS[0])))
        self.assertIsNone(b._prefetched(("post", URIS[0])))       # se consume: un estado usado ya no es fiable
        self.assertEqual(b._prefetched(("profile", "uno.bsky.social"))["did"], "did:plc:uno")

    def test_expired_entries_are_ignored(self):
        b._PREFETCH[("post", URIS[0])] = {"cid": "c", "viewer": {}, "t": time.time() - b.PREFETCH_TTL - 5}
        self.assertIsNone(b._prefetched(("post", URIS[0])))

    def test_a_failing_batch_is_skipped_not_fatal(self):
        def boom(*a, **k):
            raise RuntimeError("500")
        with patch.object(b, "_get", side_effect=boom):
            b.prefetch(uris=URIS[:3], handles=["x"])
        self.assertEqual(b._PREFETCH, {})

    def test_follow_uses_the_prefetched_profile_and_respects_following(self):
        posted = []
        b._PREFETCH[("profile", "nueva.bsky.social")] = {"did": "did:plc:n", "viewer": {"following": None}, "t": time.time()}
        with patch.object(b, "_require_credentials"), patch.object(b, "_get", side_effect=AssertionError("no debe leer")), \
             patch.object(b, "_session", return_value={"did": "did:plc:yo"}), \
             patch.object(b, "_post_xrpc", side_effect=lambda path, body: posted.append(body) or {"uri": "at://did:plc:yo/app.bsky.graph.follow/1", "cid": "c"}):
            self.assertEqual(b.follow("nueva.bsky.social"), "followed")
        self.assertEqual(posted[0]["record"]["subject"], "did:plc:n")
        b._PREFETCH[("profile", "ya.bsky.social")] = {"did": "did:plc:y", "viewer": {"following": "at://x"}, "t": time.time()}
        with patch.object(b, "_require_credentials"), patch.object(b, "_get", side_effect=AssertionError("no debe leer")):
            self.assertEqual(b.follow("ya.bsky.social"), "already")


class ResolveCacheTests(unittest.TestCase):
    def setUp(self):
        b._DID_CACHE.clear()

    def test_handle_resolution_is_memoized_and_warmed_in_parallel(self):
        calls = []

        def fake_get(base, path, params, auth=True, **kw):
            calls.append(params["handle"])
            return {"did": "did:plc:" + params["handle"].split(".")[0]}

        with patch.object(b, "_get", side_effect=fake_get):
            b.warm_dids(["uno.bsky.social", "dos.bsky.social", "@uno.bsky.social", "did:plc:ya"])
            self.assertEqual(sorted(calls), ["dos.bsky.social", "uno.bsky.social"])
            self.assertEqual(b._resolve_did("UNO.bsky.social"), "did:plc:uno")      # sin segunda peticion
            self.assertEqual(len(calls), 2)

    def test_warming_ignores_unresolvable_handles(self):
        def fake_get(base, path, params, auth=True, **kw):
            if params["handle"].startswith("muerto"):
                raise RuntimeError("Unable to resolve handle")
            return {"did": "did:plc:ok"}
        with patch.object(b, "_get", side_effect=fake_get):
            b.warm_dids(["muerto.bsky.social", "vivo.bsky.social"])
            self.assertNotIn("muerto.bsky.social", b._DID_CACHE)
            self.assertIn("vivo.bsky.social", b._DID_CACHE)


if __name__ == "__main__":
    unittest.main()
