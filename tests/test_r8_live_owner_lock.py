"""R8: una sesión Edge viva no caduca por edad del fichero.

El bloqueo actual de action_ledger.exclusive puede borrar un lock cuyo PID
sigue vivo cuando age >= stale_after. Solo tempestades de procesos ficticios,
ficheros bajo tempfile, sin navegador ni red.
"""
import os
import pathlib
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import action_ledger as ledger


class LiveOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = pathlib.Path(self.temp.name)
        self.lockfile = self.folder / "rrss_lock_edge_browser.lock"

    def tearDown(self):
        self.temp.cleanup()

    def make_lock(self, value, age_seconds):
        self.lockfile.write_text(value, encoding="utf-8")
        old = time.time() - age_seconds
        os.utime(self.lockfile, (old, old))

    def test_live_owner_remains_exclusive_past_stale_after(self):
        self.make_lock(f"{os.getpid()} 1", 3600)
        with self.assertRaises(ledger.RoundBusy):
            with ledger.exclusive("edge_browser", stale_after=10, directory=self.folder):
                self.fail("doble turno Edge")
        self.assertTrue(self.lockfile.exists())
        self.assertEqual(self.lockfile.read_text(encoding="utf-8"), f"{os.getpid()} 1")

    def test_dead_owner_is_recovered_without_waiting_two_hours(self):
        self.make_lock("800012 1", 20)
        with mock.patch.object(ledger, "_pid_alive", return_value=False):
            with ledger.exclusive("edge_browser", stale_after=7200, directory=self.folder):
                self.assertEqual(self.lockfile.read_text(encoding="utf-8").split()[0], str(os.getpid()))
        self.assertFalse(self.lockfile.exists())

    def test_recent_empty_file_is_not_stolen_during_writer_start(self):
        self.make_lock("", 2)
        with self.assertRaises(ledger.RoundBusy):
            with ledger.exclusive("edge_browser", stale_after=7200, directory=self.folder):
                self.fail("no se puede pisar un PID en proceso de escritura")
        self.assertTrue(self.lockfile.exists())

    def test_old_empty_file_is_recoverable_after_crash(self):
        self.make_lock("", 120)
        with ledger.exclusive("edge_browser", stale_after=7200, directory=self.folder):
            self.assertTrue(self.lockfile.read_text(encoding="utf-8").startswith(str(os.getpid())))
        self.assertFalse(self.lockfile.exists())

    def test_old_malformed_file_can_be_recovered(self):
        self.make_lock("pid_invalido", 120)
        with ledger.exclusive("edge_browser", stale_after=7200, directory=self.folder):
            self.assertTrue(self.lockfile.read_text(encoding="utf-8").startswith(str(os.getpid())))
        self.assertFalse(self.lockfile.exists())

    def test_cannot_reenter_own_live_lock_even_with_zero_stale_after(self):
        with ledger.exclusive("edge_browser", stale_after=0, directory=self.folder):
            with self.assertRaises(ledger.RoundBusy):
                with ledger.exclusive("edge_browser", stale_after=0, directory=self.folder):
                    self.fail("mismo proceso ha robado su propio turno")



class GuardRaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = pathlib.Path(self.temp.name)
        self.lock = self.folder / "rrss_lock_edge_browser.lock"

    def tearDown(self):
        self.temp.cleanup()

    def test_two_reclaimers_cannot_erase_a_new_owner(self):
        import contextlib
        import threading
        self.lock.write_text("800012 1", encoding="utf-8")
        inspected = threading.Event()
        resume = threading.Event()
        entered = threading.Event()
        leave = threading.Event()
        errors = []

        def dead(_pid):
            if threading.current_thread().name == "delayed-reclaimer":
                inspected.set()
                if not resume.wait(4):
                    raise AssertionError("timeout de coordinación")
            return False

        def worker():
            try:
                with ledger.exclusive("edge_browser", directory=self.folder):
                    entered.set()
                    leave.wait(4)
            except Exception as exc:
                errors.append(exc)

        with mock.patch.object(ledger, "_pid_alive", side_effect=dead):
            t = threading.Thread(target=worker, name="delayed-reclaimer")
            t.start()
            try:
                self.assertTrue(inspected.wait(4))
                with contextlib.ExitStack() as stack:
                    own_second = False
                    try:
                        stack.enter_context(ledger.exclusive("edge_browser", directory=self.folder))
                        own_second = True
                    except ledger.RoundBusy:
                        pass
                    resume.set()
                    self.assertTrue(entered.wait(4))
                    self.assertFalse(own_second, "dos reclamadores poseen simultáneamente Edge")
            finally:
                resume.set()
                leave.set()
                t.join(5)
        self.assertFalse(t.is_alive())
        self.assertEqual(errors, [])

    def test_guard_blocks_if_pid_file_vanishes_while_owned(self):
        with ledger.exclusive("edge_browser", directory=self.folder):
            self.lock.unlink()
            with self.assertRaises(ledger.RoundBusy):
                with ledger.exclusive("edge_browser", directory=self.folder):
                    self.fail("un segundo turno ha entrado sin respetar el guard")

    def test_cleanup_keeps_replacement_lock_of_another_owner(self):
        with ledger.exclusive("edge_browser", directory=self.folder):
            self.lock.unlink()
            self.lock.write_text("777777 1", encoding="utf-8")
        self.assertEqual(self.lock.read_text(encoding="utf-8"), "777777 1")


    def test_exception_releases_guard_for_next_owner(self):
        with self.assertRaisesRegex(RuntimeError, "error sintético"):
            with ledger.exclusive("edge_browser", directory=self.folder):
                raise RuntimeError("error sintético")
        self.assertFalse(self.lock.exists())
        with ledger.exclusive("edge_browser", directory=self.folder):
            self.assertTrue(self.lock.exists())
        self.assertTrue((self.folder / "rrss_lock_edge_browser.lock.oslock").exists())

    def test_process_crash_releases_guard_and_recovers_dead_pid(self):
        import subprocess
        script = (
            "import os, sys; sys.path.insert(0, sys.argv[1]); "
            "import action_ledger; "
            "owner = action_ledger.exclusive('edge_browser', directory=sys.argv[2]); "
            "owner.__enter__(); os._exit(14)"
        )
        result = subprocess.run(
            [sys.executable, "-c", script,
             str(pathlib.Path(ledger.__file__).parent), str(self.folder)],
            capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 14, result.stderr)
        self.assertTrue(self.lock.exists())
        with ledger.exclusive("edge_browser", directory=self.folder):
            self.assertTrue(self.lock.exists())
        self.assertFalse(self.lock.exists())

    def test_pid_reuse_fail_closed_without_borrowing_other_process(self):
        self.lock.write_text("777777 1", encoding="utf-8")
        os.utime(self.lock, (1, 1))
        with mock.patch.object(ledger, "_pid_alive", return_value=True):
            with self.assertRaises(ledger.RoundBusy):
                with ledger.exclusive("edge_browser", stale_after=1, directory=self.folder):
                    pass

    def test_failed_pid_stream_is_cleaned_and_guard_released(self):
        with mock.patch.object(ledger.os, "fdopen", side_effect=OSError("escritura fallida")):
            with self.assertRaises(OSError):
                with ledger.exclusive("edge_browser", directory=self.folder):
                    pass
        self.assertFalse(self.lock.exists())
        with ledger.exclusive("edge_browser", directory=self.folder):
            self.assertTrue(self.lock.exists())


    def test_corrupt_utf8_fresh_is_not_stolen(self):
        self.lock.write_bytes(b"\xff\xfe")
        with self.assertRaises(ledger.RoundBusy):
            with ledger.exclusive("edge_browser", directory=self.folder):
                self.fail("fichero corrupto reciente debe conservar el margen")

    def test_corrupt_utf8_old_is_recoverable(self):
        self.lock.write_bytes(b"\xff\xfe")
        os.utime(self.lock, (1, 1))
        with ledger.exclusive("edge_browser", directory=self.folder):
            self.assertTrue(self.lock.read_text(encoding="utf-8").startswith(str(os.getpid())))
        self.assertFalse(self.lock.exists())

    def test_malformed_recent_pid_retains_sixty_seconds_even_if_ttl_zero(self):
        self.lock.write_text("pid_invalido", encoding="utf-8")
        with self.assertRaises(ledger.RoundBusy):
            with ledger.exclusive("edge_browser", stale_after=0, directory=self.folder):
                self.fail("TTL de sesión no debe robar escritor inicializando")


    def test_finalizer_closes_reader_before_unlink(self):
        import builtins
        real_open = builtins.open
        real_remove = os.remove
        opened = []
        def track_open(file, *args, **kwargs):
            stream = real_open(file, *args, **kwargs)
            if str(file) == str(self.lock):
                opened.append(stream)
            return stream
        def check_remove(path):
            if str(path) == str(self.lock):
                self.assertTrue(all(stream.closed for stream in opened),
                                "Windows no permite borrar un fichero aún abierto")
            return real_remove(path)
        with mock.patch.object(ledger, "open", side_effect=track_open, create=True):
            with mock.patch.object(ledger.os, "remove", side_effect=check_remove):
                with ledger.exclusive("edge_browser", directory=self.folder):
                    pass
        self.assertFalse(self.lock.exists())



