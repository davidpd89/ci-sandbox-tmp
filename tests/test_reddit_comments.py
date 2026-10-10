import datetime
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import reddit_comments as rc
import reddit_interact as r
import x_replies


def thread(title, comments=3, sub="libros", url=None, created=None, author="otra"):
    return {"subreddit": f"r/{sub}", "title": title, "url": url or f"https://www.reddit.com/r/{sub}/comments/1abc{abs(hash(title)) % 9999}/t/", "author": author,
            "comment_count": comments, "post_type": "image", "created": created or datetime.datetime.now(datetime.timezone.utc).isoformat()}


class ClassifyTest(unittest.TestCase):
    def test_intents(self):
        self.assertEqual(rc.classify("Mi estantería después de la mudanza"), "shelf")
        self.assertEqual(rc.classify("Muestro mi última compra"), "haul")
        self.assertEqual(rc.classify("Joyitas que encontré en la feria del libro"), "haul")
        self.assertEqual(rc.classify("Acabo de terminar Mistborn"), "finished")
        self.assertEqual(rc.classify("Por fin terminé mi novela"), "writing_win")
        self.assertEqual(rc.classify("Estoy atascado con el segundo capítulo"), "writing_struggle")
        self.assertEqual(rc.classify("Hola a todos, me presento"), "welcome")

    def test_excludes_questions_opinions_politics(self):
        for title in ("¿Qué libro me recomendáis?", "Comparto mi relato, valoradlo", "Mi estantería y la política de Sánchez", "Megahilo semanal de lecturas", "Reglas del subreddit"):
            self.assertIsNone(rc.classify(title), title)


class PlanTest(unittest.TestCase):
    def test_plan_respects_limits_and_age(self):
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=40)).isoformat()
        threads = [thread("Mi estantería nueva"), thread("Mis compras de hoy", sub="escribir"), thread("Mi biblioteca en casa", comments=80), thread("Mi coleccion antigua", created=old),
                   thread("Mi estantería otra", sub="libros"), thread("Mi rincón de lectura", sub="libros")]
        plan = rc.build_plan(threads, max_comments=5, per_sub=2, rng=random.Random(1))
        subs = [p["subreddit"] for p in plan]
        self.assertLessEqual(subs.count("libros"), 2)
        self.assertEqual(len({p["url"] for p in plan}), len(plan))
        self.assertFalse(any("antigua" in p["motivo"] or "en casa" in p["motivo"] for p in plan))
        for p in plan:
            r._check_micro_comment(p["text"])

    def test_skips_own_threads_and_done(self):
<<<<<<< HEAD
        mine = thread("Mi estantería", author="AutoraDemoEscritor")
=======
        mine = thread("Mi estantería", author="DavidPortoEscritor")
>>>>>>> origin/research/public-reuse-parent
        done = thread("Mi biblioteca en casa")
        plan = rc.build_plan([mine, done], max_comments=2, done_keys={done["url"]})
        self.assertEqual(plan, [])


if __name__ == "__main__":
    unittest.main()


