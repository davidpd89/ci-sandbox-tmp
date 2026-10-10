"""Regresiones adversariales de lectura Graph; datos exclusivamente sinteticos."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import facebook_api as fb


class FacebookAdversarialReadTests(unittest.TestCase):
    def test_second_page_graph_error_never_returns_partial_inbox(self):
        def fake_get(base, path, token, **params):
            if path.endswith("/posts"):
                return {"data": [{"id": "post-1"}]}
            if params.get("after"):
                return {"error": {"code": 200, "message": "synthetic denied"}}
            return {"data": [{"id": "c-1", "message": "¿Dónde?",
                             "from": {"id": "reader-1"}, "comment_count": 0}],
                    "paging": {"next": "https://invalid.example/?opaque=synthetic",
                               "cursors": {"after": "next"}}}
        with mock.patch.object(fb.mc, "graph_get", side_effect=fake_get):
            with self.assertRaises(fb.FacebookPaginationError):
                fb.comments_pending("synthetic", "page-1")

    def test_duplicate_comment_id_is_only_listed_once(self):
        def fake_get(base, path, token, **params):
            if path.endswith("/posts"):
                return {"data": [{"id": "post-1", "message": "Libro"}]}
            one = {"id": "c-1", "message": "¿Dónde?", "from": {"id": "r-1"},
                   "created_time": "2026-10-08T12:00:00Z", "comment_count": 0}
            if params.get("after"):
                return {"data": [one]}
            return {"data": [one], "paging": {
                "next": "https://invalid.example/?opaque=synthetic",
                "cursors": {"after": "next"}}}
        with mock.patch.object(fb.mc, "graph_get", side_effect=fake_get):
            self.assertEqual([x["id"] for x in fb.comments_pending("synthetic", "page-1")], ["c-1"])

    def test_missing_comment_count_triggers_reply_lookup(self):
        paths = []
        def fake_get(base, path, token, **params):
            paths.append(path)
            if path.endswith("/posts"):
                return {"data": [{"id": "post-1"}]}
            if path == "post-1/comments":
                return {"data": [{"id": "c-1", "message": "¿Cuándo?",
                                  "from": {"id": "reader"}}]}
            return {"data": [{"id": "r-page", "from": {"id": "page-1"}}]}
        with mock.patch.object(fb.mc, "graph_get", side_effect=fake_get):
            self.assertEqual(fb.comments_pending("synthetic", "page-1"), [])
        self.assertIn("c-1/comments", paths)


    def test_hidden_reply_identity_never_becomes_false_pending(self):
        for hidden in (None, {}, {"name": "Oculto"}, "anonimo"):
            with self.subTest(hidden=hidden):
                def fake_get(base, path, token, **params):
                    if path.endswith("/posts"):
                        return {"data": [{"id": "post-1", "message": "Novela"}]}
                    if path == "post-1/comments":
                        return {"data": [{"id": "c-1", "message": "¿Dónde lo compro?",
                                         "from": {"id": "reader-1"}, "comment_count": 1}]}
                    if path == "c-1/comments":
                        return {"data": [{"id": "r-1", "from": hidden}]}
                    raise AssertionError(path)
                with mock.patch.object(fb.mc, "graph_get", side_effect=fake_get):
                    with self.assertRaisesRegex(fb.FacebookPaginationError, "identidad"):
                        fb.comments_pending("synthetic", "page-1")

    def test_known_external_reply_does_not_hide_unanswered_question(self):
        def fake_get(base, path, token, **params):
            if path.endswith("/posts"):
                return {"data": [{"id": "post-1", "message": "Novela"}]}
            if path == "post-1/comments":
                return {"data": [{"id": "c-1", "message": "¿Hay edición de bolsillo?",
                                 "from": {"id": "reader-1"}, "comment_count": 1}]}
            return {"data": [{"id": "r-1", "from": {"id": "reader-2"}}]}
        with mock.patch.object(fb.mc, "graph_get", side_effect=fake_get):
            self.assertEqual([x["id"] for x in fb.comments_pending("synthetic", "page-1")], ["c-1"])


if __name__ == "__main__":
    unittest.main()
