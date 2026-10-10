"""PR #79: pruebas de integración writer -> decisions -> builder -> executor offline.

Los tests previos validaban record/attach, pero no la reconstrucción de las
acciones que hace cada red a partir de los IDs compactos de sus escáneres.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import reply_provenance as proof
import reply_writer as writer
import bluesky_build_plan as bluesky
import mastodon_build_plan as mastodon
import tiktok_build_plan as tiktok
import tiktok_mobile_execute as mobile
import bluesky_execute as blue_exec


class BuilderProofPipeline(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patcher = mock.patch.dict(os.environ, {
            "RRSS_GPT_PROVENANCE_PATH": os.path.join(self.temp.name, "proofs.json"),
            "RRSS_ALLOW_UNMARKED_TEXT": "0",
        })
        self.patcher.start()
        self.text = "Qué ganas de leer esa historia."
        self.original = "Acabo de terminar la mejor novela de fantasía del año"

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def decision(self, net, source, post, target):
        self.assertTrue(proof.record(net, source, self.text,
                                     prompt_hash="a" * 64))
        attached = proof.attach(dict(target, kind="reply", text=self.text), source, net)
        self.assertIsNotNone(attached)
        return {k: v for k, v in attached.items()
                if k in ("gpt_proof", "gpt_context_hash", "gpt_prompt_hash", "post_text")} | {
                    "post": post, "kind": "comment" if net == "tiktok" else "reply",
                    "text": self.text,
                    **({"post_uri": source["post_uri"]} if net in ("bluesky", "mastodon") else {}),
                }

    def test_bluesky_preserves_proof_and_rejects_stale_text(self):
        uri = "at://did:plc:abc123/app.bsky.feed.post/3abced"
        url = "https://bsky.app/profile/lectora.example/post/3abced"
        post = {"id": "G001-P1", "uri": uri, "url": url, "text": self.original,
                "actions": ["reply"]}
        scan = {"shortlist": [{"id": "G001", "handle": "lectora.example",
                               "posts": [post]}]}
        source = {"post_uri": uri, "text": self.original}
        decision = self.decision("bluesky", source, "G001-P1", {"post_uri": uri})
        with mock.patch.object(bluesky._sc, "opinion_guard", return_value=None):
            plan = bluesky.build(scan, {"actions": [decision]})
        self.assertEqual(len(plan), 1)
        self.assertTrue(proof.verify(plan[0], "bluesky"))
        self.assertEqual(writer.require_gpt(plan, "bluesky"), plan)
        altered_scan = {"shortlist": [{**scan["shortlist"][0],
                                      "posts": [{**post, "text": self.original+" cambiado"}]}]}
        with mock.patch.object(bluesky._sc, "opinion_guard", return_value=None):
            self.assertEqual(bluesky.build(altered_scan, {"actions": [decision]}), [])

    def test_mastodon_preserves_proof_and_rejects_target_change(self):
        uri = "999991"
        url = "https://mastodon.social/@lectora/999991"
        post = {"id": "M001-P1", "status_id": uri, "url": url,
                "text": self.original, "actions": ["reply"]}
        scan = {"shortlist": [{"id": "M001", "acct": "lectora",
                               "posts": [post]}]}
        decision = self.decision("mastodon", {"post_uri": uri, "text": self.original},
                                 "M001-P1", {"status_id": uri})
        with mock.patch.object(mastodon._sc, "opinion_guard", return_value=None):
            plan = mastodon.build(scan, {"actions": [decision]})
        self.assertEqual(len(plan), 1)
        self.assertTrue(proof.verify(plan[0], "mastodon"))
        tampered = {**decision, "gpt_proof": "0" * 64}
        with mock.patch.object(mastodon._sc, "opinion_guard", return_value=None):
            self.assertEqual(mastodon.build(scan, {"actions": [tampered]}), [])

    def test_tiktok_preserves_proof_and_blocks_other_video(self):
        url = "https://www.tiktok.com/@lectora/video/12345"
        post = {"id": "T001-P1", "url": url, "caption": self.original,
                "actions": ["comment"]}
        scan = {"shortlist": [{"id": "T001", "handle": "lectora", "posts": [post]}]}
        decision = self.decision("tiktok", {"url": url, "text": self.original},
                                 "T001-P1", {"url": url})
        plan = tiktok.build(scan, {"actions": [decision]})
        self.assertEqual(len(plan), 1)
        self.assertTrue(proof.verify(plan[0], "tiktok"))
        different = {"shortlist": [{**scan["shortlist"][0],
                                   "posts": [{**post, "url": url[:-1]+"6"}]}]}
        self.assertEqual(tiktok.build(different, {"actions": [decision]}), [])

    def test_bluesky_final_preflight_rejects_url_uri_mismatch(self):
        a = "at://did:plc:abc123/app.bsky.feed.post/3aaaaa"
        b = "at://did:plc:abc123/app.bsky.feed.post/3bbbbb"
        good = {"kind": "reply", "handle": "lectora.example",
                "url": "https://bsky.app/profile/lectora.example/post/3aaaaa",
                "post_uri": a, "text": self.text, "gpt_proof": "x" * 64}
        bad = {**good, "url": "https://bsky.app/profile/lectora.example/post/3bbbbb"}
        with mock.patch.object(blue_exec.b, "_url_to_uri", side_effect=lambda u: b if u.endswith("3bbbbb") else a), \
             mock.patch.object(blue_exec.b, "warm_dids", return_value=None), \
             mock.patch.object(blue_exec.b, "_check_length", return_value=None), \
             mock.patch.object(blue_exec.b, "_check_spanish_orthography", return_value=None), \
             mock.patch.object(blue_exec.sc, "guard_plan_item", return_value=None), \
             mock.patch.object(blue_exec.dup, "check", return_value=[]):
            self.assertEqual(blue_exec._preflight_plan([bad]), [])
            self.assertEqual(len(blue_exec._preflight_plan([good])), 1)

    def test_reddit_direct_comment_id_matches_signed_destination(self):
        import reddit_comments as rc
        thread = "https://www.reddit.com/r/libros/comments/abc123/tema/?sort=new"
        signed = rc._reply_permalink(thread, "t1_cdef")
        self.assertEqual(signed,
                         "https://www.reddit.com/r/libros/comments/abc123/tema/?comment_id=cdef")
        item = {"id": "t1_cdef", "url": signed, "gpt_proof": "a" * 64}
        self.assertTrue(rc._certified_dom_target(thread, item))
        self.assertFalse(rc._certified_dom_target(thread, {**item, "id": "t1_otra"}))
        self.assertFalse(rc._certified_dom_target(
            "https://www.reddit.com/r/libros/comments/otro/tema/", item))

    def test_tiktok_web_with_proof_never_uses_fuzzy_fragment(self):
        import tiktok_execute as old_web
        action = {"kind": "comment", "handle": "lectora", "text": self.text,
                  "url": "https://www.tiktok.com/@lectora/video/12345"}
        source = {"url": action["url"], "text": self.original}
        self.assertTrue(proof.record("tiktok", source, self.text))
        signed = proof.attach(action, source, "tiktok")
        with mock.patch.object(old_web.tt, "comment", side_effect=AssertionError("No escribir")):
            self.assertEqual(old_web.run_plan([signed])[0]["resultado"],
                             "saltado_destino_web_no_verificable")

    def test_tiktok_mobile_uses_permalink_not_mutable_post_ref(self):
        original = "https://www.tiktok.com/@lectora/video/12345"
        ref = {"handle": "lectora", "ordinal": 0, "cap": "otro video",
               "id": "tt://@lectora/0/aaaaaaaa"}
        action = {"kind": "comment", "url": original, "post_ref": ref,
                  "text": self.text, "gpt_proof": "x" * 64}
        class Adapter:
            def __init__(self): self.target = None
            def comment(self, target, text): self.target = target; return "created"
        adapter = Adapter()
        self.assertEqual(mobile._one_action(adapter, action), "confirmado")
        self.assertEqual(adapter.target, original)


if __name__ == "__main__":
    unittest.main()
