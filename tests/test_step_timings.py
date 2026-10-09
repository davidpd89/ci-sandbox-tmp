"""Cronometría offline de los pasos: nunca usa teléfono, Edge ni APIs."""
import datetime
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import mechanical_round as mr


class TimedStepsTests(unittest.TestCase):
    def test_realistic_tiktok_phases_are_classified(self):
        cases = [
            ("tiktok_bulk_follow.py --max-follows", ["python", "tools/tiktok_bulk_follow.py"], "bulk"),
            ("tiktok_growth_flow.py prepare", ["python", "tools/tiktok_growth_flow.py", "prepare"], "scan"),
            ("tiktok_comment_writer.py", ["python", "tools/tiktok_comment_writer.py"], "plan"),
            ("build", ["python", "tools/tiktok_growth_flow.py", "build"], "plan"),
            ("execute", ["python", "tools/tiktok_growth_flow.py", "run"], "execute"),
            ("post tiktok_reciprocity_audit.py", ["python", "tools/tiktok_reciprocity_audit.py"], "post"),
        ]
        for label, cmd, kind in cases:
            with self.subTest(label=label):
                phase, script = mr._phase_for_timing(label, cmd)
                self.assertEqual(phase, kind)
                self.assertTrue(script.endswith(".py"))

    def test_elapsed_monotonic_and_exit_code_preserved(self):
        with mock.patch.object(mr.time, "monotonic", side_effect=[100.0, 153.6]):
            code, text, started, ended, elapsed = mr._time_runner(
                lambda _: (0, "sin acciones confirmadas"), ["python", "script.py"]
            )
        self.assertEqual((code, text), (0, "sin acciones confirmadas"))
        self.assertAlmostEqual(elapsed, 53.6)
        datetime.datetime.fromisoformat(started)
        datetime.datetime.fromisoformat(ended)

    def test_runner_error_is_sanitized_and_duration_recorded(self):
        def fail(_):
            raise OSError("C:/private/secret/token.txt")

        with mock.patch.object(mr.time, "monotonic", side_effect=[1.0, 2.0]):
            code, text, _, _, elapsed = mr._time_runner(fail, ["python", "script.py"])
        self.assertEqual(code, 1)
        self.assertEqual(text, "FALLO_LOCAL_RUNNER: OSError")
        self.assertEqual(elapsed, 1)
        self.assertNotIn("secret", text)

    def test_mock_round_writes_step_timing_to_existing_mech_log(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            folder = root / "SISTEMA_DIARIO_TIKTOK"
            folder.mkdir()
            cfg = {
                "dir": "SISTEMA_DIARIO_TIKTOK",
                "pre": [[sys.executable, "tools/tiktok_bulk_follow.py", "--max-minutes", "50"],
                        [sys.executable, "tools/tiktok_growth_flow.py", "prepare"]],
                "decisions": None, "decisions_default": None,
                "write_decisions": None, "build": None,
                "plan": "tiktok_plan.json",
                "execute": [sys.executable, "tools/tiktok_growth_flow.py", "run"],
                "post": [], "shape": False,
            }
            messages = []
            with mock.patch.object(mr, "ROOT", str(root)), \
                 mock.patch.dict(mr.PIPELINES, {"tiktok": cfg}):
                result = mr._run(
                    "tiktok", dry=True, runner=lambda cmd: (1, "FALLO_LOCAL_RUNNER: simulado"),
                    out=messages.append, shape=False,
                    today=datetime.date(2026, 10, 9),
                )
            self.assertFalse(result.get("ok", False))
            logs = list((folder / "cache").glob("mech_*.log"))
            self.assertEqual(len(logs), 1)
            body = logs[0].read_text(encoding="utf-8")
            self.assertIn("TIEMPO_ETAPA", body)
            self.assertIn("phase=scan", body)  # bulk es omitido por --dry
            self.assertTrue(any("TIEMPO_ETAPA" in msg for msg in messages))


if __name__ == "__main__":
    unittest.main()
