"""08/10: ningun banco de frases y ninguna respuesta/comentario sin texto de ChatGPT (David vio en Reddit respuestas sin sentido, p. ej. «¿lo recomiendas sin spoilers?» a quien puso «Audiolibros»)."""
import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import mastodon_welcome as mw
import pinterest_growth as pg
import reddit_comments as rc
import reply_writer as rw
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
        plan = rc.build_plan([{"url": "https://reddit.com/r/libros/comments/a/b", "subreddit": "libros", "title": "Nuevas adquisiciones después de mucho tiempo", "author": "x", "comment_count": 1, "created": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)).isoformat()}], max_comments=2)
        self.assertTrue(plan and all(item["text"] == rc.PENDING_TEXT for item in plan))
        replies = rc.plan_replies([{"id": "t1_a", "author": "ana", "depth": 0, "text": "Para mí fue Los juegos del hambre"}], max_replies=2)
        self.assertTrue(replies and all(item["text"] == rc.PENDING_TEXT for item in replies))


class ProvenanceGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "gpt_texts.json")
        self.saved = os.environ.pop("RRSS_ALLOW_UNMARKED_TEXT", None)

    def tearDown(self):
        if self.saved is not None:
            os.environ["RRSS_ALLOW_UNMARKED_TEXT"] = self.saved
        self.tmp.cleanup()

    def test_unmarked_text_is_removed_and_gpt_or_manual_text_stays(self):
        rw.mark_gpt("Enhorabuena, qué paso más grande", self.path)
        plan = [
            {"kind": "reply", "handle": "a", "text": "Qué buen libro."},                                   # banco / sin procedencia: fuera
            {"kind": "reply", "handle": "b", "text": "  Enhorabuena,  qué paso más grande "},               # de ChatGPT (normalizado): se queda
            {"kind": "comment", "handle": "c", "text": "Escrito a mano", "authored": "manual"},            # explicitamente manual: se queda
            {"kind": "like", "handle": "d"},                                                              # sin texto: no afecta
            {"kind": "reply", "handle": "e", "text": rc.PENDING_TEXT},                                    # marcador pendiente: fuera
        ]
        kept = rw.require_gpt(plan, "test", log=lambda *_: None, path=self.path)
        self.assertEqual([i["handle"] for i in kept], ["b", "c", "d"])

    def test_text_written_by_write_replies_passes_the_guard(self):
        saved = rw.GPT_TEXTS
        rw.GPT_TEXTS = self.path
        try:
            fake = lambda question, attachments, wait: ('[{"id": "p1", "reply": "Cerrar una saga entera da mucha alegría, ya nos dirás cuál viene ahora."}]', "url")
            out = rw.write_replies([{"id": "p1", "network": "bluesky", "author": "ana_test_xyz", "text": "Terminé de leer una saga de fantasía y me ha encantado mucho"}], "bluesky", consult=fake, recent=[], log=lambda *_: None)
            self.assertEqual(len(out), 1)
            kept = rw.require_gpt([{"kind": "reply", "handle": "ana", "text": out["p1"]}, {"kind": "reply", "handle": "otra", "text": "Texto de banco cualquiera."}], "bluesky", log=lambda *_: None, path=self.path)
            self.assertEqual([i["handle"] for i in kept], ["ana"])
        finally:
            rw.GPT_TEXTS = saved

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
        asked = {}

        def fake_get(items, network, log):
            asked["items"] = items
            return {"https://pin/1": "Esa paleta de colores da ganas de leer."}

        saved = sys.modules.get("reply_queue")
        sys.modules["reply_queue"] = types.SimpleNamespace(get_or_enqueue=fake_get)
        try:
            plan = [
                {"kind": "react", "url": "https://pin/1", "title": "x"},
                {"kind": "comment", "url": "https://pin/1", "text": pg.PENDING_TEXT, "title": "Estantería de fantasía con luces", "desc": "Mi rincón de lectura para este otoño"},
                {"kind": "comment", "url": "https://pin/2", "text": pg.PENDING_TEXT, "title": "Libros", "desc": ""},
            ]
            out = pg.write_comments(plan, {}, log=lambda *_: None)
        finally:
            if saved is not None:
                sys.modules["reply_queue"] = saved
            else:
                del sys.modules["reply_queue"]
        self.assertEqual([a["kind"] for a in out], ["react", "comment"])
        self.assertEqual(out[1]["text"], "Esa paleta de colores da ganas de leer.")
        self.assertIn("rincón de lectura", asked["items"][0]["text"])
        self.assertEqual(len(asked["items"]), 1)         # el pin de una palabra no se pide


if __name__ == "__main__":
    unittest.main()