class ReplyTests(unittest.TestCase):
    def test_reply_kind(self):
        self.assertEqual(rc.reply_kind("Ensayo sobre la ceguera."), "title")
        self.assertEqual(rc.reply_kind("Flores para Algernon, de Daniel Keyes. Lo terminé el domingo y todavía lo recuerdo"), "explained")
        self.assertEqual(rc.reply_kind("Me dolió muchísimo ese final, aún pienso en él"), "empathic")
        self.assertEqual(rc.reply_kind("jajaja, el de siempre"), "humor")
        for text in ("¿Y tú cuál elegirías?", "Los amo a todos agregenme a ig para hablar de libros.", "Quarta asa ... Eu realmente nao estava esperando", "", "x"):
            self.assertIsNone(rc.reply_kind(text), text)

    def test_plan_replies_skips_done_own_and_children(self):
        comments = [
            {"id": "t1_a", "author": "ana", "depth": 0, "text": "Ensayo sobre la ceguera."},
            {"id": "t1_b", "author": "luis", "depth": 0, "text": "De ratones y hombres"},
<<<<<<< HEAD
            {"id": "t1_c", "author": "AutoraDemoEscritor", "depth": 1, "text": "Gran elección."},     # ya respondido a luis
=======
            {"id": "t1_c", "author": "DavidPortoEscritor", "depth": 1, "text": "Gran elección."},     # ya respondido a luis
>>>>>>> origin/research/public-reuse-parent
            {"id": "t1_d", "author": "pepe", "depth": 1, "text": "Venía a decir esto"},                # hijo de otro: no
            {"id": "t1_e", "author": "mar", "depth": 0, "text": "Soy leyenda"},
            {"id": "t1_f", "author": "AutoModerator", "depth": 0, "text": "Recordad las normas del subreddit"},
        ]
        plan = rc.plan_replies(comments, done_ids={"t1_e"}, max_replies=5, rng=random.Random(4))
        self.assertEqual([p["id"] for p in plan], ["t1_a"])
        rc.check_reply(plan[0]["text"])

    def test_check_reply_rules(self):
        rc.check_reply("¿Qué fue lo que más te marcó, sin hacer spoiler?")
        for bad in ("", "¿Qué tal? ¿Y el final?", "Mira https://x.com", " ".join(["palabra"] * 26)):
            with self.assertRaises(ValueError):
                rc.check_reply(bad)


class NoBankTests(unittest.TestCase):
    def test_micro_comments_need_chatgpt_text_and_a_concrete_title(self):
        import reply_queue
<<<<<<< HEAD
        threads = [{"url": "u1", "title": "Audiolibros", "author": "a"}, {"url": "u2", "title": "Terminé mi primera novela de fantasía", "author": "b"}]
        plan = [{"kind": "comment", "subreddit": "libros", "url": "u1", "text": "¿Lo recomendarías sin spoilers?"}, {"kind": "comment", "subreddit": "libros", "url": "u2", "text": "banco"}]
        original = reply_queue.get_or_enqueue
        try:
            reply_queue.get_or_enqueue = lambda items, network, log=print: {i["id"]: "Enhorabuena, qué paso más grande" for i in items}
            out = rc.write_comment_texts(plan, threads, log=lambda *_: None)
            self.assertEqual([a["url"] for a in out], ["u2"])                  # «Audiolibros» (1 palabra) no se comenta
            self.assertEqual(out[0]["text"], "Enhorabuena, qué paso más grande")  # nunca el texto del banco
            reply_queue.get_or_enqueue = lambda items, network, log=print: {}
            self.assertEqual(rc.write_comment_texts(plan, threads, log=lambda *_: None), [])   # sin respuesta de ChatGPT no se comenta
        finally:
            reply_queue.get_or_enqueue = original
