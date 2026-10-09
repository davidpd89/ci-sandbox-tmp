import csv
import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import api_comment_writer as acw
import loyalty
import relationship_policy as rp
import repost_policy
import reply_writer as rw


class RepostGuardTests(unittest.TestCase):
    def test_guard_drops_uncurated_and_caps_curated(self):
        with tempfile.TemporaryDirectory() as tmp:
            registro = os.path.join(tmp, "r.csv")
            plan = [{"kind": "repost", "url": "a"}, {"kind": "repost", "url": "b", "curated": True}, {"kind": "like", "url": "c"}] + [{"kind": "boost", "curated": True}] * 4
            kept = repost_policy.guard(plan, registro)
            self.assertEqual(sum(1 for i in kept if i["kind"] in repost_policy.SHARE_KINDS), 3)
            self.assertTrue(all(i.get("curated") for i in kept if i["kind"] in repost_policy.SHARE_KINDS))
            self.assertTrue(any(i["kind"] == "like" for i in kept))


class WriterRulesTests(unittest.TestCase):
    def test_prompt_has_memory_feedback_rule_and_reply_to_us(self):
        items = [{"id": "p1", "network": "x", "author": "a", "text": "Hola a todos", "context": "x", "reply_to_us": True}]
        prompt = rw.build_prompt(items, "x", recent=["Qué bien suena ese final, ya nos dirás qué lees ahora"], memoria=rw.memoria_texto(["Qué bien suena ese final, ya nos dirás qué lees ahora"]))
        self.assertIn("LO ÚLTIMO QUE HEMOS PUBLICADO", prompt)
        self.assertIn("Deseando leer más", prompt)
        self.assertIn("nos ha hecho a nosotros", prompt)
        self.assertIn("NO confiable", prompt)
        self.assertIn("ERRORES QUE NO SE PUEDEN REPETIR", prompt)
        self.assertIn("CÓMO SE SUELE CONTESTAR EN CADA RED", rw.build_prompt(items, "x"))

    def test_remember_and_memoria(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "m.json")
            rw.remember("buenas", "post uno", "respuesta uno", path=path)
            rw.remember("malas", "post dos", "respuesta dos", "no encaja", path=path)
            text = rw.memoria_texto(path=path)
            self.assertIn("respuesta uno", text)
            self.assertIn("no encaja", text)

    def test_authors_already_commented_are_skipped_unless_they_commented_us(self):
        original = rw.replied_authors
        rw.replied_authors = lambda network, days=30, today=None: {"slowbookish"}
        try:
            items = [{"id": "p1", "author": "slowbookish", "text": "x"}, {"id": "p2", "author": "slowbookish", "text": "y", "reply_to_us": True}, {"id": "p3", "author": "otra", "text": "z"}]
            kept = rw.new_authors_only(items, "threads", log=lambda *_: None)
            self.assertEqual([i["id"] for i in kept], ["p2", "p3"])
        finally:
            rw.replied_authors = original


class LoyaltyTests(unittest.TestCase):
    def test_record_dedupes_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "in.csv")
            old = rp.INBOUND
            rp.INBOUND = path
            try:
                today = datetime.date.today().isoformat()
                self.assertTrue(rp.log_inbound("bluesky", "ana", "like", path=path))
                self.assertFalse(rp.log_inbound("bluesky", "ana", "like", path=path))
                rp.log_inbound("bluesky", "ana", "comment", path=path)
                rp.log_inbound("bluesky", "bea", "follow", path=path)
                loyal = loyalty.loyal_accounts("bluesky")
                self.assertEqual(loyal["ana"], {"like": 1, "comment": 1})
                self.assertEqual(loyalty.loyal_handles("bluesky")[0], "ana")
                self.assertIn(today, open(path, encoding="utf-8").read())
            finally:
                rp.INBOUND = old


class ApiWriterTests(unittest.TestCase):
    def test_pick_posts_one_per_candidate_best_score(self):
        state = {"shortlist": [
            {"id": "G1", "handle": "a", "score": 9, "profile": {"bio": "lectora"}, "posts": [{"id": "G1-P1", "text": "Un post bastante largo sobre fantasía y libros que me gustan", "es": True, "actions": ["like", "reply"]}]},
            {"id": "G2", "handle": "b", "score": 5, "posts": [{"id": "G2-P1", "text": "corto", "es": True, "actions": ["reply"]}]},
            {"id": "G3", "handle": "c", "score": 7, "posts": [{"id": "G3-P1", "text": "Otro texto largo en inglés que no debería salir porque no es español", "es": False, "actions": ["reply"]}]},
        ]}
        items = acw.pick_posts(state, 5)
        self.assertEqual([i["id"] for i in items], ["G1-P1"])

    def test_merge_reply_replaces_like_on_same_post(self):
        merged = acw.merge({"actions": [{"post": "M1-P1", "kind": "favourite"}, {"post": "M2-P1", "kind": "favourite"}]}, [{"kind": "reply", "post": "M1-P1", "text": "hola"}])
        self.assertEqual(sorted((a["post"], a["kind"]) for a in merged["actions"]), [("M1-P1", "reply"), ("M2-P1", "favourite")])


if __name__ == "__main__":
    unittest.main()
