import datetime
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import reply_queue as rq
import reply_writer as rw


class ReplyQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (rq.DIR, rq.PENDING, rq.ANSWERS, rw.replied_authors, rw.recent_reply_texts)
        rq.DIR = self.tmp.name
        rq.PENDING = os.path.join(self.tmp.name, "pending.json")
        rq.ANSWERS = os.path.join(self.tmp.name, "answers.json")
        rw.replied_authors = lambda network, days=30, today=None: set()
        rw.recent_reply_texts = lambda limit=120: []

    def tearDown(self):
        rq.DIR, rq.PENDING, rq.ANSWERS, rw.replied_authors, rw.recent_reply_texts = self.saved
        self.tmp.cleanup()

    def test_enqueue_then_answers_are_used(self):
        items = [{"id": "a1", "author": "ana", "text": "Terminé de leer una saga de fantasía y me ha encantado", "network": "bluesky"}]
        quiet = lambda *_: None
        self.assertEqual(rq.get_or_enqueue(items, "bluesky", quiet), {})              # primera vez: se encola
        self.assertEqual(len(rq._load(rq.PENDING)), 1)
        fake = lambda question, attachments, wait: ('[{"id": "q1", "reply": "Cerrar una saga completa da mucha alegría, ya nos dirás cuál viene ahora."}]', "url")
        self.assertEqual(rq.work_once(consult=fake, log=quiet), 1)
        self.assertEqual(rq._load(rq.PENDING), {})
        out = rq.get_or_enqueue(items, "bluesky", quiet)                               # segunda vez: ya hay respuesta
        self.assertEqual(out, {"a1": "Cerrar una saga completa da mucha alegría, ya nos dirás cuál viene ahora."})

    def test_failed_consult_keeps_pending_and_null_is_not_asked_again(self):
        items = [{"id": "a1", "author": "ana", "text": "Un post cualquiera sobre libros de fantasía", "network": "mastodon"}]
        quiet = lambda *_: None
        rq.get_or_enqueue(items, "mastodon", quiet)

        def boom(*_):
            raise RuntimeError("sin navegador")
        self.assertEqual(rq.work_once(consult=boom, log=quiet), 0)
        self.assertEqual(len(rq._load(rq.PENDING)), 1)                                 # se conserva
        null = lambda question, attachments, wait: ('[{"id": "q1", "reply": null}]', "url")
        rq.work_once(consult=null, log=quiet)
        self.assertEqual(rq._load(rq.PENDING), {})
        self.assertEqual(rq.get_or_enqueue(items, "mastodon", quiet), {})
        self.assertEqual(rq._load(rq.PENDING), {})                                     # descartada: no vuelve a encolarse


