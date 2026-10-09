"""Regresiones R6.2 (todas offline; nunca se llama al Programador real)."""
import contextlib
import io
import pathlib
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import schedule_round_canaries as schedule


class CanaryScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "tools").mkdir()
        (self.root / "tools" / "round_canaries.py").write_text("pass\n", encoding="utf-8")
        (self.root / "tools" / schedule.RUNNER).write_text("pass\n", encoding="utf-8")
        self.python = self.root / "Python 311" / "python.exe"
        self.python.parent.mkdir()
        self.python.write_text("", encoding="utf-8")
        self.python.with_name("pythonw.exe").write_text("", encoding="utf-8")

    def completed(self, code=0, out="", err=""):
        return SimpleNamespace(returncode=code, stdout=out, stderr=err)

    def test_intervals_restricted_and_current_script_uses_pythonw(self):
        for interval in (30, 60):
            cmd = schedule.create_command(self.root, python_exe=self.python, interval=interval)
            self.assertEqual(cmd[:4], ["schtasks", "/Create", "/SC", "MINUTE"])
            self.assertEqual(cmd[cmd.index("/MO")+1], str(interval))
            self.assertNotIn("/F", cmd)
            self.assertEqual(cmd[cmd.index("/RL")+1], "LIMITED")
            self.assertIn("/IT", cmd)
            self.assertNotIn("/RU", cmd)
            self.assertNotIn("/RP", cmd)
            self.assertIn(schedule.RUNNER, cmd[cmd.index("/TR")+1])
            self.assertIn('"', cmd[cmd.index("/TR")+1])
            self.assertIn("pythonw.exe", cmd[cmd.index("/TR")+1])
        for interval in (0, 5, 1439):
            with self.assertRaises(ValueError):
                schedule.create_command(self.root, python_exe=self.python, interval=interval)

    def test_task_name_is_captured_by_existing_stop_start_protocol(self):
        self.assertTrue(schedule.TASK_NAME.startswith("RRSS_"))
        self.assertEqual(schedule.TASK_NAME, "RRSS_Canarios_Rondas")

    def test_missing_dependencies_never_runs_a_command(self):
        runner = mock.Mock()
        (self.root / "tools" / schedule.RUNNER).unlink()
        with self.assertRaises(FileNotFoundError):
            schedule.install(self.root, python_exe=self.python, platform="win32", run=runner)
        runner.assert_not_called()
        (self.root / "tools" / schedule.RUNNER).write_text("pass\n")
        (self.root / "tools" / "round_canaries.py").unlink()
        with self.assertRaises(FileNotFoundError):
            schedule.install(self.root, python_exe=self.python, platform="win32", run=runner)
        runner.assert_not_called()

    def test_stopped_rondas_rejects_install_without_windows_calls(self):
        stop = self.root / "00_OPERATIVO" / "cola_parar.flag"
        stop.parent.mkdir()
        stop.write_text("parada solicitada", encoding="utf-8")
        calls = mock.Mock()
        with self.assertRaisesRegex(RuntimeError, "detenidas"):
            schedule.install(self.root, python_exe=self.python, platform="win32", run=calls)
        calls.assert_not_called()

    def test_stop_requested_during_preflight_rejects_creation(self):
        stop = self.root / "00_OPERATIVO" / "cola_parar.flag"
        def side_effect(*args, **kwargs):
            if args[0][0] == "powershell.exe":
                stop.parent.mkdir(exist_ok=True)
                stop.write_text("parada", encoding="utf-8")
                return self.completed(out="ABSENT")
            return self.completed()
        calls = mock.Mock(side_effect=side_effect)
        with self.assertRaisesRegex(RuntimeError, "detenidas"):
            schedule.install(self.root, python_exe=self.python, platform="win32", run=calls)
        self.assertEqual(calls.call_count, 2)
        self.assertNotIn("/Create", str(calls.call_args_list))

    @unittest.skipUnless(sys.platform == "win32", "lectura de Task Scheduler solo en CI Windows")
    def test_real_powershell_query_is_read_only_and_parses(self):
        probe = subprocess.run(schedule.query_command(), capture_output=True,
                               text=True, timeout=35, check=False)
        self.assertEqual(probe.returncode, 0, probe.stderr)
        self.assertIn(probe.stdout.strip(), {"EXISTS", "ABSENT"})

    def test_unreadable_stop_signal_fails_closed(self):
        with mock.patch.object(pathlib.Path, "stat",
                               side_effect=PermissionError("denegado")):
            with self.assertRaisesRegex(RuntimeError, "señal de parada"):
                schedule._ensure_rondas_active(self.root)

    @unittest.skipUnless(sys.platform == "win32", "preflight real solo en CI Windows")
    def test_real_windows_python_pair_and_import_preflight(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        console, gui = schedule.python_pair(sys.executable)
        self.assertTrue(console.is_file())
        self.assertTrue(gui.is_file())
        cmd = schedule.preflight_command(root, console)
        check = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=20, check=False)
        self.assertEqual(check.returncode, 0, check.stderr)

    def test_linux_install_never_runs_commands(self):
        runner = mock.Mock()
        with self.assertRaises(RuntimeError):
            schedule.install(self.root, python_exe=self.python, platform="linux", run=runner)
        runner.assert_not_called()

    def test_pythonw_missing_never_runs_commands(self):
        self.python.with_name("pythonw.exe").unlink()
        runner = mock.Mock()
        with self.assertRaises(FileNotFoundError):
            schedule.install(self.root, python_exe=self.python, platform="win32", run=runner)
        runner.assert_not_called()

    def test_unknown_python_name_does_not_create(self):
        with self.assertRaises(ValueError):
            schedule.create_command(self.root, python_exe="C:\\Python311\\py.exe")

    def test_import_failure_aborts_before_scheduler_query(self):
        runner = mock.Mock(return_value=self.completed(1, err="ImportError"))
        with self.assertRaisesRegex(RuntimeError, "json/csv"):
            schedule.install(self.root, python_exe=self.python, platform="win32", run=runner)
        self.assertEqual(runner.call_count, 1)
        self.assertEqual(runner.call_args.args[0][1:3], ["-I", "-c"])

    def test_existing_task_cannot_be_replaced(self):
        runner = mock.Mock(side_effect=[self.completed(), self.completed(out="EXISTS")])
        with self.assertRaisesRegex(RuntimeError, "ya existe"):
            schedule.install(self.root, python_exe=self.python, platform="win32", run=runner)
        self.assertEqual(runner.call_count, 2)

    def test_localized_error_never_authorizes_creation(self):
        for outcome in (self.completed(2, err="Acceso denegado"),
                        self.completed(1, err="Datei nicht gefunden"),
                        self.completed(out=""), self.completed(out="ABSENT\nEXISTS")):
            runner = mock.Mock(side_effect=[self.completed(), outcome])
            with self.assertRaisesRegex(RuntimeError, "ambigua"):
                schedule.install(self.root, python_exe=self.python, platform="win32", run=runner)
            self.assertEqual(runner.call_count, 2)

    def test_query_uses_locale_independent_structured_status(self):
        cmd = schedule.query_command()
        self.assertEqual(cmd[:4], ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive"])
        self.assertIn("Get-ScheduledTask", cmd[-1])
        self.assertIn("-ErrorAction Stop", cmd[-1])
        self.assertIn("TASK_QUERY_FAILED", cmd[-1])
        self.assertNotIn("SilentlyContinue", cmd[-1])

    def test_valid_install_queries_then_creates_with_negative_stdin(self):
        runner = mock.Mock(side_effect=[self.completed(), self.completed(out="ABSENT"), self.completed()])
        self.assertEqual(schedule.install(self.root, python_exe=self.python,
                                          platform="win32", run=runner), schedule.TASK_NAME)
        self.assertEqual(runner.call_count, 3)
        args, kwargs = runner.call_args
        self.assertEqual(args[0][:2], ["schtasks", "/Create"])
        self.assertEqual(kwargs["input"], "N\n")
        self.assertNotIn("/F", args[0])
        self.assertNotIn("/RU", args[0])
        self.assertNotIn("/RP", args[0])

    def test_failed_create_is_not_success(self):
        runner = mock.Mock(side_effect=[self.completed(), self.completed(out="ABSENT"),
                                        self.completed(1, err="Access denied")])
        with self.assertRaisesRegex(RuntimeError, "no confirmó"):
            schedule.install(self.root, python_exe=self.python, platform="win32", run=runner)

    def test_long_path_rejected_before_mutation(self):
        with self.assertRaisesRegex(ValueError, "262"):
            schedule.create_command(self.root / ("x"*230), python_exe=self.python)

    def test_dry_run_prints_only_even_without_canary(self):
        with mock.patch.object(schedule, "install") as fn:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                schedule.main(["--root", str(self.root), "--interval", "30"])
        fn.assert_not_called()
        self.assertIn("ENSAYO", out.getvalue())
        self.assertIn("/IT", out.getvalue())

    def test_invalid_cli_interval_does_not_install(self):
        with mock.patch.object(schedule, "install") as fn:
            with self.assertRaises(SystemExit):
                schedule.main(["--interval", "5", "--install"])
        fn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
