"""R5 / F10: un fallo del plan no debe abrir el breaker de la cuenta.

Simula mechanical_round.run() con _run falso. No accede a Edge, cuentas,
CSV, cache real ni deja ficheros de estado en el repositorio.
"""
import contextlib
import json
import tempfile
import pathlib
import random
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import mechanical_round as mr


class BreakerRootCauseTests(unittest.TestCase):
    def _round(self, result, signals=()):
        messages = []

        def fake_run(network, *, signals=None, **kwargs):
            if signals is not None:
                signals.extend(self.signals)
            return dict(result)

        self.signals = signals
        with mock.patch("action_ledger.exclusive", return_value=contextlib.nullcontext()):
            with mock.patch.object(mr.cb, "check", return_value=(True, "")):
                with mock.patch.object(mr, "_run", side_effect=fake_run):
                    with mock.patch.object(mr.cb, "record", return_value={}) as rec:
                        with mock.patch.object(mr, "_record_plan_failure"):
                            got = mr.run("mastodon", rng=random.Random(7), out=messages.append)
        return got, rec, messages

    def test_plan_failure_does_not_touch_platform_breaker(self):
        got, record, messages = self._round({"ok": False, "stage": "plan"})
        self.assertFalse(got["ok"])
        record.assert_not_called()
        self.assertTrue(any("FALLO_LOCAL_NO_BREAKER" in line for line in messages))

    def test_preflight_failure_does_not_touch_platform_breaker(self):
        got, record, _ = self._round({"ok": False, "stage": "preflight"})
        self.assertFalse(got["ok"])
        record.assert_not_called()

    def test_unclassified_execution_failure_counts_for_platform_breaker(self):
        got, record, _ = self._round({"ok": False, "stage": "execute"})
        self.assertFalse(got["ok"])
        record.assert_called_once()
        self.assertFalse(record.call_args.args[1])

    def test_execute_returncode_one_without_preflight_is_classified_execute(self):
        with tempfile.TemporaryDirectory() as root:
            pathlib.Path(root, "plan.json").write_text("[]", encoding="utf-8")
            cfg = {"dir": "TEST", "pre": [], "decisions_default": None,
                   "write_decisions": None, "build": None,
                   "plan": "plan.json", "execute": ["python", "fake_execute.py"],
                   "post": [], "shape": False}
            with mock.patch.object(mr, "ROOT", root), \
                 mock.patch.dict(mr.PIPELINES, {"synthetic": cfg}):
                result = mr._run("synthetic", shape=False,
                                 runner=lambda cmd: (1, "FALLO: ejecutor simulado"),
                                 signals=[], out=lambda *_: None)
            self.assertFalse(result["ok"])
            self.assertEqual(result["failure_kind"], "execute")
            self.assertEqual(result["stage"], "execute")

    def test_plan_failure_writes_machine_readable_event_without_post_text(self):
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(mr, "ROOT", root):
                mr._record_plan_failure("mastodon", "build", "C:/logs/build.log")
            directory = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_plan")
            files = list(directory.glob("*.json"))
            self.assertEqual(len(files), 1)
            data = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual((data["red"], data["stage"], data["log_name"]),
                             ("mastodon", "build", "build.log"))
            self.assertNotIn("post_text", data)

    def test_explicit_rate_limit_still_opens_breaker(self):
        _, record, _ = self._round({"ok": False, "stage": "execute"}, signals=["rate"])
        self.assertEqual(record.call_count, 1)
        self.assertEqual(record.call_args.kwargs["signal"], "rate")
        self.assertFalse(record.call_args.args[1])

    def test_explicit_auth_failure_still_opens_breaker(self):
        _, record, _ = self._round({"ok": False, "stage": "plan"}, signals=["auth"])
        self.assertEqual(record.call_args.kwargs["signal"], "auth")

    def test_success_clears_existing_breaker_failures(self):
        _, record, _ = self._round({"ok": True})
        self.assertEqual(record.call_count, 1)
        self.assertTrue(record.call_args.args[1])
        self.assertIsNone(record.call_args.kwargs["signal"])

    def test_real_pipeline_pre_steps_and_paused_instagram(self):
        active = {"bluesky", "mastodon", "threads", "x", "facebook", "pinterest", "tiktok"}
        self.assertEqual(active, set(mr.PIPELINES) - {"instagram"})
        for network in active:
            with self.subTest(network=network):
                kinds = [mr._pre_failure_kind(cmd) for cmd in mr.PIPELINES[network]["pre"]]
                self.assertTrue(all(kind in ("plan", "execute") for _, kind in kinds))
                self.assertTrue(any(stage == "scan" and kind == "execute"
                                    for stage, kind in kinds))
        self.assertEqual(mr._pre_failure_kind(["python", "tools/pinterest_growth.py", "plan"]),
                         ("build", "plan"))
        self.assertEqual(mr._pre_failure_kind(["python", "tools/reply_writer.py", "x"]),
                         ("write", "plan"))

    def test_runner_exception_is_counted_without_exposing_exception_text(self):
        with tempfile.TemporaryDirectory() as root:
            pathlib.Path(root, "plan.json").write_text("[]", encoding="utf-8")
            cfg = {"dir": "TEST", "pre": [], "decisions_default": None,
                   "write_decisions": None, "build": None, "plan": "plan.json",
                   "execute": ["python", "fake_execute.py"], "post": [], "shape": False}
            def crash(_):
                raise OSError("private browser profile path")
            with mock.patch.object(mr, "ROOT", root), \
                 mock.patch.dict(mr.PIPELINES, {"synthetic": cfg}):
                got = mr._run("synthetic", shape=False, runner=crash,
                              signals=[], out=lambda *_: None)
            self.assertFalse(got["ok"])
            self.assertEqual(got["failure_kind"], "execute")
            self.assertNotIn("private browser profile", pathlib.Path(got["log"]).read_text(encoding="utf-8"))

    def test_plan_events_3_in_2h_privacy_corruption_and_7d_purge(self):
        import plan_failure_events as pfe
        import os
        now = mr.datetime.datetime(2026, 10, 8, 20, 0)
        with tempfile.TemporaryDirectory() as root:
            folder = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_plan")
            for n in range(2):
                self.assertTrue(pfe.record(root, "pinterest", "build",
                                           "C:/private/mech_1.log", cause="exit_1", now=now))
            self.assertEqual(pfe.collect_alerts(root, now=now), [])
            self.assertTrue(pfe.record(root, "pinterest", "build",
                                       "C:/private/mech_1.log", cause="exit_1", now=now))
            alerts = pfe.collect_alerts(root, now=now)
            self.assertEqual((alerts[0]["code"], alerts[0]["count"], alerts[0]["last_cause"]),
                             ("FALLO_PLAN_REPETIDO", 3, "exit_1"))
            self.assertNotIn("C:/private", next(folder.glob("*.json")).read_text(encoding="utf-8"))
            (folder / "bad.json").write_text("{invalid", encoding="utf-8")
            self.assertEqual(pfe.collect_alerts(root, now=now)[0]["count"], 3)
            old = next(folder.glob("*.json"))
            os.utime(old, (now.timestamp() - 9 * 86400, now.timestamp() - 9 * 86400))
            pfe.prune(root, now=now)
            self.assertFalse(old.exists())
            self.assertEqual(len(list(folder.glob("*.json"))), 3)

    def test_existing_status_command_consumes_plan_alerts(self):
        import daily_review
        import plan_failure_events as pfe
        now = mr.datetime.datetime.now()
        with tempfile.TemporaryDirectory() as root:
            for _ in range(3):
                pfe.record(root, "pinterest", "build", "mech_1.log",
                           cause="plan_unavailable", now=now)
            with mock.patch.object(daily_review, "ROOT", root):
                report = daily_review.extra_sections(now.date().isoformat())
            self.assertTrue(any("FALLO_PLAN_REPETIDO" in line for line in report))

    def test_auth_regex_and_statuses(self):
        self.assertEqual(mr.cb.detect("HTTP 401 Unauthorized"), "auth")
        self.assertEqual(mr.cb.detect("status: 401"), "auth")
        self.assertEqual(mr.cb.detect("HTTP 429"), "rate")
        self.assertIsNone(mr.cb.detect("status 200"))

    def test_pinterest_pipeline_scan_plan_5xx_and_auth(self):
        import action_ledger as al
        for fault, message, kind, signal in (
            ("scan", "Edge disconnected", "execute", None),
            ("scan", "NameError: broken_scan", "plan", None),
            ("scan", "NameError: quoted post\nEdge disconnected", "execute", None),
            ("plan", "NameError: write_comments", "plan", None),
            ("plan", "HTTP 503 Service Unavailable", "execute", None),
            ("plan", "HTTP 401 Unauthorized", "execute", "auth"),
        ):
            with self.subTest(step=fault, error=message):
                with tempfile.TemporaryDirectory() as root:
                    def runner(cmd):
                        if cmd[1].endswith("pinterest_growth.py") and cmd[2] == fault:
                            return 1, message
                        return 0, ""
                    with mock.patch.object(mr, "ROOT", root), \
                         mock.patch.object(al, "exclusive", return_value=contextlib.nullcontext()), \
                         mock.patch.object(al, "browser_session", return_value=contextlib.nullcontext()), \
                         mock.patch.object(mr.cb, "check", return_value=(True, "")), \
                         mock.patch.object(mr.cb, "record", return_value={}) as record:
                        got = mr.run("pinterest", shape=False, runner=runner,
                                     rng=random.Random(0), out=lambda *_: None)
                    self.assertFalse(got["ok"])
                    self.assertEqual(got["failure_kind"], kind)
                    if kind == "execute" or signal:
                        record.assert_called_once()
                        self.assertEqual(record.call_args.kwargs["signal"], signal)
                    else:
                        record.assert_not_called()
                        files = list(pathlib.Path(root, "00_OPERATIVO", "cache",
                                                  "errores_plan").glob("*.json"))
                        self.assertEqual(len(files), 1)
                        if "NameError" in message:
                            stored = json.loads(files[0].read_text(encoding="utf-8"))
                            self.assertEqual(stored["cause"], "NameError")
                            self.assertNotIn("broken_scan", json.dumps(stored))
                            self.assertNotIn("write_comments", json.dumps(stored))

    def test_build_http_server_failure_not_hidden_as_bad_plan(self):
        cfg = {"dir": "TEST", "pre": [], "decisions_default": None,
               "write_decisions": None, "build": ["python", "build.py"],
               "plan": "unused.json", "execute": ["python", "exec.py"],
               "post": [], "shape": False}
        for output, kind in (("HTTP 503", "execute"),
                             ("status: 403", "execute"),
                             ("NameError: local_bug", "plan")):
            with self.subTest(output=output):
                with tempfile.TemporaryDirectory() as root:
                    with mock.patch.object(mr, "ROOT", root), \
                         mock.patch.dict(mr.PIPELINES, {"synthetic": cfg}):
                        result = mr._run("synthetic", shape=False,
                                         runner=lambda cmd: (1, output),
                                         signals=[], out=lambda *_: None)
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["stage"], "build")
                    self.assertEqual(result["failure_kind"], kind)

    def test_skipped_mobile_busy_does_not_reset_stored_breaker_failure(self):
        result, recorder, _ = self._round({"ok": True, "skipped": True,
                                           "stage": "scan"})
        self.assertTrue(result["skipped"])
        recorder.assert_not_called()

    def test_rate_in_optional_pre_step_stops_before_any_other_action(self):
        import action_ledger as al
        commands = []
        def runner(cmd):
            commands.append(tuple(cmd))
            if cmd[1] == "tools/conversation_followups.py":
                return 1, "HTTP 429 Too Many Requests"
            return 0, ""
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(mr, "ROOT", root), \
                 mock.patch.object(al, "exclusive", return_value=contextlib.nullcontext()), \
                 mock.patch.object(mr.cb, "check", return_value=(True, "")), \
                 mock.patch.object(mr.cb, "record", return_value={}) as record:
                got = mr.run("mastodon", shape=False, runner=runner,
                             rng=random.Random(0), out=lambda *_: None)
        self.assertFalse(got["ok"])
        self.assertEqual(record.call_args.kwargs["signal"], "rate")
        self.assertEqual(len(commands), 3)
        self.assertNotIn("tools/mastodon_growth_flow.py", [c[1] for c in commands])

    def test_auth_in_executor_does_not_continue_best_effort_post_steps(self):
        import action_ledger as al
        commands = []
        def runner(cmd):
            commands.append(tuple(cmd))
            if cmd[1] == "tools/mastodon_execute.py":
                return 1, "HTTP 401 Unauthorized"
            return 0, ""
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(mr, "ROOT", root), \
                 mock.patch.object(al, "exclusive", return_value=contextlib.nullcontext()), \
                 mock.patch.object(mr.cb, "check", return_value=(True, "")), \
                 mock.patch.object(mr.cb, "record", return_value={}) as record:
                got = mr.run("mastodon", shape=False, runner=runner,
                             rng=random.Random(0), out=lambda *_: None)
        self.assertFalse(got["ok"])
        self.assertEqual(record.call_args.kwargs["signal"], "auth")
        self.assertFalse(any(cmd[1] == "tools/loyalty.py" for cmd in commands))

    def test_canary_export_reads_real_plan_event_source(self):
        import plan_failure_events as pfe
        import round_canaries as canaries
        now = mr.datetime.datetime(2026, 10, 8, 20, 0)
        with tempfile.TemporaryDirectory() as root:
            for _ in range(3):
                self.assertTrue(pfe.record(root, "mastodon", "build",
                                           "C:/private/mech.log",
                                           cause="exit_1", now=now))
            report = canaries.collect(root, now=now, pid_alive=lambda _: False)
            found = [a for a in report["alerts"]
                     if a["code"] == "FALLO_PLAN_REPETIDO"]
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["network"], "mastodon")
            self.assertEqual(found[0]["count"], 3)
            self.assertNotIn("C:/private", json.dumps(report))
            target = pathlib.Path(root) / "00_OPERATIVO" / "cache" / "alertas_rondas.json"
            canaries.save_report(target, report)
            self.assertIn("FALLO_PLAN_REPETIDO", target.read_text(encoding="utf-8"))

    def test_rate_during_post_stops_following_steps_and_counts_completed_work(self):
        import action_ledger as al
        seen = []
        def runner(cmd):
            seen.append(tuple(cmd))
            if cmd[1] == "tools/mastodon_execute.py":
                return 0, "confirmado favourite"
            if cmd[1] == "tools/loyalty.py":
                return 1, "confirmado follow\nHTTP 429 Too Many Requests"
            return 0, ""
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(mr, "ROOT", root), \
                 mock.patch.object(al, "exclusive", return_value=contextlib.nullcontext()), \
                 mock.patch.object(mr.cb, "check", return_value=(True, "")), \
                 mock.patch.object(mr.cb, "record", return_value={}) as record:
                result = mr.run("mastodon", shape=False, runner=runner,
                                rng=random.Random(0), out=lambda *_: None)
        self.assertFalse(result["ok"])
        self.assertEqual(record.call_args.kwargs["signal"], "rate")
        self.assertEqual(result["summary"]["confirmadas"].get("favourite"), 1)
        self.assertEqual(result["summary"]["confirmadas"].get("follow"), 1)
        self.assertFalse(any(cmd[1] == "tools/mastodon_cleanup_ttl.py" for cmd in seen))

    def test_dry_does_not_call_like_bulk_follow_publisher_or_executor(self):
        for network in ("bluesky", "mastodon", "tiktok"):
            with self.subTest(network=network):
                commands = []
                with tempfile.TemporaryDirectory() as root:
                    def runner(cmd):
                        commands.append(tuple(str(p) for p in cmd))
                        return 0, ""
                    with mock.patch.object(mr, "ROOT", root):
                        result = mr._run(network, dry=True, runner=runner,
                                         shape=False, signals=[], out=lambda *_: None)
                self.assertTrue(result["ok"])
                self.assertTrue(result["dry"])
                for cmd in commands:
                    self.assertNotIn("--like", cmd)
                    self.assertNotIn("tools/tiktok_bulk_follow.py", cmd)
                    self.assertNotIn("tools/content_publisher.py", cmd)
                    self.assertNotIn(tuple(mr.PIPELINES[network]["execute"]), [cmd])

    def test_microsecond_events_report_latest_cause(self):
        import plan_failure_events as events
        now = mr.datetime.datetime(2026, 10, 8, 20, 0, 0)
        with tempfile.TemporaryDirectory() as root:
            for index, cause in enumerate(("exit_1", "NameError", "plan_unavailable")):
                event_at = now + mr.datetime.timedelta(microseconds=index + 1)
                self.assertTrue(events.record(root, "mastodon", "plan", None,
                                              cause=cause, now=event_at))
            report = events.collect_alerts(root, now=now + mr.datetime.timedelta(seconds=1))
            self.assertEqual(report[0]["last_cause"], "plan_unavailable")

    def test_failed_event_write_is_explicitly_reported_not_claimed_saved(self):
        messages = []
        with mock.patch("action_ledger.exclusive", return_value=contextlib.nullcontext()), \
             mock.patch.object(mr.cb, "check", return_value=(True, "")), \
             mock.patch.object(mr.cb, "record", return_value={}) as rec, \
             mock.patch.object(mr, "_run", return_value={
                 "ok": False, "stage": "build", "failure_kind": "plan",
                 "exit_code": 1, "log": "private.log"
             }), \
             mock.patch.object(mr, "_record_plan_failure", return_value=False):
            result = mr.run("mastodon", rng=random.Random(0), out=messages.append)
        self.assertFalse(result["ok"])
        rec.assert_not_called()
        self.assertTrue(any("EVENTO_NO_PERSISTIDO" in line for line in messages))
        self.assertFalse(any("evento en 00_OPERATIVO/cache" in line for line in messages))

    def test_internal_parent_exceptions_create_plan_event_without_breaker(self):
        for error in (OSError("private profile path"), KeyError("secret"),
                      NameError("missing local variable"), RuntimeError("local code")):
            with self.subTest(exception=type(error).__name__):
                messages = []
                with mock.patch("action_ledger.exclusive", return_value=contextlib.nullcontext()), \
                     mock.patch.object(mr.cb, "check", return_value=(True, "")), \
                     mock.patch.object(mr.cb, "record", return_value={}) as record, \
                     mock.patch.object(mr, "_run", side_effect=error), \
                     mock.patch.object(mr, "_record_plan_failure", return_value=True) as save:
                    result = mr.run("mastodon", rng=random.Random(3),
                                    out=messages.append)
                self.assertFalse(result["ok"])
                self.assertEqual(result["failure_kind"], "plan")
                self.assertEqual(result["error_reason"], type(error).__name__)
                save.assert_called_once()
                record.assert_not_called()
                self.assertFalse(any("private profile path" in m or "secret" in m
                                     or "missing local variable" in m for m in messages))

    def test_local_python_classification_ignores_intermediate_post_text(self):
        self.assertIsNone(mr._local_python_error(
            "NameError: un post menciona un error\nEdge disconnected"))
        self.assertEqual(mr._local_python_error(
            "Traceback (most recent call last):\n  File x, line 7\nNameError: wrong_name"
        ), "NameError")
        self.assertEqual(mr._local_python_error(
            "ModuleNotFoundError: No module named 'x'"), "ModuleNotFoundError")

    def test_breaker_state_remains_valid_when_atomic_replace_fails(self):
        with tempfile.TemporaryDirectory() as root:
            state = mr.cb.record(root, False, signal="rate")
            path = pathlib.Path(root, "cache", "breaker.json")
            original = path.read_bytes()
            self.assertTrue(state["open_until"])
            with mock.patch.object(mr.cb.os, "replace", side_effect=OSError("disk busy")):
                with self.assertRaises(OSError):
                    mr.cb.record(root, True)
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(mr.cb.load(root)["open_until"])
            self.assertEqual(list(path.parent.glob(".breaker.*.tmp")), [])

    def test_breaker_json_serialization_failure_preserves_previous_state(self):
        with tempfile.TemporaryDirectory() as root:
            mr.cb.record(root, False, signal="auth")
            path = pathlib.Path(root, "cache", "breaker.json")
            original = path.read_bytes()
            with self.assertRaises(TypeError):
                mr.cb._save(root, {"open_until": object()})
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.glob(".breaker.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
