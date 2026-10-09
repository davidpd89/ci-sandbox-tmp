"""09/10: movil ocupado con exit 0 (tiktok_bulk_follow) omite la ronda en vez de seguir con los pasos siguientes."""
import datetime
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
