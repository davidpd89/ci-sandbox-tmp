"""Regresion #73: Threads API no publica sin firma #79 y destino cotejado.

Se usan las funciones reales de la capa API con GET/POST simulados.
"""
import os
import datetime as dt
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import threads_api as api
import reply_provenance as proof
import reply_writer as writer
import repost_policy as repost


URL = "https://www.threads.com/@lectora/post/ABC123"
OTHER = "https://www.threads.com/@otra/post/XYZ987"
TEXT = "Me ha sorprendido mucho esta novela de fantasía."
ACTION = {
    "kind": "reply",
    "reply_to_id": "99",
    "url": URL,
    "post_text": TEXT,
    "post_created_at": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat(),
    "text": "El final me parece muy logrado.",
    "gpt_proof": "no-es-una-prueba-valida",
}


class DirectThreadsContract(unittest.TestCase):
    def setUp(self):
        # Ni siquiera los tests que simulan un POST acertado leen o escriben
        # el ledger de la máquina de producción.
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        env = mock.patch.dict(os.environ, {
            "RRSS_THREADS_ACTION_LEDGER_PATH": os.path.join(temp.name, "ledger.sqlite3")})
        env.start()
        self.addCleanup(env.stop)

    def test_unproved_reply_never_sends_api_post(self):
        with (mock.patch.object(api, "api_post") as post,
              mock.patch.object(api, "api_get") as get):
            with self.assertRaisesRegex(PermissionError, "certificado"):
                api.publish_reply("token-falso", "1", "99", ACTION["text"])
            post.assert_not_called()
            get.assert_not_called()

            with self.assertRaisesRegex(PermissionError, "certificado"):
                api.publish_reply("token-falso", "1", "99", ACTION["text"], proof_action=ACTION)
            post.assert_not_called()
            get.assert_not_called()

    def test_valid_proof_cannot_be_retargeted_to_different_api_id(self):
        with (mock.patch.object(proof, "verify", return_value=True),
              mock.patch.object(api, "api_post") as post,
              mock.patch.object(api, "api_get") as get):
            with self.assertRaisesRegex(PermissionError, "certificado"):
                api.publish_reply("token-falso", "1", "100", ACTION["text"], proof_action=ACTION)
            get.assert_not_called()
            post.assert_not_called()

    def test_valid_proof_wrong_live_permalink_or_text_does_not_publish(self):
        cases = [
            {"id": "99", "permalink": OTHER, "text": TEXT},
            {"id": "100", "permalink": URL, "text": TEXT},
            {"id": "99", "permalink": URL, "text": "Otro mensaje"},
            {"id": "99", "permalink": "", "text": TEXT},
            {"id": "99", "permalink": URL},  # contexto remoto incompleto
        ]
        for target in cases:
            with self.subTest(target=target), \
                 mock.patch.object(proof, "verify", return_value=True), \
                 mock.patch.object(api, "api_get", return_value=target) as get, \
                 mock.patch.object(api, "api_post") as post:
                with self.assertRaisesRegex(PermissionError, "no coinciden"):
                    api.publish_reply("token-falso", "1", "99", ACTION["text"], proof_action=ACTION)
                get.assert_called_once_with("99", "token-falso", fields="id,permalink,text")
                post.assert_not_called()

    def test_failed_target_get_is_fail_closed(self):
        with (mock.patch.object(proof, "verify", return_value=True),
              mock.patch.object(api, "api_get", side_effect=TimeoutError("offline")),
              mock.patch.object(api, "api_post") as post):
            with self.assertRaisesRegex(PermissionError, "no se pudo verificar"):
                api.publish_reply("token-falso", "1", "99", ACTION["text"], proof_action=ACTION)
            post.assert_not_called()

    def test_second_post_timeout_or_missing_ack_is_uncertain_not_retryable(self):
        import exec_common as common
        import action_ledger as ledger
        action = dict(ACTION)
        remote = {"id": "99", "permalink": URL, "text": TEXT}
        for response in (TimeoutError("timed out"), {"unexpected": "schema"},
                         {"id": True}, {"id": []}, {"id": ""}, None):
            with self.subTest(response=type(response).__name__):
                calls = []
                def fake_post(path, token, **kwargs):
                    calls.append(path)
                    if len(calls) == 1:
                        return {"id": "container"}
                    if isinstance(response, BaseException):
                        raise response
                    return response
                with tempfile.TemporaryDirectory() as variant, \
                     mock.patch.dict(os.environ, {
                         "RRSS_THREADS_ACTION_LEDGER_PATH": os.path.join(variant, "ledger.sqlite3")}), \
                     mock.patch.object(proof, "verify", return_value=True), \
                     mock.patch.object(api, "api_get", return_value=remote), \
                     mock.patch.object(api, "api_post", side_effect=fake_post):
                    with self.assertRaises(common.WriteOutcomeUnknown):
                        api.publish_reply("token-falso", "1", "99", ACTION["text"],
                                          proof_action=action)
                self.assertEqual(calls, ["1/threads", "1/threads_publish"])
                self.assertEqual(ledger.outcome_to_status("pendiente_verificacion"),
                                 ledger.UNCERTAIN)

    def test_executor_retains_uncertain_reply_and_continues_follow(self):
        import threads_execute as execute
        import exec_common as common
        # Solo la reply tiene el estado remoto incierto. El follow no se bloquea
        # por error global; toda accion remota se sustituye por mock.
        item = {**ACTION, "handle": "lectora"}
        following = {"kind": "follow", "handle": "lector2", "vet": False}
        with (mock.patch.object(writer, "require_gpt", return_value=[item, following]),
              mock.patch.object(repost, "guard", side_effect=lambda plan, _: list(plan)),
              mock.patch.object(execute, "_pause"),
              mock.patch.object(execute.t, "beat", create=True),
              mock.patch.object(execute.t, "follow", return_value="followed") as follow,
              mock.patch.object(api, "_env", return_value={
                  "THREADS_ACCESS_TOKEN": "fake", "THREADS_USER_ID": "1"}),
              mock.patch.object(api, "publish_reply",
                                side_effect=common.WriteOutcomeUnknown("unknown")) as publish):
            result = execute.run_plan([item, following], prevalidated=True)
        self.assertEqual([row["resultado"] for row in result],
                         ["pendiente_verificacion", "confirmado"])
        publish.assert_called_once()
        follow.assert_called_once_with("lector2")

    def test_policy_denial_is_skip_not_global_execution_error(self):
        import threads_execute as execute
        item = {**ACTION, "handle": "lectora"}
        other = {"kind": "follow", "handle": "lector2", "vet": False}
        with (mock.patch.object(writer, "require_gpt", return_value=[item, other]),
              mock.patch.object(repost, "guard", side_effect=lambda plan, _: list(plan)),
              mock.patch.object(execute, "_pause"),
              mock.patch.object(execute.t, "beat", create=True),
              mock.patch.object(execute.t, "follow", return_value="followed") as follow,
              mock.patch.object(api, "_env", return_value={
                  "THREADS_ACCESS_TOKEN": "fake", "THREADS_USER_ID": "1"}),
              mock.patch.object(api, "publish_reply",
                                side_effect=PermissionError("no proof"))):
            result = execute.run_plan([item, other], prevalidated=True)
        self.assertEqual(result[0]["resultado"], "saltado_contexto_api_no_verificado")
        import action_ledger as ledger
        self.assertEqual(ledger.outcome_to_status(result[0]["resultado"]),
                         ledger.SKIPPED_POLICY)
        self.assertEqual(result[1]["resultado"], "confirmado")
        follow.assert_called_once_with("lector2")

    def test_direct_api_checks_closed_inbound_even_with_signed_text(self):
        import conversation_turn_policy as turn
        item = {**ACTION, "reply_to_us": True, "post_text": "Gracias.",
                "motivo": "followup API Threads"}
        with (mock.patch.object(proof, "verify", return_value=True),
              mock.patch.object(api, "api_get", return_value={
                  "id": "99", "permalink": URL, "text": "Gracias."}),
              mock.patch.object(api, "api_post") as post):
            with self.assertRaisesRegex(PermissionError, "cierre_social"):
                api.publish_reply("fake", "1", "99", ACTION["text"], proof_action=item)
            post.assert_not_called()

    def test_invalid_reply_types_are_denied_before_get_or_post(self):
        for invalid in (None, 12, {}, ["texto"], "", "  "):
            with self.subTest(value=repr(invalid)):
                with (mock.patch.object(api, "api_get") as get,
                      mock.patch.object(api, "api_post") as post):
                    with self.assertRaises(ValueError):
                        api.publish_reply("fake", "1", "99", invalid)
                    get.assert_not_called()
                    post.assert_not_called()

    def test_verified_target_preserves_two_stage_publish_contract(self):
        posts = []
        def fake_post(path, token, **params):
            posts.append((path, params))
            return {"id": "container1" if len(posts) == 1 else "published1"}
        with (mock.patch.object(proof, "verify", return_value=True) as verify,
              mock.patch.object(api, "api_get",
                                return_value={"id": "99", "permalink": URL, "text": TEXT}),
              mock.patch.object(api, "api_post", side_effect=fake_post)):
            result = api.publish_reply("token-falso", "1", "99", ACTION["text"], proof_action=ACTION)
        self.assertEqual(result, "published1")
        verify.assert_called_once()
        self.assertEqual([path for path, _ in posts], ["1/threads", "1/threads_publish"])
        self.assertEqual(posts[0][1]["reply_to_id"], "99")
        self.assertEqual(posts[0][1]["text"], ACTION["text"])

    def test_executor_passes_proof_action_to_api_writer(self):
        import threads_execute as execute
        item = {**ACTION, "handle": "lectora"}
        with (mock.patch.object(writer, "require_gpt", return_value=[item]),
              mock.patch.object(repost, "guard", side_effect=lambda plan, _: list(plan)),
              mock.patch.object(execute.t, "beat", create=True),
              mock.patch.object(execute, "_pause"),
              mock.patch.object(api, "_env", return_value={
                  "THREADS_ACCESS_TOKEN": "test", "THREADS_USER_ID": "1"}),
              mock.patch.object(api, "publish_reply", return_value="id") as write):
            result = execute.run_plan([item], prevalidated=True)
        write.assert_called_once()
        self.assertEqual(write.call_args.kwargs["proof_action"], item)
        self.assertEqual(write.call_args.args[2:4], ("99", ACTION["text"]))
        self.assertEqual(result[0]["resultado"], "confirmado")

    def test_executor_rejects_unmarked_reply_even_with_suite_flag(self):
        import threads_execute as execute
        item = {"kind": "reply", "handle": "lectora", "reply_to_id": "99",
                "url": URL, "post_text": TEXT, "text": ACTION["text"]}
        with mock.patch.dict(os.environ, {
                "RRSS_ALLOW_UNMARKED_TEXT": "1", "PYTEST_CURRENT_TEST": ""}), \
             mock.patch.object(api, "publish_reply") as write, \
             mock.patch.object(repost, "guard", side_effect=lambda plan, _: list(plan)), \
             mock.patch.object(execute.t, "beat", create=True):
            result = execute.run_plan([item], prevalidated=True)
        self.assertEqual(result, [])
        write.assert_not_called()

    def test_real_provenance_record_and_attach_allows_matching_api_target(self):
        # Firma REAL del modulo #79 en fichero temporal; solo POST/GET simulados.
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "context-proof.json")
            source = {"url": URL, "text": TEXT}
            self.assertTrue(proof.record("threads", source, ACTION["text"], path=path))
            action = proof.attach(
                {"kind": "reply", "reply_to_id": "99", "url": URL,
                 "text": ACTION["text"], "post_created_at": ACTION["post_created_at"]}, source, "threads", path=path)
            self.assertIsNotNone(action)
            posts = []
            def fake_post(endpoint, token, **kw):
                posts.append(endpoint)
                return {"id": "container" if len(posts) == 1 else "published"}
            with (mock.patch.object(api, "api_get", return_value={
                    "id": "99", "permalink": URL, "text": TEXT}),
                  mock.patch.object(api, "api_post", side_effect=fake_post)):
                result = api.publish_reply("fake-token", "1", "99", ACTION["text"],
                                           proof_action=action, proof_path=path)
            self.assertEqual(result, "published")
            self.assertEqual(posts, ["1/threads", "1/threads_publish"])
            forged = {**action, "reply_to_id": "100"}
            with mock.patch.object(api, "api_post") as post:
                with self.assertRaises(PermissionError):
                    api.publish_reply("fake-token", "1", "100", ACTION["text"],
                                      proof_action=forged, proof_path=path)
                post.assert_not_called()

    def test_direct_api_success_cannot_be_published_twice(self):
        import action_ledger as ledger
        calls = []
        def fake_post(endpoint, token, **params):
            calls.append(endpoint)
            return {"id": "container" if len(calls) == 1 else "published"}
        with (mock.patch.object(proof, "verify", return_value=True),
              mock.patch.object(api, "api_get", return_value={
                  "id": "99", "permalink": URL, "text": TEXT}),
              mock.patch.object(api, "api_post", side_effect=fake_post)):
            result = api.publish_reply("fake", "1", "99", ACTION["text"],
                                       proof_action=ACTION)
            self.assertEqual(result, "published")
            with self.assertRaisesRegex(PermissionError, "ya reservada o enviada"):
                api.publish_reply("fake", "1", "99", ACTION["text"],
                                  proof_action=ACTION)
        self.assertEqual(calls, ["1/threads", "1/threads_publish"])
        db = ledger.ActionLedger(os.environ["RRSS_THREADS_ACTION_LEDGER_PATH"])
        self.assertEqual(db.status("reply", "threads:reply_to:99"), ledger.CONFIRMED)

    def test_direct_api_uncertain_blocks_second_post_even_after_restart(self):
        import action_ledger as ledger
        calls = []
        def fake_post(endpoint, token, **params):
            calls.append(endpoint)
            if len(calls) == 1:
                return {"id": "container"}
            raise TimeoutError("simulated network failure after POST")
        with (mock.patch.object(proof, "verify", return_value=True),
              mock.patch.object(api, "api_get", return_value={
                  "id": "99", "permalink": URL, "text": TEXT}),
              mock.patch.object(api, "api_post", side_effect=fake_post)):
            import exec_common as ec
            with self.assertRaises(ec.WriteOutcomeUnknown):
                api.publish_reply("fake", "1", "99", ACTION["text"],
                                  proof_action=ACTION)
            with self.assertRaisesRegex(PermissionError, "ya reservada o enviada"):
                api.publish_reply("fake", "1", "99", ACTION["text"],
                                  proof_action=ACTION)
        self.assertEqual(calls, ["1/threads", "1/threads_publish"])
        db = ledger.ActionLedger(os.environ["RRSS_THREADS_ACTION_LEDGER_PATH"])
        self.assertEqual(db.status("reply", "threads:reply_to:99"), ledger.UNCERTAIN)

    def test_api_builder_preserves_real_gpt_evidence_from_decision(self):
        original = {"id": "99", "username": "lectora",
                    "permalink": URL, "text": TEXT}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "proof.json")
            source = {"url": URL, "text": TEXT, "reply_to_us": True}
            with mock.patch.dict(os.environ, {"RRSS_GPT_PROVENANCE_PATH": path}):
                self.assertTrue(proof.record("threads", source, ACTION["text"],
                                             path=path))
                issued = proof.attach({"kind": "reply", "url": URL,
                                       "text": ACTION["text"]},
                                      source, "threads", path=path)
                self.assertIsNotNone(issued)
                decision = {"id": "99", **issued}
                plan = api.build_plan([original], {"actions": [decision]})
                self.assertEqual(len(plan), 1)
                self.assertEqual(plan[0]["reply_to_id"], "99")
                self.assertTrue(plan[0]["reply_to_us"])
                self.assertTrue(proof.verify(plan[0], "threads", path=path))
                altered = {**original, "text": TEXT + " contenido diferente"}
                self.assertEqual(api.build_plan([altered],
                    {"actions": [decision]}), [],
                    "Threads/build_plan: prueba no puede reutilizarse en otro post")

    def test_api_builder_does_not_invent_provenance_for_manual_text(self):
        source = {"id": "99", "username": "lectora",
                  "permalink": URL, "text": TEXT}
        plans = api.build_plan([source], {"actions": [
            {"id": "99", "text": ACTION["text"], "authored": "manual"}]})
        self.assertEqual(len(plans), 1)
        self.assertNotIn("gpt_proof", plans[0])
        with (mock.patch.dict(os.environ, {
                  "RRSS_ALLOW_UNMARKED_TEXT": "1", "PYTEST_CURRENT_TEST": ""}),
              tempfile.TemporaryDirectory() as tmp):
            self.assertEqual(writer.require_gpt(plans, "threads",
                path=os.path.join(tmp, "empty.json")), [])

    def test_uncertain_ack_is_persistently_reserved_not_retried(self):
        import action_ledger as ledger
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "actions.sqlite3")
            db = ledger.ActionLedger(path, clock=lambda: 1000.0)
            self.assertEqual(db.reserve("reply", URL), "ok")
            db.settle("reply", URL,
                      ledger.outcome_to_status("pendiente_verificacion"),
                      "pendiente_verificacion")
            self.assertEqual(db.status("reply", URL), ledger.UNCERTAIN)
            self.assertEqual(db.reserve("reply", URL), ledger.UNCERTAIN,
                             "Threads: un POST incierto jamás se reintenta a ciegas")

    def test_contextual_denial_has_short_skip_ttl_without_hiding_error(self):
        import action_ledger as ledger
        now = [1000.0]
        with tempfile.TemporaryDirectory() as tmp:
            db = ledger.ActionLedger(os.path.join(tmp, "actions.sqlite3"),
                                      clock=lambda: now[0])
            self.assertEqual(db.reserve("reply", URL), "ok")
            denied = "saltado_contexto_api_no_verificado"
            db.settle("reply", URL, ledger.outcome_to_status(denied), denied)
            self.assertEqual(db.reserve("reply", URL), ledger.SKIPPED_POLICY)
            now[0] += 6 * 3600 + 1
            self.assertEqual(db.reserve("reply", URL), "ok")

    def test_container_without_id_never_calls_publish(self):
        with (mock.patch.object(proof, "verify", return_value=True),
              mock.patch.object(api, "api_get", return_value={
                  "id": "99", "permalink": URL, "text": TEXT}),
              mock.patch.object(api, "api_post",
                                return_value={"bad": "no id"}) as post):
            with self.assertRaises(api.ReplyNotCreated):
                api.publish_reply("fake", "1", "99", ACTION["text"],
                                  proof_action=ACTION)
            self.assertEqual(post.call_count, 1)

    def test_manually_tagged_text_does_not_count_as_proof(self):
        forged = {**ACTION, "authored": "manual", "gpt_proof": None}
        with (mock.patch.object(api, "api_post") as post,
              mock.patch.object(api, "api_get") as get):
            with self.assertRaises(PermissionError):
                api.publish_reply("token-falso", "1", "99", ACTION["text"], proof_action=forged)
            get.assert_not_called()
            post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
