"""Contratos de ejecución: un like sin metadatos no debe alcanzar la API/UI."""
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import like_context_policy as lcp


class FinalLikeSafetyTests(unittest.TestCase):
    def test_tiktok_mobile_run_skips_unverified_like_before_adapter(self):
        import tiktok_mobile_execute as te
        adapter = mock.Mock()
        result = te.run_plan([{
            "kind": "like", "handle": "lectora",
            "url": "https://www.tiktok.com/@lectora/video/123", "media_present": True,
        }], adapter, pause=False)
        adapter.like.assert_not_called()
        self.assertTrue(result[0]["resultado"].startswith("saltado_like_contexto:"))

    def test_reddit_executor_skips_unverified_vote_before_api(self):
        import reddit_execute as re
        with mock.patch.object(re.r, "vote") as vote:
            result = re.run_plan([{
                "kind": "vote", "url": "https://reddit.com/r/libros/comments/abc/ejemplo/",
                "subreddit": "libros", "media_present": True,
            }], prevalidated=True)
        vote.assert_not_called()
        self.assertTrue(result[0]["resultado"].startswith("saltado_like_contexto:"))

    def test_facebook_executor_skips_unverified_like_before_api(self):
        import facebook_execute as fe
        with mock.patch.object(fe.fb, "like_external") as publish:
            result = fe.run_plan([{
                "kind": "like_external", "permalink": "https://facebook.com/post/123", "media_present": True,
            }], prevalidated=True)
        publish.assert_not_called()
        self.assertTrue(result[0]["resultado"].startswith("saltado_like_contexto:"))

    def test_x_executor_skips_unverified_like_before_browser(self):
        import x_execute as xe
        with mock.patch.object(xe.x, "like") as publish:
            result = xe.run_plan([{
                "kind": "like", "url": "https://x.com/lectora/status/123",
                "handle": "lectora", "media_present": True,
            }], prevalidated=True)
        publish.assert_not_called()
<<<<<<< HEAD
        self.assertTrue(result[0]["resultado"].startswith("saltado_like_contexto:"))
=======
        self.assertEqual(result[0]["resultado"], "saltado_politica_auto_like")
>>>>>>> origin/research/public-reuse-parent

    def test_x_like_latest_cannot_bypass_image_only_guard(self):
        import x_execute as xe
        with mock.patch.object(xe.x, "like_latest") as like:
            result = xe.run_plan([{"kind": "like_latest",
                "handle": "lectora", "media_present": True}], prevalidated=True)
        like.assert_not_called()
<<<<<<< HEAD
        self.assertTrue(result[0]["resultado"].startswith("saltado_like_contexto:"))
=======
        self.assertEqual(result[0]["resultado"], "saltado_politica_auto_like")
>>>>>>> origin/research/public-reuse-parent

    def test_threads_both_like_paths_are_guarded(self):
        import threads_execute as te
        with mock.patch.object(te.t, "like_post") as like_post, \
             mock.patch.object(te.t, "like_latest") as like_latest:
            result = te.run_plan([
                {"kind": "like", "handle": "lectora",
                 "permalink": "https://www.threads.com/@lectora/post/abc",
                 "media_present": True},
                {"kind": "like_latest", "handle": "lectora", "media_present": True},
            ], prevalidated=True)
        like_post.assert_not_called()
        like_latest.assert_not_called()
        self.assertTrue(all(row["resultado"].startswith("saltado_like_contexto:")
                            for row in result))

    def test_non_like_actions_are_not_blocked_by_like_guard(self):
        for network in ("bluesky", "mastodon", "x", "threads",
                        "facebook", "pinterest", "reddit", "tiktok"):
            with self.subTest(network=network):
                self.assertEqual(lcp.check_execution(network, {"kind": "follow"}),
                                 (True, "accion_no_es_like"))


if __name__ == "__main__":
    unittest.main()
