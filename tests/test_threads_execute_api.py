import os
import datetime as dt
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import threads_execute as te
import threads_api as api


class ApiReplyTests(unittest.TestCase):
    ITEM = {"handle": "ana", "kind": "reply", "text": "El segundo, sin duda.", "reply_to_id": "99",
            "post_text": "Cual recomiendas?"}

    def setUp(self):
        self.ITEM = {**type(self).ITEM,
            "post_created_at": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat()}

    def test_preflight_accepts_api_reply_without_text_fragment(self):
        plan = te._preflight_plan([dict(self.ITEM)])
        self.assertEqual(plan[0]["reply_to_id"], "99")
        self.assertTrue(plan[0]["text_fragment"])

    def test_run_plan_publishes_through_the_api_and_never_opens_the_browser(self):
        calls = []
        old = (api.publish_reply, api._env, te.t.reply_to)
        api.publish_reply = lambda token, user, rid, text, **kw: calls.append((token, user, rid, text)) or "1"
        api._env = lambda: {"THREADS_ACCESS_TOKEN": "tok", "THREADS_USER_ID": "7"}
        te.t.reply_to = lambda *a, **k: self.fail("no debe usar el navegador")
        try:
            results = te.run_plan([dict(self.ITEM)])
        finally:
            api.publish_reply, api._env, te.t.reply_to = old
        self.assertEqual(calls, [("tok", "7", "99", "El segundo, sin duda.")])
        self.assertEqual(results[0]["resultado"], "confirmado")


class DuplicateGuardTests(unittest.TestCase):
    def test_detects_existing_identical_reply_through_the_api(self):
        old = (api.api_get, api._env)
        api._env = lambda: {'THREADS_ACCESS_TOKEN': 't'}
        api.api_get = lambda path, token, **p: {'data': [{'text': 'Cuatro años y por fin punto final.  Enhorabuena.'}]}
        try:
            self.assertTrue(te._already_replied_via_api('Cuatro años y por fin punto final. Enhorabuena.'))
            self.assertFalse(te._already_replied_via_api('Otra cosa.'))
            api.api_get = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('red'))
            self.assertFalse(te._already_replied_via_api('Cuatro años y por fin punto final. Enhorabuena.'))
            # tres estados: un fallo de la API es UNKNOWN, no "no existe"
            self.assertEqual(te._reply_state('Cuatro años y por fin punto final. Enhorabuena.'), te.UNKNOWN)
            api.api_get = lambda path, token, **p: {'data': []}
            self.assertEqual(te._reply_state('Algo'), te.ABSENT)
            api.api_get = lambda path, token, **p: {'data': [{'text': 'Algo'}]}
            self.assertEqual(te._reply_state('Algo'), te.PRESENT)
        finally:
            api.api_get, api._env = old


if __name__ == "__main__":
    unittest.main()
