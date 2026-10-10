"""PR #91: omisiones seguras y señales de subprocess. Fixtures sintéticos offline.

No se importan credenciales, Edge, Android, SQLite operativo ni APIs remotas.
"""
import contextlib
import datetime as dt
import io
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import exec_common as ec
import mastodon_execute as masto
import reddit_execute as reddit
import mechanical_round as mr
import plan_failure_events as events


class MastodonSafeItems(unittest.TestCase):
    def test_one_duplicate_out_of_sixty_preserves_fifty_nine(self):
        plan = [{"kind": "favourite", "status_id": str(20000 + i)}
                for i in range(60)]
        plan[30]["status_id"] = plan[1]["status_id"]
        skipped, stdout = [], io.StringIO()
        with mock.patch.object(masto.m, "_status_id", side_effect=AssertionError("remote read")):
            with contextlib.redirect_stdout(stdout):
                valid = masto._preflight_plan(plan, skipped=skipped)
        self.assertEqual(len(valid), 59)
        self.assertEqual(skipped, [{"kind": "favourite",
                                  "resultado": "saltado_preflight_objetivo_repetido_lote"}])
        self.assertIn("OMITIDO_PREFLIGHT_DUPLICADO elemento=31", stdout.getvalue())
        self.assertNotIn("20001", stdout.getvalue())

    def test_duplicate_reply_text_preserves_other_replies(self):
        plan = [{"kind": "reply", "status_id": str(30000 + i),
                 "post_created_at": (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat(),
                 "text": f"Lectura interesante del capítulo número {i}"}
                for i in range(60)]
        plan[41]["text"] = plan[2]["text"]
        skipped, stdout = [], io.StringIO()
        with mock.patch.object(masto.dup, "check", return_value=False), \
             mock.patch.object(masto.m, "_check_length"), \
             mock.patch.object(masto.m, "_check_spanish_orthography"), \
             mock.patch.object(masto.sc, "guard_plan_item"), \
             contextlib.redirect_stdout(stdout):
            valid = masto._preflight_plan(plan, skipped=skipped)
        self.assertEqual(len(valid), 59)
        self.assertEqual(skipped[0]["resultado"], "saltado_preflight_texto_repetido_lote")
        self.assertNotIn("Lectura interesante", stdout.getvalue())

    def test_security_conflict_and_invalid_identity_still_abort(self):
        with self.assertRaisesRegex(ValueError, "varias acciones"):
            masto._preflight_plan([{"kind": "favourite", "status_id": "123"},
                                   {"kind": "boost", "status_id": "123"}])
        with self.assertRaisesRegex(ValueError, "follow exige handle"):
            masto._preflight_plan([{"kind": "follow", "handle": "autora@social.ejemplo"},
                                   {"kind": "follow", "handle": None}])
        with self.assertRaisesRegex(ValueError, "status_id inválido"):
            masto._preflight_plan([{"kind": "favourite", "status_id": "a\u0000"}])

    def test_repeated_follow_safe_but_context_guard_still_runs(self):
        skipped = []
        plan = [{"kind": "follow", "handle": "escritora@ejemplo.social"},
                {"kind": "follow", "handle": "@ESCRITORA@ejemplo.social"}]
        with contextlib.redirect_stdout(io.StringIO()):
            kept = masto._preflight_plan(plan, skipped=skipped)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["resultado"], "saltado_preflight_relacion_repetida_lote")


class RedditSafeItems(unittest.TestCase):
    @staticmethod
    def vote(i, direction="up"):
        return {"kind": "vote", "subreddit": "libros",
                "url": f"https://www.reddit.com/r/libros/comments/a{i:05d}/ejemplo/",
                "direction": direction}

    def test_reddit_one_duplicate_vote_out_of_sixty(self):
        plan = [self.vote(i) for i in range(60)]
        plan[36] = dict(plan[1])
        skipped = []
        with contextlib.redirect_stdout(io.StringIO()):
            kept = reddit._preflight_plan(plan, skipped=skipped)
        self.assertEqual(len(kept), 59)
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0]["resultado"], "saltado_preflight_objetivo_repetido_lote")

    def test_reddit_opposite_vote_still_blocks_everything(self):
        with self.assertRaisesRegex(ValueError, "conflictivo"):
            reddit._preflight_plan([self.vote(3, "up"), self.vote(3, "down")])

    def test_reddit_same_microtext_on_two_posts_is_omitted(self):
        urls = [self.vote(i) for i in (1, 2)]
        plan = [{**v, "kind": "comment", "text": "Escribir."} for v in urls]
        skipped = []
        with mock.patch.object(reddit, "_recent_micro_repeat", return_value=False), \
             mock.patch.object(reddit.r, "_check_length"), \
             mock.patch.object(reddit.r, "_check_micro_comment"), \
             mock.patch.object(reddit.r, "_check_spanish_orthography"), \
             mock.patch.object(reddit.sc, "guard_plan_item"), \
             contextlib.redirect_stdout(io.StringIO()):
            kept = reddit._preflight_plan(plan, skipped=skipped)
        self.assertEqual(len(kept), 1)
        self.assertEqual(skipped[0]["resultado"], "saltado_preflight_texto_repetido_lote")

    def test_reddit_missing_target_not_silently_skipped(self):
        with self.assertRaises((ValueError, TypeError)):
            reddit._preflight_plan([{"kind": "vote", "url": None, "subreddit": "libros"}])


