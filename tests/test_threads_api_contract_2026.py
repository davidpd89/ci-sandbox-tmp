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
import threads_execute as executor


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
            items = api.paginated("me/threads", "test-token", fields="id", limit=2)
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
            if path == "post/replies":
                if not params.get("after"):
                    return page([
                        {"id": "asked1", "username": "ana", "text": "¿Qué libro?", "timestamp": "2026-10-07T10:00:00Z"},
                        {"id": "noq", "username": "bea", "text": "Gracias.", "timestamp": "2026-10-07T11:00:00Z"},
                    ], "C2")
                return page([
                    {"id": "asked2", "username": "cora", "text": "¿Dónde?", "timestamp": "2026-10-08T10:00:00Z"},
                    {"id": "asked2", "username": "cora", "text": "¿Dónde?", "timestamp": "2026-10-08T10:00:00Z"},
                ])
            raise AssertionError("endpoint inesperado")
        with patch.object(api, "api_get", side_effect=getter):
            pending = api.followups("tok", "autorademodiaz")
        self.assertEqual([r["id"] for r in pending], ["asked2"])
        self.assertEqual(pending[0]["a_nuestro"], "Mi novela")
        self.assertIn(("post/replies", "C2"), calls)

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


class ThreadsPublishContract(unittest.TestCase):
    def test_accepted_without_id_is_uncertain_not_confirmed(self):
        with patch.object(api, "api_post", side_effect=[{"id": "container-01"}, {}]) as post:
            with self.assertRaises(api.ReplyPublishUncertain):
                api.publish_reply("tok", "me", "parent", "Respuesta.")
        self.assertEqual(post.call_args_list[1].args[0], "me/threads_publish")

    def test_timeout_after_publish_sent_is_uncertain(self):
        with patch.object(api, "api_post", side_effect=[{"id": "container-01"}, TimeoutError("timeout")]):
            with self.assertRaises(api.ReplyPublishUncertain):
                api.publish_reply("tok", "me", "parent", "Respuesta.")

    def test_first_post_never_autopublishes_and_timeout_is_not_created(self):
        with patch.object(api, "api_post", side_effect=TimeoutError("offline")) as post:
            with self.assertRaises(api.ReplyNotCreated):
                api.publish_reply("tok", "me", "parent", "Respuesta.")
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["auto_publish_text"], "false")

    def test_invalid_publish_ack_id_is_uncertain(self):
        with patch.object(api, "api_post",
                          side_effect=[{"id": "container"}, {"id": 123}]):
            with self.assertRaises(api.ReplyPublishUncertain):
                api.publish_reply("tok", "me", "parent", "Respuesta.")

    def test_failed_creation_never_attempts_publish(self):
        with patch.object(api, "api_post", side_effect=RuntimeError("API 403")) as post:
            with self.assertRaises(api.ReplyNotCreated):
                api.publish_reply("tok", "me", "parent", "Respuesta.")
        self.assertEqual(post.call_count, 1)

    def test_executor_marks_ambiguous_reply_for_reconciliation(self):
        item = {"handle": "ana", "kind": "reply", "text": "El segundo, sin duda.",
                "reply_to_id": "parent", "post_text": "¿Cuál recomiendas?"}
        with patch.object(api, "_env", return_value={"THREADS_ACCESS_TOKEN": "test", "THREADS_USER_ID": "me"}), \
             patch.object(api, "publish_reply", side_effect=api.ReplyPublishUncertain("ambiguous")), \
             patch.object(executor.t, "reply_to", side_effect=AssertionError("browser forbidden")):
            outcomes = executor.run_plan([item])
        self.assertEqual([r["resultado"] for r in outcomes], ["pendiente_verificacion"])


if __name__ == "__main__":
    unittest.main()
