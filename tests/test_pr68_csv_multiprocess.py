"""PR #5: CSV compartido por procesos WEB/API/MÓVIL, sin cuentas ni datos reales."""
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

    def read_rows(self):
        with self.path.open(encoding="utf-8", newline="") as stream:
            return list(csv.reader(stream))

    def test_first_boot_with_absent_parent_directory(self):
        import datetime as dt
        self.path = Path(self.temp.name) / "new" / "nested" / "tiempos_rondas.csv"
        q.LOG = str(self.path)
        self.assertEqual(q.done_today(dt.date(2026, 10, 9)), {})
        q._append_round_csv(self.row("mastodon"))
        self.assertEqual(len(self.read_rows()), 2)

    def test_missing_or_empty_csv_has_one_header(self):
        q._append_round_csv(self.row())
        q._append_round_csv(self.row("api"))
        rows = self.read_rows()
        self.assertEqual(rows[0], list(q.ROUND_CSV_COLUMNS))
        self.assertEqual(len(rows), 3)

        self.path.write_bytes(b"")
        q._append_round_csv(self.row("tiktok"))
        rows = self.read_rows()
        self.assertEqual(len(rows), 2)
        self.assertTrue(Path(str(self.path) + ".writer.guard").exists())

    def test_torn_first_header_is_rebuilt_without_losing_new_round(self):
        header = (",".join(q.ROUND_CSV_COLUMNS) + "\r\n").encode("utf-8")
        for size in (1, 10, len(header) - 2, len(header) - 1, len(header)):
            with self.subTest(prefix_bytes=size):
                self.path.write_bytes(header[:size])
                q._append_round_csv(self.row("mastodon"))
                rows = self.read_rows()
                self.assertEqual(rows[0], list(q.ROUND_CSV_COLUMNS))
                self.assertEqual([row[1] for row in rows[1:]], ["mastodon"])

    def test_unknown_unterminated_header_is_not_overwritten(self):
        original = b"fecha,red,otra_cabecera"
        self.path.write_bytes(original)
        with self.assertRaises(ValueError):
            q._append_round_csv(self.row("mastodon"))
        self.assertEqual(self.path.read_bytes(), original)

    def test_partial_tail_from_crashed_writer_is_removed_before_append(self):
        q._append_round_csv(self.row("x"))
        with self.path.open("ab") as stream:
            stream.write(b"2026-10-09,bluesky,14:00")
            stream.flush()
            os.fsync(stream.fileno())

        q._append_round_csv(self.row("tiktok"))

        rows = self.read_rows()
        self.assertEqual(rows[0], list(q.ROUND_CSV_COLUMNS))
        self.assertEqual([row[1] for row in rows[1:]], ["x", "tiktok"])
        self.assertTrue(all(len(row) == len(q.ROUND_CSV_COLUMNS) for row in rows))

    def test_legacy_final_row_without_line_break_is_preserved(self):
        import datetime as dt
        q._append_round_csv(self.row("x"))
        original = self.path.read_bytes()
        self.assertTrue(original.endswith(b"\r\n"))
        self.path.write_bytes(original.rstrip(b"\r\n"))
        completed = q.done_today(dt.date(2026, 10, 9))
        self.assertEqual(completed, {})  # "saltada" no consume cuota.
        q._append_round_csv(self.row("bluesky"))
        self.assertEqual([row[1] for row in self.read_rows()[1:]],
                         ["x", "bluesky"])

    def test_legacy_confirmed_row_without_line_break_counts_on_restart(self):
        import datetime as dt
        complete = self.row("mastodon")
        complete[5] = "ok"
        q._append_round_csv(complete)
        self.path.write_bytes(self.path.read_bytes().rstrip(b"\r\n"))
        self.assertEqual(q.done_today(dt.date(2026, 10, 9)), {"mastodon": 1})
        self.assertEqual(q._read_round_csv_rows()[0]["estado"], "ok")
        self.assertTrue(self.path.read_bytes().endswith(b"\n"))

    def test_three_column_legacy_ledger_is_read_only_and_preserved(self):
        import datetime as dt
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(q.ROUND_CSV_LEGACY_COLUMNS)
            writer.writerow(["2026-10-09", "mastodon", "parcial"])
        before = self.path.read_bytes()
        self.assertEqual(q.done_today(dt.date(2026, 10, 9)), {"mastodon": 1})
        with self.assertRaises(ValueError):
            q._append_round_csv(self.row("x"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_three_column_legacy_without_terminator_is_not_deleted(self):
        import datetime as dt
        with self.path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(q.ROUND_CSV_LEGACY_COLUMNS)
            writer.writerow(["2026-10-09", "mastodon", "parcial"])
        self.path.write_bytes(self.path.read_bytes().rstrip(b"\r\n"))
        self.assertFalse(self.path.read_bytes().endswith(b"\n"))
        self.assertEqual(q.done_today(dt.date(2026, 10, 9)), {"mastodon": 1})
        self.assertTrue(self.path.read_bytes().endswith(b"\n"))
        self.assertEqual(len(self.read_rows()), 2)

    def test_corrupt_header_fails_closed_in_both_readers(self):
        import datetime as dt
        self.path.write_text("untrusted,date\n2026,1\n", encoding="utf-8")
        with self.assertRaises(OSError):
            q.done_today(dt.date(2026, 10, 9))
        with self.assertRaises(OSError):
            q.retry_snapshot_today(now=dt.datetime(2026, 10, 9, 14))

    def test_truncated_tail_does_not_appear_in_restart_snapshot(self):
        import datetime as dt
        success = self.row("x")
        success[5] = "ok"
        q._append_round_csv(success)
        with self.path.open("ab") as stream:
            stream.write(b"2026-10-09,bluesky,14:00:00,14:00:01,0,ok")
        self.assertEqual(q.done_today(dt.date(2026, 10, 9)), {"x": 1})
        self.assertEqual(len(self.read_rows()), 2)
        self.assertTrue(self.path.read_bytes().endswith(b"\n"))

    def test_unavailable_snapshot_never_masquerades_as_empty_ledger(self):
        from contextlib import contextmanager
        import datetime as dt

        @contextmanager
        def denied(path):
            yield False

        with (mock.patch.object(q, "_recovery_guard", side_effect=denied),
              mock.patch.object(q, "ROUND_CSV_LOCK_TIMEOUT_SECONDS", 0.0)):
            with self.assertRaises(OSError):
                q.done_today(dt.date(2026, 10, 9))
            with self.assertRaises(OSError):
                q.retry_snapshot_today(now=dt.datetime(2026, 10, 9, 14))

    def test_embedded_line_break_does_not_break_recovery_contract(self):
        invalid = self.row("x")
        invalid[6] = "{'comment': 'line one\\nline two'}".replace("\\n", "\n")
        with self.assertRaises(ValueError):
            q._append_round_csv(invalid)
        self.assertFalse(self.path.exists())

    def test_denied_interprocess_lock_preserves_previous_state(self):
        q._append_round_csv(self.row("x"))
        before = self.path.read_bytes()

        from contextlib import contextmanager

        @contextmanager
        def denied(path):
            yield False

        with (mock.patch.object(q, "_recovery_guard", side_effect=denied),
              mock.patch.object(q, "ROUND_CSV_LOCK_TIMEOUT_SECONDS", 0.0)):
            with self.assertRaises(OSError):
                q._append_round_csv(self.row("bluesky"))

        self.assertEqual(self.path.read_bytes(), before)

    def test_writer_guard_is_released_when_holder_process_is_killed(self):
        ready = Path(self.temp.name) / "writer-ready.txt"
        script = (
            "import sys,time;"
            "sys.path.insert(0,sys.argv[1]);"
            "import round_queue as q;"
            "q.LOG=sys.argv[2];"
            "ctx=q._recovery_guard(q.LOG+'.writer');"
            "held=ctx.__enter__();"
            "f=open(sys.argv[3],'w',encoding='ascii');"
            "f.write('HELD' if held else 'BLOCKED');f.close();"
            "time.sleep(60)"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", script, str(ROOT / "tools"),
             str(self.path), str(ready)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(ready.exists(), "el hijo no alcanzó el lock en 5 s")
            self.assertEqual(ready.read_text(encoding="ascii"), "HELD")
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.communicate(timeout=5)

        q._append_round_csv(self.row("mastodon"))
        rows = self.read_rows()
        self.assertEqual([row[1] for row in rows[1:]], ["mastodon"])

    def test_reader_waits_for_writer_to_finish_a_real_process(self):
        import datetime as dt
        ready = Path(self.temp.name) / "writer-ready.txt"
        success = self.row("x")
        success[5] = "ok"
        q._append_round_csv(success)
        script = (
            "import os,sys,time;"
            "sys.path.insert(0,sys.argv[1]);"
            "import round_queue as q;"
            "q.LOG=sys.argv[2];"
            "ctx=q._recovery_guard(q.LOG+'.writer');"
            "assert ctx.__enter__();"
            "f=open(q.LOG,'ab');"
            "f.write(b'2026-10-09,bluesky,14:00:00,14:00:01,0.0,ok');"
            "f.flush();os.fsync(f.fileno());"
            "open(sys.argv[3],'w',encoding='ascii').write('READY');"
            "time.sleep(0.5);"
            "f.write(b',{},0,0,0\\r\\n');f.flush();os.fsync(f.fileno());"
            "f.close();ctx.__exit__(None,None,None)"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", script, str(ROOT / "tools"),
             str(self.path), str(ready)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8",
        )
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(ready.exists(), "writer did not reach guarded append")
            start = time.monotonic()
            done = q.done_today(dt.date(2026, 10, 9))
            self.assertGreaterEqual(time.monotonic() - start, 0.2)
            self.assertEqual(done, {"x": 1, "bluesky": 1})
            out, err = proc.communicate(timeout=5)
            self.assertEqual(proc.returncode, 0, out + err)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate(timeout=5)

    def test_relaunch_snapshot_is_taken_after_chain_ownership(self):
        events = []
        fake_output = mock.Mock()
        def lock(chain):
            events.append("lock")
            return True
        def snapshot():
            events.append("snapshot")
            return {}
        def run(*args, **kwargs):
            events.append("run")
            return 0
        def release(chain):
            events.append("release")
            return True
        with (mock.patch.object(q.sys, "stdout", fake_output),
              mock.patch.object(q, "rounds_target", return_value=1),
              mock.patch.object(q, "take_chain_lock", side_effect=lock),
              mock.patch.object(q, "done_today", side_effect=snapshot),
              mock.patch.object(q, "_run_chains", side_effect=run),
              mock.patch.object(q, "release_chain_lock", side_effect=release),
              mock.patch.object(q, "control_signal", return_value=None)):
            self.assertEqual(q.main(["--only", "web"]), 0)
        self.assertEqual(events, ["lock", "snapshot", "run", "release"])

    def test_main_joins_heartbeat_before_releasing_ownership(self):
        order = []

        class FakeHeartbeat:
            def __init__(self, *args, **kwargs):
                pass

            def start(self):
                order.append("heartbeat-start")

            def join(self, timeout=None):
                self_assertion = timeout is None
                if not self_assertion:
                    raise AssertionError("No liberar el lock con heartbeat aún vivo")
                order.append("heartbeat-joined")

        def release(chain):
            order.append("lock-released")
            return True

        with (mock.patch.object(q.sys, "stdout", mock.Mock()),
              mock.patch.object(q.threading, "Thread", FakeHeartbeat),
              mock.patch.object(q, "rounds_target", return_value=1),
              mock.patch.object(q, "take_chain_lock", return_value=True),
              mock.patch.object(q, "done_today", return_value={}),
              mock.patch.object(q, "_run_chains", return_value=0),
              mock.patch.object(q, "release_chain_lock", side_effect=release),
              mock.patch.object(q, "control_signal", return_value=None)):
            self.assertEqual(q.main(["--only", "web"]), 0)

        self.assertEqual(order,
                         ["heartbeat-start", "heartbeat-joined", "lock-released"])

    def test_bad_snapshot_releases_owned_chain_without_relaunch(self):
        fake_output = mock.Mock()
        with (mock.patch.object(q.sys, "stdout", fake_output),
              mock.patch.object(q, "rounds_target", return_value=1),
              mock.patch.object(q, "take_chain_lock", return_value=True),
              mock.patch.object(q, "done_today", side_effect=OSError("bad CSV")),
              mock.patch.object(q, "release_chain_lock", return_value=True) as release,
              mock.patch.object(q, "control_signal", return_value="recargar"),
              mock.patch.object(q, "relaunch") as relaunch,
              mock.patch.object(q, "_run_chains") as run):
            with self.assertRaises(OSError):
                q.main(["--only", "web"])
            release.assert_called_once_with("web")
            relaunch.assert_not_called()
            run.assert_not_called()

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

    def test_many_independent_python_processes_write_exactly_once(self):
        script = (
            "import sys,time;"
            "sys.path.insert(0,sys.argv[1]);"
            "import round_queue as q;"
            "q.LOG=sys.argv[2];"
            "time.sleep(max(0,float(sys.argv[3])-time.time()));"
            "q._append_round_csv(['2026-10-09',sys.argv[4],'00:00:00','00:00:00',0,"
            "'saltada','{}',1,0,0])"
        )
        start = time.time() + 2.5
        networks = ["x", "threads", "bluesky", "mastodon", "tiktok", "pinterest"]
        procs = []
        try:
            for network in networks:
                procs.append(subprocess.Popen(
                    [sys.executable, "-c", script, str(ROOT / "tools"),
                     str(self.path), str(start), network],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8",
                ))
            for proc in procs:
                out, err = proc.communicate(timeout=25)
                self.assertEqual(proc.returncode, 0, out + err)
        finally:
            for proc in procs:
                if proc.poll() is None:
                    proc.kill()
                    proc.communicate(timeout=5)

        rows = self.read_rows()
        self.assertEqual(rows[0], list(q.ROUND_CSV_COLUMNS))
        self.assertEqual(len(rows), 1 + len(networks))
        self.assertEqual(sum(row and row[0] == "fecha" for row in rows), 1)
        self.assertEqual(sorted(row[1] for row in rows[1:]), sorted(networks))
        self.assertTrue(all(len(row) == len(q.ROUND_CSV_COLUMNS) for row in rows))


if __name__ == "__main__":
    unittest.main()
