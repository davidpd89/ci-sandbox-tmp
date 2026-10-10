"""Regresión PR152: intenciones write-ahead TikTok, todo offline."""
import csv
import contextlib
import io
import json
import datetime as dt
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tiktok_mobile_execute as te
import tiktok_mobile_interact as tm
import tiktok_safety as safety
import tiktok_growth_flow as flow
import tiktok_bulk_follow as bulk
import action_ledger as ledger


class IntentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "registro.csv"
        p = mock.patch.object(te, "REGISTRO_CSV", str(self.path))
        p.start()
        self.addCleanup(p.stop)
        pause = mock.patch.object(safety, "COOLDOWN_PATH", str(Path(self.temp.name) / "cooldown.json"))
        pause.start()
        self.addCleanup(pause.stop)

    def _rows(self):
        with self.path.open(encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    def _run(self, adapter, plan):
        with mock.patch("reply_writer.require_gpt", side_effect=lambda plan, network: plan), \
             mock.patch("conversation_turn_policy.check_execution", return_value=(True, "ok")), \
             mock.patch.object(safety, "require_writable"), \
             mock.patch.object(safety, "follow_paused", return_value=False), \
             mock.patch("like_context_policy.check_execution", return_value=(True, "context_ok")):
            return te.run_plan(plan, adapter, pause=False, on_result=te._append_registro_one)

    def test_already_like_resolves_pending_without_consuming_cupo(self):
        class Adapter:
            def like(self, ref):
                return "already"
        plan = [{"kind":"like","handle":"lectora","url":"https://www.tiktok.com/@lectora/video/1"}]
        result = self._run(Adapter(), plan)
        self.assertEqual(result[0]["resultado"], "saltado_ya_like")
        self.assertEqual([r["resultado"] for r in self._rows()], ["pendiente_verificacion", "saltado_ya_like"])
        counts, pending = safety.recorded_actions(str(self.path), today=dt.date.today())
        self.assertEqual(counts["like"], 0)
        self.assertFalse(pending)

    def test_context_reject_is_skip_and_closes_intention(self):
        class Adapter:
            def like(self, ref):
                raise tm.TikTokTargetNotFound("like_contexto:adjunto_sin_contexto_literario_suficiente")
        plan = [{"kind":"like","handle":"lectora","url":"https://www.tiktok.com/@lectora/video/2"}]
        result = self._run(Adapter(), plan)
        self.assertTrue(result[0]["resultado"].startswith("saltado_like_contexto:"))
        counts, pending = safety.recorded_actions(str(self.path))
        self.assertEqual(counts["like"], 0)
        self.assertFalse(pending)

    def test_uncertain_remains_blocked_even_after_process_exits(self):
        class Adapter:
            def like(self, ref):
                raise tm.TikTokWriteUnverified("ACK desconocido")
        plan = [{"kind":"like","handle":"lectora","url":"https://www.tiktok.com/@lectora/video/3"}]
        result = self._run(Adapter(), plan)
        self.assertEqual(result[0]["resultado"], "pendiente_verificacion")
        self.assertEqual([row["resultado"] for row in self._rows()], ["pendiente_verificacion"],
                         "no reabrir la intención al capturar un ACK incierto")
        counts, pending = safety.recorded_actions(str(self.path))
        self.assertEqual(counts["like"], 1)
        self.assertIn(("like", plan[0]["url"]), pending)



    def test_write_ahead_failure_does_not_call_adapter(self):
        calls = []
        class Adapter:
            def like(self, ref):
                calls.append(ref)
                return "created"
        item = {"kind": "like", "handle": "lectora",
                "url": "https://www.tiktok.com/@lectora/video/10"}
        with mock.patch("reply_writer.require_gpt", side_effect=lambda plan, network: plan), \
             mock.patch("conversation_turn_policy.check_execution", return_value=(True, "ok")), \
             mock.patch.object(safety, "require_writable"), \
             mock.patch("like_context_policy.check_execution", return_value=(True, "ok")):
            with self.assertRaises(te.TikTokPersistenceError):
                te.run_plan([item], Adapter(), pause=False,
                            on_result=lambda entry: (_ for _ in ()).throw(OSError("disco lleno")))
        self.assertEqual(calls, [])

    def test_failed_confirmation_write_preserves_the_open_intent(self):
        calls = []
        class Adapter:
            def like(self, ref):
                calls.append(ref)
                return "created"
        item = {"kind": "like", "handle": "lectora",
                "url": "https://www.tiktok.com/@lectora/video/11"}
        def callback(entry):
            if entry["resultado"] == "confirmado":
                raise OSError("no se confirmó fsync")
            te._append_registro_one(entry)
        err = io.StringIO()
        with mock.patch("reply_writer.require_gpt", side_effect=lambda plan, network: plan), \
             mock.patch("conversation_turn_policy.check_execution", return_value=(True, "ok")), \
             mock.patch.object(safety, "require_writable"), \
             mock.patch("like_context_policy.check_execution", return_value=(True, "ok")), \
             contextlib.redirect_stderr(err):
            with self.assertRaises(te.TikTokPersistenceError):
                te.run_plan([item], Adapter(), pause=False, on_result=callback)
        self.assertNotIn("-> confirmado", err.getvalue())
        self.assertEqual(len(calls), 1)
        self.assertEqual([r["resultado"] for r in self._rows()], ["pendiente_verificacion"])
        counts, pending = safety.recorded_actions(str(self.path))
        self.assertEqual(counts["like"], 1)
        self.assertIn(("like", item["url"]), pending)

    def test_mobile_transport_error_does_not_duplicate_open_intent(self):
        class Adapter:
            def like(self, ref):
                raise te.MobileCliError("transporte interrumpido; tap incierto")
        plan = [{"kind": "like", "handle": "lectora",
                 "url": "https://www.tiktok.com/@lectora/video/7"}]
        result = self._run(Adapter(), plan)
        self.assertEqual(result[0]["resultado"], "pendiente_verificacion")
        self.assertEqual([r["resultado"] for r in self._rows()], ["pendiente_verificacion"])
        counts, pending = safety.recorded_actions(str(self.path))
        self.assertEqual(counts["like"], 1)
        self.assertIn(("like", plan[0]["url"]), pending)

    def test_unknown_target_failure_keeps_pending_for_human_review(self):
        class Adapter:
            def like(self, ref):
                raise tm.TikTokTargetNotFound("botón ambiguo; no hay prueba de no tap")
        plan = [{"kind": "like", "handle": "lectora",
                 "url": "https://www.tiktok.com/@lectora/video/8"}]
        result = self._run(Adapter(), plan)
        self.assertTrue(result[0]["resultado"].startswith("fallo:"))
        self.assertEqual([r["resultado"] for r in self._rows()], ["pendiente_verificacion"])
        _, pending = safety.recorded_actions(str(self.path))
        self.assertIn(("like", plan[0]["url"]), pending)

    def test_malformed_intent_id_cannot_be_treated_as_legacy(self):
        self.path.write_text(
            "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n"
            "2026-10-09,@lectora,like,u1,,pendiente_verificacion,intent_id=corto\n",
            encoding="utf-8",
        )
        with self.assertRaises(safety.SafetyStateError):
            safety.recorded_actions(str(self.path))


    def test_intent_missing_or_impossible_date_fails_closed(self):
        iid = "e" * 32
        self.path.write_text(
            "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n"
            f"no-es-fecha,@lectora,like,u1,,pendiente_verificacion,intent_id={iid}\n",
            encoding="utf-8",
        )
        with self.assertRaises(safety.SafetyStateError):
            safety.recorded_actions(str(self.path))

    def test_literal_intent_id_inside_caption_is_not_a_second_token(self):
        iid = "f" * 32
        self.path.write_text(
            "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n"
            f"2026-10-09,@lectora,like,u1,,pendiente_verificacion,"
            f"transporte=android_native | intent_id={iid} | caption=el código intent_id=abc\n"
            f"2026-10-09,@lectora,like,u1,,saltado_ya_like,"
            f"transporte=android_native | intent_id={iid}\n",
            encoding="utf-8",
        )
        counts, pending = safety.recorded_actions(str(self.path), today=dt.date(2026, 10, 9))
        self.assertEqual(counts["like"], 0)
        self.assertFalse(pending)

    def test_closure_kind_mismatch_is_corrupt(self):
        iid = "d" * 32
        self.path.write_text(
            "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n"
            f"2026-10-09,@lectora,follow,,,pendiente_verificacion,intent_id={iid}\n"
            f"2026-10-09,@lectora,follow,,,saltado_ya_like,intent_id={iid}\n",
            encoding="utf-8",
        )
        with self.assertRaises(safety.SafetyStateError):
            safety.recorded_actions(str(self.path))

    def test_confirmed_closes_pending_and_counts_exactly_one(self):
        class Adapter:
            def like(self, ref):
                return "created"
        plan = [{"kind":"like","handle":"lectora","url":"https://www.tiktok.com/@lectora/video/4"}]
        self._run(Adapter(), plan)
        counts, pending = safety.recorded_actions(str(self.path))
        self.assertEqual(counts["like"], 1)
        self.assertFalse(pending)

    def test_plan_shortage_is_diagnosed_by_source_of_discard(self):
        state = self.path.parent / "state.json"
        plan_path = self.path.parent / "plan.json"
        state.write_text('{"shortlist": []}', encoding="utf-8")
        raw = [
            {"kind": "like", "handle": "lectora", "url": "https://example.test/a"},
            {"kind": "like", "handle": "lectora", "url": "https://example.test/b"},
            {"kind": "follow", "handle": "lectora"},
        ]
        eligible = raw[1:]
        output = io.StringIO()
        args = SimpleNamespace(state=str(state), decisions=None,
                               plan=str(plan_path), no_follows=True)
        with mock.patch.object(flow.builder, "build", return_value=raw), \
             mock.patch.object(flow, "drop_already_done", return_value=eligible) as filt, \
             contextlib.redirect_stdout(output):
            self.assertEqual(flow.build(args), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["propuestas_iniciales"], 3)
        self.assertEqual(report["descartadas_por_registro"], 1)
        self.assertEqual(report["descartadas_follows"], 1)
        self.assertEqual(report["actions"], 1)
        self.assertEqual(filt.call_count, 1)
        self.assertTrue(report["plan_pobre"])

    def test_legacy_pending_not_auto_dropped(self):
        self.path.write_text("fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n"
                             "2026-10-09,@lectora,like,https://www.tiktok.com/@lectora/video/5,,pendiente_verificacion,legacy\n",
                             encoding="utf-8")
        _, pending = safety.recorded_actions(str(self.path))
        self.assertIn(("like","https://www.tiktok.com/@lectora/video/5"), pending)

    def test_corrupted_id_pair_fails_closed(self):
        iid = "a"*32
        self.path.write_text("fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n"
                             f"2026-10-09,@a,like,u1,,pendiente_verificacion,intent_id={iid}\n"
                             f"2026-10-09,@b,like,u2,,saltado_ya_like,intent_id={iid}\n",
                             encoding="utf-8")
        with self.assertRaises(safety.SafetyStateError):
            safety.recorded_actions(str(self.path))

    def test_double_closure_of_intent_is_corrupt_fail_closed(self):
        iid = "b" * 32
        header = "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n"
        rows = [
            f"2026-10-09,@lectora,like,u1,,pendiente_verificacion,intent_id={iid}",
            f"2026-10-09,@lectora,like,u1,,confirmado,intent_id={iid}",
            f"2026-10-09,@lectora,like,u1,,saltado_ya_like,intent_id={iid}",
        ]
        self.path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
        with self.assertRaises(safety.SafetyStateError):
            safety.recorded_actions(str(self.path))

    def test_pending_cannot_be_reopened_after_closure(self):
        iid = "c" * 32
        header = "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n"
        rows = [
            f"2026-10-09,@lectora,like,u1,,pendiente_verificacion,intent_id={iid}",
            f"2026-10-09,@lectora,like,u1,,saltado_ya_like,intent_id={iid}",
            f"2026-10-09,@lectora,like,u1,,pendiente_verificacion,intent_id={iid}",
        ]
        self.path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")
        with self.assertRaises(safety.SafetyStateError):
            safety.recorded_actions(str(self.path))

    def test_follow_limit_after_uncertain_tap_never_marks_clean_session(self):
        class Adapter:
            def _tree(self):
                return {}
            def follow(self, handle):
                raise tm.TikTokWriteUnverified("ACK remoto no verificable")
        plan = [{"kind": "follow", "handle": "lectora"}]
        with mock.patch.object(safety, "check_screen", side_effect=[
                None, safety.SafetyFollowLimit("aviso de frecuencia")]), \
             mock.patch.object(safety, "restrict", return_value=60):
            result = self._run(Adapter(), plan)
        self.assertEqual(result[0]["resultado"], "saltado_limite_follow")
        self.assertTrue(te._session_has_uncertain_result(result))
        self.assertEqual([r["resultado"] for r in self._rows()], ["pendiente_verificacion"])
        used, pending = safety.recorded_actions(str(self.path))
        self.assertEqual(used["follow"], 1)
        self.assertIn(("follow", "lectora"), pending)
        self.assertFalse(te._session_has_uncertain_result([
            {"resultado": "saltado_limite_follow"}]))  # pausa pre-intento

    def test_shared_ledger_contract_is_unchanged_for_other_networks(self):
        self.assertEqual(ledger.outcome_to_status("saltado_ya_like"), ledger.CONFIRMED)
        self.assertEqual(ledger.outcome_to_status("saltado_like_contexto:insuficiente"),
                         ledger.SKIPPED_POLICY)
        self.assertEqual(ledger.outcome_to_status("pendiente_verificacion"),
                         ledger.UNCERTAIN)

    def test_bulk_budget_respects_closed_already_follow(self):
        class Adapter:
            def follow(self, handle):
                return "already"
        self._run(Adapter(), [{"kind": "follow", "handle": "lectora"}])
        with mock.patch.object(bulk, "REGISTRO_CSV", str(self.path)):
            done, used = bulk.followed_before()
        self.assertIn("lectora", done)
        self.assertEqual(used, 0, "follow existente no consume cupo nuevo")

    def test_bulk_budget_retains_unresolved_follow(self):
        class Adapter:
            def follow(self, handle):
                raise tm.TikTokWriteUnverified("ACK desconocido")
        self._run(Adapter(), [{"kind": "follow", "handle": "lectora"}])
        with mock.patch.object(bulk, "REGISTRO_CSV", str(self.path)):
            done, used = bulk.followed_before()
        self.assertIn("lectora", done)
        self.assertEqual(used, 1, "ACK incierto bloquea cupo")

    def test_dedupe_does_not_reoffer_observed_already_like(self):
        url = "https://www.tiktok.com/@lectora/video/6"
        self._run(type("A", (), {"like": lambda s, r: "already"})(), [
            {"kind": "like", "handle": "lectora", "url": url}])
        with mock.patch.object(flow.scan, "REGISTRO_CSV", str(self.path)):
            kept = flow.drop_already_done([
                {"kind": "like", "handle": "lectora", "url": url}])
        self.assertEqual(kept, [])

    def test_clean_run_emits_aggregate_lifecycle_not_false_orphans(self):
        url = "https://www.tiktok.com/@lectora/video/13"
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self._run(type("A", (), {"like": lambda s, r: "already"})(), [
                {"kind": "like", "handle": "lectora", "url": url}])
        self.assertIn("TIKTOK_INTENTS opened=1 closed=1 unresolved=0", err.getvalue())

    def test_context_rejection_does_not_claim_existing_like(self):
        url = "https://www.tiktok.com/@lectora/video/12"
        class Adapter:
            def like(self, ref):
                raise tm.TikTokTargetNotFound("like_contexto:insuficiente")
        self._run(Adapter(), [{"kind": "like", "handle": "lectora", "url": url}])
        with mock.patch.object(flow.scan, "REGISTRO_CSV", str(self.path)):
            item = {"kind": "like", "handle": "lectora", "url": url}
            today_plan = flow.drop_already_done([item], today=dt.date.today())
            tomorrow_plan = flow.drop_already_done(
                [item], today=dt.date.today() + dt.timedelta(days=1))
        self.assertEqual(today_plan, [], "veto de contexto no se repite hoy")
        self.assertEqual(tomorrow_plan, [item], "veto temporal no demuestra acción realizada")

    def test_next_day_confirmation_belongs_to_opening_day_budget(self):
        iid = "1" * 32
        rows = [
            ["fecha", "cuenta", "tipo", "post_resumen", "texto_usado", "resultado", "notas"],
            ["2026-10-08", "@lectora", "like", "u1", "", "pendiente_verificacion", f"intent_id={iid}"],
            ["2026-10-09", "@lectora", "like", "u1", "", "confirmado", f"intent_id={iid}"],
        ]
        with self.path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(rows)
        before, pending = safety.recorded_actions(str(self.path), today=dt.date(2026, 10, 8))
        after, pending_after = safety.recorded_actions(str(self.path), today=dt.date(2026, 10, 9))
        self.assertEqual(before["like"], 1)
        self.assertEqual(after["like"], 0)
        self.assertFalse(pending)
        self.assertFalse(pending_after)

    def test_reader_rejects_truncated_or_extra_csv_columns(self):
        header = "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n"
        for invalid in (
            "2026-10-09,@lectora,like,u1,,pendiente_verificacion",  # falta notas
            "2026-10-09,@lectora,like,u1,,pendiente_verificacion,legacy,extra",
        ):
            with self.subTest(invalid=invalid):
                self.path.write_text(header + invalid + "\n", encoding="utf-8")
                with self.assertRaises(safety.SafetyStateError):
                    safety.recorded_actions(str(self.path))

    def test_writer_does_not_append_to_unknown_legacy_header(self):
        original = "fecha,tipo,cuenta,post_resumen,resultado\n"
        self.path.write_text(original, encoding="utf-8")
        class Adapter:
            def like(self, ref):
                raise AssertionError("nunca abrir la interacción")
        item = {"kind": "like", "handle": "lectora",
                "url": "https://www.tiktok.com/@lectora/video/14"}
        with mock.patch("reply_writer.require_gpt", side_effect=lambda plan, network: plan), \
             mock.patch("conversation_turn_policy.check_execution", return_value=(True, "ok")), \
             mock.patch.object(safety, "require_writable"), \
             mock.patch("like_context_policy.check_execution", return_value=(True, "ok")):
            with self.assertRaises(te.TikTokPersistenceError):
                te.run_plan([item], Adapter(), pause=False, on_result=te._append_registro_one)
        self.assertEqual(self.path.read_text(encoding="utf-8"), original)

    def test_reader_rejects_duplicate_required_column(self):
        self.path.write_text(
            "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,resultado,notas\n"
            "2026-10-09,@lectora,like,u1,,confirmado,,origen\n",
            encoding="utf-8",
        )
        with self.assertRaises(safety.SafetyStateError):
            safety.recorded_actions(str(self.path))


if __name__ == "__main__":
    unittest.main()
