"""R8: una cola corrupta no puede interpretarse como vacía ni sobrescribirse.

Todo ocurre en un TemporaryDirectory; los tests NO leen ni escriben datos
operativos de David.
"""
import pathlib
import json
import datetime
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reply_queue as rq


class CorruptedReplyQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pending = pathlib.Path(self.tmp.name) / "pending.json"
        self.answers = pathlib.Path(self.tmp.name) / "answers.json"
        self.old = (rq.ROOT, rq.DIR, rq.PENDING, rq.ANSWERS)
        rq.ROOT, rq.DIR, rq.PENDING, rq.ANSWERS = (
            self.tmp.name, self.tmp.name, str(self.pending), str(self.answers))

    def tearDown(self):
        rq.ROOT, rq.DIR, rq.PENDING, rq.ANSWERS = self.old
        self.tmp.cleanup()

    def test_missing_file_is_empty_only_for_first_run(self):
        self.assertEqual(rq._load(str(self.pending)), {})

    def test_invalid_json_is_quarantined_and_alerted_without_data_loss(self):
        original = b'{"tarea":"sin terminar"'
        self.pending.write_bytes(original)
        self.assertEqual(rq._load(str(self.pending)), {})
        backups = list(pathlib.Path(self.tmp.name).glob("pending.json.corrupto-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertFalse(self.pending.exists())
        events = list(pathlib.Path(self.tmp.name, "00_OPERATIVO", "cache",
                                   "errores_cola").glob("*.json"))
        self.assertEqual(len(events), 1)
        self.assertIn("COLA_CORRUPTA_RECUPERADA", events[0].read_text(encoding="utf-8"))
        self.assertNotIn("sin terminar", events[0].read_text(encoding="utf-8"))

    def test_wrong_root_is_backed_up_before_starting_empty(self):
        self.answers.write_text('["registro incompleto"]', encoding="utf-8")
        self.assertEqual(rq._load(str(self.answers)), {})
        backups = list(pathlib.Path(self.tmp.name).glob("answers.json.corrupto-*"))
        self.assertEqual(len(backups), 1)

    def test_get_or_enqueue_recovers_corrupt_pending_and_can_continue(self):
        original = b'{"entrada":'  # antes se convertía a {} y se reescribía
        self.pending.write_bytes(original)
        item = {"id": "test1", "network": "mastodon", "author": "lectora",
                "text": "He terminado un libro de fantasía y quiero comentarlo"}
        with mock.patch.object(rq.rw, "new_authors_only", return_value=[item]):
            self.assertEqual(rq.get_or_enqueue([item], "mastodon", log=lambda *_: None), {})
        self.assertEqual(len(rq._load(str(self.pending))), 1)
        self.assertEqual(list(pathlib.Path(self.tmp.name).glob("pending.json.corrupto-*"))[0].read_bytes(), original)

    def test_worker_quarantines_corrupt_queue_without_consulting_gpt(self):
        original = b'{"otro":"truncado"'
        self.pending.write_bytes(original)
        self.assertEqual(rq.work_once(consult=lambda *_: AssertionError("No debería consultar GPT")), 0)
        self.assertEqual(list(pathlib.Path(self.tmp.name).glob("pending.json.corrupto-*"))[0].read_bytes(), original)

    def test_permission_error_is_visible_not_treated_as_new_queue(self):
        with mock.patch("builtins.open", side_effect=PermissionError("locked")):
            with self.assertRaises(rq.QueueStateCorrupted):
                rq._load(str(self.answers))


class ExtendedRecoveryTests(unittest.TestCase):
    """Escenarios negativos sin datos productivos ni servicios remotos."""
    setUp = CorruptedReplyQueueTests.setUp
    tearDown = CorruptedReplyQueueTests.tearDown

    def test_transient_permission_on_read_retries_and_preserves_valid(self):
        item = {"k": {"network": "bluesky", "text": "Un libro",
                      "ts": datetime.datetime.now().isoformat()}}
        self.pending.write_text(json.dumps(item), encoding="utf-8")
        original_open = open
        calls = {"n": 0}
        def sometimes_locked(*args, **kwargs):
            if str(args[0]) == str(self.pending) and calls["n"] == 0:
                calls["n"] += 1
                raise PermissionError("read locked")
            return original_open(*args, **kwargs)
        with mock.patch("builtins.open", side_effect=sometimes_locked), \
             mock.patch.object(rq.time, "sleep") as sleep:
            self.assertEqual(rq._load(str(self.pending)), item)
        sleep.assert_called_once()
        self.assertEqual(calls["n"], 1)
        self.assertEqual(list(pathlib.Path(self.tmp.name).glob("pending.json.corrupto-*")), [])

    def test_persistent_permission_returns_empty_without_aborting_round(self):
        good = b'{"k":"dato preservado"}'
        self.pending.write_bytes(good)
        items = [{"id": "p1", "network": "mastodon", "author": "ana",
                  "text": "Esta semana estoy leyendo fantasía"}]
        original_open = open
        def locked_pending(*args, **kwargs):
            if str(args[0]) == str(self.pending):
                raise PermissionError("locked")
            return original_open(*args, **kwargs)
        with mock.patch.object(rq.rw, "new_authors_only", return_value=items), \
             mock.patch("builtins.open", side_effect=locked_pending), \
             mock.patch.object(rq.time, "sleep") as sleep:
            self.assertEqual(rq.get_or_enqueue(items, "mastodon", log=lambda *_: None), {})
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(self.pending.read_bytes(), good)
        self.assertFalse(list(pathlib.Path(self.tmp.name).glob("pending.json.corrupto-*")))

    def test_save_replace_retries_and_preserves_existing_on_failure(self):
        self.pending.write_bytes(b'{"conservado": true}')
        original_replace = rq.os.replace
        calls = {"n": 0}
        def transient(src, dst):
            calls["n"] += 1
            if calls["n"] == 1:
                raise PermissionError("sharing violation")
            return original_replace(src, dst)
        with mock.patch.object(rq.os, "replace", side_effect=transient), \
             mock.patch.object(rq.time, "sleep") as sleep:
            rq._save(str(self.pending), {"nuevo": True})
        self.assertEqual(calls["n"], 2)
        sleep.assert_called_once()
        self.assertEqual(json.loads(self.pending.read_text()), {"nuevo": True})
        with mock.patch.object(rq.os, "replace", side_effect=PermissionError("locked")), \
             mock.patch.object(rq.time, "sleep") as sleep:
            with self.assertRaises(rq.QueueStateCorrupted):
                rq._save(str(self.pending), {"mal": True})
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(json.loads(self.pending.read_text()), {"nuevo": True})
        self.assertEqual(list(pathlib.Path(self.tmp.name).glob(".pending.json.*.tmp")), [])

    def test_mixed_entries_salvages_good_records_without_losing_bytes(self):
        now = datetime.datetime.now().isoformat()
        payload = {"bien": {"network": "mastodon", "text": "Un libro", "ts": now},
                   "mal": "texto", "ts_malo": {"network": "x", "text": "post", "ts": "X"}}
        original = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.pending.write_bytes(original)
        self.assertEqual(rq._load(str(self.pending)), {"bien": payload["bien"]})
        self.assertEqual(json.loads(self.pending.read_text()), {"bien": payload["bien"]})
        backup = list(pathlib.Path(self.tmp.name).glob("pending.json.corrupto-*"))
        self.assertEqual(len(backup), 1)
        self.assertEqual(backup[0].read_bytes(), original)
        events = list(pathlib.Path(self.tmp.name, "00_OPERATIVO", "cache", "errores_cola").glob("*.json"))
        self.assertTrue(any(json.loads(e.read_text()).get("count") == 2 for e in events))
        with mock.patch.object(rq.rw, "write_replies", return_value={}):
            self.assertEqual(rq.work_once(log=lambda *_: None), 0)

    def test_quarantine_rename_failure_alerts_and_preserves_source(self):
        original = b'{bad:'
        self.pending.write_bytes(original)
        with mock.patch.object(rq.os, "rename", side_effect=PermissionError("rename blocked")), \
             mock.patch.object(rq.time, "sleep"):
            with self.assertRaises(rq.QueueStateCorrupted):
                rq._load(str(self.pending))
        self.assertEqual(self.pending.read_bytes(), original)
        events = list(pathlib.Path(self.tmp.name, "00_OPERATIVO", "cache", "errores_cola").glob("*.json"))
        self.assertTrue(any(json.loads(e.read_text()).get("code") == "COLA_CUARENTENA_FALLIDA" for e in events))

    def test_retention_never_deletes_the_last_quarantine(self):
        import os
        now = datetime.datetime.now().isoformat()
        self.pending.write_text(json.dumps({"ok": {"network": "bluesky", "text": "Un post", "ts": now}}))
        old = pathlib.Path(self.tmp.name, "pending.json.corrupto-20200101T000000000000-old")
        newest = pathlib.Path(self.tmp.name, "pending.json.corrupto-20200102T000000000000-new")
        old.write_bytes(b"old")
        newest.write_bytes(b"new")
        old_ts = datetime.datetime.now().timestamp() - 20 * 86400
        os.utime(old, (old_ts, old_ts))
        os.utime(newest, (old_ts + 100, old_ts + 100))
        self.assertEqual(len(rq._load(str(self.pending))), 1)
        self.assertFalse(old.exists())
        self.assertTrue(newest.exists())

    def test_recovery_read_after_save_avoids_dropping_valid_answers(self):
        now = datetime.datetime.now().isoformat()
        payload = {"good": {"ts": now, "reply": "Me gustó mucho", "network": "mastodon"},
                   "bad": "string"}
        self.answers.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(rq._load(str(self.answers)), {"good": payload["good"]})
        self.assertEqual(rq._load(str(self.answers)), {"good": payload["good"]})


    def test_failed_answers_write_preserves_generated_text_locally(self):
        old = {"previous": {"ts": datetime.datetime.now().isoformat(),
                            "network": "mastodon", "reply": "Ya escrita"}}
        self.answers.write_text(json.dumps(old), encoding="utf-8")
        generated = {"new": {"ts": datetime.datetime.now().isoformat(),
                             "network": "mastodon", "reply": "Respuesta no confirmada"}}
        with mock.patch.object(rq.os, "replace", side_effect=PermissionError("locked")), \
             mock.patch.object(rq.time, "sleep"):
            with self.assertRaises(rq.QueueStateCorrupted):
                rq._save(str(self.answers), generated)
        self.assertEqual(json.loads(self.answers.read_text()), old)
        saved = list(pathlib.Path(self.tmp.name).glob("answers.json.escritura-fallida-*"))
        self.assertEqual(len(saved), 1)
        self.assertEqual(json.loads(saved[0].read_text()), generated)
        self.assertEqual(list(pathlib.Path(self.tmp.name).glob(".answers.json.*.tmp")), [])

    def test_partial_data_write_failure_keeps_original_bytes(self):
        now = datetime.datetime.now().isoformat()
        raw = json.dumps({"valid": {"network": "mastodon", "text": "Libro", "ts": now},
                          "bad": "texto"}).encode("utf-8")
        self.pending.write_bytes(raw)
        with mock.patch.object(rq.os, "replace", side_effect=PermissionError("locked")), \
             mock.patch.object(rq.time, "sleep"):
            with self.assertRaises(rq.QueueStateCorrupted):
                rq._load(str(self.pending))
        self.assertEqual(self.pending.read_bytes(), raw)
        backups = list(pathlib.Path(self.tmp.name).glob("pending.json.corrupto-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), raw)

    def test_transient_rename_error_recovers_on_retry(self):
        original = b'{"incompleto":'
        self.pending.write_bytes(original)
        rename = rq.os.rename
        calls = {"n": 0}
        def one_failure(src, dst):
            calls["n"] += 1
            if calls["n"] == 1:
                raise PermissionError("windows sharing")
            return rename(src, dst)
        with mock.patch.object(rq.os, "rename", side_effect=one_failure), \
             mock.patch.object(rq.time, "sleep") as sleep:
            self.assertEqual(rq._load(str(self.pending)), {})
        self.assertEqual(calls["n"], 2)
        sleep.assert_called_once()
        self.assertEqual(list(pathlib.Path(self.tmp.name).glob("pending.json.corrupto-*"))[0].read_bytes(), original)

    def test_expired_event_files_pruned_on_valid_read(self):
        import os
        stamp = datetime.datetime.now().isoformat()
        self.pending.write_text(json.dumps({"ok": {"network": "x", "text": "Libro", "ts": stamp}}))
        alerts = pathlib.Path(self.tmp.name, "00_OPERATIVO", "cache", "errores_cola")
        alerts.mkdir(parents=True)
        old_event = alerts / "20200101-old.json"
        old_event.write_text('{"code":"COLA_CORRUPTA_RECUPERADA"}')
        old_ts = datetime.datetime.now().timestamp() - 20 * 86400
        os.utime(old_event, (old_ts, old_ts))
        self.assertEqual(len(rq._load(str(self.pending))), 1)
        self.assertFalse(old_event.exists())

    def test_worker_loop_keeps_interval_from_pr119(self):
        import inspect
        self.assertEqual(inspect.signature(rq.loop).parameters["pause_min"].default, 0.25)


class ConcurrentReplyQueueRegressionTests(CorruptedReplyQueueTests):
    """Reproducciones deterministas de carreras y reinicio sin acceder a redes."""

    def test_multiprocess_producers_do_not_overwrite_each_other(self):
        import os
        import subprocess
        script = """
import os, sys
sys.path.insert(0, sys.argv[1])
import reply_queue as rq
rq.ROOT = rq.DIR = sys.argv[2]
rq.PENDING = os.path.join(rq.DIR, "pending.json")
rq.ANSWERS = os.path.join(rq.DIR, "answers.json")
rq.rw.new_authors_only = lambda items, network, log: items
for i in range(5):
    n = sys.argv[3]
    item = {"id": n + "-" + str(i), "network": "mastodon",
            "author": n + "-" + str(i),
            "text": "Recomendación de lectura " + n + " " + str(i)}
    rq.get_or_enqueue([item], "mastodon", log=lambda *_: None)
"""
        tools = str(pathlib.Path(__file__).resolve().parents[1] / "tools")
        children = [subprocess.Popen(
            [sys.executable, "-c", script, tools, self.tmp.name, str(n)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for n in range(4)]
        try:
            for proc in children:
                stdout, stderr = proc.communicate(timeout=30)
                self.assertEqual(proc.returncode, 0, f"{stdout}\n{stderr}")
        finally:
            for proc in children:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate()
        self.assertEqual(len(rq._load(str(self.pending))), 20)

    def test_lock_permission_error_is_safe_and_round_continues(self):
        item = {"id": "one", "network": "bluesky", "author": "ana",
                "text": "Me gustan estos libros de fantasía"}
        with mock.patch.object(rq.rw, "new_authors_only", return_value=[item]), \
             mock.patch.object(rq.os, "open", side_effect=PermissionError("no lock")):
            self.assertEqual(rq.get_or_enqueue([item], "bluesky", log=lambda *_: None), {})
        self.assertFalse(self.pending.exists())
        alerts = pathlib.Path(self.tmp.name, "00_OPERATIVO", "cache", "errores_cola")
        self.assertTrue(any(
            json.loads(p.read_text()).get("code") == "COLA_BLOQUEO_FALLIDO"
            for p in alerts.glob("*.json")))

    def test_short_lock_releases_before_remote_consultation(self):
        import threading
        now = datetime.datetime.now().isoformat(timespec="seconds")
        rq._save(str(self.pending), {"first": {"network": "mastodon", "text": "Primera", "ts": now}})
        errors = []
        def consultation(*args, status, **kwargs):
            extra = [{"id": "p2", "author": "b", "network": "bluesky", "text": "Segunda lectura"}]
            def concurrent_producer():
                try:
                    rq.get_or_enqueue(extra, "bluesky", log=lambda *_: None)
                except Exception as exc:
                    errors.append(exc)
            with mock.patch.object(rq.rw, "new_authors_only", side_effect=lambda items, *_: items):
                th = threading.Thread(target=concurrent_producer, daemon=True)
                th.start()
                th.join(timeout=2)
                self.assertFalse(th.is_alive(), "El lock no puede durar la consulta a GPT")
            self.assertEqual(errors, [])
            status["consulted"] = True
            # Un None solo es terminal si el escritor certifica null explícito.
            status["outcomes"] = {"q1": "null"}
            return {"q1": None}
        with mock.patch.object(rq.rw, "write_replies", side_effect=consultation):
            self.assertEqual(rq.work_once(log=lambda *_: None), 0)
        self.assertEqual(len(rq._load(str(self.pending))), 1)

    def test_state_file_lock_is_reentrant_in_same_thread(self):
        with rq._storage_lock():
            rq._save(str(self.pending), {"a": {
                "network": "bluesky", "text": "Libro",
                "ts": datetime.datetime.now().isoformat(timespec="seconds")}})
            self.assertEqual(len(rq._load(str(self.pending))), 1)

    def test_worker_preserves_new_enqueue_while_gpt_writes(self):
        now = datetime.datetime.now().isoformat(timespec="seconds")
        first = {"network": "mastodon", "author": "a", "text": "Primera lectura", "ts": now}
        second = {"network": "bluesky", "author": "b", "text": "Segunda lectura", "ts": now}
        rq._save(str(self.pending), {"first": first})
        def consultation(items, network, *, status, **kwargs):
            # Otra ronda hace una operación real de escritura mientras el
            # trabajador ha liberado el almacenamiento para consultar GPT.
            current = rq._load(str(self.pending))
            current["second"] = second
            rq._save(str(self.pending), current)
            status["consulted"] = True
            return {"q1": "Me quedo con esa recomendación."}
        with mock.patch.object(rq.rw, "write_replies", side_effect=consultation):
            self.assertEqual(rq.work_once(log=lambda *_: None), 1)
        # R9 reindexa claves legadas durante la conciliación; comprobar
        # que se conservan los datos y la respuesta, no el alias antiguo.
        self.assertEqual(rq._load(str(self.pending)),
                         {rq.key_for("bluesky", second): second})
        self.assertIn(rq.key_for("mastodon", first), rq._load(str(self.answers)))

    def test_restart_uses_existing_answer_without_reconsulting_gpt(self):
        now = datetime.datetime.now().isoformat(timespec="seconds")
        rq._save(str(self.pending), {"k": {"network": "mastodon", "text": "Libro", "ts": now}})
        cached = {"reply": "Ya escrita por ChatGPT.", "network": "mastodon", "ts": now}
        rq._save(str(self.answers), {"k": cached})
        with mock.patch.object(rq.rw, "write_replies", side_effect=AssertionError("reconsulta evitada")):
            self.assertEqual(rq.work_once(log=lambda *_: None), 0)
        self.assertEqual(rq._load(str(self.pending)), {})
        self.assertEqual(rq._load(str(self.answers))["k"], cached)



if __name__ == "__main__":
    unittest.main()
