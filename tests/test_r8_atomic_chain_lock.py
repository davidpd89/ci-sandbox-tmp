"""R8/F7: dos colas no pueden poseer simultáneamente una cadena.

Reproducer de la ventana TOCTOU: antes se hacia open(read) y open(write),
ambos hilos veian FileNotFoundError y adquirian el mismo lock.
El fichero, los mocks y las sincronizaciones viven en tempfile.
"""
import builtins
import os
import pathlib
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import round_queue as q


class AtomicChainLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved_dir = q.QUEUE_LOCK_DIR
        q.QUEUE_LOCK_DIR = self.temp.name

    def tearDown(self):
        q.QUEUE_LOCK_DIR = self.saved_dir
        self.temp.cleanup()

    def test_simultaneous_callers_cannot_both_take_web(self):
        path = q._lock_path("web")
        begin = threading.Barrier(2)
        non_atomic_write = threading.Barrier(2)
        original_open = builtins.open

        def collide_on_old_write(file, mode="r", *args, **kwargs):
            # Old implementation: two open(path, "w") both reached this
            # barrier after individually observing FileNotFoundError.
            # Correct implementation must use O_EXCL and bypass this barrier.
            if os.fspath(file) == path and mode == "w":
                non_atomic_write.wait(timeout=5)
            return original_open(file, mode, *args, **kwargs)

        def contender():
            begin.wait(timeout=5)
            return q.take_chain_lock("web")

        with mock.patch.object(builtins, "open", side_effect=collide_on_old_write):
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(contender) for _ in range(2)]
                results = [f.result(timeout=9) for f in futures]
        self.assertEqual(sorted(results), [False, True])
        q.release_chain_lock("web")

    def test_same_process_cannot_claim_same_chain_twice(self):
        self.assertTrue(q.take_chain_lock("api"))
        self.assertFalse(q.take_chain_lock("api"))
        q.release_chain_lock("api")

    def test_independent_chains_are_allowed(self):
        self.assertTrue(q.take_chain_lock("web"))
        self.assertTrue(q.take_chain_lock("tiktok"))
        q.release_chain_lock("web")
        q.release_chain_lock("tiktok")

    def test_dead_pid_is_recovered_without_stealing_live_ownership(self):
        path = q._lock_path("api")
        with open(path, "w", encoding="utf-8") as f:
            f.write("700000")
        with mock.patch.object(q, "_pid_alive", side_effect=lambda p: p != 700000):
            self.assertTrue(q.take_chain_lock("api"))
            self.assertFalse(q.take_chain_lock("api"))
        q.release_chain_lock("api")

    def test_empty_old_lock_is_recovered(self):
        path = q._lock_path("web")
        pathlib.Path(path).write_text("", encoding="utf-8")
        os.utime(path, (time.time() - 120, time.time() - 120))
        self.assertTrue(q.take_chain_lock("web"))
        self.assertFalse(q.take_chain_lock("web"))
        q.release_chain_lock("web")

    def test_malformed_old_lock_is_recovered(self):
        path = q._lock_path("api")
        pathlib.Path(path).write_text("pid-incompleto", encoding="utf-8")
        os.utime(path, (time.time() - 120, time.time() - 120))
        self.assertTrue(q.take_chain_lock("api"))
        q.release_chain_lock("api")

    def test_old_reclaim_with_dead_owner_is_recovered(self):
        path = q._lock_path("web")
        pathlib.Path(path).write_text("700000", encoding="utf-8")
        marker = path + ".reclaim"
        pathlib.Path(marker).write_text("700001", encoding="utf-8")
        os.utime(marker, (time.time() - 120, time.time() - 120))
        with mock.patch.object(q, "_pid_alive", side_effect=lambda pid: pid not in (700000, 700001)):
            self.assertTrue(q.take_chain_lock("web"))
        self.assertFalse(os.path.exists(marker))
        q.release_chain_lock("web")

    def test_recent_reclaim_is_not_stolen(self):
        path = q._lock_path("web")
        pathlib.Path(path).write_text("700000", encoding="utf-8")
        pathlib.Path(path + ".reclaim").write_text("700001", encoding="utf-8")
        with mock.patch.object(q, "_pid_alive", return_value=False):
            self.assertFalse(q.take_chain_lock("web"))

    def test_relaunch_after_release_does_not_collide(self):
        self.assertTrue(q.take_chain_lock("api"))
        self.assertFalse(q.take_chain_lock("api"))
        q.release_chain_lock("api")
        self.assertTrue(q.take_chain_lock("api"))
        q.release_chain_lock("api")

    def test_malformed_owner_fails_closed(self):
        with open(q._lock_path("web"), "w", encoding="utf-8") as f:
            f.write("not-a-pid")
        self.assertFalse(q.take_chain_lock("web"))


    def test_import_failure_fails_closed(self):
        path = q._lock_path("api")
        pathlib.Path(path).write_text(str(os.getpid()), encoding="ascii")
        with mock.patch.dict(sys.modules, {"mobile_runtime": None}):
            self.assertTrue(q._pid_alive(os.getpid()))
            self.assertFalse(q.take_chain_lock("api"))
        self.assertEqual(pathlib.Path(path).read_text(encoding="ascii"), str(os.getpid()))

    def test_pid_reuse_detected_by_creation_identity(self):
        path = q._lock_path("web")
        pathlib.Path(path).write_text("700000:12345", encoding="ascii")
        actual = q._process_birth
        with mock.patch.object(q, "_process_birth",
                               side_effect=lambda p: "54321" if p == 700000 else actual(p)):
            self.assertTrue(q.take_chain_lock("web"))
        q.release_chain_lock("web")

    def test_uncertain_or_matching_creation_identity_blocks(self):
        path = q._lock_path("web")
        pathlib.Path(path).write_text("700000:12345", encoding="ascii")
        for result in (None, "12345"):
            with self.subTest(result=result), mock.patch.object(q, "_process_birth", return_value=result):
                self.assertFalse(q.take_chain_lock("web"))

    def test_old_numeric_pid_format_is_accepted(self):
        path = q._lock_path("api")
        pathlib.Path(path).write_text(str(os.getpid()), encoding="ascii")
        self.assertFalse(q.take_chain_lock("api"))

    def test_two_separate_python_processes_observe_one_owner(self):
        import subprocess
        script = (
            "import sys,time;sys.path.insert(0,sys.argv[1]);"
            "import round_queue as q;q.QUEUE_LOCK_DIR=sys.argv[2];"
            "ok=q.take_chain_lock('web');print('HELD' if ok else 'BLOCKED',flush=True);"
            "time.sleep(float(sys.argv[3]));"
            "q.release_chain_lock('web') if ok else None"
        )
        cmd = [sys.executable, "-u", "-c", script,
               str(pathlib.Path(q.__file__).parent), self.temp.name]
        holder = subprocess.Popen(cmd + ["2"], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(holder.stdout.readline().strip(), "HELD")
            contender = subprocess.run(cmd + ["0"], capture_output=True, text=True, timeout=12)
            self.assertEqual(contender.returncode, 0, contender.stderr)
            self.assertEqual(contender.stdout.strip(), "BLOCKED")
            holder.communicate(timeout=12)
            self.assertEqual(holder.returncode, 0)
            self.assertTrue(q.take_chain_lock("web"))
            q.release_chain_lock("web")
        finally:
            if holder.poll() is None:
                holder.kill()
                holder.communicate(timeout=5)

    def test_relaunch_releases_before_new_real_lock_claim(self):
        claimed = []
        with mock.patch.object(q, "rounds_target", return_value=0), \
             mock.patch.object(q, "done_today", return_value={}), \
             mock.patch.object(q, "_run_chains", return_value=0), \
             mock.patch.object(q, "control_signal", return_value="recargar"), \
             mock.patch.object(q, "relaunch", side_effect=lambda *_: claimed.append(q.take_chain_lock("api"))):
            self.assertEqual(q.main(["--only", "api"]), 0)
        self.assertEqual(claimed, [True])
        q.release_chain_lock("api")

    def test_zero_inode_does_not_disable_owner_recheck(self):
        from types import SimpleNamespace as S
        a = S(st_ino=0, st_size=6, st_mtime_ns=40, st_ctime_ns=10, st_dev=1)
        b = S(st_ino=0, st_size=6, st_mtime_ns=41, st_ctime_ns=10, st_dev=1)
        self.assertFalse(q._same_snapshot(a, b))

    def test_active_pid_cannot_be_stolen_by_stale_heartbeat(self):
        path = q._lock_path("api")
        self.assertTrue(q.take_chain_lock("api"))
        old = time.time() - 1800
        os.utime(path, (old, old))
        self.assertFalse(q.take_chain_lock("api"))
        q.release_chain_lock("api")

    def test_guard_permission_failure_does_not_authorize_ronda(self):
        original = os.open
        def denied(path, flags, *args):
            if os.fspath(path).endswith(".lock.guard"):
                raise PermissionError("guard inaccessible")
            return original(path, flags, *args)
        with mock.patch.object(q.os, "open", side_effect=denied):
            self.assertFalse(q.take_chain_lock("api"))
        self.assertFalse(os.path.exists(q._lock_path("api")))

    def test_dead_reclaimer_with_reused_pid_is_recovered(self):
        path = q._lock_path("web")
        pathlib.Path(path).write_text("700000", encoding="ascii")
        marker = path + ".reclaim"
        pathlib.Path(marker).write_text("700001:12345", encoding="ascii")
        older = time.time() - 120
        os.utime(marker, (older, older))
        real_birth = q._process_birth
        with mock.patch.object(q, "_pid_alive", return_value=False), \
             mock.patch.object(q, "_process_birth",
                               side_effect=lambda p: "99999" if p == 700001 else real_birth(p)):
            self.assertTrue(q.take_chain_lock("web"))
        self.assertFalse(os.path.exists(marker))
        q.release_chain_lock("web")

    def test_living_reclaimer_marker_not_deleted_even_if_old(self):
        path = q._lock_path("api")
        pathlib.Path(path).write_text("700000", encoding="ascii")
        marker = path + ".reclaim"
        pathlib.Path(marker).write_text(str(os.getpid()), encoding="ascii")
        older = time.time() - 120
        os.utime(marker, (older, older))
        with mock.patch.object(q, "_pid_alive", side_effect=lambda p: p != 700000):
            self.assertFalse(q.take_chain_lock("api"))
        self.assertTrue(os.path.exists(marker))

    def test_heartbeat_only_refreshes_own_lock(self):
        path = q._lock_path("web")
        self.assertTrue(q.take_chain_lock("web"))
        old = time.time() - 120
        os.utime(path, (old, old))
        stop = threading.Event()
        with mock.patch.object(q, "LOCK_HEARTBEAT_SECONDS", 0.02):
            worker = threading.Thread(target=q._heartbeat_owned_locks,
                                      args=(("web",), stop), daemon=True)
            worker.start()
            time.sleep(0.08)
            stop.set()
            worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertGreater(os.stat(path).st_mtime, old + 30)
        q.release_chain_lock("web")

    def test_release_guard_blocks_interleaved_reacquisition(self):
        """A late release may not unlink a successor's valid ownership."""
        path = q._lock_path("web")
        self.assertTrue(q.take_chain_lock("web"))
        original_unlink = os.unlink
        observed = []
        def interleave(file, *args, **kwargs):
            if os.fspath(file) == path and not observed:
                # Model a same-process release between ownership check and unlink.
                original_unlink(file)
                observed.append(q.take_chain_lock("web"))
                if observed[-1]:
                    original_unlink(file)  # the stale release destroys successor lock
                return
            return original_unlink(file, *args, **kwargs)
        with mock.patch.object(q.os, "unlink", side_effect=interleave):
            self.assertTrue(q.release_chain_lock("web"))
        self.assertEqual(observed, [False],
                         "the release raced with another acquisition")
        self.assertFalse(pathlib.Path(path).exists())

    def test_legacy_owned_lock_can_be_released_after_upgrade(self):
        path = q._lock_path("api")
        pathlib.Path(path).write_text(str(os.getpid()), encoding="ascii")
        self.assertTrue(q.release_chain_lock("api"))
        self.assertFalse(pathlib.Path(path).exists())

    def test_old_invalid_ascii_reclaim_recovers_without_decode_crash(self):
        path = q._lock_path("web")
        pathlib.Path(path).write_text("700000", encoding="ascii")
        marker = path + ".reclaim"
        pathlib.Path(marker).write_bytes(bytes((255, 254)))
        os.utime(marker, (time.time() - 180, time.time() - 180))
        with mock.patch.object(q, "_pid_alive", return_value=False):
            self.assertTrue(q.take_chain_lock("web"))
        self.assertFalse(pathlib.Path(marker).exists())
        self.assertTrue(q.release_chain_lock("web"))

    def test_partial_ledger_from_integration_is_preserved(self):
        import csv
        import datetime as dt
        path = pathlib.Path(self.temp.name) / "rounds.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["fecha", "red", "estado"])
            writer.writerow([dt.date.today().isoformat(), "mastodon", "parcial"])
        with mock.patch.object(q, "LOG", str(path)):
            self.assertEqual(q.done_today().get("mastodon"), 1)

    def test_confirmed_actions_followed_by_error_mark_partial(self):
        from types import SimpleNamespace
        import datetime as dt
        summary = "[mastodon] 4 confirmadas {'like': 4}, 1 saltadas, 1 fallos"
        log = pathlib.Path(self.temp.name) / "rounds.csv"
        with mock.patch.object(q, "LOG", str(log)), \
             mock.patch.object(q.subprocess, "run",
                               return_value=SimpleNamespace(stdout=summary, stderr="", returncode=2)):
            self.assertEqual(q.run_round("mastodon"), "parcial")
        with log.open(encoding="utf-8", newline="") as stream:
            self.assertEqual(list(__import__("csv").DictReader(stream))[-1]["estado"], "parcial")

    def test_api_partial_does_not_relaunch_identical_round(self):
        import datetime as dt
        deadline = dt.datetime.now() + dt.timedelta(minutes=1)
        with mock.patch.object(q, "run_round", return_value="parcial") as runner, \
             mock.patch.object(q, "control_signal", return_value=None), \
             mock.patch.object(q, "budget_left", return_value=0), \
             mock.patch.object(q, "nap", return_value=None):
            q.spaced_chain("mastodon", deadline, 1, 0, "mastodon")
        self.assertEqual(runner.call_count, 1)

    @unittest.skipUnless(os.name == "nt", "requiere Windows real")
    def test_windows_process_start_time_is_available(self):
        birth = q._process_birth(os.getpid())
        self.assertIsNotNone(birth)
        self.assertRegex(birth, r"^[1-9][0-9]{12,}$")
        self.assertEqual(q._owner_token(), f"{os.getpid()}:{birth}")

    @unittest.skipUnless(os.name == "nt", "requiere Windows real")
    def test_windows_exited_pid_code_259_is_not_considered_alive(self):
        import subprocess
        child = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.exit(259)"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        try:
            self.assertEqual(child.wait(timeout=10), 259)
            # The Popen handle remains available even after exit. Windows
            # returns STILL_ACTIVE=259 for living processes AND exit code 259.
            self.assertEqual(q._process_birth(child.pid), "")
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


    def test_crash_after_lock_write_is_recovered_by_real_successor(self):
        import subprocess
        script = (
            "import sys,os;sys.path.insert(0,sys.argv[1]);"
            "import round_queue as q;q.QUEUE_LOCK_DIR=sys.argv[2];"
            "ok=q.take_chain_lock('web');"
            "print('HELD' if ok else 'DENIED',flush=True);"
            "os._exit(47 if ok else 1)"
        )
        cmd = [sys.executable, "-u", "-c", script,
               str(pathlib.Path(q.__file__).parent), self.temp.name]
        finished = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        self.assertEqual(finished.returncode, 47, finished.stderr)
        self.assertEqual(finished.stdout.strip(), "HELD")
        self.assertTrue(q.take_chain_lock("web"))
        self.assertTrue(q.release_chain_lock("web"))

    @unittest.skipUnless(os.name == "nt", "PowerShell solo en Windows")
    def test_powershell_control_parses_without_executing_tasks(self):
        import subprocess
        path = pathlib.Path(__file__).resolve().parents[1] / "tools" / "rondas_control.ps1"
        quoted = str(path).replace("'", "''")
        script = (
            "$tokens = $null; $errors = $null; "
            "[System.Management.Automation.Language.Parser]::ParseFile("
            f"'{quoted}', [ref]$tokens, [ref]$errors) | Out-Null; "
            "if ($errors.Count -gt 0) { $errors | Out-String | Write-Error; exit 1 }"
        )
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
