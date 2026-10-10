import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import facebook_api as fb
import instagram_api as ig
import meta_common as mc


class CommonTests(unittest.TestCase):
    def test_unanswered_keeps_only_questions_from_others_not_yet_answered(self):
        items = [{"id": "1", "text": "¿Dónde lo compro?", "username": "ana", "timestamp": "2026-10-01"},
                 {"id": "2", "text": "Gracias", "username": "luis", "timestamp": "2026-10-02"},
                 {"id": "3", "text": "¿Y tú?", "username": "Yo", "timestamp": "2026-10-03"},
                 {"id": "4", "text": "¿Cuándo sale?", "username": "eva", "timestamp": "2026-10-04"},
                 {"id": "5", "text": "¿Seguro?", "username": "pau", "timestamp": "2026-10-05"}]
        out = mc.unanswered(items, ["yo"], answered_ids={"4"})
        self.assertEqual([i["id"] for i in out], ["5", "1"])

    def test_text_and_question_rules(self):
        self.assertEqual(mc.check_text("  Hola ", 10), "Hola")
        for bad in ("", "  ", "x" * 11):
            with self.assertRaises(ValueError):
                mc.check_text(bad, 10)
        with self.assertRaises(ValueError):
            mc.reject_returned_question("Gracias. ¿Y tú?")
        self.assertEqual(mc.reject_returned_question("Gracias. ¿Y tú?", allow=True), "Gracias. ¿Y tú?")

    def test_write_env_replaces_and_appends_keeping_crlf(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, ".env"), "wb") as stream:
                stream.write(b"A=1" + bytes([13, 10]) + b"TOKEN=old" + bytes([13, 10]))
            mc.write_env({"TOKEN": "new", "EXTRA": "x"}, root=tmp)
            raw = open(os.path.join(tmp, ".env"), "rb").read().decode()
            crlf = chr(13) + chr(10)
            self.assertEqual(raw, "A=1" + crlf + "TOKEN=new" + crlf + "EXTRA=x" + crlf)
            self.assertEqual(mc.read_env(root=tmp), {"A": "1", "TOKEN": "new", "EXTRA": "x"})


class PublishGuardTests(unittest.TestCase):
    def test_publishing_requires_explicit_approval(self):
        with self.assertRaises(PermissionError):
            fb.publish("t", "1", "Hola")
        with self.assertRaises(PermissionError):
            ig.publish_image("t", "1", "https://x/y.jpg", "caption")

    def test_reply_rejects_returned_question(self):
        with self.assertRaises(ValueError):
            fb.reply_comment("t", "1", "Sí. ¿Y tú?")
        with self.assertRaises(ValueError):
            ig.reply_comment("t", "1", "Sí. ¿Y tú?")


class InstagramTokenTests(unittest.TestCase):
    def test_days_left_and_refresh_skip(self):
        env = {"IG_TOKEN_CREATED": "2026-10-03", "IG_ACCESS_TOKEN": "x"}
        self.assertEqual(ig.token_days_left(env, datetime.date(2026, 10, 13)), 50)
        self.assertIsNone(ig.token_days_left({}, datetime.date(2026, 10, 13)))
        done, message = ig.refresh(env, today=datetime.date(2026, 10, 10), if_due=True)
        self.assertFalse(done)
        self.assertIn("no toca", message)

    def test_comments_pending_uses_replies_to_skip_answered_comments(self):
        calls = {"media": {"data": [{"id": "m1", "caption": "Mi post"}]},
                 "comments": {"data": [
                     {"id": "c1", "text": "¿Dónde?", "username": "ana", "timestamp": "2026-10-02",
                      "replies": {"data": [{"username": "autorademodiaz"}]}},
                     {"id": "c2", "text": "¿Cuándo?", "username": "eva", "timestamp": "2026-10-03"}]}}

        def fake_get(base, path, token, **params):
            return calls["media"] if path.endswith("/media") else calls["comments"]
        old = mc.graph_get
        mc.graph_get = fake_get
        try:
            pending = ig.comments_pending("t", "1", "autorademodiaz")
        finally:
            mc.graph_get = old
        self.assertEqual([c["id"] for c in pending], ["c2"])


if __name__ == "__main__":
    unittest.main()
