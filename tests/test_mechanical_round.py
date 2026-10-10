"""mechanical_round.py (02/10): ronda sin IA, orquestacion y resumen."""
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import mechanical_round as mr

EXEC_OUT = """=== RESUMEN ===
confirmado           like     @a
confirmado           like     @b
confirmado           follow   @c
saltado_ya_reaccionado like   @d
OMITIDO antes de ejecutar: like sobre x
FALLO: RuntimeError: algo
Metricas finales: seguidores=10 siguiendo=20
"""


class SummarizeTests(unittest.TestCase):
    def test_counts_by_kind_skips_and_failures(self):
        s = mr.summarize(EXEC_OUT)
        self.assertEqual(s["confirmadas"], {"like": 2, "follow": 1})
        self.assertEqual(s["saltadas"], 2)
        self.assertEqual(len(s["fallos"]), 1)


class RunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._root = mr.ROOT
        mr.ROOT = self.tmp.name
        self._lock = mr.LOCK_DIR
        mr.LOCK_DIR = self.tmp.name
        self.calls = []

    def tearDown(self):
        mr.ROOT = self._root
        mr.LOCK_DIR = self._lock
        self.tmp.cleanup()

    def runner(self, fail_at=None):
        def run(cmd):
            self.calls.append(cmd[1:3])
            if fail_at and fail_at in cmd[1]:
                return 1, "boom"
            if "build" in cmd:
                return 0, '{"actions": 42}'
            if "execute" in cmd[1]:
                return 0, EXEC_OUT
            return 0, "ok"
        return run

    def test_bluesky_full_run_writes_empty_decisions_and_executes(self):
        lines = []
        res = mr.run("bluesky", runner=self.runner(), out=lines.append)
        self.assertTrue(res["ok"])
        with open(os.path.join(self.tmp.name, "bluesky_mech_decisions.json")) as f:
            self.assertEqual(json.load(f), {"actions": []})
        self.assertTrue(any("tools/bluesky_execute.py" in c[0].replace("\\", "/") for c in self.calls))
        # plan normal (3) + fidelizacion (3) + oleada de semillas (3) + oleada de follow-back (3) de los ejecutores extra
        self.assertTrue(any("12 confirmadas" in l for l in lines))
        self.assertTrue(any("bluesky_seed_wave.py" in c[0].replace("\\", "/") or "bluesky_seed_wave.py" in " ".join(map(str, c)) for c in self.calls))

    def test_extra_slot_beyond_the_stage_rounds_is_skipped(self):
        lines = []
        res = mr.run("bluesky", runner=self.runner(), out=lines.append, slot=9)   # la etapa 0 son 3 rondas/dia
        self.assertTrue(res["skipped"])
        self.assertEqual(self.calls, [])
        self.assertTrue(any("no se lanza" in l for l in lines))

    def test_dry_run_never_executes(self):
        res = mr.run("mastodon", dry=True, runner=self.runner(), out=lambda *_: None)
        self.assertTrue(res["dry"])
        self.assertFalse(any("execute" in c[0] for c in self.calls))

    def test_failure_stops_the_pipeline(self):
        res = mr.run("mastodon", runner=self.runner(fail_at="auto_decide"), out=lambda *_: None)
        self.assertFalse(res["ok"])
        self.assertFalse(any("build" in c[1:] or "execute" in c[0] for c in self.calls))


class FailureSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._root = mr.ROOT
        mr.ROOT = self.tmp.name
        self._lock = mr.LOCK_DIR
        mr.LOCK_DIR = self.tmp.name

    def tearDown(self):
        mr.ROOT = self._root
        mr.LOCK_DIR = self._lock
        self.tmp.cleanup()

    def test_like_step_failure_does_not_abort_the_round(self):
        calls = []

        def runner(cmd):
            calls.append(cmd[1])
            if "--like" in cmd:
                return 1, "boom"
            return (0, '{"actions": 2}') if "build" in cmd else (0, "ok")
        res = mr.run("bluesky", dry=True, runner=runner, out=lambda *_: None)
        self.assertTrue(res["ok"])

    def test_like_step_failure_in_a_real_run_still_executes(self):
        calls = []

        def runner(cmd):
            calls.append(" ".join(cmd))
            if "--like" in cmd:
                return 1, "boom"
            if "execute" in cmd[1]:
                return 0, "confirmado like @a" + chr(10)
            return 0, '{"actions": 1}'
        res = mr.run("bluesky", runner=runner, out=lambda *_: None)
        self.assertTrue(res["ok"])
        self.assertTrue(any("bluesky_execute" in c for c in calls))

    def test_preflight_failure_is_not_reported_as_success(self):
        def runner(cmd):
            if "execute" in cmd[1]:
                return 0, "FALLO DE PREFLIGHT: ValueError: algo" + chr(10)
            return 0, '{"actions": 1}'
        res = mr.run("bluesky", runner=runner, out=lambda *_: None)
        self.assertFalse(res["ok"])


