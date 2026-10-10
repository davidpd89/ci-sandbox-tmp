"""Contrato PR53-A: X nunca planifica ni ejecuta likes automáticos.

Sin navegador, sin credenciales, sin cuentas ni escritura de CSV.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import x_automation_policy as policy
import x_build_plan as planner
import x_execute as executor


class XNoAutomatedLikes(unittest.TestCase):
    def test_policy_is_closed_and_filters_without_mutating_input(self):
        self.assertIs(policy.x_likes_automaticos, False)
        raw = [{"kind": "like", "url": "https://x.com/a/status/123"},
               {"kind": "like_latest", "handle": "a"},
               {"kind": "follow", "handle": "lectora"},
               {"kind": "repost", "url": "https://x.com/a/status/456"}]
        out = policy.without_automatic_likes(raw)
        self.assertEqual([a["kind"] for a in out], ["follow", "repost"])
        self.assertEqual(len(raw), 4)

    def test_candidates_may_repost_curated_but_never_like(self):
        candidates = [
            {"kind": "like", "url": "https://x.com/a/status/123",
             "source": "lista:editoriales", "text": "Libros " * 20},
            {"kind": "like", "url": "https://x.com/b/status/456",
             "source": "busqueda:libros", "text": "Una lectura agradable"},
            {"kind": "follow", "handle": "lectora"},
            {"kind": "reply", "url": "https://x.com/c/status/789",
             "text": "Estoy leyendo algo parecido"},
        ]
        plan, replies = planner.build(candidates, max_follows=2, max_reposts=2)
        self.assertEqual({a["kind"] for a in plan}, {"repost", "follow"})
        self.assertEqual(len(replies), 1)

    def test_pool_does_not_create_likes_for_posts_or_accounts(self):
        posts = [{"handle": "lectora", "permalink": "https://x.com/a/status/123",
                  "score": 9, "source": "feed"}]
        accounts = [{"handle": "autora", "score": 20, "source": "backfollow"}]
        import x_pool
        with mock.patch.object(x_pool, "pick", return_value=posts), \
             mock.patch.object(x_pool, "pick_accounts", return_value=accounts):
            plan = planner.build_from_pool(None, likes=8, follows=3, known={})
        self.assertTrue(plan)
        self.assertEqual({a["kind"] for a in plan}, {"follow"})

    def test_merge_cannot_reintroduce_old_likes(self):
        plan = planner.merge(
            [{"kind": "like", "url": "https://x.com/a/status/123"},
             {"kind": "follow", "handle": "lectora"}],
            [{"kind": "like_latest", "handle": "autora"},
             {"kind": "repost", "url": "https://x.com/b/status/456"}])
        self.assertEqual([a["kind"] for a in plan], ["follow", "repost"])

    def test_preflight_drops_old_likes_without_dropping_follow(self):
        old = [{"kind": "like", "url": "https://x.com/a/status/123"},
               {"kind": "like_latest", "handle": "a"},
               {"kind": "follow", "handle": "lectora"}]
        validated = executor._preflight_plan(old)
        self.assertEqual([a["kind"] for a in validated], ["follow"])

    def test_prevalidated_execution_never_calls_like_or_like_latest(self):
        legacy = [{"kind": "like", "url": "https://x.com/a/status/123"},
                  {"kind": "like_latest", "handle": "autora"}]
        with mock.patch("reply_writer.require_gpt", side_effect=lambda p, n: p), \
             mock.patch("repost_policy.guard", side_effect=lambda p, n: p), \
             mock.patch.object(executor.x, "like", side_effect=AssertionError("LIKE REMOTO")), \
             mock.patch.object(executor.x, "like_latest",
                               side_effect=AssertionError("LIKE_LATEST REMOTO")):
            actual = executor.run_plan(legacy, prevalidated=True)
        self.assertEqual(len(actual), 2)
        self.assertTrue(all(r["resultado"] == "saltado_politica_auto_like" for r in actual))


if __name__ == "__main__":
    unittest.main()
