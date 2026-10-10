"""Regresiones offline de propiedad compartida WEB/MOBILE.

No usa Edge, Android, credenciales, ni conexiones. Compatible con Windows y
Python 3.11: un subproceso real prueba la exclusión entre procesos.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import action_ledger
import mobile_runtime


class MobileOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name) / "device.lock"

    def test_default_legacy_path_can_be_overridden_by_env(self):
        with mock.patch.dict(os.environ, {"MOBILE_SESSION_LOCK": str(self.path)}):
            with mobile_runtime.mobile_session_lock() as path:
                self.assertEqual(path, str(self.path))
                self.assertTrue(self.path.exists())
                self.assertTrue(self.path.with_suffix(".lock.oslock").exists())
        self.assertFalse(self.path.exists())

    def test_two_sessions_cannot_share_a_live_device(self):
        with mobile_runtime.mobile_session_lock(str(self.path)):
            with self.assertRaises(mobile_runtime.MobileSessionBusy):
                with mobile_runtime.mobile_session_lock(str(self.path)):
                    self.fail("reentrant mobile lock")
        self.assertFalse(self.path.exists())

    def test_live_owner_not_stolen_after_expiration(self):
        with mobile_runtime.mobile_session_lock(str(self.path)):
            os.utime(self.path, (1, 1))
            with self.assertRaises(mobile_runtime.MobileSessionBusy):
                with mobile_runtime.mobile_session_lock(str(self.path), stale_after=0):
                    self.fail("TTL is not proof of owner death")

    def test_legacy_live_pid_colon_marker_is_respected(self):
        self.path.write_text(f"{os.getpid()}:123", encoding="ascii")
        os.utime(self.path, (1, 1))
        with self.assertRaises(mobile_runtime.MobileSessionBusy):
            with mobile_runtime.mobile_session_lock(str(self.path), stale_after=0):
                self.fail("overwrote an older live mobile runtime")
        self.assertEqual(self.path.read_text(encoding="ascii"), f"{os.getpid()}:123")

    def test_legacy_dead_pid_colon_marker_recovered(self):
        self.path.write_text("99999999:123", encoding="ascii")
        with mock.patch.object(action_ledger, "_pid_alive", return_value=False):
            with mobile_runtime.mobile_session_lock(str(self.path)):
                self.assertNotIn(":", self.path.read_text(encoding="ascii").split()[0])
        self.assertFalse(self.path.exists())

    def test_recent_partial_owner_marker_not_stolen(self):
        self.path.write_text("", encoding="ascii")
        with self.assertRaises(mobile_runtime.MobileSessionBusy):
            with mobile_runtime.mobile_session_lock(str(self.path)):
                self.fail("partial writer was stolen")

    def test_old_partial_owner_marker_recovered(self):
        self.path.write_bytes(b"\xff")
        os.utime(self.path, (1, 1))
        with mobile_runtime.mobile_session_lock(str(self.path)):
            self.assertTrue(self.path.read_text(encoding="utf-8").startswith(str(os.getpid())))
        self.assertFalse(self.path.exists())

    def test_path_parent_is_created_on_demand(self):
        nested = self.path.parent / "sub" / "device.lock"
        with mobile_runtime.mobile_session_lock(str(nested)):
            self.assertTrue(nested.exists())
        self.assertFalse(nested.exists())

    def test_exception_releases_lock_and_guard(self):
        with self.assertRaisesRegex(ValueError, "synthetic"):
            with mobile_runtime.mobile_session_lock(str(self.path)):
                raise ValueError("synthetic")
        with mobile_runtime.mobile_session_lock(str(self.path)):
            self.assertTrue(self.path.exists())

    def test_nested_edge_contention_preserves_exception_type(self):
        # El wrapper móvil no debe hacer pasar errores de Edge por móvil ocupado.
        with self.assertRaises(action_ledger.RoundBusy):
            with mobile_runtime.mobile_session_lock(str(self.path)):
                raise action_ledger.RoundBusy("edge_browser: ocupado")
        self.assertFalse(self.path.exists())

    def test_cleanup_does_not_remove_replacement_lock(self):
        with mobile_runtime.mobile_session_lock(str(self.path)):
            self.path.unlink()
            self.path.write_text("777777 1", encoding="ascii")
        self.assertEqual(self.path.read_text(encoding="ascii"), "777777 1")

    def test_edge_default_lock_filename_is_unchanged(self):
        with action_ledger.exclusive("edge_browser", directory=self.temp.name) as path:
            self.assertEqual(path, os.path.join(self.temp.name, "rrss_lock_edge_browser.lock"))
        self.assertFalse(os.path.exists(path))

    def test_interprocess_contention_then_release(self):
        program = (
            "import sys; sys.path.insert(0,sys.argv[1]); "
            "from mobile_runtime import mobile_session_lock; "
            "with mobile_session_lock(sys.argv[2]):\n"
            " print('ACQUIRED',flush=True)\n"
            " sys.stdin.read()\n"
        )
        # Python compounds cannot follow a semicolon: prefix uses a newline.
        program = program.replace("; with mobile_session_lock", "\nwith mobile_session_lock")
        proc = subprocess.Popen(
            [sys.executable, "-c", program, str(TOOLS), str(self.path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True,
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), "ACQUIRED",
                             proc.stderr.read() if proc.poll() is not None else "")
            os.utime(self.path, (1, 1))
            with self.assertRaises(mobile_runtime.MobileSessionBusy):
                with mobile_runtime.mobile_session_lock(str(self.path), stale_after=0):
                    self.fail("parallel process obtained same Android")
        finally:
            proc.stdin.close()
            proc.wait(timeout=10)
            proc.stdout.close()
            proc.stderr.close()
        self.assertEqual(proc.returncode, 0)
        with mobile_runtime.mobile_session_lock(str(self.path)):
            self.assertTrue(self.path.exists())

    def test_crashed_owner_is_recovered_without_ttl(self):
        program = (
            "import os,sys; sys.path.insert(0,sys.argv[1]); "
            "from mobile_runtime import mobile_session_lock\n"
            "lock=mobile_session_lock(sys.argv[2]); lock.__enter__(); os._exit(17)"
        )
        result = subprocess.run([sys.executable, "-c", program, str(TOOLS), str(self.path)],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 17, result.stderr)
        self.assertTrue(self.path.exists())
        with mobile_runtime.mobile_session_lock(str(self.path)):
            self.assertTrue(self.path.exists())
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