class WatchdogRetryTests(unittest.TestCase):
<<<<<<< HEAD
    """06/10: si el vigilante aborta el ejecutor de una red por navegador (Edge colgado), la ronda reanuda los workers y reintenta UNA vez."""
=======
    """#59: un watchdog deja ACK incierto y nunca reejecuta la escritura."""
>>>>>>> origin/research/public-reuse-parent

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._root, self._lock = mr.ROOT, mr.LOCK_DIR
        mr.ROOT = mr.LOCK_DIR = self.tmp.name
        os.makedirs(os.path.join(self.tmp.name, "SISTEMA_DIARIO_THREADS"))
        with open(os.path.join(self.tmp.name, "SISTEMA_DIARIO_THREADS", "threads_plan.json"), "w") as f:
            json.dump([{"kind": "like", "handle": f"h{i}"} for i in range(20)], f)

    def tearDown(self):
        mr.ROOT, mr.LOCK_DIR = self._root, self._lock
        self.tmp.cleanup()

<<<<<<< HEAD
    def test_retry_after_watchdog_resumes_workers_and_sums_both_attempts(self):
=======
    def test_watchdog_no_retry_preserves_prior_confirmations(self):
>>>>>>> origin/research/public-reuse-parent
        calls, executes = [], []

        def runner(cmd):
            calls.append(" ".join(cmd))
            if "threads_execute" in cmd[1]:
                executes.append(1)
                if len(executes) == 1:
                    return 6, "confirmado like @a" + chr(10) + "VIGILANTE: 307 s sin actividad en el navegador (Edge colgado)" + chr(10)
                return 0, "confirmado like @b" + chr(10) + "confirmado follow @c" + chr(10)
            return 0, "ok"
        lines = []
        res = mr.run("threads", runner=runner, out=lines.append)
<<<<<<< HEAD
        self.assertEqual(len(executes), 2)
        self.assertTrue(any("cdp_resume_workers" in c for c in calls))
        self.assertTrue(any("3 confirmadas" in l for l in lines), lines)
=======
        self.assertEqual(len(executes), 1)
        self.assertTrue(any("cdp_resume_workers" in item for item in calls))
        self.assertFalse(any("reintento tras vigilante" in item for item in calls))
        self.assertEqual(res["error_reason"], "edge_ack_uncertain")
        self.assertEqual(res["summary"]["confirmadas"], {"like": 1})
        self.assertTrue(res["partial"])
        self.assertTrue(any("1 confirmadas" in line and "1 fallos" in line
                            for line in lines), lines)
>>>>>>> origin/research/public-reuse-parent

    def test_no_retry_without_the_watchdog_message(self):
        executes = []

        def runner(cmd):
            if "threads_execute" in cmd[1]:
                executes.append(1)
                return 0, "confirmado like @a" + chr(10)
            return 0, "ok"
        mr.run("threads", runner=runner, out=lambda *_: None)
        self.assertEqual(len(executes), 1)


class VolumeShapingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._root = mr.ROOT
        mr.ROOT = self.tmp.name
        self._lock = mr.LOCK_DIR
        mr.LOCK_DIR = self.tmp.name

    def tearDown(self):
        mr.ROOT = self._root
        mr.LOCK_DIR = self._lock
        self.tmp.cleanup()

    def runner_with_plan(self, n):
        plan_path = os.path.join(self.tmp.name, "bluesky_mech_plan.json")

        def runner(cmd):
            if "build" in cmd:
                with open(plan_path, "w", encoding="utf-8") as stream:
                    json.dump([{"kind": "like", "i": i} for i in range(n)], stream)
                return 0, '{"actions": %d}' % n
            return 0, "ok"
        return runner, plan_path

    def test_big_plan_is_trimmed_to_the_run_cap_and_reported(self):
        import random
        runner, plan_path = self.runner_with_plan(2000)
        lines = []
        mr.run("bluesky", dry=True, runner=runner, out=lines.append, daily=300, rng=random.Random(5))
        shaped = json.load(open(plan_path, encoding="utf-8"))
        self.assertLess(len(shaped), 2000)
        self.assertTrue(any("tope de esta ronda" in l for l in lines))

    def test_no_shape_keeps_the_full_plan(self):
        runner, plan_path = self.runner_with_plan(500)
        mr.run("bluesky", dry=True, runner=runner, out=lambda *_: None, daily=60, shape=False)
        self.assertEqual(len(json.load(open(plan_path, encoding="utf-8"))), 500)

    def test_spread_delays_real_runs_but_not_dry_runs(self):
        import random
        slept = []
        runner, _ = self.runner_with_plan(5)
        mr.run("bluesky", dry=True, runner=runner, out=lambda *_: None, spread_minutes=20, sleeper=slept.append)
        self.assertEqual(slept, [])
        mr.run("bluesky", runner=runner, out=lambda *_: None, spread_minutes=20, sleeper=slept.append,
               rng=random.Random(4))
        self.assertEqual(len(slept), 1)
        self.assertTrue(0 <= slept[0] <= 20 * 60)