class PidLivenessCrossPlatformTests(unittest.TestCase):
    """PID no equivale siempre a proceso ejecutándose."""

    def test_current_process_is_alive(self):
        self.assertTrue(ledger._pid_alive(os.getpid()))

    def test_nonpositive_pids_are_dead(self):
        self.assertFalse(ledger._pid_alive(0))
        self.assertFalse(ledger._pid_alive(-1))

    @unittest.skipUnless(sys.platform.startswith("linux"), "solo Linux /proc")
    def test_linux_zombie_can_be_reclaimed_despite_kill_zero(self):
        import subprocess
        proc = subprocess.Popen([sys.executable, "-c", "import os; os._exit(0)"])
        try:
            state = None
            end = time.monotonic() + 4
            while time.monotonic() < end:
                with open(f"/proc/{proc.pid}/status", encoding="ascii") as stream:
                    row = next((v for v in stream if v.startswith("State:")), "")
                state = row.partition(":")[2].strip()[:1]
                if state == "Z":
                    break
                time.sleep(0.01)
            self.assertEqual(state, "Z", "no se pudo observar el proceso zombi")
            os.kill(proc.pid, 0)  # antiguo _pid_alive lo confundía con vivo
            self.assertFalse(ledger._pid_alive(proc.pid))
            with tempfile.TemporaryDirectory() as directory:
                lock = pathlib.Path(directory) / "rrss_lock_edge_browser.lock"
                lock.write_text(f"{proc.pid} 1", encoding="utf-8")
                with ledger.exclusive("edge_browser", directory=directory):
                    self.assertEqual(lock.read_text(encoding="utf-8").split()[0], str(os.getpid()))
                self.assertFalse(lock.exists())
        finally:
            proc.wait(timeout=5)

    @unittest.skipUnless(sys.platform.startswith("linux"), "solo Linux /proc")
    def test_proc_status_unreadable_fails_closed(self):
        with mock.patch.object(ledger.os, "kill", return_value=None):
            with mock.patch.object(ledger, "open", side_effect=PermissionError("proc"), create=True):
                self.assertTrue(ledger._pid_alive(876543))

    @unittest.skipUnless(os.name == "nt", "solo Windows")
    def test_windows_terminated_process_exit_code_259_not_alive(self):
        import subprocess
        proc = subprocess.Popen([sys.executable, "-c", "import os; os._exit(259)"])
        try:
            self.assertEqual(proc.wait(timeout=5), 259)
            self.assertFalse(ledger._pid_alive(proc.pid))
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)



    def test_out_of_range_pid_recent_uses_incomplete_owner_grace(self):
        huge = str(1 << 70)
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rrss_lock_edge_browser.lock"
            path.write_text(huge, encoding="utf-8")
            with self.assertRaises(ledger.RoundBusy):
                with ledger.exclusive("edge_browser", stale_after=0, directory=directory):
                    self.fail("PID numérico imposible no debe robarse en inicialización")

    def test_out_of_range_pid_old_recovers_without_overflow(self):
        huge = str(1 << 70)
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rrss_lock_edge_browser.lock"
            path.write_text(huge, encoding="utf-8")
            os.utime(path, (1, 1))
            with ledger.exclusive("edge_browser", directory=directory):
                self.assertTrue(path.read_text(encoding="utf-8").startswith(str(os.getpid())))
            self.assertFalse(path.exists())

    def test_direct_liveness_with_unrepresentable_pid_fails_closed(self):
        self.assertTrue(ledger._pid_alive(1 << 70))


    def test_stat_failure_closes_pid_descriptor(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = str(pathlib.Path(directory) / "rrss_lock_edge_browser.lock")
            opened = []
            real_open = os.open

            def tracking_open(path, *args, **kwargs):
                fd = real_open(path, *args, **kwargs)
                if str(path) == filename:
                    opened.append(fd)
                return fd

            with mock.patch.object(ledger.os, "open", side_effect=tracking_open):
                with mock.patch.object(ledger.os, "stat", side_effect=OSError("stat sintético")):
                    with self.assertRaisesRegex(OSError, "stat sintético"):
                        with ledger.exclusive("edge_browser", directory=directory):
                            self.fail("no debe entrar")
            self.assertEqual(len(opened), 1)
            with self.assertRaises(OSError):
                os.fstat(opened[0])  # descriptor cerrado también ante fallo temprano



    def test_guard_rejects_real_second_process_then_allows_it(self):
        import subprocess
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = pathlib.Path(temp.name)
        self.lock = self.folder / "rrss_lock_edge_browser.lock"
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from action_ledger import exclusive, RoundBusy; "
            "directory = sys.argv[2]\\n"
            "try:\\n"
            "    with exclusive('edge_browser', directory=directory): pass\\n"
            "except RoundBusy: sys.exit(21)\\n"
        )
        # La cadena enviada a -c necesita saltos de línea reales.
        code = code.replace("\\n", "\n")

        def other_process():
            return subprocess.run(
                [sys.executable, "-c", code, str(pathlib.Path(ledger.__file__).parent), str(self.folder)],
                capture_output=True, text=True, timeout=15,
            )

        with ledger.exclusive("edge_browser", directory=self.folder):
            busy = other_process()
            self.assertEqual(busy.returncode, 21, busy.stderr)
            self.assertTrue(self.lock.exists())
        free = other_process()
        self.assertEqual(free.returncode, 0, free.stderr)
        self.assertFalse(self.lock.exists())



class CorruptedCleanupTests(unittest.TestCase):
    def test_corruption_during_owned_turn_does_not_abort_finally(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "rrss_lock_edge_browser.lock"
            with ledger.exclusive("edge_browser", directory=directory):
                path.write_bytes(b"\xff\xfe")  # misma ruta, contenido corrupto
            self.assertEqual(path.read_bytes(), b"\xff\xfe")


if __name__ == "__main__":
    unittest.main()
