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
        plan = api.build_plan(pending, {"actions": [{"id": "nested", "text": "Sí, está publicada."}]})
        self.assertTrue(plan[0]["reply_to_us"])
        self.assertEqual(plan[0]["target_created_at"], "2026-10-08T10:00:00Z")
        self.assertEqual(plan[0]["thread_turns"], pending[0]["thread_turns"])
        self.assertIn("root/conversation", calls)

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



class ThreadsTransportTests(unittest.TestCase):
    def test_api_only_dispatch_uses_existing_executor(self):
        items = [{"kind": "reply", "reply_to_id": "synthetic-1"}]
        self.assertFalse(executor._plan_needs_browser(items))
        self.assertTrue(executor._plan_needs_browser(items + [{"kind": "like"}]))
        with patch.object(executor, "run_plan", return_value=[{"resultado": "confirmado"}]) as runner, \
             patch.object(executor.t, "ensure_browser") as startup, \
             patch.object(executor.t, "session") as session:
            result = executor._run_by_transport(items)
        self.assertEqual(result[0]["resultado"], "confirmado")
        runner.assert_called_once()
        startup.assert_not_called()
        session.assert_not_called()

    def test_offline_metrics_decode(self):
        with patch.object(api, "_env", return_value={"THREADS_ACCESS_TOKEN": "synthetic"}), \
             patch.object(api, "api_get", return_value={
                 "data": [{"name": "followers_count", "total_value": {"value": 17}}]
             }) as getter:
            metrics = executor._fetch_metrics_api()
        self.assertEqual(metrics, {"followers": "17"})
        self.assertEqual(getter.call_args.args[0], "me/threads_insights")

    def test_unknown_followers_do_not_erase_last_verified_value(self):
        with patch.object(executor, "_append_metricas") as append, \
             patch.object(executor, "_update_estado") as update:
            executor._persist_metrics_without_erasing_known_followers([], {"followers": "?"})
            append.assert_called_once()
            update.assert_not_called()

    def test_verified_followers_update_dashboard(self):
        with patch.object(executor, "_append_metricas") as append, \
             patch.object(executor, "_update_estado") as update:
            executor._persist_metrics_without_erasing_known_followers([], {"followers": "17"})
            append.assert_called_once()
            update.assert_called_once()


    def test_offline_plan_build_uses_neither_env_nor_browser(self):
        import io
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            source = os.path.join(temporary, "threads_api_followups.json")
            decisions = os.path.join(temporary, "decisions.json")
            output = os.path.join(temporary, "plan.json")
            with open(source, "w", encoding="utf-8") as stream:
                json.dump([{"id": "reply1", "username": "ana",
                            "text": "¿Alguna recomendación?",
                            "timestamp": "2026-10-08T12:00:00Z"}], stream)
            with open(decisions, "w", encoding="utf-8") as stream:
                json.dump({"actions": [{"id": "reply1", "text": "La segunda."}]}, stream)
            with patch.object(api, "ROOT", temporary), \
                 patch.object(api, "_env", side_effect=AssertionError("build must be offline")), \
                 patch.object(api.sys, "stdout", io.StringIO()):
                code = api.main(["build", decisions, output])
            self.assertEqual(code, 0)
            with open(output, encoding="utf-8") as stream:
                plan = json.load(stream)
            self.assertEqual(plan[0]["reply_to_id"], "reply1")
            self.assertEqual(plan[0]["target_created_at"], "2026-10-08T12:00:00Z")


    def test_pool_uncertain_result_is_persistently_non_retriable(self):
        import sqlite3
        import threads_pool as pool
        self.assertEqual(
            executor._pool_post_status({"resultado": "pendiente_verificacion"}),
            "pending_verification",
        )
        self.assertEqual(executor._pool_post_status({"resultado": "confirmado"}), "done")
        self.assertIsNone(executor._pool_post_status({"resultado": "no_intentado"}))
        db = sqlite3.connect(":memory:")
        try:
            db.execute("CREATE TABLE posts (permalink TEXT PRIMARY KEY, status TEXT, acted_at TEXT)")
            db.execute("INSERT INTO posts (permalink, status) VALUES (?, ?)",
                       ("https://www.threads.com/@test/post/test12345", "new"))
            pool.mark(db, "https://www.threads.com/@test/post/test12345",
                      executor._pool_post_status({"resultado": "pendiente_verificacion"}))
            row = db.execute("SELECT status FROM posts").fetchone()
            self.assertEqual(row[0], "pending_verification")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM posts WHERE status = 'new'").fetchone()[0], 0)
        finally:
            db.close()


    def test_shared_age_policy_rejects_stale_followup_without_new_rules(self):
        import post_age_policy as age
        now = datetime.datetime(2026, 10, 9, 12, tzinfo=datetime.timezone.utc)
        recent = {"kind": "reply", "reply_to_us": True,
                  "target_created_at": "2026-10-08T10:00:00Z"}
        old = {"kind": "reply", "reply_to_us": True,
               "target_created_at": "2026-09-29T10:00:00Z"}
        self.assertTrue(age.check("threads", recent, now=now)[0])
        self.assertFalse(age.check("threads", old, now=now)[0])


if __name__ == "__main__":
    unittest.main()
