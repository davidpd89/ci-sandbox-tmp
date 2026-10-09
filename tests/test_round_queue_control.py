"""08/10: INICIAR_RONDAS (recargar) y PARAR_RONDAS (parar) controlan la cola sin perder el punto en que iba."""
import os
import pathlib
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import round_queue as rq


class ControlSignalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patches = [
            mock.patch.object(rq, "RELOAD_FLAG", os.path.join(self.tmp.name, "recargar.flag")),
            mock.patch.object(rq, "STOP_FLAG", os.path.join(self.tmp.name, "parar.flag")),
            mock.patch.object(rq, "QUEUE_LOCK_DIR", self.tmp.name),
        ]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()
        self.tmp.cleanup()

    def touch(self, path, when):
        open(path, "w").close()
        os.utime(path, (when, when))

    def test_only_signals_after_start_count(self):
        now = time.time()
        self.touch(rq.RELOAD_FLAG, now - 100)
        self.assertIsNone(rq.control_signal(started=now))
        self.touch(rq.RELOAD_FLAG, now + 1)
        self.assertEqual(rq.control_signal(started=now), "recargar")

    def test_stop_wins_over_reload(self):
        now = time.time()
        self.touch(rq.RELOAD_FLAG, now + 1)
        self.touch(rq.STOP_FLAG, now + 1)
        self.assertEqual(rq.control_signal(started=now), "parar")

    def test_nap_returns_early_on_signal(self):
        with mock.patch.object(rq, "control_signal", return_value="recargar"):
            start = time.time()
            rq.nap(600)
            self.assertLess(time.time() - start, 2)

    def test_one_live_queue_per_chain(self):
        self.assertTrue(rq.take_chain_lock("api"))
        with mock.patch.object(rq, "_pid_alive", return_value=True), mock.patch.object(rq.os, "getpid", return_value=999999):
            self.assertFalse(rq.take_chain_lock("api"))
            self.assertTrue(rq.take_chain_lock("web"))        # otra cadena distinta convive
        rq.release_chain_lock("api")
        self.assertFalse(os.path.exists(rq._lock_path("api")))

    def test_stale_lock_of_dead_process_is_taken(self):
        with open(rq._lock_path("web"), "w") as stream:
            stream.write("12345")
        with mock.patch.object(rq, "_pid_alive", return_value=False):
            self.assertTrue(rq.take_chain_lock("web"))

    def test_new_queue_skips_chains_already_running(self):
        started = []

        def fake(argv, until, targets, done, only=None):
            started.append(set(only))
            return 0

        with mock.patch.object(rq, "_run_chains", side_effect=fake), \
             mock.patch.object(rq, "done_today", return_value={}), mock.patch.object(rq, "control_signal", return_value=None):
            self.assertTrue(rq.take_chain_lock("api"))
            with mock.patch.object(rq, "_pid_alive", return_value=True), mock.patch.object(rq.os, "getpid", return_value=999999):
                rq.main(["--only", "web,api,tiktok"])
        self.assertEqual(started, [{"web", "tiktok"}])

    def test_without_only_three_independent_processes_are_launched(self):
        launched = []

        class FakeProc:
            pid = 1

            def wait(self):
                return 0

        def fake_popen(cmd, **kwargs):
            launched.append(cmd)
            return FakeProc()

        with mock.patch.object(rq.subprocess, "Popen", side_effect=fake_popen), mock.patch.object(rq.time, "sleep"), \
             mock.patch.object(rq, "_run_chains", side_effect=AssertionError("el lanzador no corre cadenas")):
            rq.main(["--until", "22:00"])
        chains = [cmd[cmd.index("--only") + 1] for cmd in launched]
        self.assertEqual(chains, ["web", "api", "tiktok"])
        self.assertTrue(all(cmd[-2:] == ["--until", "22:00"] for cmd in launched))

    def test_reload_relaunches_queue_with_same_args(self):
        calls = []
        with mock.patch.object(rq, "_run_chains", return_value=0), \
             mock.patch.object(rq, "control_signal", return_value="recargar"), \
             mock.patch.object(rq, "relaunch", side_effect=lambda args, log: calls.append((args, log))), \
             mock.patch.object(rq, "done_today", return_value={}):
            rq.main(["--only", "api"])
        self.assertEqual(calls, [([os.path.join("tools", "round_queue.py"), "--only", "api"], "cola_rondas_api.log")])


class RelaunchTests(unittest.TestCase):
    def test_relaunch_survives_a_locked_log_file(self):
        """08/10: la recarga de la cola web murio con PermissionError porque la tarea programada tenia cola_rondas.log abierto."""
        real_open = open
        opened = []

        def fake_open(path, *args, **kwargs):
            if str(path).endswith("cola_rondas.log"):
                raise PermissionError(13, "Permission denied")
            opened.append(str(path))
            return real_open(os.devnull, "a")

        with mock.patch("builtins.open", side_effect=fake_open), mock.patch.object(rq.subprocess, "Popen") as popen:
            rq.relaunch([os.path.join("tools", "round_queue.py")], "cola_rondas.log")
        self.assertTrue(popen.called)
        self.assertTrue(opened[0].endswith(f"cola_rondas_{os.getpid()}.log"))


if __name__ == "__main__":
    unittest.main()
