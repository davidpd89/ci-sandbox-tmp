"""Contratos sintéticos de Graph API; sin cuentas, archivos .env ni acceso a red."""
import copy
import io
import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import facebook_api as fb
import meta_common as mc

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "facebook_graph_contracts.json")
with open(FIXTURE, encoding="utf-8") as stream:
    CASES = json.load(stream)


class FacebookGraphContractTests(unittest.TestCase):
    def test_pages_and_nested_replies_are_exhausted_without_following_token_url(self):
        requests = []
        pages = CASES["pagination"]

        def fake_get(base, path, token, **params):
            self.assertEqual(base, fb.BASE)
            self.assertEqual(token, "SYNTHETIC_TOKEN")
            self.assertNotIn("access_token", params)
            requests.append((path, dict(params)))
            table = pages[path]
            if "data" in table:
                return copy.deepcopy(table)
            return copy.deepcopy(table[params.get("after", "first")])

        with mock.patch.object(fb.mc, "graph_get", side_effect=fake_get):
            pending = fb.comments_pending("SYNTHETIC_TOKEN", "page-1")
        self.assertEqual([row["id"] for row in pending], ["c-pending"])
        self.assertIn(("post-1/comments", mock.ANY), requests)
        self.assertTrue(any(path == "post-1/comments" and p.get("after") == "cursor-comments-2"
                            for path, p in requests))
        self.assertTrue(any(path == "c-answered/comments" and p.get("after") == "cursor-replies-2"
                            for path, p in requests))
        self.assertFalse(any("access_token" in str(p) for _, p in requests))
        self.assertFalse(any("SYNTHETIC_NEVER_REAL" in str(p) for _, p in requests))

    def test_graph_200_envelope_does_not_become_fake_empty_inbox(self):
        with mock.patch.object(fb.mc, "graph_get", return_value=CASES["permission_denied"]):
            with self.assertRaises(fb.FacebookPaginationError):
                fb.comments_pending("T", "page-1")
        def fake_get(base, path, token, **params):
            if path.endswith("/posts"):
                return {"data": [{"id": "post-1"}]}
            return CASES["permission_denied"]
        with mock.patch.object(fb.mc, "graph_get", side_effect=fake_get):
            with self.assertRaises(fb.FacebookPaginationError):
                fb.comments_pending("T", "page-1")

    def test_expired_token_and_permission_http_errors_are_not_suppressed(self):
        for name in ("expired_token", "permission_denied"):
            payload = json.dumps(CASES[name]).encode("utf-8")
            failure = urllib.error.HTTPError(
                url="https://graph.facebook.com/v26.0/page-1/posts?access%5Ftoken=SYNTHETIC_TOKEN",
                code=400, msg="Bad Request", hdrs={}, fp=io.BytesIO(payload))
            with self.subTest(name=name), mock.patch.object(mc.urllib.request, "urlopen", side_effect=failure):
                with self.assertRaisesRegex(RuntimeError, "API 400") as caught:
                    fb.comments_pending("SYNTHETIC_TOKEN", "page-1")
                self.assertNotIn("SYNTHETIC_TOKEN", str(caught.exception))
                self.assertIn(CASES[name]["error"]["message"], str(caught.exception))

    def test_missing_after_cursor_fails_closed(self):
        bad = {"data": [{"id": "c", "message": "¿Dónde?"}],
               "paging": {"next": "https://graph.facebook.com/v26.0/xyz?access%5Ftoken=SYNTHETIC_TOKEN"}}
        with mock.patch.object(fb.mc, "graph_get", return_value=bad):
            with self.assertRaisesRegex(fb.FacebookPaginationError, "cursor"):
                list(fb._paged_rows("SYNTHETIC_TOKEN", "post-1/comments"))
 
    def test_repeated_cursor_and_page_budget_fail_closed(self):
        repeat = {"data": [], "paging": {"next": "https://graph.facebook.com/next",
                                          "cursors": {"after": "same"}}}
        with mock.patch.object(fb.mc, "graph_get", return_value=repeat):
            with self.assertRaisesRegex(fb.FacebookPaginationError, "repitio"):
                list(fb._paged_rows("T", "p/comments"))
            with self.assertRaisesRegex(fb.FacebookPaginationError, "limite"):
                list(fb._paged_rows("T", "p/comments", max_pages=1))

    def test_global_read_budget_aborts_instead_of_reporting_partials(self):
        repeating = {"data": [], "paging": {"next": "https://graph.facebook.com/next",
                                            "cursors": {"after": "second"}}}
        with mock.patch.object(fb.mc, "graph_get", return_value=repeating) as get:
            with self.assertRaisesRegex(fb.FacebookPaginationError, "global"):
                list(fb._paged_rows("T", "p/comments", max_pages=10, budget=[1]))
        self.assertEqual(get.call_count, 1)

    def test_before_after_on_same_fixture_not_a_speed_benchmark(self):
        pages = CASES["pagination"]
        first = pages["post-1/comments"]["first"]["data"]
        # Baseline previo: solo la primera pagina de comentarios y respuestas.
        old_reply_ids = [r["from"]["id"] for r in pages["c-answered/comments"]["first"]["data"]]
        baseline_false_pending = [c["id"] for c in first if "?" in c["message"]
                                  and c["comment_count"] and "page-1" not in old_reply_ids]
        self.assertEqual(baseline_false_pending, ["c-answered"])
        # El contrato nuevo se comprueba integralmente en test_pages_and_nested_replies...
        self.assertNotIn("c-pending", [c["id"] for c in first])

    def test_timeout_after_reply_dispatch_is_not_retried(self):
        # Error incierto: la escritura pudo haber llegado; no confirmar ni reintentar.
        with mock.patch.object(fb.mc, "graph_post", side_effect=TimeoutError("respuesta perdida")) as post:
            with self.assertRaises(TimeoutError):
                fb.reply_comment("SYNTHETIC_TOKEN", "c-1", "Gracias por preguntar.")
        self.assertEqual(post.call_count, 1)

    def test_truncated_second_page_aborts_complete_pending_result(self):
        pages = CASES["pagination"]
        def fake_get(base, path, token, **params):
            if path == "post-1/comments" and params.get("after"):
                raise TimeoutError("lectura incompleta")
            table = pages[path]
            return copy.deepcopy(table if "data" in table else table[params.get("after", "first")])
        with mock.patch.object(fb.mc, "graph_get", side_effect=fake_get):
            with self.assertRaisesRegex(TimeoutError, "incompleta"):
                fb.comments_pending("T", "page-1")


if __name__ == "__main__":
    unittest.main()