class BrowserPipelineConfigTests(unittest.TestCase):
    def test_browser_networks_have_a_complete_pipeline_and_skip_the_build_step(self):
        for net in ('x', 'threads'):
            cfg = mr.PIPELINES[net]
            self.assertTrue(cfg['browser'])
            self.assertIsNone(cfg['build'])
            self.assertEqual([c[1] for c in cfg['pre']][0].split('/')[-1], f'{net}_scan.py')
            self.assertIn(cfg['plan'], cfg['execute'])
            self.assertIn(net, __import__('volume_shape').BASE_DAILY)


class CircuitBreakerIntegrationTests(unittest.TestCase):
    setUp = RunTests.setUp
    tearDown = RunTests.tearDown
    runner = RunTests.runner

    def test_rate_limit_in_a_round_opens_the_breaker_and_next_round_is_skipped(self):
        def limited(cmd):
            self.calls.append(cmd[1:3])
            return (0, "HTTP 429 Too Many Requests") if len(self.calls) == 1 else (0, "ok")
        lines = []
        mr.run("bluesky", runner=limited, out=lines.append, shape=False)
        self.assertTrue(any("cortacircuitos ABIERTO" in line for line in lines))
        before = len(self.calls)
        again = mr.run("bluesky", runner=self.runner(), out=lines.append, shape=False)
        self.assertTrue(again.get("skipped"))
        self.assertEqual(len(self.calls), before)

    def test_dry_run_neither_checks_nor_records(self):
        mr.run("bluesky", dry=True, runner=self.runner(), out=lambda *_: None, shape=False)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "SISTEMA_DIARIO_BLUESKY", "cache", "breaker.json")))


class XDailySessionTests(unittest.TestCase):
    def test_x_rounds_follow_the_ramp_with_a_minimum_plan(self):
        # 06/10 (David: «quitale tanta restriccion, que tenga rondas»): X ya no es una sola sesion diaria; las rondas/dia las pone la etapa de la rampa
        import volume_shape as vs
        cfg = mr.PIPELINES["x"]
        self.assertNotIn("runs_per_day", cfg)
        self.assertGreaterEqual(vs.runs_per_day("x", cfg), 3)
        self.assertGreaterEqual(cfg["min_plan"], 20)

    def test_single_session_cap_is_three_times_a_three_round_cap(self):
        import random
        import datetime
        import volume_shape as vs
        today = datetime.date(2026, 10, 6)
        one = vs.run_cap("x", today, random.Random(1), runs_per_day=1)
        three = vs.run_cap("x", today, random.Random(1), runs_per_day=3)
        self.assertGreater(one, three)

    def test_poor_plan_is_flagged_as_a_scan_failure(self):
        tmp = tempfile.TemporaryDirectory()
        old_root, old_lock = mr.ROOT, mr.LOCK_DIR
        mr.ROOT = mr.LOCK_DIR = tmp.name
        try:
            os.makedirs(os.path.join(tmp.name, "SISTEMA_DIARIO_X"))
            with open(os.path.join(tmp.name, "SISTEMA_DIARIO_X", "x_plan.json"), "w") as stream:
                json.dump([{"kind": "like", "url": "u"}] * 5, stream)
            lines = []
            mr.run("x", dry=True, runner=lambda cmd: (0, "ok"), out=lines.append, shape=False)
            self.assertTrue(any("plan pobre" in line for line in lines), lines)
        finally:
            mr.ROOT, mr.LOCK_DIR = old_root, old_lock
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
