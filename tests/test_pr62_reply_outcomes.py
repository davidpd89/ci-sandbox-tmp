"""PR #62: contratos de respuesta diferida, sin navegador ni cuentas reales."""
import datetime as dt
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reply_queue as rq
import reply_writer as rw


class DeferredReplyReliabilityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        self.real_build_prompt = rw.build_prompt
        patchers = [
            mock.patch.multiple(rq, ROOT=str(self.root), DIR=str(self.root),
                                PENDING=str(self.root / "pending.json"),
                                ANSWERS=str(self.root / "answers.json"),
                                LOCK=str(self.root / "worker.lock")),
            mock.patch.object(rw, "new_authors_only", side_effect=lambda items, *_: items),
            mock.patch.object(rw, "recent_reply_texts", return_value=[]),
            mock.patch.object(rw, "build_prompt", return_value="prompt sintético y fijo"),
            mock.patch.object(rw, "valid_reply", return_value=(True, "")),
            mock.patch.object(rw, "mark_gpt", return_value=True),
            mock.patch.object(rq, "_proof_ready", return_value=True),
            mock.patch.object(rq, "already_used", return_value=False),
            mock.patch.object(rq, "worker_running", return_value=False),
            mock.patch.dict(os.environ, {"RRSS_ALLOW_UNMARKED_TEXT": ""}),
        ]
        for p in patchers:
            p.start()
            self.addCleanup(p.stop)
        self.quiet = lambda *_: None

    def item(self, suffix, *, context="Lectura de fantasía", history=""):
        return {
            "id": "i" + suffix, "network": "bluesky",
            "author": "lectora_" + suffix,
            "text": "Un comentario sobre una lectura reciente",
            "context": context, "conversation_context": history,
            "post_uri": "at://did:plc:abc/app.bsky.feed.post/" + suffix,
        }

    def enqueue(self, *items):
        return rq.get_or_enqueue(items, "bluesky", log=self.quiet)

    def consult(self, payload):
        return lambda *_: (payload, "offline://consulta-falsa")

    def test_partial_json_keeps_unmentioned_pending_for_next_round(self):
        a, b = self.item("a"), self.item("b")
        self.enqueue(a, b)
        self.assertEqual(rq.work_once(consult=self.consult(
            '[{"id":"q1","reply":"El primero parece interesante."}]'), log=self.quiet), 1)
        pending = rq._load(rq.PENDING)
        answers = rq._load(rq.ANSWERS)
        self.assertEqual(set(pending), {rq.key_for("bluesky", b)})
        self.assertEqual(answers[rq.key_for("bluesky", a)]["state"], "written")
        self.assertNotIn(rq.key_for("bluesky", b), answers)
        self.assertEqual(pending[rq.key_for("bluesky", b)]["incomplete_attempts"], 1)
        # Un intento posterior con null explícito cierra solamente el ID b.
        pending[rq.key_for("bluesky", b)]["retry_after"] = "2020-01-01T00:00:00"
        rq._save(rq.PENDING, pending)
        self.assertEqual(rq.work_once(consult=self.consult(
            '[{"id":"q1","reply":null}]'), log=self.quiet), 0)
        self.assertEqual(rq._load(rq.PENDING), {})
        self.assertEqual(rq._load(rq.ANSWERS)[rq.key_for("bluesky", b)]["state"], "null")

    def test_broken_json_keeps_pending_and_enforces_backoff(self):
        a = self.item("a")
        self.enqueue(a)
        self.assertEqual(rq.work_once(consult=self.consult("Esto no es JSON"), log=self.quiet), 0)
        pending = rq._load(rq.PENDING)
        self.assertEqual(len(pending), 1)
        entry = next(iter(pending.values()))
        self.assertEqual(entry["incomplete_attempts"], 1)
        self.assertGreater(dt.datetime.fromisoformat(entry["retry_after"]), dt.datetime.now())
        self.assertEqual(rq._load(rq.ANSWERS), {})
        with mock.patch.object(rw, "write_replies", side_effect=AssertionError("no reconsultar")):
            self.assertEqual(rq.work_once(log=self.quiet), 0)

    def test_four_malformed_batches_do_not_spin_forever(self):
        a = self.item("a")
        self.enqueue(a)
        for attempt in range(1, rq.MAX_INCOMPLETE_ATTEMPTS + 1):
            self.assertEqual(rq.work_once(consult=self.consult("malformed"), log=self.quiet), 0)
            pending = rq._load(rq.PENDING)
            self.assertEqual(next(iter(pending.values()))["incomplete_attempts"], attempt)
            if attempt < rq.MAX_INCOMPLETE_ATTEMPTS:
                key = next(iter(pending))
                pending[key]["retry_after"] = "2020-01-01T00:00:00"
                rq._save(rq.PENDING, pending)
        with mock.patch.object(rw, "write_replies", side_effect=AssertionError("agotado")):
            self.assertEqual(rq.work_once(log=self.quiet), 0)
        self.assertEqual(rq.stats_snapshot()["pendientes_reintentos_agotados"], 1)

    def test_invalid_reply_is_rejected_but_explicit_null_is_distinct(self):
        a, b = self.item("a"), self.item("b")
        self.enqueue(a, b)
        with mock.patch.object(rw, "valid_reply", return_value=(False, "texto fuera de política")):
            self.assertEqual(rq.work_once(consult=self.consult(
                '[{"id":"q1","reply":"Texto inválido"},{"id":"q2","reply":null}]'),
                log=self.quiet), 0)
        answers = rq._load(rq.ANSWERS)
        self.assertEqual(answers[rq.key_for("bluesky", a)]["state"], "rejected")
        self.assertEqual(answers[rq.key_for("bluesky", b)]["state"], "null")
        self.assertTrue(all(x["reply"] is None for x in answers.values()))
        self.assertEqual(rq.stats_snapshot()["rechazadas"], 1)

    def test_unproved_reply_is_not_silently_recorded_as_null(self):
        a = self.item("a")
        self.enqueue(a)
        with mock.patch.object(rw, "mark_gpt", return_value=False):
            self.assertEqual(rq.work_once(consult=self.consult(
                '[{"id":"q1","reply":"Me interesa esa historia."}]'),
                log=self.quiet), 0)
        self.assertEqual(rq._load(rq.ANSWERS), {})
        self.assertEqual(len(rq._load(rq.PENDING)), 1)

    def test_context_change_never_reuses_answer_for_same_post(self):
        old = self.item("a", context="Bio breve", history="Turno anterior")
        new = self.item("a", context="Bio breve y conversación completa",
                        history="Turno anterior y rectificación")
        self.assertEqual(rq.key_for("bluesky", old), rq.key_for("bluesky", new))
        self.enqueue(old)
        rq.work_once(consult=self.consult(
            '[{"id":"q1","reply":"Primera respuesta al hilo."}]'), log=self.quiet)
        saved = rq._load(rq.ANSWERS)[rq.key_for("bluesky", old)]
        self.assertEqual(saved["source_hash"], rq._source_hash(old))
        self.assertEqual(self.enqueue(new), {})
        self.assertEqual(rq._load(rq.ANSWERS), {})
        self.assertEqual(next(iter(rq._load(rq.PENDING).values()))["conversation_context"],
                         new["conversation_context"])
        rq.work_once(consult=self.consult(
            '[{"id":"q1","reply":"Respuesta al hilo actualizado."}]'), log=self.quiet)
        self.assertEqual(self.enqueue(new), {"ia": "Respuesta al hilo actualizado."})

    def test_crash_after_answers_written_recovers_without_reconsulting(self):
        a = self.item("a")
        self.enqueue(a)
        key = rq.key_for("bluesky", a)
        rq._save(rq.ANSWERS, {key: {
            "network": "bluesky", "reply": "Recuperada del disco",
            "state": "written", "source_hash": rq._source_hash(a),
            "ts": dt.datetime.now().isoformat(timespec="seconds")}})
        with mock.patch.object(rw, "write_replies", side_effect=AssertionError("no duplicar")):
            self.assertEqual(rq.work_once(log=self.quiet), 0)
        self.assertEqual(rq._load(rq.PENDING), {})

    def test_crash_with_stale_answer_must_reconsult(self):
        old = self.item("a", context="Biografía antigua")
        fresh = self.item("a", context="Biografía ampliada")
        self.enqueue(fresh)
        key = rq.key_for("bluesky", old)
        rq._save(rq.ANSWERS, {key: {
            "network": "bluesky", "reply": "Basada en otra conversación",
            "state": "written", "source_hash": rq._source_hash(old),
            "ts": dt.datetime.now().isoformat(timespec="seconds")}})
        self.assertEqual(rq.work_once(consult=self.consult(
            '[{"id":"q1","reply":"Respuesta a la biografía nueva."}]'), log=self.quiet), 1)
        self.assertEqual(rq._load(rq.ANSWERS)[key]["reply"],
                         "Respuesta a la biografía nueva.")

    def test_answer_replace_failure_keeps_pending_and_recovery_evidence(self):
        a = self.item("a")
        self.enqueue(a)
        before = (self.root / "pending.json").read_bytes()
        with mock.patch.object(rq.os, "replace", side_effect=PermissionError("simulated sharing")), \
             mock.patch.object(rq.time, "sleep", return_value=None):
            with self.assertRaises(rq.QueueStateCorrupted):
                rq.work_once(consult=self.consult(
                    '[{"id":"q1","reply":"Una respuesta sintética y nueva."}]'),
                    log=self.quiet)
        self.assertEqual((self.root / "pending.json").read_bytes(), before)
        evidence = list(self.root.glob("answers.json.escritura-fallida-*"))
        self.assertEqual(len(evidence), 1)
        self.assertIn("Una respuesta sintética", evidence[0].read_text(encoding="utf-8"))

    def test_diagnostics_does_not_modify_bytes_or_timestamps(self):
        a = self.item("a")
        self.enqueue(a)
        rq.work_once(consult=self.consult("[]"), log=self.quiet)
        paths = [self.root / "pending.json"]
        baseline = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
        result = rq.stats_snapshot()
        self.assertEqual(result["pendientes_en_pausa"], 1)
        self.assertEqual([(p.read_bytes(), p.stat().st_mtime_ns) for p in paths], baseline)

    def test_invalid_candidates_are_not_enqueued(self):
        valid = self.item("a")
        invalid = [None, 4, "texto ajeno", [], {}, {"id": "bad", "text": "  "},
                   {"id": [], "text": "Libro"}, {"id": "no-texto", "text": 5}]
        self.enqueue(*(invalid + [valid]))
        pending = rq._load(rq.PENDING)
        self.assertEqual(len(pending), 1)
        self.assertEqual(next(iter(pending.values()))["text"], valid["text"])

    def test_history_is_present_in_actual_prompt(self):
        item = self.item("a", history="Afirmó que todavía no había leído el libro")
        with mock.patch.object(rw, "estilo_red_texto", return_value=""):
            prompt = self.real_build_prompt([item], "bluesky", memoria="")
        self.assertIn("Historial previo del hilo", prompt)
        self.assertIn(item["conversation_context"], prompt)


    def test_unhashable_model_id_keeps_pending_without_exception(self):
        a = self.item("a")
        self.enqueue(a)
        self.assertEqual(rq.work_once(consult=self.consult(
            '[{"id":["q1"],"reply":"Nunca usar esta respuesta."}]'),
            log=self.quiet), 0)
        self.assertEqual(rq._load(rq.ANSWERS), {})
        self.assertEqual(len(rq._load(rq.PENDING)), 1)

    def test_rejected_text_is_not_logged(self):
        a = self.item("a")
        self.enqueue(a)
        seen = []
        with mock.patch.object(rw, "valid_reply", return_value=(False, "no apto")):
            rq.work_once(consult=self.consult(
                '[{"id":"q1","reply":"Dato personal ficticio no publicar"}]'),
                log=seen.append)
        self.assertTrue(any("descartada" in x for x in seen))
        self.assertFalse(any("Dato personal ficticio" in x for x in seen))

    def test_wait_must_not_return_answer_for_another_context(self):
        old = self.item("a", history="Comentario antiguo")
        fresh = self.item("a", history="Comentario corregido y distinto")
        key = rq.key_for("bluesky", old)
        rq._save(rq.ANSWERS, {key: {
            "network": "bluesky", "reply": "No corresponde a este hilo",
            "state": "written", "source_hash": rq._source_hash(old),
            "ts": dt.datetime.now().isoformat(timespec="seconds")}})
        clock = {"now": 100.0}
        with mock.patch.object(rq.time, "time", side_effect=lambda: clock["now"]), \
             mock.patch.object(rq.time, "sleep", side_effect=lambda s: clock.__setitem__("now", clock["now"] + 80)):
            got = rq._wait_for_batch([fresh], "bluesky", {key: True}, 1, self.quiet)
        self.assertEqual(got, {})

    def test_richer_context_reopens_paused_unresolved_request(self):
        brief = self.item("a", context="Bio")
        richer = self.item("a", context="Bio y contexto de lectura completa")
        self.enqueue(brief)
        rq.work_once(consult=self.consult("[]"), log=self.quiet)
        self.assertEqual(rq.stats_snapshot()["pendientes_en_pausa"], 1)
        self.enqueue(richer)
        entry = next(iter(rq._load(rq.PENDING).values()))
        self.assertEqual(entry["context"], richer["context"])
        self.assertNotIn("retry_after", entry)
        self.assertEqual(rq.work_once(consult=self.consult(
            '[{"id":"q1","reply":"Responder ahora con contexto."}]'),
            log=self.quiet), 1)


    def test_duplicate_gpt_id_must_not_confirm_first_null_or_first_text(self):
        item = self.item("a")
        for payload in (
            '[{"id":"q1","reply":null},{"id":"q1","reply":"Texto dudoso"}]',
            '[{"id":"q1","reply":"Texto dudoso"},{"id":"q1","reply":null}]',
        ):
            self.enqueue(item)
            self.assertEqual(rq.work_once(consult=self.consult(payload), log=self.quiet), 0)
            self.assertEqual(rq._load(rq.ANSWERS), {})
            pending = rq._load(rq.PENDING)
            self.assertEqual(len(pending), 1)
            # Avanzar el reloj de reintento sin acceder a sistemas reales.
            key = next(iter(pending))
            pending[key]["retry_after"] = "2020-01-01T00:00:00"
            rq._save(rq.PENDING, pending)

    def test_duplicate_fields_inside_json_object_are_not_accepted(self):
        item = self.item("a")
        self.enqueue(item)
        response = '[{"id":"q1","reply":"Texto distinto","reply":null}]'
        self.assertEqual(rq.work_once(consult=self.consult(response), log=self.quiet), 0)
        self.assertEqual(rq._load(rq.ANSWERS), {})
        self.assertEqual(len(rq._load(rq.PENDING)), 1)

    def test_provider_exception_does_not_log_external_contents(self):
        item = self.item("a")
        self.enqueue(item)
        seen = []
        def fail(*_):
            raise RuntimeError("secreto_simulado_123")
        self.assertEqual(rq.work_once(consult=fail, log=seen.append), 0)
        self.assertFalse(any("secreto_simulado" in line for line in seen))
        self.assertEqual(len(rq._load(rq.PENDING)), 1)

    def test_network_is_canonicalized_and_unknown_network_is_omitted(self):
        upper = dict(self.item("a"), network="BLUESKY")
        bad = dict(self.item("b"), network="una_red_falsa")
        self.enqueue(upper, bad)
        pending = rq._load(rq.PENDING)
        self.assertEqual(len(pending), 1)
        self.assertEqual(next(iter(pending.values()))["network"], "bluesky")
        self.assertTrue(rq._valid_entry(rq.PENDING, next(iter(pending.values()))))
        self.assertFalse(rq._valid_entry(rq.PENDING, {
            "network": "una_red_falsa", "text": "Publicación", "ts": "2026-10-09T11:00:00"
        }))

    def test_non_text_provider_payload_is_incomplete_not_exception(self):
        item = self.item("a")
        self.enqueue(item)
        self.assertEqual(rq.work_once(consult=lambda *_: ({"id": "q1"}, "fake"),
                                      log=self.quiet), 0)
        self.assertEqual(rq._load(rq.ANSWERS), {})
        self.assertEqual(next(iter(rq._load(rq.PENDING).values()))["incomplete_attempts"], 1)

    def test_naive_clock_rejects_aware_or_malformed_timestamps(self):
        now = dt.datetime(2026, 10, 9, 12, 0)
        self.assertFalse(rq._fresh({"ts": "2026-10-09T10:00:00+00:00"}, now))
        self.assertFalse(rq._fresh({"ts": []}, now))
        self.assertFalse(rq._retry_due({"retry_after": "2026-10-09T10:00:00Z"}, now))
        self.assertFalse(rq._retry_due({"retry_after": 22}, now))
        self.assertTrue(rq._retry_due({"retry_after": "2026-10-09T11:59:59"}, now))

    def test_mismatched_durable_state_cannot_be_loaded_as_valid(self):
        key = rq.key_for("bluesky", self.item("a"))
        for answer in (
            {"ts": "2026-10-09T12:00:00", "reply": "Texto", "state": "null"},
            {"ts": "2026-10-09T12:00:00", "reply": None, "state": "written"},
            {"ts": "2026-10-09T12:00:00", "reply": "", "state": "written"},
            {"ts": "2026-10-09T12:00:00", "reply": "Texto", "state": "uncertain"},
        ):
            self.assertFalse(rq._valid_entry(rq.ANSWERS, answer))
        self.assertTrue(rq._valid_entry(rq.ANSWERS, {
            "ts": "2026-10-09T12:00:00", "reply": "Texto", "state": "written",
            "network": "bluesky", "source_hash": rq._source_hash(self.item("a")),
        }))

    def test_shorten_and_change_same_post_context_replaces_old_context(self):
        old = self.item("a", context="Una biografía extensa con referencia a lectura antigua")
        latest = self.item("a", context="Nueva respuesta con matiz distinto")
        self.enqueue(old)
        rq.work_once(consult=self.consult(
            '[{"id":"q1","reply":"Respuesta al contexto obsoleto."}]'), log=self.quiet)
        self.assertEqual(self.enqueue(latest), {})
        pending = next(iter(rq._load(rq.PENDING).values()))
        self.assertEqual(pending["context"], latest["context"])
        self.assertNotIn(rq.key_for("bluesky", old), rq._load(rq.ANSWERS))
        rq.work_once(consult=self.consult(
            '[{"id":"q1","reply":"Respuesta con información actual."}]'), log=self.quiet)
        self.assertEqual(self.enqueue(latest), {"ia": "Respuesta con información actual."})

    def test_legacy_rekey_never_splices_two_mismatched_threads(self):
        now = dt.datetime.now().isoformat(timespec="seconds")
        earlier = (dt.datetime.now() - dt.timedelta(minutes=4)).isoformat(timespec="seconds")
        a = dict(self.item("a", context="Contexto largo anterior y diferente",
                           history="Hilo ajeno con varias intervenciones"), ts=earlier)
        b = dict(self.item("a", context="Nuevo asunto", history="Otro intercambio"), ts=now)
        merged = rq._rekey_pending({"antiguo": a, "reciente": b})
        self.assertEqual(len(merged), 1)
        self.assertEqual(next(iter(merged.values())), b)



if __name__ == "__main__":
    unittest.main()
