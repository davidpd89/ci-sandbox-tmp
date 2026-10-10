import datetime
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import threads_api as ta


def reply(id, text, user="ana", ts="2026-10-02T10:00:00+0000"):
    return {"id": id, "text": text, "username": user, "timestamp": ts}


class UnansweredTests(unittest.TestCase):
    def test_only_questions_from_others_not_already_answered(self):
        replies = [reply("1", "¿Cuál recomiendas?"), reply("2", "Gracias, apuntado."),
                   reply("3", "¿Y tú?", user="davidportodiaz"), reply("4", "¿Lo has leído?"),
                   reply("5", "¿Seguro?", ts="2026-10-03T09:00:00+0000")]
        out = ta.unanswered(replies, "DavidPortoDiaz", answered_ids={"4"})
        self.assertEqual([r["id"] for r in out], ["5", "1"])   # mas reciente primero

    def test_token_days_left(self):
        env = {"THREADS_TOKEN_CREATED": "2026-10-03"}
        self.assertEqual(ta.token_days_left(env, datetime.date(2026, 10, 13)), 50)
        self.assertIsNone(ta.token_days_left({}, datetime.date(2026, 10, 13)))


class WriteEnvAndRefreshTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.old_root = ta.ROOT
        ta.ROOT = self.tmp.name
        with open(os.path.join(self.tmp.name, '.env'), 'wb') as f:
            f.write(b'A=1' + bytes([13, 10]) + b'THREADS_ACCESS_TOKEN=old' + bytes([13, 10]))

    def tearDown(self):
        ta.ROOT = self.old_root
        self.tmp.cleanup()

    def test_write_env_replaces_and_appends_keeping_crlf(self):
        ta._write_env({'THREADS_ACCESS_TOKEN': 'new', 'THREADS_TOKEN_CREATED': '2026-10-03'})
        raw = open(os.path.join(self.tmp.name, '.env'), 'rb').read().decode()
        self.assertEqual(raw, 'A=1' + chr(13) + chr(10) + 'THREADS_ACCESS_TOKEN=new' + chr(13) + chr(10) + 'THREADS_TOKEN_CREATED=2026-10-03' + chr(13) + chr(10))

    def test_refresh_if_due_skips_when_plenty_of_days_left(self):
        env = {'THREADS_ACCESS_TOKEN': 'x', 'THREADS_TOKEN_CREATED': '2026-10-03'}
        done, message = ta.refresh(env, today=datetime.date(2026, 10, 10), if_due=True)
        self.assertFalse(done)
        self.assertIn('no toca', message)


class ReplyBuildTests(unittest.TestCase):
    ITEMS = [{'id': '99', 'username': 'ana', 'text': 'Cual?', 'timestamp': 't'}]

    def test_build_plan_uses_api_ids_and_rejects_questions(self):
        plan = ta.build_plan(self.ITEMS, {'actions': [{'id': '99', 'text': 'El segundo, sin duda.'}]})
        self.assertEqual((plan[0]['reply_to_id'], plan[0]['kind'], plan[0]['handle']), ('99', 'reply', 'ana'))
        with self.assertRaises(ValueError):
            ta.build_plan(self.ITEMS, {'actions': [{'id': '99', 'text': 'El segundo. ¿Y tú?'}]})
        with self.assertRaises(ValueError):
            ta.build_plan(self.ITEMS, {'actions': [{'id': '1', 'text': 'x'}]})

    def test_check_reply_text_limits(self):
        self.assertEqual(ta.check_reply_text('  Hola.  '), 'Hola.')
        for bad in ('', '   ', 'x' * 501):
            with self.assertRaises(ValueError):
                ta.check_reply_text(bad)

    def test_container_failure_is_reported_as_not_created(self):
        calls = []
        def fake_post(path, token, **params):
            calls.append(path)
            raise RuntimeError('Threads API 400: nope')
        old = ta.api_post
        ta.api_post = fake_post
        try:
            # El test de transporte parte de un preflight contextual ya probado
            # por separado. No permitir que un reply sin firma llegue al POST.
            import tempfile
            with tempfile.TemporaryDirectory() as temp, \
                 mock.patch.dict(os.environ, {
                     "RRSS_THREADS_ACTION_LEDGER_PATH": os.path.join(temp, "ledger.sqlite3")}), \
                 mock.patch.object(ta, "_verify_reply_destination", return_value=None):
                with self.assertRaises(ta.ReplyNotCreated):
                    ta.publish_reply('t', '1', '99', 'Hola.', proof_action={"kind": "reply",
                    "post_created_at": (datetime.datetime.now(datetime.timezone.utc)
                                        - datetime.timedelta(hours=2)).isoformat()})
        finally:
            ta.api_post = old
        self.assertEqual(calls, ['1/threads'])


if __name__ == "__main__":
    unittest.main()