=======
        import reply_provenance as proof
        import tempfile
        from unittest import mock
        bad = "https://www.reddit.com/r/libros/comments/abcd01/audiolibros/"
        good = "https://www.reddit.com/r/libros/comments/abcd02/primera_novela/"
        threads = [{"url": bad, "title": "Audiolibros", "author": "a"},
                   {"url": good, "title": "Terminé mi primera novela de fantasía", "author": "b"}]
        plan = [{"kind": "comment", "subreddit": "libros", "url": bad, "text": "¿Lo recomendarías sin spoilers?"},
                {"kind": "comment", "subreddit": "libros", "url": good, "text": "banco"}]
        original = reply_queue.get_or_enqueue
        response = "Enhorabuena, qué paso más grande"

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"RRSS_GPT_PROVENANCE_PATH": os.path.join(tmp, "proof.json")}):
                def generated(items, network, log=print):
                    for item in items:
                        self.assertTrue(proof.record(network, item, response))
                    return {i["id"]: response for i in items}
                try:
                    reply_queue.get_or_enqueue = generated
                    out = rc.write_comment_texts(plan, threads, log=lambda *_: None)
                    self.assertEqual([a["url"] for a in out], [good])
                    self.assertEqual(out[0]["text"], response)
                    self.assertTrue(proof.verify(out[0], "reddit"))
                    self.assertEqual(rc.write_comment_texts(plan, threads, log=lambda *_: None)[0]["url"], good)
                    reply_queue.get_or_enqueue = lambda items, network, log=print: {}
                    self.assertEqual(rc.write_comment_texts(plan, threads, log=lambda *_: None), [])
                finally:
                    reply_queue.get_or_enqueue = original

    def test_reddit_micro_without_issued_proof_fails_closed(self):
        import reply_queue
        from unittest import mock
        import tempfile
        good = "https://www.reddit.com/r/libros/comments/abcd02/primera_novela/"
        plan = [{"kind": "comment", "subreddit": "libros", "url": good, "text": "banco"}]
        threads = [{"url": good, "title": "Terminé mi primera novela de fantasía", "author": "b"}]
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"RRSS_GPT_PROVENANCE_PATH": os.path.join(tmp, "proof.json")}):
                with mock.patch.object(reply_queue, "get_or_enqueue",
                                       return_value={good: "Frase de otro post"}):
                    self.assertEqual(rc.write_comment_texts(plan, threads, log=lambda *_: None), [])
>>>>>>> origin/research/public-reuse-parent


class RedditContextTests(unittest.TestCase):
    """08/10: ChatGPT recibe título y texto del post; no se contesta a cierres en nuestros hilos."""

    def test_body_is_passed_with_title(self):
        text, context = rc.post_text_for_gpt("r/libros", "Audiolibros", "Llevo un mes escuchando audiolibros en el coche y no sé cuál elegir ahora")
        self.assertIn("Audiolibros", text)
        self.assertIn("audiolibros en el coche", text)
        self.assertIn("título y el texto", context)

    def test_vague_title_without_body_is_skipped(self):
        self.assertEqual(rc.post_text_for_gpt("libros", "Audiolibros", ""), ("", ""))

    def test_closing_comments_in_our_threads_get_no_reply(self):
        comments = [
            {"id": "t1_a", "author": "ana", "depth": 0, "text": "¡Gracias!"},
            {"id": "t1_b", "author": "luis", "depth": 0, "text": "Genial"},
            {"id": "t1_c", "author": "eva", "depth": 0, "text": "Para mí fue Los juegos del hambre"},
        ]
        plan = rc.plan_replies(comments, max_replies=5)
        self.assertEqual([item["author"] for item in plan], ["eva"])

    def test_comment_texts_use_body(self):
        import sys
        import types
        captured = {}
        fake = types.SimpleNamespace(get_or_enqueue=lambda items, net, log: captured.setdefault("items", items) and {})
        saved = sys.modules.get("reply_queue")
        sys.modules["reply_queue"] = fake
        try:
            threads = [{"url": "u1", "title": "Audiolibros", "author": "x", "body": "Busco recomendaciones de audiolibros de fantasía para el trabajo"}]
            rc.write_comment_texts([{"url": "u1", "subreddit": "libros"}], threads, log=lambda *_: None)
        finally:
            if saved is not None:
                sys.modules["reply_queue"] = saved
            else:
                del sys.modules["reply_queue"]
        self.assertIn("audiolibros de fantasía", captured["items"][0]["text"])

class RedditRepliesUseTheQueueTests(unittest.TestCase):
    def test_replies_in_our_threads_never_call_chatgpt_inside_the_browser(self):
        """08/10: write_replies dentro del navegador Playwright fallaba («Sync API inside the asyncio loop») y, sin banco, Reddit no respondia nunca."""
        import inspect
        source = inspect.getsource(rc.run_replies)
        self.assertNotIn("write_replies(", source)
        self.assertIn("reply_queue.get_or_enqueue(", source)