class OrchestratorSignals(unittest.TestCase):
    def test_omit_diagnostic_and_executor_result_count_once(self):
        diagnostic = []
        skipped = []
        ec.record_preflight_skip(skipped, network="mastodon", index=5,
                                 kind="reply", reason="texto_repetido_lote",
                                 log=diagnostic.append)
        # El ejecutor emite una fila de resultado, el preflight solo un aviso.
        output = diagnostic[0] + "\n" + skipped[0]["resultado"] + " reply\n"
        summary = mr.summarize(output)
        self.assertEqual(summary["saltadas"], 1)
        self.assertEqual(summary["elementos_omitidos_por_motivo"],
                         {"texto_repetido_lote": 1})

    def test_summary_counts_reasons_without_private_text(self):
        transcript = ("confirmado follow\n"
                      "saltado_preflight_texto_repetido_lote reply\n"
                      "saltado_preflight_objetivo_repetido_lote favourite\n"
                      "FALLO: HTTP 403 objetivo no permitido\n")
        s = mr.summarize(transcript)
        self.assertEqual(s["confirmadas"], {"follow": 1})
        self.assertEqual(s["fallos_total"], 1)
        self.assertEqual(s["elementos_omitidos_por_motivo"],
                         {"texto_repetido_lote": 1, "objetivo_repetido_lote": 1})

    def test_tiktok_zero_exit_safety_stop_does_not_run_more_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            commands, output = [], []
            cfg = {"dir": "SISTEMA_DIARIO_TIKTOK", "decisions_default": None,
                   "pre": [[sys.executable, "tools/tiktok_bulk_follow.py"],
                           [sys.executable, "tools/tiktok_growth_flow.py", "prepare"]]}
            def fake_runner(cmd):
                commands.append(cmd[1])
                if cmd[1].endswith("tiktok_bulk_follow.py"):
                    return 0, "PARADA TIKTOK: sesión no segura\nTIKTOK_STEP_STATUS=restricted"
                return 0, ""
            with mock.patch.object(mr, "ROOT", tmp), \
                 mock.patch.dict(mr.PIPELINES, {"tiktok": cfg}), \
                 mock.patch.object(mr, "CONTENT_QUEUE_NETWORKS", set()), \
                 mock.patch.object(mr, "PUBLISH_NETWORKS", set()):
                result = mr._run("tiktok", runner=fake_runner, out=output.append,
                                 signals=[])
            self.assertFalse(result["ok"])
            # Contrato tipado de #41: la parada llega como TIKTOK_STEP_STATUS=restricted y corta las etapas siguientes.
            self.assertEqual(commands, ["tools/tiktok_bulk_follow.py"])
            self.assertEqual(result["error_reason"], "bulk_restricted")
            self.assertIn("bulk detenido", " ".join(output))

    def test_only_known_sanitized_reasons(self):
        with self.assertRaisesRegex(ValueError, "no permitido"):
            ec.record_preflight_skip([], network="mastodon", index=1,
                                     kind="reply", reason="../texto privado")


class ReadOnlyPlanEvents(unittest.TestCase):
    def test_last_event_is_sanitized_and_no_stale_or_future(self):
        with tempfile.TemporaryDirectory() as folder:
            now = dt.datetime(2026, 10, 9, 10, 0)
            self.assertTrue(events.record(folder, "mastodon", "preflight", "/tmp/a.log",
                                          cause="invalid_schema", now=now))
            self.assertTrue(events.record(folder, "reddit", "build", "/tmp/b.log",
                                          cause="/ruta/privada", now=now))
            last = events.last_failures(folder, now=now)
            self.assertEqual(last["mastodon"]["cause"], "invalid_schema")
            self.assertEqual(last["reddit"]["cause"], "unknown")
            self.assertNotIn("bluesky", last)
            self.assertEqual(events.last_failures(folder, now=now+dt.timedelta(days=9)), {})



