"""PR38: deshabilitar ranking por conversiones TikTok no certificadas (sin móvil)."""
import datetime
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import tiktok_bulk_follow as bulk
import tiktok_reciprocity_audit as audit


class SourcePrioritySafetyTests(unittest.TestCase):
    def test_legacy_yield_does_not_override_configured_seed_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = pathlib.Path(tmp) / "state.json"
            state.write_text('{"shortlist":[]}', encoding="utf-8")
            done = {"primera": {"yield": 0.01},
                    "segunda": {"yield": 0.99},
                    "tercera": {"yield": "NaN"}}
            with (mock.patch.object(bulk, "STATE_PATH", str(state)),
                  mock.patch.object(bulk, "DEFAULT_SEEDS", [])):
                chosen = bulk.pick_seeds({"bulk_seeds": ["primera", "segunda", "tercera"]},
                                         done, limit=3)
            self.assertEqual(chosen, ["primera", "segunda", "tercera"])
            self.assertEqual(json.loads(state.read_text(encoding="utf-8")), {"shortlist": []})

    def test_existing_three_day_rotation_remains_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = pathlib.Path(tmp) / "state.json"
            state.write_text("{}", encoding="utf-8")
            today = datetime.date.today().isoformat()
            done = {"primera": {"last": today, "yield": 0.99}}
            with (mock.patch.object(bulk, "STATE_PATH", str(state)),
                  mock.patch.object(bulk, "DEFAULT_SEEDS", [])):
                self.assertEqual(
                    bulk.pick_seeds({"bulk_seeds": ["primera", "segunda"]}, done, 3),
                    ["segunda"],
                )

    def test_audit_keeps_legacy_data_but_never_generates_new_yield(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "seeds.json"
            path.write_text('{"primera":{"note":"keep"},"otra":{"yield":0.8}}', encoding="utf-8")
            with mock.patch.object(audit.bulk, "SEEDS_PATH", str(path)):
                self.assertTrue(audit.update_seeds({
                    "followers:@primera": {"followed": 3, "back": 2, "rate": 0.667}
                }))
            new = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(new["primera"]["followed"], 3)
            self.assertEqual(new["primera"]["note"], "keep")
            self.assertNotIn("yield", new["primera"])
            self.assertEqual(new["otra"], {"yield": 0.8})


if __name__ == "__main__":
    unittest.main()
