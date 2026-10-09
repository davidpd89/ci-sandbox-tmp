import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import facebook_api as fb


class LikeCommentsTests(unittest.TestCase):
    def fake_get(self, base, path, token, **params):
        if path.endswith("/posts"):
            return {"data": [{"id": "P1"}]}
        return {"data": [
            {"id": "c1", "from": {"id": "u1"}, "user_likes": False},
            {"id": "c2", "from": {"id": "PAGE"}},                      # comentario nuestro
            {"id": "c3", "from": {"id": "u2"}, "user_likes": True},    # ya marcado
            {"id": "c4", "from": {"id": "u3"}, "can_like": False},
            {"id": "c5", "from": {"id": "u4"}},
        ]}

    def test_only_unliked_foreign_comments_are_liked(self):
        posted = []
        with mock.patch.object(fb.mc, "graph_get", self.fake_get), \
                mock.patch.object(fb.mc, "graph_post", lambda base, path, token, **kw: posted.append(path) or {"success": True}):
            self.assertEqual(fb.like_comments("T", "PAGE"), (2, 0))
        self.assertEqual(posted, ["c1/likes", "c5/likes"])

    def test_dry_run_writes_nothing_and_failures_are_counted(self):
        with mock.patch.object(fb.mc, "graph_get", self.fake_get), \
                mock.patch.object(fb.mc, "graph_post", side_effect=AssertionError("no debe escribir")):
            self.assertEqual(fb.like_comments("T", "PAGE", dry=True), (2, 0))
        with mock.patch.object(fb.mc, "graph_get", self.fake_get), \
                mock.patch.object(fb.mc, "graph_post", side_effect=RuntimeError("API 400")):
            self.assertEqual(fb.like_comments("T", "PAGE"), (0, 2))


if __name__ == "__main__":
    unittest.main()