class SecondPassRegressionTests(unittest.TestCase):
    """Adversarial: rejected batches must not log committed omissions."""

    def test_late_invalid_mastodon_discards_early_skips_and_log(self):
        plan = [
            {"kind": "favourite", "status_id": "100"},
            {"kind": "favourite", "status_id": "100"},
            {"kind": "follow", "handle": None},
        ]
        output, skipped = io.StringIO(), []
        with contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(ValueError, "follow exige handle"):
                masto._preflight_plan(plan, skipped=skipped)
        self.assertEqual(skipped, [])
        self.assertNotIn("OMITIDO_PREFLIGHT_DUPLICADO", output.getvalue())

    def test_late_invalid_reddit_discards_early_skips_and_log(self):
        plan = [RedditSafeItems.vote(1), RedditSafeItems.vote(1),
                RedditSafeItems.vote(2, direction="sideways")]
        output, skipped = io.StringIO(), []
        with contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(ValueError, "direction"):
                reddit._preflight_plan(plan, skipped=skipped)
        self.assertEqual(skipped, [])
        self.assertNotIn("OMITIDO_PREFLIGHT_DUPLICADO", output.getvalue())

    def test_previously_published_reply_logs_only_on_commit(self):
        plan = [
            {"kind": "reply", "status_id": "100", "text": "Texto ya publicado"},
            {"kind": "follow", "handle": None},
        ]
        log, skipped = io.StringIO(), []
        with mock.patch.object(masto.dup, "check", return_value=True), \
             mock.patch.object(masto.m, "_check_length"), \
             mock.patch.object(masto.m, "_check_spanish_orthography"), \
             mock.patch.object(masto.sc, "guard_plan_item"), \
             contextlib.redirect_stdout(log):
            with self.assertRaisesRegex(ValueError, "follow exige handle"):
                masto._preflight_plan(plan, skipped=skipped)
        self.assertEqual(skipped, [])
        self.assertNotIn("OMITIDO_PREFLIGHT_DUPLICADO", log.getvalue())

    @staticmethod
    def _synthetic_runner(exit_code, output, *, run_full=False):
        with tempfile.TemporaryDirectory() as folder:
            (pathlib.Path(folder) / "plan.json").write_text(
                '[{"kind":"follow","handle":"synthetic"}]', encoding="utf-8")
            calls = []
            cfg = {"dir": "TEST", "pre": [], "decisions_default": None,
                   "write_decisions": None, "build": None, "plan": "plan.json",
                   "execute": [sys.executable, "fake_execute.py"],
                   "post": [[sys.executable, "fake_post.py"]], "shape": False}
            def runner(cmd):
                calls.append(cmd[1])
                if cmd[1] == "fake_execute.py":
                    return exit_code, output
                return 0, "confirmado follow"
            with mock.patch.object(mr, "ROOT", folder), \
                 mock.patch.object(mr, "LOCK_DIR", folder), \
                 mock.patch.dict(mr.PIPELINES, {"synthetic": cfg}), \
                 mock.patch.object(mr, "CONTENT_QUEUE_NETWORKS", set()), \
                 mock.patch.object(mr, "PUBLISH_NETWORKS", set()):
                if run_full:
                    with mock.patch.object(mr.cb, "record", return_value={}) as record:
                        with mock.patch.object(mr.cb, "check", return_value=(True, "")):
                            result = mr.run("synthetic", shape=False, runner=runner,
                                            rng=__import__("random").Random(1),
                                            out=lambda *_: None)
                        records = list(record.call_args_list)
                else:
                    result = mr._run("synthetic", shape=False, runner=runner,
                                     out=lambda *_: None, signals=[])
                    records = []
            return result, calls, records

    def test_exit_one_with_item_failure_reaches_breaker(self):
        result, calls, records = self._synthetic_runner(
            1, "confirmado follow\nFALLO: RuntimeError: executor crashed", run_full=True)
        self.assertEqual(calls, ["fake_execute.py"])
        self.assertFalse(result["ok"])
        self.assertFalse(result["partial"])
        self.assertEqual(len(records), 1)
        self.assertIs(records[0].args[1], False)

    def test_stop_with_exit_zero_blocks_post_without_needing_429(self):
        result, calls, _ = self._synthetic_runner(
            0, "confirmado follow\nPARADA TOTAL: comprobación de identidad")
        self.assertFalse(result["ok"])
        self.assertFalse(result["partial"])
        self.assertEqual(calls, ["fake_execute.py"])

    def test_failed_preflight_with_exit_zero_never_runs_post(self):
        result, calls, _ = self._synthetic_runner(
            0, "FALLO DE PREFLIGHT: ValueError: malformed target")
        self.assertFalse(result["ok"])
        self.assertEqual(result["failure_kind"], "plan")
        self.assertEqual(calls, ["fake_execute.py"])

    def test_clean_executor_still_runs_post(self):
        result, calls, _ = self._synthetic_runner(
            0, "confirmado follow")
        self.assertTrue(result["ok"])
        self.assertEqual(calls, ["fake_execute.py", "fake_post.py"])

    def test_item_level_failure_exit_zero_preserves_partial(self):
        result, _, _ = self._synthetic_runner(
            0, "confirmado follow\nFALLO: objetivo no disponible")
        self.assertTrue(result["ok"])
        self.assertTrue(result["partial"])



if __name__ == "__main__":
    unittest.main()
