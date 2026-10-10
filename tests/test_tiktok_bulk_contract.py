"""Clasificación de resultado bulk en la ronda; todas las rutas son offline."""
import datetime
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import mechanical_round as mr


class BulkStatusContractTests(unittest.TestCase):
    def _run(self, marker, exit_code):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "SISTEMA_DIARIO_TIKTOK").mkdir()
            cfg = {
                "dir": "SISTEMA_DIARIO_TIKTOK",
                "pre": [[sys.executable, "tools/tiktok_bulk_follow.py"],
                        [sys.executable, "tools/tiktok_growth_flow.py", "prepare"]],
                "decisions": None, "decisions_default": None, "write_decisions": None,
                "build": None, "plan": "plan.json",
                "execute": [sys.executable, "tools/tiktok_growth_flow.py", "run"],
                "post": [], "shape": False,
            }
            seen = []
            def runner(cmd):
                if "tiktok_" in cmd[1]:
                    seen.append(cmd[1])
                if "bulk_follow" in cmd[1]:
                    return exit_code, marker
                return 0, 'no se ejecutaron escrituras'
            with mock.patch.object(mr, "ROOT", str(root)), mock.patch.dict(mr.PIPELINES, {"tiktok": cfg}):
                res = mr._run("tiktok", runner=runner, out=lambda _: None,
                              today=datetime.date(2026, 10, 9), shape=False)
            return res, seen

    def test_busy_both_exit_zero_and_three_never_runs_next_stage(self):
        for code in (0, 3):
            with self.subTest(code=code):
                res, seen = self._run("TIKTOK_STEP_STATUS=busy", code)
                self.assertTrue(res["skipped"])
                self.assertEqual(len(seen), 1)

    def test_safety_restriction_is_critical_local_stops_are_not(self):
        for status, code in (("restricted", 4), ("local_error", 2), ("uncertain", 5)):
            with self.subTest(status=status):
                res, seen = self._run("TIKTOK_STEP_STATUS=" + status, code)
                self.assertFalse(res["ok"])
                self.assertEqual(res["failure_kind"],
                                 "execute" if status == "restricted" else "plan")
                if status == "restricted":
                    self.assertEqual(res["signal"], "auth")
                self.assertEqual(len(seen), 1)

    def test_missing_duplicate_and_bad_status_fail_closed(self):
        for bad in ("", "TIKTOK_STEP_STATUS=completed\nTIKTOK_STEP_STATUS=busy",
                    "TIKTOK_STEP_STATUS=unknown"):
            with self.subTest(bad=bad):
                res, seen = self._run(bad, 0)
                self.assertFalse(res["ok"])
                self.assertEqual(len(seen), 1)

    def test_completed_wrong_exit_fails_closed(self):
        res, seen = self._run("TIKTOK_STEP_STATUS=completed", 2)
        self.assertFalse(res["ok"])
        self.assertEqual(len(seen), 1)

    def test_completed_continues_to_prepare_then_stops_if_no_plan(self):
        res, seen = self._run("TIKTOK_STEP_STATUS=completed", 0)
        self.assertEqual(len(seen), 2)
        self.assertFalse(res["ok"])
