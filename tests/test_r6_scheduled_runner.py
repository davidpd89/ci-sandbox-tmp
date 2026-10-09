"""Integración offline del ejecutor oculto, latido y registro limitado."""
import datetime as dt
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import run_round_canaries_scheduled as runner


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.operativo = self.root / "00_OPERATIVO"

    def test_success_writes_heartbeat_and_rotating_log(self):
        seen = []
        def canary(args):
            seen.append(args)
            print("{\"alert_count\": 1}")
            return 0
        now = dt.datetime(2026, 10, 8, 17, 30, tzinfo=dt.timezone.utc)
        self.assertEqual(runner.run_once(self.root, canary=canary, now=now), 0)
        self.assertEqual(seen[0][0], "--root")
        self.assertEqual(pathlib.Path(seen[0][1]).resolve(), self.root.resolve())
        self.assertEqual((self.operativo / "canarios_ultimo_ok.txt").read_text().strip(),
                         "2026-10-08T17:30:00+00:00")
        log = (self.operativo / "canarios.log").read_text()
        self.assertIn("canario_ok", log)
        self.assertNotIn("alert_count", log)
        self.assertFalse(list(self.operativo.glob("*.tmp")))

    def test_nonzero_does_not_advance_heartbeat(self):
        self.assertEqual(runner.run_once(self.root, canary=lambda _args: 0), 0)
        original = (self.operativo / "canarios_ultimo_ok.txt").read_text()
        self.assertEqual(runner.run_once(self.root, canary=lambda _args: 2), 2)
        self.assertEqual((self.operativo / "canarios_ultimo_ok.txt").read_text(), original)
        self.assertIn("canario_codigo=2", (self.operativo / "canarios.log").read_text())

    def test_exception_not_logged_with_private_content(self):
        def fail(_args):
            print("mensaje privado")
            raise RuntimeError("token-secreto; usuario@example.com")
        self.assertEqual(runner.run_once(self.root, canary=fail), 2)
        self.assertFalse((self.operativo / "canarios_ultimo_ok.txt").exists())
        log = (self.operativo / "canarios.log").read_text()
        self.assertIn("canario_excepcion=RuntimeError", log)
        self.assertNotIn("token-secreto", log)
        self.assertNotIn("mensaje privado", log)

    def test_log_io_failure_never_advances_heartbeat(self):
        with mock.patch.object(runner.CheckedRotatingFileHandler, "shouldRollover",
                               side_effect=OSError("disco lleno")):
            with self.assertRaises(OSError):
                runner.run_once(self.root, canary=lambda _args: 0)
        self.assertFalse((self.operativo / "canarios_ultimo_ok.txt").exists())

    def test_log_rotation_is_bounded_after_many_runs(self):
        for _ in range(550):
            self.assertEqual(runner.run_once(self.root, canary=lambda _: 0), 0)
        self.assertLessEqual(len(list(self.operativo.glob("canarios.log*"))), 3)


if __name__ == "__main__":
    unittest.main()
