import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import re
import unittest

import growth_core as gc


class GrowthCoreTests(unittest.TestCase):
    def test_tiktok_pipeline_has_mechanical_round_contract(self):
        spec = gc.pipeline_for("tiktok", "py")
        for key in ("dir", "plan", "pre", "build", "execute", "post", "min_plan", "runs_per_day"):
            self.assertIn(key, spec)
        self.assertTrue(gc.uses_phone(spec))
        self.assertEqual(spec["execute"][:3], ["py", "tools/tiktok_growth_flow.py", "run"])
        self.assertIn("--apply", spec["execute"])

    def test_unknown_network_rejected(self):
        with self.assertRaises(KeyError):
            gc.pipeline_for("bluesky")

    def test_executor_line_matches_round_summary_regex(self):
        confirmed = re.compile(r"^confirmado\s+(\w+)", re.MULTILINE)
        self.assertEqual(confirmed.findall("confirmado      follow   @ana\n"), ["follow"])


if __name__ == "__main__":
    unittest.main()
