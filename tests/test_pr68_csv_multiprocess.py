"""PR68: CSV compartido por procesos WEB/API/MÓVIL, sin cuentas ni datos reales."""
import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import round_queue as q

class RoundCsvAtomicity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "tiempos_rondas.csv"
        patch = mock.patch.object(q, "LOG", str(self.path))
        patch.start()
        self.addCleanup(patch.stop)

    @staticmethod
    def row(network="web"):
        return ["2026-10-09", network, "14:00:00", "14:00:01", 0.0,
                "saltada", "{}", 1, 0, 0]

    def test_missing_or_empty_csv_has_one_header(self):
        q._append_round_csv(self.row())
        q._append_round_csv(self.row("api"))
        with self.path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], list(q.ROUND_CSV_COLUMNS))
        self.assertEqual(len(rows), 3)
        self.path.write_bytes(b"")
        q._append_round_csv(self.row("tiktok"))
        with self.path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(len(rows), 2)
        self.assertTrue(Path(str(self.path) + ".writer.guard").exists())

    def test_denied_interprocess_lock_cannot_write(self):
        with mock.patch.object(q, "_recovery_guard") as lock:
            from contextlib import contextmanager
            @contextmanager
            def denied(path):
                yield False
            lock.side_effect = denied
            with self.assertRaises(OSError):
                q._append_round_csv(self.row())
        self.assertFalse(self.path.exists())

    def test_skip_does_not_increment_or_reset_failure_count_after_restart(self):
        import datetime as dt
        fake_day = dt.datetime(2026, 10, 9, 10, 45, 0)
        rows = [
            ["2026-10-09", "x", "10:00:00", "10:00:05", 0.1,
             "error", "{}", 0, 1, 1],
            ["2026-10-09", "x", "10:10:00", "10:10:05", 0.1,
             "saltada", "{}", 3, 0, 0],
            ["2026-10-09", "x", "10:20:00", "10:20:05", 0.1,
             "error", "{}", 0, 1, 1],
        ]
        for row in rows:
            q._append_round_csv(row)
        recovered = q.retry_snapshot_today(now=fake_day)
        self.assertEqual(recovered["x"][0], 2)
        self.assertGreater(recovered["x"][1], fake_day)

    def test_failed_relaunch_releases_log_handle(self):
        # Cubre la misma reparación de handle de #60 en el árbol de #68.
        operational = Path(self.temp.name) / "00_OPERATIVO"
        operational.mkdir()
        log = operational / "cola_rondas_recarga.log"
        with (mock.patch.object(q, "ROOT", self.temp.name),
              mock.patch.object(q.subprocess, "Popen",
                                side_effect=OSError("spawn test error"))):
            with self.assertRaises(OSError):
                q.relaunch(["tools/round_queue.py"], log.name)
        self.assertTrue(log.is_file())
        log.rename(operational / "renamed.log")  # También debe cerrar en Windows.

    def test_many_independent_python_processes_write_only_one_header(self):
        # Cada hijo importa la implementación REAL en un proceso nuevo; los
        # temporales se transmiten por argumento y no hay acceso al repo operativo.
        script = (
            "import sys,time;"
            "sys.path.insert(0,sys.argv[1]);"
            "import round_queue as q;"
            "q.LOG=sys.argv[2];"
            "time.sleep(max(0,float(sys.argv[3])-time.time()));"
            "q._append_round_csv(['2026-10-09','web','00:00:00','00:00:00',0,"
            "'saltada','{}',1,0,0])"
        )
        start = time.time() + 2.5
        procs = []
        try:
            for _ in range(6):
                procs.append(subprocess.Popen(
                    [sys.executable, "-c", script, str(ROOT/"tools"),
                     str(self.path), str(start)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8"))
            for proc in procs:
                out, err = proc.communicate(timeout=25)
                self.assertEqual(proc.returncode, 0, out+err)
        finally:
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate(timeout=5)
        with self.path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.reader(f))
        self.assertEqual(rows[0], list(q.ROUND_CSV_COLUMNS))
        self.assertEqual(len(rows), 7)
        self.assertEqual(sum(row and row[0]=="fecha" for row in rows), 1)

if __name__=="__main__":
    unittest.main()
