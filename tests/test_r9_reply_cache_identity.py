"""R9: dos posts distintos no pueden reutilizar una reply por los primeros 80 chars."""
import pathlib
import datetime
import json
import tempfile
from unittest import mock
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reply_queue as rq


class ReplyQueueIdentityTests(unittest.TestCase):
    def test_same_author_same_first_80_but_different_body_is_not_same_post(self):
        prefix = "La lectura del segundo libro de la saga avanza mucho y la autora lo comenta. " * 2
        a = {"author": "lectora", "text": prefix + "Acabo de empezar el primer capítulo"}
        b = {"author": "lectora", "text": prefix + "Lo he terminado y no quiero spoilers"}
        self.assertNotEqual(rq.key_for("mastodon", a), rq.key_for("mastodon", b))

    def test_identical_text_different_thread_context_is_not_same_reply(self):
        a = {"author": "lectora", "text": "Ese libro me interesa", "context": "pregunta si tiene romance"}
        b = {"author": "lectora", "text": "Ese libro me interesa", "context": "pregunta por la edad recomendada"}
        self.assertNotEqual(rq.key_for("threads", a), rq.key_for("threads", b))

    def test_external_comment_and_reply_to_us_must_not_share_cached_answer(self):
        a = {"author": "lectora", "text": "Qué historia tan curiosa", "reply_to_us": False}
        b = {**a, "reply_to_us": True}
        self.assertNotEqual(rq.key_for("bluesky", a), rq.key_for("bluesky", b))

    def test_same_author_text_at_different_verified_post_urls_is_different(self):
        a = {"author": "lectora", "text": "Se viene saga nueva", "post_uri": "at://did:plc:abc/post/uno"}
        b = {**a, "post_uri": "at://did:plc:abc/post/dos"}
        self.assertNotEqual(rq.key_for("bluesky", a), rq.key_for("bluesky", b))

    def test_legacy_pending_key_is_reindexed_but_answer_not_guessed(self):
        original = {"network": "mastodon", "author": "ana@instancia.ejemplo",
                    "text": "Leyendo una trilogía", "context": "bio: libros",
                    "ts": datetime.datetime.now().isoformat(timespec="seconds")}
        new_key = rq.key_for("mastodon", original)
        rekeyed = rq._rekey_pending({"1234567890abcdef": original})
        self.assertEqual(list(rekeyed), [new_key])
        self.assertEqual(rekeyed[new_key], original)

    def test_same_verified_post_partial_and_complete_context_has_one_key(self):
        post = {"author": "lectora", "text": "Me ha gustado este libro",
                "post_uri": "at://did:plc:abc/app.bsky.feed.post/1",
                "context": "bio: lectora", "reply_to_us": True}
        full = {**post, "id": "p88", "context": "bio: lectora y escritora",
                "conversation_context": "Dos respuestas de un hilo anterior"}
        self.assertEqual(rq.key_for("bluesky", post),
                         rq.key_for("bluesky", full))

    def test_pending_context_update_is_not_enqueued_twice(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            a = {"id": "p1", "author": "lectora", "text": "Me ha gustado",
                 "post_uri": "at://did:plc:abc/post/a",
                 "context": "fragmento"}
            b = {**a, "id": "p2", "context": "fragmento más completo"}
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(rq.rw, "new_authors_only", side_effect=lambda items,*_: items):
                    rq.get_or_enqueue([a], "bluesky", log=lambda *_: None)
                    rq.get_or_enqueue([b], "bluesky", log=lambda *_: None)
                pending = json.loads((path / "pending.json").read_text(encoding="utf-8"))
                self.assertEqual(len(pending), 1)
                self.assertEqual(next(iter(pending.values()))["context"], b["context"])

    def test_reused_answer_already_published_is_not_returned(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            item = {"id": "p1", "author": "lectora", "text": "Una nueva lectura",
                    "post_uri": "at://did:plc:abc/post/b"}
            key = rq.key_for("bluesky", item)
            (path / "answers.json").write_text(json.dumps({key: {
                "network": "bluesky", "reply": "Texto que ya publicamos",
                "ts": datetime.datetime.now().isoformat(timespec="seconds")}}),
                encoding="utf-8")
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(rq.rw, "new_authors_only", return_value=[item]), \
                     mock.patch.object(rq, "already_used", return_value=True):
                    result = rq.get_or_enqueue([item], "bluesky", log=lambda *_: None)
                self.assertEqual(result, {})
                self.assertEqual(len(rq._load(rq.PENDING)), 1)

    def test_api_writer_attaches_real_post_id_not_round_index(self):
        import api_comment_writer as api
        txt = "Estoy leyendo una saga juvenil de fantasía y he llegado al segundo libro"
        state = {"shortlist": [{"acct": "lector@ejemplo.social", "score": 1,
                "posts": [{"id": "M001-P1", "status_id": "99887",
                           "text": txt, "actions": ["reply"], "es": True}]}]}
        items = api.pick_posts(state, 1)
        self.assertEqual(items[0]["post_uri"], "99887")

    def test_ephemeral_batch_id_must_not_invalidate_cache(self):
        a = {"id": "p1", "author": "lectora", "text": "He vuelto a leerlo", "context": "sin spoilers"}
        b = {**a, "id": "p99"}
        self.assertEqual(rq.key_for("x", a), rq.key_for("x", b))

    def test_normalization_and_network_separation_still_work(self):
        a = {"author": "@Lectora", "text": " Este libro me gustó   mucho "}
        b = {"author": "@lectora", "text": "Este libro me gustó mucho"}
        self.assertEqual(rq.key_for("x", a), rq.key_for("x", b))
        self.assertNotEqual(rq.key_for("x", a), rq.key_for("reddit", b))


    def test_wait_min_api_preserved_after_r9(self):
        import inspect
        self.assertEqual(inspect.signature(rq.get_or_enqueue).parameters["wait_min"].default, 0)
        self.assertTrue(callable(rq._wait_for_batch))

    def test_stale_items_do_not_saturate_max_pending(self):
        import os
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            old = {f"old{i}": {"network": "x", "author": "a", "text": f"texto {i}",
                              "ts": "2020-01-01T00:00:00"} for i in range(rq.MAX_PENDING)}
            (path / "pending.json").write_text(json.dumps(old), encoding="utf-8")
            item = {"id": "p1", "author": "a", "text": "un texto nuevo"}
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(rq.rw, "new_authors_only", side_effect=lambda items,*_: items):
                    rq.get_or_enqueue([item], "x", log=lambda *_: None)
                self.assertEqual(len(rq._load(rq.PENDING)), 1)

    def test_worker_preserves_enqueue_during_model_call(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            a = {"id": "p1", "author": "ana", "text": "Un mensaje del primer autor"}
            b = {"id": "p2", "author": "bea", "text": "Un mensaje del segundo autor"}
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(rq.rw, "new_authors_only", side_effect=lambda items,*_: items):
                    rq.get_or_enqueue([a], "bluesky", log=lambda *_: None)
                    def generated(items, network, **kwargs):
                        rq.get_or_enqueue([b], "bluesky", log=lambda *_: None)
                        kwargs["status"]["consulted"] = True
                        return {"q1": "Me interesa ese primer libro."}
                    with mock.patch.object(rq.rw, "write_replies", side_effect=generated):
                        self.assertEqual(rq.work_once(log=lambda *_: None), 1)
                pending = rq._load(rq.PENDING)
                self.assertEqual(len(pending), 1)
                self.assertEqual(next(iter(pending.values()))["author"], "bea")
                self.assertEqual(len(rq._load(rq.ANSWERS)), 1)

    def test_worker_does_not_consume_enriched_context(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            base = {"id": "p1", "author": "ana", "text": "El libro empieza fuerte",
                    "post_uri": "at://did:plc:abc/app.bsky.feed.post/xyz", "context": "breve"}
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(rq.rw, "new_authors_only", side_effect=lambda items,*_: items):
                    rq.get_or_enqueue([base], "bluesky", log=lambda *_: None)
                    def generated(items, network, **kwargs):
                        rq.get_or_enqueue([{**base, "context": "bio detallada y conversación"}],
                                          "bluesky", log=lambda *_: None)
                        kwargs["status"]["consulted"] = True
                        return {"q1": "Respuesta al contexto antiguo"}
                    with mock.patch.object(rq.rw, "write_replies", side_effect=generated):
                        self.assertEqual(rq.work_once(log=lambda *_: None), 0)
                self.assertEqual(len(rq._load(rq.PENDING)), 1)
                self.assertEqual(rq._load(rq.ANSWERS), {})

    def test_recover_answer_written_before_pending_removal(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            item = {"network": "x", "author": "ana", "text": "Un contenido de otro día",
                    "ts": datetime.datetime.now().isoformat(timespec="seconds")}
            key = rq.key_for("x", item)
            (path / "pending.json").write_text(json.dumps({key: item}), encoding="utf-8")
            (path / "answers.json").write_text(json.dumps({key: {
                "network": "x", "reply": "Una respuesta ya generada",
                "ts": datetime.datetime.now().isoformat(timespec="seconds")}}), encoding="utf-8")
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(rq.rw, "write_replies", side_effect=AssertionError("No reconsultar")):
                    self.assertEqual(rq.work_once(log=lambda *_: None), 0)
                self.assertEqual(rq._load(rq.PENDING), {})

    def test_parallel_producers_do_not_drop_each_other(self):
        import concurrent.futures
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            def enqueue(n):
                item = {"id": str(n), "author": "a" + str(n), "text": "Post distinto " + str(n)}
                rq.get_or_enqueue([item], "x", log=lambda *_: None)
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(rq.rw, "new_authors_only", side_effect=lambda items,*_: items):
                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                        list(pool.map(enqueue, range(25)))
                self.assertEqual(len(rq._load(rq.PENDING)), 25)


    def test_old_sha1_answer_not_reused_without_provenance(self):
        import hashlib
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            item = {"id": "p1", "author": "ana", "text": "Uno" * 45}
            legacy_base = f"bluesky|{rq.rw._fold('ana')}|{rq.rw._fold(item['text'])[:80]}"
            old_key = hashlib.sha1(legacy_base.encode("utf-8")).hexdigest()[:16]
            (path / "answers.json").write_text(json.dumps({old_key: {
                "reply": "No puede atribuirse a un post completo",
                "ts": datetime.datetime.now().isoformat(timespec="seconds")
            }}), encoding="utf-8")
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(rq.rw, "new_authors_only", return_value=[item]):
                    self.assertEqual(rq.get_or_enqueue([item], "bluesky", log=lambda *_: None), {})
                self.assertIn(old_key, rq._load(rq.ANSWERS))
                self.assertEqual(len(rq._load(rq.PENDING)), 1)

    def test_worker_prunes_expired_answers_and_keeps_fresh(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            item = {"network": "x", "author": "ana", "text": "Hola",
                    "ts": datetime.datetime.now().isoformat(timespec="seconds")}
            key = rq.key_for("x", item)
            (path / "pending.json").write_text(json.dumps({key: item}), encoding="utf-8")
            (path / "answers.json").write_text(json.dumps({
                "a" * 16: {"reply": "Antigua", "ts": "2020-01-01T00:00:00"},
                "b" * 24: {"reply": "Reciente", "ts": datetime.datetime.now().isoformat(timespec="seconds")}
            }), encoding="utf-8")
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                def generated(items, network, **kwargs):
                    kwargs["status"]["consulted"] = True
                    return {"q1": "Nueva respuesta"}
                with mock.patch.object(rq.rw, "write_replies", side_effect=generated):
                    self.assertEqual(rq.work_once(log=lambda *_: None), 1)
                self.assertNotIn("a" * 16, rq._load(rq.ANSWERS))
                self.assertIn("b" * 24, rq._load(rq.ANSWERS))


    def test_malformed_cache_fails_closed_without_overwriting(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            for filename in ("answers.json", "pending.json"):
                (path / "answers.json").write_text("{}", encoding="utf-8")
                (path / "pending.json").write_text("{}", encoding="utf-8")
                target = path / filename
                target.write_bytes(b'{"registro": ')
                previous = target.read_bytes()
                with mock.patch.multiple(rq, ROOT=root, DIR=root, PENDING=str(path / "pending.json"),
                                         ANSWERS=str(path / "answers.json")):
                    with mock.patch.object(rq.rw, "new_authors_only", side_effect=lambda items,*_: items):
                        rq.get_or_enqueue([{"id": "a", "author": "a", "text": "Un mensaje"}],
                                          "bluesky", log=lambda *_: None)
                # #105 R8 no sobrescribe bytes corruptos: los pone en cuarentena
                # y permite continuar con un estado nuevo y un evento recuperable.
                backups = list(path.glob(filename + ".corrupto-*"))
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0].read_bytes(), previous)
                # #105 permite que answers.json permanezca ausente después de
                # cuarentena si no hubo ninguna respuesta que escribir.
                if target.exists():
                    self.assertIsInstance(json.loads(target.read_text(encoding="utf-8")), dict)
                else:
                    self.assertEqual(filename, "answers.json")
                events = list((path / "00_OPERATIVO" / "cache" / "errores_cola").glob("*.json"))
                self.assertTrue(events)

    def test_duplicate_history_failure_withholds_cached_reply(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            item = {"id": "a", "author": "ana", "text": "Una novela nueva"}
            key = rq.key_for("x", item)
            answer = {"network": "x", "reply": "Respuesta que no se debe reutilizar a ciegas",
                      "ts": datetime.datetime.now().isoformat(timespec="seconds")}
            (path / "answers.json").write_text(json.dumps({key: answer}), encoding="utf-8")
            import check_duplicate_phrase as dup
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(rq.rw, "new_authors_only", return_value=[item]):
                    with mock.patch.object(dup, "check", side_effect=OSError("ledger no accesible")):
                        self.assertEqual(rq.get_or_enqueue([item], "x", log=lambda *_: None), {})
                self.assertIn(key, rq._load(rq.ANSWERS))
                self.assertEqual(rq._load(rq.PENDING), {})

    def test_wait_does_not_release_unverified_reply(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            item = {"id": "a", "author": "ana", "text": "Una novela nueva"}
            key = rq.key_for("x", item)
            (path / "answers.json").write_text(json.dumps({key: {
                "reply": "Texto sin comprobar", "network": "x",
                "ts": datetime.datetime.now().isoformat(timespec="seconds")
            }}), encoding="utf-8")
            import check_duplicate_phrase as dup
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(dup, "check", side_effect=PermissionError("ledger inaccesible")) as check:
                    with mock.patch.object(rq.time, "sleep", return_value=None):
                        self.assertEqual(rq._wait_for_batch([item], "x", {key: True},
                                       1, log=lambda *_: None), {})
                    check.assert_called_once_with("Texto sin comprobar")

    def test_stale_duplicate_does_not_discard_fresh_same_post(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            old = {"network": "x", "author": "ana", "text": "Mismo mensaje",
                   "context": "antiguo y extensísimo " * 20, "post_uri": "https://example.invalid/post/abc",
                   "ts": "2020-01-01T00:00:00"}
            new = {**old, "context": "vigente", "ts": datetime.datetime.now().isoformat(timespec="seconds")}
            (path / "pending.json").write_text(json.dumps({"legacy_old": old, "legacy_new": new}), encoding="utf-8")
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(rq.rw, "new_authors_only", side_effect=lambda items,*_: items):
                    rq.get_or_enqueue([{"id": "i", "author": "ana", "text": "Mismo mensaje",
                                       "post_uri": old["post_uri"]}], "x", log=lambda *_: None)
                got = rq._load(rq.PENDING)
                self.assertEqual(len(got), 1)
                self.assertEqual(next(iter(got.values()))["context"], "vigente")


<<<<<<< HEAD
    def test_two_fresh_legacy_aliases_keep_newer_ttl_and_richer_context(self):
=======
    def test_two_fresh_legacy_aliases_keep_newer_snapshot_without_splicing_context(self):
>>>>>>> origin/research/public-reuse-parent
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            older = {"network": "x", "author": "ana", "text": "La novela fantástica",
                     "post_uri": "https://example.invalid/item/7", "reply_to_us": True,
                     "context": "bio extensa " * 20, "conversation_context": "hilo completo",
                     "ts": (datetime.datetime.now() - datetime.timedelta(hours=30)).isoformat(timespec="seconds")}
            latest = {**older,
                      "context": "bio nueva", "conversation_context": "",
                      "ts": datetime.datetime.now().isoformat(timespec="seconds")}
            (path / "pending.json").write_text(json.dumps({"k1": older, "k2": latest}), encoding="utf-8")
            with mock.patch.multiple(rq, DIR=root, PENDING=str(path / "pending.json"),
                                     ANSWERS=str(path / "answers.json")):
                with mock.patch.object(rq.rw, "new_authors_only", side_effect=lambda items,*_: items):
                    rq.get_or_enqueue([{"id": "id", "author": "ana", "text": "La novela fantástica",
                                       "post_uri": older["post_uri"], "reply_to_us": True}],
                                      "x", log=lambda *_: None)
                pending = rq._load(rq.PENDING)
                self.assertEqual(len(pending), 1)
                only = next(iter(pending.values()))
                self.assertEqual(only["ts"], latest["ts"])
<<<<<<< HEAD
                self.assertEqual(only["context"], older["context"])
=======
                # Contexto nuevo y bio antigua no deben componerse:
                # la combinación nunca fue un snapshot de publicación real.
                self.assertEqual(only["context"], latest["context"])
                self.assertEqual(only["conversation_context"], latest["conversation_context"])
>>>>>>> origin/research/public-reuse-parent
                self.assertTrue(only["reply_to_us"])


    def test_failed_replace_preserves_generated_answer_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root)
            target = path / "answers.json"
            previous = b'{"clave": {"reply": "respuesta anterior"}}'
            target.write_bytes(previous)
            with mock.patch.multiple(rq, DIR=root, ANSWERS=str(target)):
                with mock.patch.object(rq.os, "replace", side_effect=PermissionError("sharing violation")):
                    with self.assertRaises(rq.QueueStateCorrupted):
                        rq._save(str(target), {"otra": {"reply": "Una respuesta útil"}})
            self.assertEqual(target.read_bytes(), previous)
            backups = list(path.glob("answers.json.escritura-fallida-*"))
            self.assertEqual(len(backups), 1)
            self.assertIn("Una respuesta útil", backups[0].read_text(encoding="utf-8"))

if __name__ == "__main__":
    unittest.main()
