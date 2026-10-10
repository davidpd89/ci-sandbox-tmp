"""08/10: ningun banco de frases y ninguna respuesta/comentario sin texto de ChatGPT (David vio en Reddit respuestas sin sentido, p. ej. «¿lo recomiendas sin spoilers?» a quien puso «Audiolibros»)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import mastodon_welcome as mw
import pinterest_growth as pg
import reddit_comments as rc
import reply_writer as rw
import reply_provenance as proof
import x_replies as xr


class NoBanksTests(unittest.TestCase):
    def test_banks_do_not_exist(self):
        for module, names in ((xr, ("BANK",)), (rc, ("BANK", "REPLY_BANK", "TITLES", "REC_TEMPLATES")), (mw, ("OPENERS", "QUESTIONS", "TOPIC", "COLLECTION_LINES")), (pg, ("COMMENTS", "SPECIFIC_COMMENTS"))):
            for name in names:
                self.assertFalse(hasattr(module, name), f"{module.__name__}.{name} no deberia existir")
        for module, name in ((rc, "recommendation"), (mw, "compose"), (pg, "pick_comment")):
            self.assertFalse(hasattr(module, name), f"{module.__name__}.{name} no deberia existir")

    def test_builders_only_put_a_pending_marker(self):
        self.assertEqual(xr.choose_phrase("finished_book", set(), None), xr.PENDING_TEXT)
        self.assertIsNone(xr.choose_phrase(None, set(), None))
        plan = rc.build_plan([{"url": "https://reddit.com/r/libros/comments/a/b", "subreddit": "libros", "title": "Nuevas adquisiciones después de mucho tiempo", "author": "x", "comment_count": 1}], max_comments=2)
        self.assertTrue(plan and all(item["text"] == rc.PENDING_TEXT for item in plan))
        replies = rc.plan_replies([{"id": "t1_a", "author": "ana", "depth": 0, "text": "Para mí fue Los juegos del hambre"}], max_replies=2)
        self.assertTrue(replies and all(item["text"] == rc.PENDING_TEXT for item in replies))


class ProvenanceGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "gpt_provenance_v1.json")
        self.saved = os.environ.pop("RRSS_ALLOW_UNMARKED_TEXT", None)
        self.old_proof = os.environ.get("RRSS_GPT_PROVENANCE_PATH")
        os.environ["RRSS_GPT_PROVENANCE_PATH"] = self.path

    def tearDown(self):
        if self.saved is not None:
            os.environ["RRSS_ALLOW_UNMARKED_TEXT"] = self.saved
        if self.old_proof is None:
            os.environ.pop("RRSS_GPT_PROVENANCE_PATH", None)
        else:
            os.environ["RRSS_GPT_PROVENANCE_PATH"] = self.old_proof
        self.tmp.cleanup()

    def test_gpt_proof_is_scoped_and_manual_cannot_bypass(self):
        source = {"post_uri": "at://did:plc:abc123/app.bsky.feed.post/3abcd",
                  "text": "Una reseña de fantasía", "context": "lectura de saga"}
        text = "Enhorabuena, qué paso más grande"
        self.assertTrue(rw.mark_gpt(text, self.path, network="bluesky", source=source))
        proved = proof.attach({"kind": "reply", "handle": "b", "post_uri": source["post_uri"],
                               "text": "  Enhorabuena,  qué paso más grande "},
                              source, "bluesky", path=self.path)
        self.assertIsNotNone(proved)
        plan = [
            {"kind": "reply", "handle": "a", "text": "Qué buen libro."},
            proved,
            {"kind": "comment", "handle": "c", "text": "Escrito a mano", "authored": "manual"},
            {"kind": "like", "handle": "d"},
            {"kind": "reply", "handle": "e", "text": rc.PENDING_TEXT},
            {**proved, "handle": "f", "post_uri": source["post_uri"] + "x"},
        ]
        kept = rw.require_gpt(plan, "bluesky", log=lambda *_: None, path=self.path)
        self.assertEqual([i["handle"] for i in kept], ["b", "d"])

    def test_text_written_by_write_replies_passes_only_its_target(self):
        source = {"id": "p1", "network": "bluesky", "author": "ana_test_xyz",
                  "post_uri": "at://did:plc:abc123/app.bsky.feed.post/3abcde",
                  "text": "Terminé de leer una saga de fantasía y me ha encantado mucho"}
        fake = lambda question, attachments, wait: ('[{"id": "p1", "reply": "Cerrar una saga entera da mucha alegría, ya nos dirás cuál viene ahora."}]', "url")
        out = rw.write_replies([source], "bluesky", consult=fake, recent=[], log=lambda *_: None)
        self.assertEqual(len(out), 1)
        genuine = proof.attach({"kind": "reply", "handle": "ana", "post_uri": source["post_uri"],
                                "text": out["p1"]}, source, "bluesky", path=self.path)
        self.assertIsNotNone(genuine)
        kept = rw.require_gpt([genuine, {**genuine, "handle": "otra",
                                         "post_uri": source["post_uri"] + "x"}],
                              "bluesky", log=lambda *_: None, path=self.path)
        self.assertEqual([i["handle"] for i in kept], ["ana"])

    def test_every_executor_calls_the_guard(self):
        import glob
        tools = os.path.join(os.path.dirname(__file__), "..", "tools")
        # 08/10: TODOS los ejecutores (los nuevos tambien) salvo Instagram (parado) y pinterest_execute (solo publica pines propios, no comenta)
        executors = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(tools, "*_execute.py"))} - {"instagram_execute", "pinterest_execute"}
        self.assertGreaterEqual(len(executors), 8)
        for name in sorted(executors | {"pinterest_growth"}):
            source = open(os.path.join(os.path.dirname(__file__), "..", "tools", name + ".py"), encoding="utf-8").read()
            self.assertIn("require_gpt(", source, name)


class PinterestWriteCommentsTests(unittest.TestCase):
    """08/10: el plan de Pinterest fallaba con NameError (write_comments no existia) desde que se quitaron los bancos."""

    def test_every_name_called_by_the_plan_step_exists(self):
        import inspect
        source = inspect.getsource(pg.cmd_plan)
        self.assertIn("write_comments(", source)
        self.assertTrue(callable(pg.write_comments))

    def test_comments_use_chatgpt_text_and_pending_ones_are_dropped(self):
        import sys
        import types
        from unittest import mock
        asked = {}
        pin1 = "https://www.pinterest.com/pin/12345/"
        pin2 = "https://www.pinterest.com/pin/12346/"

        def fake_get(items, network, log):
            asked["items"] = items
            for source in items:
                self.assertTrue(proof.record(network, source,
                                "Esa paleta de colores da ganas de leer."))
            return {pin1: "Esa paleta de colores da ganas de leer."}

        saved = sys.modules.get("reply_queue")
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.dict(os.environ, {"RRSS_GPT_PROVENANCE_PATH":
                                               os.path.join(root, "provenance.json")}):
                sys.modules["reply_queue"] = types.SimpleNamespace(get_or_enqueue=fake_get)
                try:
                    plan = [
                        {"kind": "react", "url": pin1, "title": "x"},
                        {"kind": "comment", "url": pin1, "text": pg.PENDING_TEXT,
                         "title": "Estantería de fantasía con luces",
                         "desc": "Mi rincón de lectura para este otoño"},
                        {"kind": "comment", "url": pin2, "text": pg.PENDING_TEXT,
                         "title": "Libros", "desc": ""},
                    ]
                    out = pg.write_comments(plan, {}, log=lambda *_: None)
                    self.assertEqual([a["kind"] for a in out], ["react", "comment"])
                    self.assertEqual(out[1]["text"], "Esa paleta de colores da ganas de leer.")
                    self.assertTrue(proof.verify(out[1], "pinterest"))
                    self.assertIn("rincón de lectura", asked["items"][0]["text"])
                    self.assertEqual(len(asked["items"]), 1)
                finally:
                    if saved is not None:
                        sys.modules["reply_queue"] = saved
                    else:
                        del sys.modules["reply_queue"]


if __name__ == "__main__":
    unittest.main()
