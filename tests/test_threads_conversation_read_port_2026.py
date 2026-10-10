"""Contratos offline con estructura de respuesta documentada en Postman oficial de Meta.

Sin navegador, credenciales ni llamadas HTTP reales. Ejecucion:
python -m pytest tests/test_threads_api_contract_2026.py -q
"""
import datetime
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import threads_api as api


def page(rows, after=None):
    """Estructura oficial: data + paging.next / paging.cursors.after."""
    out = {"data": rows}
    if after is not None:
        out["paging"] = {
            "cursors": {"after": after},
            "next": "https://graph.threads.net/v1.0/next?after=" + after
        }
    return out


class ThreadsPaginationContract(unittest.TestCase):
    def test_after_cursor_and_deduplication_no_next_url_fetch(self):
        calls = []
        def getter(path, token, **params):
            calls.append((path, params))
            return page([{"id": "a"}, {"id": "b"}], "CURSOR") if "after" not in params else page([{"id": "b"}, {"id": "c"}])
        with patch.object(api, "api_get", side_effect=getter):
            items = api.paginated("me/threads", "test-token", fields="id", limit=3)
        self.assertEqual([i["id"] for i in items], ["a", "b", "c"])
        self.assertEqual([c[1].get("after") for c in calls], [None, "CURSOR"])
        self.assertEqual([c[0] for c in calls], ["me/threads", "me/threads"])

    def test_cursor_only_full_page_continues_without_next_url(self):
        calls = []
        def getter(path, token, **params):
            calls.append(params.get("after"))
            if "after" not in params:
                return {"data": [{"id": "first"}, {"id": "second"}],
                        "paging": {"cursors": {"after": "C2"}}}
            return {"data": [{"id": "third"}],
                    "paging": {"cursors": {"after": "C3"}}}
        with patch.object(api, "api_get", side_effect=getter):
            found = api.paginated("me/replies", "test-token", fields="id", limit=2)
        self.assertEqual([item["id"] for item in found],
                         ["first", "second", "third"])
        self.assertEqual(calls, [None, "C2"])

    def test_full_page_without_any_cursor_must_not_silently_truncate(self):
        with patch.object(api, "api_get", return_value={
                "data": [{"id": "one"}, {"id": "two"}],
                "paging": {"cursors": {"before": "B"}}}):
            with self.assertRaisesRegex(RuntimeError, "potencialmente incompleta"):
                api.paginated("me/replies", "tok", fields="id", limit=2)

    def test_bad_cursor_shape_never_triggers_third_party_url(self):
        with patch.object(api, "api_get", return_value={
                "data": [{"id": "one"}],
                "paging": {"next": "https://invalid.example/steal-token",
                           "cursors": ["no", "dictionary"]}}):
            with self.assertRaisesRegex(RuntimeError, "invalidos"):
                api.paginated("me/replies", "tok", fields="id", limit=2)

    def test_repeated_cursor_and_page_budget_fail_closed(self):
        with patch.object(api, "api_get", return_value=page([{"id": "a"}], "same")):
            with self.assertRaisesRegex(RuntimeError, "repetido"):
                api.paginated("me/replies", "tok", fields="id", limit=2)
            with self.assertRaisesRegex(RuntimeError, "incompleta"):
                api.paginated("me/replies", "tok", fields="id", limit=2, max_pages=1)

    def test_missing_data_and_missing_cursor_fail_closed(self):
        for response in ({}, {"data": {"id": "x"}}, {"data": [{"id": "x"}], "paging": {"next": "next"}}):
            with self.subTest(response=response), patch.object(api, "api_get", return_value=response):
                with self.assertRaises(RuntimeError):
                    api.paginated("me/replies", "tok", fields="id")
        for bad in (0, 101):
            with self.assertRaises(ValueError):
                api.paginated("me/replies", "tok", fields="id", limit=bad)

    def test_reconciles_own_replies_and_paginated_inbound_questions(self):
        calls = []
        def getter(path, token, **params):
            calls.append((path, params.get("after")))
            if path == "me/threads":
                return page([{"id": "post", "text": "Mi novela", "has_replies": True}])
            if path == "me/replies":
                return page([{"id": "own", "replied_to": {"id": "asked1"}}])
            if path == "post/conversation":
                if not params.get("after"):
                    return page([
                        {"id": "asked1", "username": "ana", "text": "¿Qué libro?", "replied_to": {"id": "post"}, "timestamp": "2026-10-07T10:00:00Z"},
                        {"id": "noq", "username": "bea", "text": "Gracias.", "replied_to": {"id": "post"}, "timestamp": "2026-10-07T11:00:00Z"},
                    ], "C2")
                return page([
                    {"id": "asked2", "username": "cora", "text": "¿Dónde?", "replied_to": {"id": "post"}, "timestamp": "2026-10-08T10:00:00Z"},
                    {"id": "asked2", "username": "cora", "text": "¿Dónde?", "replied_to": {"id": "post"}, "timestamp": "2026-10-08T10:00:00Z"},
                ])
            raise AssertionError("endpoint inesperado")
        with patch.object(api, "api_get", side_effect=getter):
            pending = api.followups("tok", "autorademodiaz")
        self.assertEqual([r["id"] for r in pending], ["asked2"])
        self.assertEqual(pending[0]["a_nuestro"], "Mi novela")
        self.assertIn(("post/conversation", "C2"), calls)

    def test_nested_question_to_our_reply_preserves_verified_ancestry(self):
        calls = []
        def getter(path, token, **params):
            calls.append(path)
            if path == "me/threads":
                return page([{"id": "root", "text": "Leamos", "has_replies": True}])
            if path == "me/replies":
                return page([{"id": "own", "replied_to": {"id": "question"}}])
            if path == "root/conversation":
                return page([
                    {"id": "question", "username": "ana", "text": "¿Qué libro?",
                     "timestamp": "2026-10-07T08:00:00Z",
                     "replied_to": {"id": "root"}},
                    {"id": "own", "username": "autorademodiaz", "text": "El segundo.",
                     "timestamp": "2026-10-07T09:00:00Z",
                     "replied_to": {"id": "question"}, "is_reply_owned_by_me": True},
                    {"id": "nested", "username": "ana", "text": "¿Y la secuela?",
                     "timestamp": "2026-10-08T10:00:00Z",
                     "permalink": "https://www.threads.com/@ana/post/fake12345",
                     "replied_to": {"id": "own"}},
                    {"id": "third_party", "username": "bea", "text": "¿Y mi libro?",
                     "timestamp": "2026-10-08T11:00:00Z",
                     "replied_to": {"id": "question"}},
                ])
            raise AssertionError(path)
        with patch.object(api, "api_get", side_effect=getter):
            pending = api.followups("tok", "autorademodiaz")
        self.assertEqual([r["id"] for r in pending], ["nested"])
        self.assertEqual(pending[0]["a_nuestro"], "El segundo.")
        self.assertEqual([t["post_id"] for t in pending[0]["thread_turns"]],
                         ["root", "question", "own", "nested"])
        self.assertEqual([t["role"] for t in pending[0]["thread_turns"]],
                         ["ours", "theirs", "ours", "theirs"])
        with patch("reply_provenance.carry_decision_proof", side_effect=lambda action, *args, **kwargs: action):
            plan = api.build_plan(pending, {"actions": [{"id": "nested", "text": "Sí, está publicada."}]})
        self.assertTrue(plan[0]["reply_to_us"])
        self.assertEqual(plan[0]["target_created_at"], "2026-10-08T10:00:00Z")
        self.assertEqual(plan[0]["thread_turns"], pending[0]["thread_turns"])
        self.assertIn("root/conversation", calls)

    def test_own_reply_visible_only_in_conversation_blocks_duplicate(self):
        def getter(path, token, **params):
            if path == "me/threads":
                return page([{"id": "root", "text": "Inicio", "has_replies": True}])
            if path == "me/replies":
                return page([])
            if path == "root/conversation":
                return page([
                    {"id": "question", "username": "ana", "text": "¿Cuál eliges?",
                     "replied_to": {"id": "root"}, "timestamp": "2026-10-08T10:00:00Z"},
                    {"id": "our-answer", "username": "autorademodiaz",
                     "is_reply_owned_by_me": True, "text": "El segundo.",
                     "replied_to": {"id": "question"}, "timestamp": "2026-10-08T11:00:00Z"},
                    {"id": "new-question", "username": "ana", "text": "¿Y el tercero?",
                     "replied_to": {"id": "our-answer"}, "timestamp": "2026-10-08T12:00:00Z"},
                ])
            raise AssertionError(path)
        with patch.object(api, "api_get", side_effect=getter):
            pending = api.followups("tok", "autorademodiaz")
        self.assertEqual([r["id"] for r in pending], ["new-question"])

    def test_unverifiable_nested_parent_is_not_treated_as_available(self):
        def getter(path, token, **params):
            if path == "me/threads":
                return page([{"id": "root", "text": "Inicio", "has_replies": True}])
            if path == "me/replies":
                return page([{"id": "own-missing", "replied_to": {"id": "old-question"}}])
            if path == "root/conversation":
                return page([{"id": "nested", "username": "ana", "text": "¿Y ahora?",
                              "replied_to": {"id": "own-missing"}}])
            raise AssertionError(path)
        with patch.object(api, "api_get", side_effect=getter):
            with self.assertRaisesRegex(RuntimeError, "cadena de respuestas incompleta"):
                api.followups("tok", "autorademodiaz")

    def test_own_reply_without_parent_does_not_mask_duplicate_risk(self):
        def getter(path, token, **params):
            if path == "me/threads":
                return page([{"id": "root", "text": "Inicio", "has_replies": True}])
            if path == "me/replies":
                return page([{"id": "own-no-parent"}])
            raise AssertionError(path)
        with patch.object(api, "api_get", side_effect=getter):
            with self.assertRaisesRegex(RuntimeError, "carece de replied_to"):
                api.followups("tok", "autorademodiaz")

    def test_missing_parent_on_inbound_question_fails_closed(self):
        def getter(path, token, **params):
            if path == "me/threads":
                return page([{"id": "root", "text": "Inicio", "has_replies": True}])
            if path == "me/replies":
                return page([])
            if path == "root/conversation":
                return page([{"id": "unbound", "username": "ana", "text": "¿Sigues ahí?"}])
            raise AssertionError(path)
        with patch.object(api, "api_get", side_effect=getter):
            with self.assertRaisesRegex(RuntimeError, "respuesta recibida sin replied_to"):
                api.followups("tok", "autorademodiaz")

    def test_denied_permissions_and_expired_token_never_return_empty_inbox(self):
        for error in ("API 401: expired token", "API 403: missing threads_read_replies"):
            with self.subTest(error=error), patch.object(api, "api_get", side_effect=RuntimeError(error)):
                with self.assertRaisesRegex(RuntimeError, "API"):
                    api.followups("tok", "autorademodiaz")

    def test_refresh_expired_token_does_not_overwrite_on_401(self):
        env = {"THREADS_ACCESS_TOKEN": "old", "THREADS_TOKEN_CREATED": "2026-01-01"}
        with patch.object(api, "api_get", side_effect=RuntimeError("API 401: expired")), \
             patch.object(api, "_write_env") as write:
            with self.assertRaisesRegex(RuntimeError, "401"):
                api.refresh(env, today=datetime.date(2026, 10, 9), if_due=True)
            write.assert_not_called()


    def test_uncertified_text_does_not_create_action(self):
        items = [{"id": "target", "username": "ana", "text": "¿Cuál?", "timestamp": "2026-10-10T09:00:00Z",
                  "thread_turns": [{"role": "theirs", "text": "¿Cuál?", "post_id": "target"}]}]
        with patch("reply_provenance.carry_decision_proof", return_value=None):
            self.assertEqual(api.build_plan(items, {"actions": [{"id": "target", "text": "El segundo."}]}), [])

    def test_legacy_verified_publication_contract_is_preserved(self):
        import inspect
        self.assertIn("proof_action", inspect.signature(api.publish_reply).parameters)
        self.assertIn("proof_path", inspect.signature(api.publish_reply).parameters)
        self.assertTrue(callable(api._verify_reply_destination))

