"""09/10: movil ocupado con exit 0 (tiktok_bulk_follow) omite la ronda en vez de seguir con los pasos siguientes."""
import datetime
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import mechanical_round as mr


class BusyPhoneExitZeroTests(unittest.TestCase):
    def test_busy_message_with_exit_zero_skips_round(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "SISTEMA_DIARIO_TIKTOK").mkdir()
            cfg = {
                "dir": "SISTEMA_DIARIO_TIKTOK",
                "pre": [[sys.executable, "tools/tiktok_bulk_follow.py"], [sys.executable, "tools/tiktok_growth_flow.py", "prepare"]],
                "decisions": None, "decisions_default": None, "write_decisions": None, "build": None,
                "plan": "tiktok_plan.json", "execute": [sys.executable, "tools/tiktok_growth_flow.py", "run"],
                "post": [], "shape": False,
            }
            calls = []

            def runner(cmd):
                calls.append(cmd[1])
                return 0, "MobileSessionBusy: el movil lo usa otra sesion; se omite el seguimiento masivo"

            with mock.patch.object(mr, "ROOT", str(root)), mock.patch.dict(mr.PIPELINES, {"tiktok": cfg}):
                result = mr._run("tiktok", dry=False, runner=runner, out=lambda m: None, shape=False,
                                 today=datetime.date(2026, 10, 9))
        self.assertTrue(result.get("skipped"), result)
        self.assertNotIn("tools/tiktok_growth_flow.py", calls)


if __name__ == "__main__":
    unittest.main()


class FollowPauseKeepsRoundAliveTests(unittest.TestCase):
    """09/10: con pausa solo de follows, el bulk se omite y la ronda sigue (antes `restricted` la cortaba entera)."""

    def run_round(self, pause_only):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "SISTEMA_DIARIO_TIKTOK").mkdir()
            cfg = {
                "dir": "SISTEMA_DIARIO_TIKTOK",
                "pre": [[sys.executable, "tools/tiktok_bulk_follow.py"], [sys.executable, "tools/tiktok_growth_flow.py", "prepare"]],
                "decisions": None, "decisions_default": None, "write_decisions": None, "build": None,
                "plan": "tiktok_plan.json", "execute": [sys.executable, "tools/tiktok_growth_flow.py", "run"],
                "post": [], "shape": False,
            }
            calls, output = [], []

            def runner(cmd):
                calls.append(os.path.basename(cmd[1]))
                if cmd[1].endswith("tiktok_bulk_follow.py"):
                    return 4, "[bulk] restringido\nTIKTOK_STEP_STATUS=restricted"
                return 0, "TIKTOK_STEP_STATUS=completed"

            with mock.patch.object(mr, "ROOT", str(root)), mock.patch.dict(mr.PIPELINES, {"tiktok": cfg}), \
                 mock.patch.object(mr, "_tiktok_follow_pause_only", return_value=pause_only):
                result = mr._run("tiktok", dry=False, runner=runner, out=output.append, shape=False, today=datetime.date(2026, 10, 9))
            return result, calls, output

    def test_bulk_is_skipped_and_round_continues(self):
        result, calls, output = self.run_round(True)
        self.assertNotIn("tiktok_bulk_follow.py", calls)
        self.assertIn("tiktok_growth_flow.py", calls)
        self.assertTrue(any("pausa de follows activa" in line for line in output))

    def test_global_restriction_still_stops_the_round(self):
        result, calls, output = self.run_round(False)
        self.assertIn("tiktok_bulk_follow.py", calls)
        self.assertNotIn("tiktok_growth_flow.py", calls)
        self.assertFalse(result.get("ok", False))


if __name__ == "__main__":
    unittest.main()