class WaitForBatchTests(unittest.TestCase):
    """08/10: la ronda espera a que el trabajador escriba su lote y lo usa en la misma ronda (antes solo se publicaba el 25 % de lo escrito)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (rq.DIR, rq.PENDING, rq.ANSWERS, rw.replied_authors, rq.worker_running)
        rq.DIR = self.tmp.name
        rq.PENDING = os.path.join(self.tmp.name, "pending.json")
        rq.ANSWERS = os.path.join(self.tmp.name, "answers.json")
        rw.replied_authors = lambda network, days=30, today=None: set()

    def tearDown(self):
        rq.DIR, rq.PENDING, rq.ANSWERS, rw.replied_authors, rq.worker_running = self.saved
        self.tmp.cleanup()

    def items(self):
        return [{"id": "p1", "network": "tiktok", "author": "ana_x", "text": "Terminé de leer una saga de fantasía y me ha encantado el final"},
                {"id": "p2", "network": "tiktok", "author": "luis_y", "text": "Empiezo un libro nuevo de fantasía juvenil este fin de semana"}]

    def test_round_uses_the_batch_the_worker_writes_while_it_waits(self):
        rq.worker_running = lambda: True
        calls = {"n": 0}
        items = self.items()

        def fake_sleep(_seconds):
            calls["n"] += 1
            if calls["n"] == 2:                      # el trabajador contesta a la segunda comprobacion
                answers = {rq.key_for("tiktok", items[0]): {"reply": "Ese final suena a final de los buenos.", "network": "tiktok", "ts": datetime.datetime.now().isoformat(timespec="seconds")},
                           rq.key_for("tiktok", items[1]): {"reply": None, "network": "tiktok", "ts": datetime.datetime.now().isoformat(timespec="seconds")}}
                rq._save(rq.ANSWERS, answers)

        with mock.patch.object(rq.time, "sleep", side_effect=fake_sleep):
            got = rq.get_or_enqueue(items, "tiktok", log=lambda *_: None, wait_min=5)
        self.assertEqual(got, {"p1": "Ese final suena a final de los buenos."})
        self.assertGreaterEqual(calls["n"], 2)

    def test_no_waiting_when_the_worker_is_not_running(self):
        rq.worker_running = lambda: False
        with mock.patch.object(rq.time, "sleep", side_effect=AssertionError("no debe esperar")):
            got = rq.get_or_enqueue(self.items(), "tiktok", log=lambda *_: None, wait_min=5)
        self.assertEqual(got, {})
        self.assertEqual(len(rq._load(rq.PENDING)), 2)         # sigue encolado para el trabajador

    def test_default_does_not_wait(self):
        rq.worker_running = lambda: True
        with mock.patch.object(rq.time, "sleep", side_effect=AssertionError("no debe esperar")):
            self.assertEqual(rq.get_or_enqueue(self.items(), "tiktok", log=lambda *_: None), {})

    def test_gives_up_after_the_deadline_and_keeps_going(self):
        rq.worker_running = lambda: True
        clock = {"t": 1000.0}
        with mock.patch.object(rq.time, "time", side_effect=lambda: clock["t"]), \
             mock.patch.object(rq.time, "sleep", side_effect=lambda s: clock.__setitem__("t", clock["t"] + 400)):
            got = rq.get_or_enqueue(self.items(), "tiktok", log=lambda *_: None, wait_min=5)
        self.assertEqual(got, {})


if __name__ == "__main__":
    unittest.main()


class StaleReplyAndAuthorTests(unittest.TestCase):
    """08/10: Mastodon repetia una respuesta ya publicada (autor None en api_comment_writer) y el preflight tumbaba la ronda entera."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = (rq.DIR, rq.PENDING, rq.ANSWERS, rw.replied_authors)
        rq.DIR = self.tmp.name
        rq.PENDING = os.path.join(self.tmp.name, "pending.json")
        rq.ANSWERS = os.path.join(self.tmp.name, "answers.json")
        rw.replied_authors = lambda network, days=30, today=None: set()

    def tearDown(self):
        rq.DIR, rq.PENDING, rq.ANSWERS, rw.replied_authors = self.saved
        self.tmp.cleanup()

    def test_candidate_with_acct_keeps_its_author(self):
        import api_comment_writer as w
        state = {"shortlist": [{"id": "M001", "acct": "ana@masto.es", "bio": "Lectora", "score": 3,
                                "posts": [{"id": "M001-P1", "text": "Acabo de terminar una saga de fantasía y estoy muy contento con el final", "actions": ["reply"]}]}]}
        items = w.pick_posts(state, 5)
        self.assertEqual(items[0]["author"], "ana@masto.es")
        self.assertIn("Lectora", items[0]["context"])

    def test_candidate_without_any_author_is_skipped(self):
        import api_comment_writer as w
        state = {"shortlist": [{"id": "M002", "posts": [{"id": "M002-P1", "text": "x" * 60, "actions": ["reply"]}]}]}
        self.assertEqual(w.pick_posts(state, 5), [])

    def test_cached_reply_already_published_is_not_reused(self):
        import check_duplicate_phrase as dup
        item = {"id": "p1", "network": "mastodon", "author": "nuevo_autor_xyz", "text": "Terminé de leer una saga de fantasía y me ha encantado mucho"}
        key = rq.key_for("mastodon", item)
        rq._save(rq.ANSWERS, {key: {"reply": "Frase que ya publicamos ayer.", "network": "mastodon", "ts": datetime.datetime.now().isoformat(timespec="seconds")}})
        saved = dup.check
        try:
            dup.check = lambda text: [("Mastodon", "2026-10-07", "@x", text)]
            got = rq.get_or_enqueue([item], "mastodon", log=lambda *_: None)
        finally:
            dup.check = saved
        self.assertEqual(got, {})
        self.assertNotIn(key, rq._load(rq.ANSWERS))
        self.assertIn(key, rq._load(rq.PENDING))
