"""R8: un solo trabajador de ChatGPT; bloqueo del SO, no check-then-open.

Pruebas offline. La contención usa hilos y procesos reales del runner,
pero NO abre cuentas, Edge, APIs ni ficheros operativos.
"""
import contextlib
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import worker_singleton as single
import reply_queue as rq


class WorkerSingletonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.pidfile = pathlib.Path(self.temp.name) / "worker.lock"

    def tearDown(self):
        self.temp.cleanup()

    def test_second_thread_cannot_claim_while_first_owns_lock(self):
        acquired = threading.Event()
        release = threading.Event()
        result = []

        def owner():
            with single.claim(self.pidfile) as ok:
                result.append(ok)
                acquired.set()
                release.wait(5)

        t = threading.Thread(target=owner)
        t.start()
        try:
            self.assertTrue(acquired.wait(5))
            with single.claim(self.pidfile) as second:
                self.assertFalse(second)
            self.assertEqual(result, [True])
            self.assertEqual(self.pidfile.read_text(encoding="ascii"), str(os.getpid()))
        finally:
            release.set()
            t.join(5)
        self.assertFalse(t.is_alive())
        self.assertFalse(self.pidfile.exists())


    @unittest.skipUnless(sys.platform.startswith("linux"), "requiere /proc Linux")
    def test_unreaped_dead_pid_cannot_block_recovery(self):
        # El proceso es zombi: kill(pid, 0) todavía encuentra el PID, pero
        # ya no puede realizar trabajo ni poseer el candado del SO.
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        try:
            child.kill()
            state = None
            for _ in range(200):
                status = pathlib.Path(f"/proc/{child.pid}/status").read_text(encoding="utf-8")
                state = next((line.split()[1] for line in status.splitlines()
                              if line.startswith("State:")), None)
                if state == "Z":
                    break
                time.sleep(0.01)
            self.assertEqual(state, "Z", "no se pudo observar el PID zombi")
            self.pidfile.write_text(str(child.pid), encoding="ascii")
            with mock.patch.object(rq, "LOCK", str(self.pidfile)):
                self.assertFalse(rq.worker_running())
            with single.claim(self.pidfile) as acquired:
                self.assertTrue(acquired)
        finally:
            child.wait(timeout=5)

    def test_worker_running_still_reports_live_legacy_pid(self):
        self.pidfile.write_text("98765", encoding="ascii")
        with mock.patch.object(rq, "LOCK", str(self.pidfile)), \
             mock.patch.object(single, "_legacy_pid_alive", return_value=True):
            self.assertTrue(rq.worker_running())

    def test_proc_unreadable_respects_legacy_pid(self):
        with mock.patch.object(single, "_pid_alive", return_value=True), \
             mock.patch.object(single.sys, "platform", "linux"), \
             mock.patch("builtins.open", side_effect=PermissionError("proc cerrado")):
            self.assertTrue(single._legacy_pid_alive(98765))

    def test_loop_reaches_os_guard_even_if_pid_probe_says_running(self):
        # Antes, worker_running() == True retornaba antes de claim().
        with mock.patch.object(rq, "worker_running", return_value=True), \
             mock.patch.object(single, "claim", return_value=contextlib.nullcontext(True)) as guard, \
             mock.patch("round_queue.control_signal", return_value="parar"):
            now = __import__("datetime").datetime.now()
            self.assertEqual(rq.loop(now + __import__("datetime").timedelta(minutes=1)), 0)
        guard.assert_called_once_with(rq.LOCK)

    def test_crashed_process_releases_os_lock_without_deleting_guard_file(self):
        child_code = (
            "import sys,time\n"
            "sys.path.insert(0,sys.argv[2])\n"
            "import worker_singleton as lock\n"
            "with lock.claim(sys.argv[1]) as acquired:\n"
            "  print('READY' if acquired else 'BUSY',flush=True)\n"
            "  if acquired: time.sleep(40)\n"
        )
        child = subprocess.Popen(
            [sys.executable, "-c", child_code, str(self.pidfile), str(pathlib.Path(single.__file__).parent)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            self.assertEqual(child.stdout.readline().strip(), "READY")
            with single.claim(self.pidfile) as claimed:
                self.assertFalse(claimed)
        finally:
            child.kill()
            child.wait(timeout=5)
            child.stdout.close()
            child.stderr.close()

        # Hay PID viejo, pero la terminación del proceso libera el candado.
        self.assertTrue(pathlib.Path(str(self.pidfile) + ".oslock").exists())
        with single.claim(self.pidfile) as claimed:
            self.assertTrue(claimed)
            self.assertEqual(self.pidfile.read_text(encoding="ascii"), str(os.getpid()))
        self.assertFalse(self.pidfile.exists())

    def test_legacy_live_worker_is_respected_on_upgrade(self):
        self.pidfile.write_text("981234", encoding="ascii")
        with mock.patch.object(single, "_pid_alive", return_value=True):
            with single.claim(self.pidfile) as claimed:
                self.assertFalse(claimed)
        self.assertEqual(self.pidfile.read_text(encoding="ascii"), "981234")

    def test_malformed_legacy_pid_does_not_block_new_worker(self):
        self.pidfile.write_text("PID_CORRUPTO", encoding="ascii")
        with single.claim(self.pidfile) as claimed:
            self.assertTrue(claimed)
        self.assertFalse(self.pidfile.exists())

    def test_exception_releases_lock_and_only_own_pid_file_is_removed(self):
        with self.assertRaisesRegex(ValueError, "simulado"):
            with single.claim(self.pidfile) as claimed:
                self.assertTrue(claimed)
                raise ValueError("simulado")
        with single.claim(self.pidfile) as claimed:
            self.assertTrue(claimed)

    def test_does_not_unlink_a_replaced_pid_file(self):
        with single.claim(self.pidfile) as claimed:
            self.assertTrue(claimed)
            self.pidfile.write_text("999999", encoding="ascii")
        self.assertEqual(self.pidfile.read_text(encoding="ascii"), "999999")

    def test_worker_loop_refuses_when_other_process_owns_os_lock(self):
        with mock.patch.object(rq, "worker_running", return_value=False), \
             mock.patch.object(single, "claim", return_value=contextlib.nullcontext(False)), \
             mock.patch.object(rq, "work_once", side_effect=AssertionError("doble trabajador")):
            self.assertEqual(rq.loop(__import__("datetime").datetime.now()), 0)

    def test_manual_work_command_does_not_run_while_loop_owns_lock(self):
        with mock.patch.object(single, "claim", return_value=contextlib.nullcontext(False)), \
             mock.patch.object(rq, "work_once", side_effect=AssertionError("doble consulta")):
            self.assertEqual(rq.work_command(12), 2)

    def test_manual_work_command_holds_lock_until_work_once_finishes(self):
        seen = []
        @contextlib.contextmanager
        def owned(_):
            seen.append("acquire")
            try:
                yield True
            finally:
                seen.append("release")

        with mock.patch.object(single, "claim", side_effect=owned), \
             mock.patch.object(rq, "work_once", side_effect=lambda n: seen.append(f"work:{n}") or 3):
            self.assertEqual(rq.work_command(12), 0)
        self.assertEqual(seen, ["acquire", "work:12", "release"])


    def test_pending_load_error_does_not_abort_worker_or_unlock_early(self):
        # Regresión relevante para la cuarentena de #105: antes el _load
        # estaba fuera del try, provocaba la salida del bucle y del guard.
        import datetime
        seen = []

        @contextlib.contextmanager
        def owner(_):
            seen.append("lock")
            try:
                yield True
            finally:
                seen.append("unlock")

        signals = {"calls": 0}

        def signal(*_):
            signals["calls"] += 1
            return None if signals["calls"] == 1 else "parar"

        with mock.patch.object(single, "claim", side_effect=owner), \
             mock.patch.object(rq, "_load", side_effect=OSError("cola inaccesible")), \
             mock.patch.object(rq, "work_once", side_effect=AssertionError("sin GPT")), \
             mock.patch("round_queue.control_signal", side_effect=signal), \
             mock.patch.object(rq.time, "sleep", side_effect=AssertionError("no dormir tras parada")):
            self.assertEqual(rq.loop(datetime.datetime.now() + datetime.timedelta(minutes=2)), 0)
        self.assertEqual(seen, ["lock", "unlock"])

    def test_os_lock_contention_returns_false_without_pid_file(self):
        with mock.patch.object(single, "_take", side_effect=BlockingIOError(11, "ocupado")):
            with single.claim(self.pidfile) as acquired:
                self.assertFalse(acquired)
        self.assertFalse(self.pidfile.exists())

    def test_unexpected_lock_io_error_fails_closed_and_recovers(self):
        import errno
        with mock.patch.object(single, "_take", side_effect=OSError(errno.EIO, "disco")):
            with self.assertRaises(OSError):
                with single.claim(self.pidfile) as acquired:
                    self.fail("no debe conceder el turno")
        self.assertFalse(self.pidfile.exists())
        with single.claim(self.pidfile) as acquired:
            self.assertTrue(acquired)

    def test_pid_write_error_releases_os_guard(self):
        import errno
        with mock.patch.object(pathlib.Path, "write_text", side_effect=OSError(errno.EIO, "sin espacio")):
            with self.assertRaises(OSError):
                with single.claim(self.pidfile) as acquired:
                    self.fail("no debe llegar a ChatGPT")
        with single.claim(self.pidfile) as acquired:
            self.assertTrue(acquired)

    def test_release_failure_still_closes_descriptor(self):
        import errno
        with mock.patch.object(single, "_release", side_effect=OSError(errno.EIO, "fallo de unlock")):
            with self.assertRaises(OSError):
                with single.claim(self.pidfile) as acquired:
                    self.assertTrue(acquired)
        # El finally cierra fd incluso si el unlock ha fallado.
        with single.claim(self.pidfile) as acquired:
            self.assertTrue(acquired)

    def test_two_real_python_workers_one_owner_no_json_mutation(self):
        """Dos CLI reales; el rival sale sin entrar a GPT ni tocar archivos."""
        folder = pathlib.Path(self.temp.name)
        pending = folder / "pending.json"
        answers = folder / "answers.json"
        pending.write_text('{"fixture": {"network": "mastodon", "text": "prueba"}}',
                           encoding="utf-8")
        answers.write_text('{"fixture": {"reply": "conservada"}}', encoding="utf-8")
        before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (pending, answers)]
        tools_dir = str(pathlib.Path(single.__file__).parent)
        owner_code = (
            "import sys;sys.path.insert(0,sys.argv[2]);"
            "import worker_singleton as w;"
            "ctx=w.claim(sys.argv[1]);"
            "ok=ctx.__enter__();"
            "print('READY' if ok else 'BUSY',flush=True);"
            "sys.stdin.readline();"
            "ctx.__exit__(None,None,None)"
        )
        contender_code = (
            "import sys,datetime;sys.path.insert(0,sys.argv[4]);"
            "import reply_queue as r;"
            "r.LOCK=sys.argv[1];r.PENDING=sys.argv[2];r.ANSWERS=sys.argv[3];"
            "raise SystemExit(r.loop(datetime.datetime.now()+datetime.timedelta(minutes=2)))"
        )
        owner = subprocess.Popen(
            [sys.executable, "-u", "-c", owner_code, str(self.pidfile), tools_dir],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        try:
            self.assertEqual(owner.stdout.readline().strip(), "READY")
            contender = subprocess.run(
                [sys.executable, "-u", "-c", contender_code, str(self.pidfile),
                 str(pending), str(answers), tools_dir],
                capture_output=True, text=True, encoding="utf-8", timeout=12,
            )
            self.assertEqual(contender.returncode, 0, contender.stderr)
            self.assertIn("otra instancia tiene el turno", contender.stdout)
            self.assertIsNone(owner.poll(), "el rival terminó al propietario activo")
            self.assertEqual(self.pidfile.read_text(encoding="ascii"), str(owner.pid))
            self.assertEqual(
                [(p.read_bytes(), p.stat().st_mtime_ns) for p in (pending, answers)],
                before,
            )
        finally:
            if owner.poll() is None:
                owner.stdin.write("\n")
                owner.stdin.flush()
                owner.communicate(timeout=12)
            for pipe in (owner.stdin, owner.stdout, owner.stderr):
                if pipe and not pipe.closed:
                    pipe.close()
        self.assertEqual(owner.returncode, 0)
        self.assertFalse(self.pidfile.exists())

    def test_guard_file_stays_on_disk_without_preventing_next_run(self):
        with single.claim(self.pidfile) as claimed:
            self.assertTrue(claimed)
        guard = pathlib.Path(str(self.pidfile) + ".oslock")
        self.assertTrue(guard.exists())
        with single.claim(self.pidfile) as claimed:
            self.assertTrue(claimed)
        self.assertTrue(guard.exists())


if __name__ == "__main__":
    unittest.main()
