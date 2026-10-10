"""Regresiones del contrato de auditoría de configuración/capacidades (#43).

Únicamente archivos temporales sintéticos: no se importan scanners activos.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import config_capability_audit as audit


def config(*, shortlist=None):
    return {
        "version": 1,
        "budgets": {"max_read_requests": 12, "max_candidates": 42},
        "coverage": {"required_surfaces": ["post_search"], "optional_surfaces": ["actor_search"]},
        "shortlist": shortlist or {},
    }


class ConfigCapabilityAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "tools").mkdir()

    def write_config(self, network, data):
        path = self.root / audit.CONFIG_PATHS[network]
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def report(self, pipelines=None, cleanup_adapters=None, harvesters=None):
        return audit.audit(self.root, pipelines=pipelines if pipelines is not None else {},
                           cleanup_adapters=cleanup_adapters if cleanup_adapters is not None else {},
                           harvesters=harvesters if harvesters is not None else {})

    def test_nine_networks_and_no_live_actions(self):
        result = self.report()
        self.assertEqual(len(result["capabilities"]), 9)
        self.assertIn("instagram", result["capabilities"])
        self.assertIsNone(result["pipelines"]["instagram"]["primary_lane"])
        self.assertEqual(result["configurations"]["instagram"]["status"], "not_declared")
        self.assertEqual(result["configurations"]["tiktok"]["status"], "missing_in_checkout")
        self.assertEqual(result["errors"], 0)

    def test_lane_and_explicit_defaults_do_not_invent_dynamic_rounds(self):
        report = self.report(pipelines={
            "instagram": {"browser": True, "pre": [["python", "tools/instagram_build_plan.py"]]},
            "tiktok": {"phone": True, "shape": False, "runs_per_day": 6},
            "bluesky": {"pre": [["python", "tools/api_comment_writer.py", "bluesky"]]},
        })
        self.assertEqual(report["pipelines"]["instagram"]["primary_lane"], "WEB")
        self.assertEqual(report["pipelines"]["instagram"]["runs_source"], "runtime_dynamic_or_default")
        self.assertIsNone(report["pipelines"]["instagram"]["runs_per_day"])
        self.assertEqual(report["pipelines"]["tiktok"]["primary_lane"], "MOBILE")
        self.assertFalse(report["pipelines"]["tiktok"]["shape"])
        self.assertEqual(report["pipelines"]["tiktok"]["runs_per_day"], 6)
        self.assertEqual(report["pipelines"]["bluesky"]["primary_lane"], "API")
        self.assertEqual(report["wiring"]["bluesky"]["gpt_writer"], "wired")

    def test_available_not_wired_is_different_from_missing(self):
        result = self.report(pipelines={"instagram": {"post": []}},
                             cleanup_adapters={"instagram": object()},
                             harvesters={"instagram": object()})
        self.assertEqual(result["wiring"]["instagram"]["unfollow"], "available_not_wired")
        self.assertEqual(result["wiring"]["instagram"]["loyalty"], "available_not_wired")
        self.assertEqual(result["wiring"]["x"]["unfollow"], "missing")
        self.assertEqual(result["wiring"]["instagram"]["gpt_writer"], "not_observed_in_pre")

    def test_common_policy_alias_uses_effective_value_and_reports_override(self):
        self.write_config("bluesky", config(shortlist={"like_max_age_days": 33}))
        self.write_config("mastodon", config(shortlist={"favourite_max_age_days": 45}))
        result = self.report()
        b = result["configurations"]["bluesky"]["effective_common_policy"]
        m = result["configurations"]["mastodon"]["effective_common_policy"]
        self.assertEqual(b["community_age"], {"value": 33, "source": "shortlist.like_max_age_days"})
        self.assertEqual(m["community_age"], {"value": 45, "source": "shortlist.favourite_max_age_days"})
        self.assertEqual(b["acquisition_age"]["value"], 21)
        self.assertEqual(b["acquisition_age"]["source"], "growth_policy.default")
        self.assertTrue(any(x["kind"] == "policy_divergence" for x in result["findings"]))
        self.assertNotIn("effective_common_policy", result["configurations"]["tiktok"])
        self.assertEqual(result["errors"], 0)

    def test_json_duplicate_key_nested_is_invalid_and_does_not_echo_content(self):
        path = self.write_config("bluesky", config())
        path.write_text('{"version":1,"budgets":{"max_candidates":12,"max_candidates":99},'
                        '"payload":"NO_LOG_THIS_DATA"}', encoding="utf-8")
        result = self.report()
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["configurations"]["bluesky"]["status"], "invalid")
        self.assertNotIn("NO_LOG_THIS_DATA", json.dumps(result))

    def test_nonstandard_nan_and_infinity_rejected(self):
        path = self.write_config("bluesky", config())
        for number in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(number=number):
                path.write_text('{"version":1,"budgets":{"max_candidates":' + number + '}}',
                                encoding="utf-8")
                self.assertEqual(self.report()["errors"], 1)

    def test_bool_is_not_number_and_negative_is_invalid(self):
        cfg = config()
        cfg["budgets"]["max_candidates"] = True
        cfg["budgets"]["max_read_requests"] = -1
        self.write_config("bluesky", cfg)
        self.assertGreaterEqual(self.report()["errors"], 2)

    def test_conflicting_historical_names_do_not_silently_choose_first(self):
        cfg = config(shortlist={"like_max_age_days": 30, "favourite_max_age_days": 45})
        self.write_config("mastodon", cfg)
        result = self.report()
        self.assertEqual(result["errors"], 1)
        self.assertNotIn("effective_common_policy", result["configurations"]["mastodon"])

    def test_surfaces_bool_required_and_overlap_detected(self):
        cfg = config()
        cfg["coverage"]["optional_surfaces"].append("post_search")
        cfg["surfaces"] = {"search": 0, "for_you": True}
        self.write_config("tiktok", cfg)
        self.assertEqual(self.report()["errors"], 2)
        cfg["coverage"]["optional_surfaces"].pop()
        cfg["surfaces"]["search"] = False
        self.write_config("tiktok", cfg)
        entry = self.report()["configurations"]["tiktok"]
        self.assertEqual(entry["disabled_surfaces"], ["search"])
        self.assertEqual(entry["status"], "valid")

    def test_orphan_candidates_are_not_claimed_as_proven(self):
        cfg = config()
        cfg["budgets"]["an_experimental_key"] = 1
        self.write_config("bluesky", cfg)
        path = self.root / audit.SCANNERS["bluesky"]
        path.write_text('BUILTIN = "max_read_requests"\n', encoding="utf-8")
        result = self.report()
        candidates = result["configurations"]["bluesky"]["unverified_literal_references"]
        self.assertIn("budgets.an_experimental_key", candidates)
        self.assertNotIn("budgets.max_read_requests", candidates)
        self.assertIn("candidatas", str(result["findings"]))

    def test_only_names_of_environment_not_actual_values(self):
        (self.root / "tools" / "dummy.py").write_text(
            "import os\n"
            "X = os.getenv('FAKE_TOKEN', 'private-test-value')\n"
            "Y = os.environ.get('PROFILE_MODE', 'unrelated')\n"
            "Z = os.getenv('PROFILE_MODE', 'other')\n",
            encoding="utf-8")
        names = self.report()["environment_names"]
        self.assertEqual(names["FAKE_TOKEN"], ["dummy.py"])
        self.assertEqual(names["PROFILE_MODE"], ["dummy.py"])
        self.assertNotIn("private-test-value", json.dumps(names))
        self.assertNotIn("unrelated", json.dumps(names))

    def test_json_duplicate_across_root_never_overwrites(self):
        path = self.write_config("mastodon", config())
        path.write_text('{"version":1,"version":2,"budgets":{"max_candidates":8}}', encoding="utf-8")
        self.assertEqual(self.report()["configurations"]["mastodon"]["status"], "invalid")

    def test_lists_validate_types_without_unhandled_type_errors(self):
        cfg = config()
        cfg["coverage"]["required_surfaces"] = [[], "x"]
        cfg["coverage"]["optional_surfaces"] = ["x"]
        self.write_config("bluesky", cfg)
        report = self.report()
        self.assertEqual(report["errors"], 1)

    def test_invalid_config_does_not_override_missing_other_networks(self):
        self.write_config("mastodon", {"version": "1", "budgets": {}})
        result = self.report()
        self.assertGreater(result["errors"], 0)
        self.assertEqual(result["configurations"]["tiktok"]["status"], "missing_in_checkout")
        self.assertEqual(result["configurations"]["instagram"]["status"], "not_declared")


if __name__ == "__main__":
    unittest.main()
