"""PR #79: regresiones offline de la procedencia GPT por destino."""
import concurrent.futures
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import reply_provenance as p
import reply_writer as rw


class ProvenanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "proof.json")
        self.patch = mock.patch.dict(os.environ, {"RRSS_GPT_PROVENANCE_PATH": self.path,
                                                  "RRSS_ALLOW_UNMARKED_TEXT": "0"})
        self.patch.start()
        self.uri = "at://did:plc:abc123/app.bsky.feed.post/3abcd"
        self.source = {"post_uri": self.uri, "text": "He terminado esta novela de fantasía.",
                       "context": "reseña y saga completa", "author": "lectora"}
        self.reply = "Ese final tiene buena pinta."

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def issued(self, source=None, net="bluesky", now=None):
        source = source or self.source
        self.assertTrue(p.record(net, source, self.reply, path=self.path, now=now))
        action = {"kind": "reply", "post_uri": source["post_uri"], "text": self.reply}
        attached = p.attach(action, source, net, path=self.path, now=now)
        self.assertIsNotNone(attached)
        return attached

    def test_same_text_other_post_or_network_is_denied(self):
        action = self.issued()
        self.assertTrue(p.verify(action, "bluesky", path=self.path))
        self.assertFalse(p.verify({**action, "post_uri": self.uri + "x"}, "bluesky", path=self.path))
        self.assertFalse(p.verify(action, "mastodon", path=self.path))
        self.assertEqual(rw.require_gpt([action, {**action, "post_uri": self.uri + "x"},
                                         {"kind": "follow", "handle": "lectora"}],
                                        "bluesky", log=lambda *_: None),
                         [action, {"kind": "follow", "handle": "lectora"}])

    def test_context_and_source_edited(self):
        action = self.issued()
        self.assertIsNone(p.attach({"post_uri": self.uri, "text": self.reply},
                                   {**self.source, "context": "hilo distinto"}, "bluesky",
                                   path=self.path))
        self.assertFalse(p.verify({**action, "post_text": "Cambió el contenido original"},
                                  "bluesky", path=self.path))
        self.assertFalse(p.verify({**action, "text": "Otra frase"}, "bluesky", path=self.path))
        self.assertFalse(p.verify({**action, "gpt_context_hash": "0"*64}, "bluesky", path=self.path))

    def test_same_reply_cannot_be_relabelled_as_another_prompt(self):
        self.assertTrue(p.record("bluesky", self.source, self.reply,
                                 path=self.path, prompt_hash="a" * 64))
        original = p.attach({"kind": "reply", "post_uri": self.uri,
                             "text": self.reply}, self.source, "bluesky",
                            path=self.path)
        self.assertEqual(original["gpt_prompt_hash"], "a" * 64)
        previous_bytes = open(self.path, "rb").read()
        self.assertFalse(p.record("bluesky", self.source, self.reply,
                                  path=self.path, prompt_hash="b" * 64))
        self.assertEqual(open(self.path, "rb").read(), previous_bytes)
        self.assertTrue(p.verify(original, "bluesky", path=self.path))
        self.assertFalse(p.verify({**original, "gpt_prompt_hash": "b" * 64},
                                  "bluesky", path=self.path))

    def test_handle_renamed_same_stable_post(self):
        self.issued()
        changed = {**self.source, "author": "lectora_nuevo"}
        self.assertIsNotNone(p.attach({"post_uri": self.uri, "text": self.reply},
                                      changed, "bluesky", path=self.path))

    def test_ttl_future_unbound_and_manual_are_rejected(self):
        action = self.issued(now=1000)
        self.assertTrue(p.verify(action, "bluesky", path=self.path, now=1001))
        self.assertFalse(p.verify(action, "bluesky", path=self.path, now=1000+p.TTL))
        self.assertFalse(p.verify(action, "bluesky", path=self.path, now=1))
        self.assertEqual(rw.require_gpt([{"kind": "reply", "post_uri": self.uri,
                                           "text": self.reply, "authored": "manual"}],
                                        "bluesky", log=lambda *_: None), [])
        self.assertFalse(p.record("bluesky", {"text": "sin objetivo"}, self.reply, path=self.path))

    def test_corrupt_json_fail_closed_does_not_replace_bytes(self):
        with open(self.path, "wb") as f:
            f.write(b'{"broken"')
        old = open(self.path, "rb").read()
        self.assertFalse(p.record("bluesky", self.source, self.reply, path=self.path))
        self.assertEqual(old, open(self.path, "rb").read())

    def test_replace_error_does_not_destroy_original(self):
        old = self.issued()
        previous = open(self.path, "rb").read()
        with mock.patch.object(p.os, "replace", side_effect=PermissionError("Windows sharing")):
            self.assertFalse(p.record("bluesky", {**self.source, "context": "diferente"},
                                      "Otra respuesta", path=self.path))
        self.assertEqual(previous, open(self.path, "rb").read())
        self.assertTrue(p.verify(old, "bluesky", path=self.path))

    def test_concurrent_writes_under_shared_guard(self):
        sources = [{**self.source, "post_uri": self.uri + str(i)} for i in range(16)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            self.assertTrue(all(pool.map(lambda s: p.record("bluesky", s, self.reply, path=self.path), sources)))
        self.assertEqual(len(json.load(open(self.path, encoding="utf-8"))), 16)

    def test_canonical_network_matrix(self):
        urls = {
            "bluesky": {"post_uri": self.uri},
            "mastodon": {"status_id": "998877"},
            "x": {"url": "https://x.com/ana/status/1234567"},
            "threads": {"permalink": "https://www.threads.net/@ana/post/C12345"},
            "facebook": {"permalink": "https://www.facebook.com/ana/posts/12345"},
            "pinterest": {"url": "https://es.pinterest.com/pin/12345/"},
            "reddit": {"url": "https://www.reddit.com/r/libros/comments/abc123/titulo/"},
            "tiktok": {"url": "https://www.tiktok.com/@ana/video/1234567"},
        }
        for net, target in urls.items():
            with self.subTest(net=net):
                source = {"author": "ana", "text": "Una nueva novela de fantasía.", **target}
                self.assertTrue(p.record(net, source, self.reply, path=self.path))
                action = p.attach({"kind": "reply", "text": self.reply, **target}, source, net, path=self.path)
                self.assertIsNotNone(action)
                self.assertTrue(p.verify(action, net, path=self.path))
        self.assertFalse(p.canonical("mastodon", {"post_uri": "M001-P1"}))
        self.assertFalse(p.canonical("bluesky", {"post_uri": "G001-P1"}))
        self.assertFalse(p.canonical("reddit", {"url": "https://evil.invalid/r/a/comments/abc"}))
        self.assertFalse(p.canonical("tiktok", {"url": "https://tiktok.com/@ana"}))

    def test_queue_refuses_legacy_hit_and_recomposes_for_exact_context(self):
        import datetime
        import reply_queue as rq
        now = datetime.datetime.now().isoformat(timespec="seconds")
        src = {**self.source, "id": "p1", "network": "bluesky"}
        key = rq.key_for("bluesky", src)
        previous = {"reply": self.reply, "network": "bluesky", "ts": now}
        pending_path = os.path.join(self.tmp.name, "pending.json")
        answers_path = os.path.join(self.tmp.name, "answers.json")
        with mock.patch.multiple(rq, PENDING=pending_path, ANSWERS=answers_path,
                                 DIR=self.tmp.name), \
             mock.patch.object(rw, "new_authors_only", side_effect=lambda items,*_: items), \
             mock.patch.object(rq, "already_used", return_value=False):
            rq._save(answers_path, {key: previous})
            # Una respuesta de la cache anterior no tiene prueba: no se entrega.
            self.assertEqual(rq.get_or_enqueue([src], "bluesky", log=lambda *_: None), {})
            self.assertNotIn(key, rq._load(answers_path))
            self.assertIn(key, rq._load(pending_path))
            # La misma frase del GPT nuevo, esta vez emitida para el contexto correcto.
            self.assertTrue(p.record("bluesky", src, self.reply, path=self.path))
            rq._save(answers_path, {key: previous})
            self.assertEqual(rq.get_or_enqueue([src], "bluesky", log=lambda *_: None),
                             {"p1": self.reply})
            changed = {**src, "context": "el contenido cambió durante la ronda"}
            self.assertEqual(rq.get_or_enqueue([changed], "bluesky", log=lambda *_: None), {})
            self.assertNotIn(key, rq._load(answers_path))

    def test_queue_does_not_reask_without_stable_target(self):
        import datetime
        import reply_queue as rq
        src = {"id": "p1", "network": "bluesky", "author": "ana",
               "text": "Una saga recién terminada"}
        key = rq.key_for("bluesky", src)
        answers_path = os.path.join(self.tmp.name, "answers.json")
        pending_path = os.path.join(self.tmp.name, "pending.json")
        with mock.patch.multiple(rq, PENDING=pending_path, ANSWERS=answers_path,
                                 DIR=self.tmp.name), \
             mock.patch.object(rw, "new_authors_only", side_effect=lambda items,*_: items):
            rq._save(answers_path, {key: {"reply": self.reply, "network": "bluesky",
                                          "ts": datetime.datetime.now().isoformat(timespec="seconds")}})
            for _ in range(3):
                self.assertEqual(rq.get_or_enqueue([src], "bluesky", log=lambda *_: None), {})
            self.assertEqual(rq._load(pending_path), {})
            self.assertIn(key, rq._load(answers_path))

    def test_mastodon_alphanumeric_real_ref_versus_local_ordinal(self):
        self.assertEqual(p.canonical("mastodon", {"status_id": "external-snowflake.1"}),
                         "mastodon:status:external-snowflake.1")
        self.assertEqual(p.canonical("mastodon", {"status_id": "M001-P1"}), "")

    def test_fake_gpt_writer_to_simulated_final_executor(self):
        source = {**self.source, "id": "p1", "network": "bluesky"}
        consult = lambda *_: ('[{"id":"p1","reply":"Ese final tiene buena pinta."}]', None)
        with mock.patch.object(rw, "new_authors_only", side_effect=lambda items,*_: items), \
             mock.patch.object(rw, "recent_reply_texts", return_value=[]), \
             mock.patch.object(rw, "memoria_texto", return_value=""), \
             mock.patch.object(rw, "estilo_red_texto", return_value=""), \
             mock.patch.object(rw, "valid_reply", return_value=(True, "")):
            written = rw.write_replies([source], "bluesky", consult=consult, recent=[], log=lambda *_: None)
        self.assertEqual(written["p1"], self.reply)
        action = p.attach({"kind": "reply", "post_uri": self.uri, "text": written["p1"]},
                          source, "bluesky")
        self.assertEqual(len(action["gpt_prompt_hash"]), 64)
        self.assertEqual(rw.require_gpt([action], "bluesky", log=lambda *_: None), [action])
        forged = {**action, "gpt_prompt_hash": "0" * 64}
        self.assertEqual(rw.require_gpt([forged], "bluesky", log=lambda *_: None), [])
        other = {**action, "post_uri": self.uri + "different"}
        self.assertEqual(rw.require_gpt([other], "bluesky", log=lambda *_: None), [])


if __name__ == "__main__":
    unittest.main()
