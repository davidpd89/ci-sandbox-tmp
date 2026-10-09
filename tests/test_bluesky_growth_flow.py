"""Regresiones offline del orquestador de crecimiento Bluesky."""
import json
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import bluesky_growth_flow as flow


class BlueskyGrowthFlowTests(unittest.TestCase):
    def result(self, *, fresh=24, target=24, missing=None):
        return {
            "run_id": "test-run",
            "budget": {"used": 170, "remaining": 110},
            "coverage": {"missing": list(missing or [])},
            "totals": {
                "profiles_seen": 500,
                "shortlist": 36,
                "community": 12,
                "acquisition": 24,
                "fresh_acquisition": fresh,
            },
            "readiness": {
                "acquisition_target": target,
                "fresh_target_met": fresh >= target,
                "opportunities": {"follow": 12, "reply": 8, "like": 20},
            },
            "auto_plan": [],
            "shortlist": [],
            "source_metrics": {
                "second_wave:d1:at://a/post/1": {
                    "fetched": 1, "accepted": 5, "new_handles": 5
                },
                "second_wave:d2:at://b/post/2": {
                    "fetched": 1, "accepted": 3, "new_handles": 3
                },
                "second_wave_author:a.bsky.social": {
                    "fetched": 1, "accepted": 5, "new_handles": 5
                },
            },
            "issues": [],
        }

    def test_report_makes_growth_readiness_explicit(self):
        report = flow._report(self.result())
        self.assertTrue(report["coverage_complete"])
        self.assertTrue(report["fresh_target_met"])
        self.assertEqual(report["fresh_acquisition"], 24)
        self.assertEqual(report["opportunities"]["follow"], 12)
        self.assertEqual(report["frontier"]["depth_reached"], 2)
        self.assertEqual(report["frontier"]["branches_opened"], 2)
        self.assertEqual(report["frontier"]["new_handles"], 8)
        self.assertEqual(report["frontier"]["new_handles_per_branch"], 4.0)

    def test_prepare_strict_returns_nonzero_for_stale_round(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = str(pathlib.Path(tmp) / "state.json")
            ai = str(pathlib.Path(tmp) / "ai.json")
            report = str(pathlib.Path(tmp) / "report.json")
            args = SimpleNamespace(
                deep=0.0,
                state=state,
                ai=ai,
                report=report,
                config="config.json",
                no_metrics=True,
                strict=True,
            )
            result = self.result(fresh=7)
            fake_growth = SimpleNamespace(
                run=lambda **kwargs: result,
                compact_ai_view=lambda payload: {"ok": True},
            )
            with patch.object(flow, "_growth_module", return_value=fake_growth):
                code = flow.prepare(args)

            self.assertEqual(code, 2)
            self.assertTrue(pathlib.Path(state).exists())
            self.assertTrue(pathlib.Path(ai).exists())
            payload = json.loads(pathlib.Path(report).read_text(encoding="utf-8"))
            self.assertFalse(payload["fresh_target_met"])

    def test_deep_collectors_are_serialized_on_shared_sqlite(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            state = pathlib.Path(tmp) / "state.json"
            state.write_text("{}", encoding="utf-8")

            def fake_run(command, **kwargs):
                calls.append(pathlib.Path(command[1]).name)
                return SimpleNamespace(returncode=0, stdout="{}", stderr="")

            with patch.object(flow.subprocess, "run", side_effect=fake_run):
                rows = flow._run_deep_collectors(20, str(state))

        self.assertEqual(calls, [
            "bluesky_jetstream_collect.py",
            "bluesky_taste_collect.py",
        ])
        self.assertEqual(len(rows), 2)

    def test_build_uses_full_state_not_compact_ai_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = pathlib.Path(tmp) / "state.json"
            decisions_path = pathlib.Path(tmp) / "decisions.json"
            plan_path = pathlib.Path(tmp) / "plan.json"
            state_path.write_text(json.dumps({
                "shortlist": [{
                    "id": "G001",
                    "handle": "lector.bsky.social",
                    "sources": ["post_search"],
                    "actions": ["follow"],
                    "posts": [],
                }],
                "auto_plan": [],
            }), encoding="utf-8")
            decisions_path.write_text(json.dumps({
                "actions": [{"candidate": "G001", "kind": "follow"}]
            }), encoding="utf-8")
            args = SimpleNamespace(
                state=str(state_path),
                decisions=str(decisions_path),
                plan=str(plan_path),
            )

            self.assertEqual(flow.build(args), 0)
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(plan[0]["handle"], "lector.bsky.social")
            self.assertEqual(plan[0]["kind"], "follow")


if __name__ == "__main__":
    unittest.main()
