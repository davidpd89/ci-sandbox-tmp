"""Pruebas offline de PR #76: controles y permisos nunca se infieren."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import cross_network_learning as c

NOW = dt.date(2026, 10, 9)


def positive(**overrides):
    row = {"feature": "hashtag_search", "origin": "bluesky",
           "metric": "new_follower_day14", "design": "randomized",
           "outcome_link": "audited", "human_reviewed": True,
           "mature_days": 14, "observed_on": "2026-10-08",
           "cohort_end": "2026-09-24",
           "baseline_nonfollowers_verified": True, "assignment_units_unique": True,
           "day14_snapshot_complete": True,
           "treatment": {"n": 100, "successes": 70},
           "control": {"n": 100, "successes": 10},
           "targets": {"mastodon": {"capability": "verified", "permission": "verified",
                                     "implemented": False, "checked_on": "2026-10-08"}}}
    row.update(overrides)
    return row


def run(*rows, history=None, date=NOW, verified=None):
    return c.review({"schema": 1, "observations": list(rows),
                     "history": history or []}, today=date,
                    trusted_verifications=verified)


class CrossNetworkTests(unittest.TestCase):
    def test_only_out_of_band_verified_evidence_reaches_manual_proposal(self):
        row = positive()
        initial = run(row)
        self.assertEqual(initial["proposals"][0]["state"],
                         "verificacion_externa_pendiente")
        proof = c._evidence_digest(row, "mastodon")
        out = run(row, verified={proof})
        self.assertEqual(out["proposals"][0]["state"], "proponer_ensayo_manual")
        self.assertGreater(out["proposals"][0]["wilson_interval_gap"], 0)
        self.assertTrue(out["proposals"][0]["needs_human_approval"])
        self.assertTrue(out["proposals"][0]["externally_verified"])
        self.assertFalse(initial["proposals"][0]["externally_verified"])
        modified = positive(treatment={"n": 100, "successes": 71})
        self.assertEqual(run(modified, verified={proof})["proposals"][0]["state"],
                         "verificacion_externa_pendiente")
        self.assertFalse(out["writes"])

    def test_all_eight_networks_report_coverage_not_fake_results(self):
        out = run()
        self.assertEqual(set(out["coverage"]), c.NETWORKS)
        self.assertEqual(set(out["coverage"]), {
            "bluesky", "mastodon", "x", "threads", "facebook",
            "pinterest", "reddit", "tiktok",
        })
        self.assertNotIn("instagram", out["coverage"])
        self.assertEqual(set(n for n, v in out["coverage"].items() if v == "partial"),
                         c.STATE_ADAPTERS)
        self.assertEqual(out["proposals"], [])

    def test_missing_control_and_partial_provenance_do_not_promote(self):
        for row in (positive(control=None), positive(outcome_link="legacy"),
                    positive(human_reviewed=False), positive(design="matched"),
                    positive(mature_days=2), positive(metric="likes")):
            self.assertEqual(run(row)["proposals"], [])

    def test_min_samples_and_wilson_overlap_prevent_promotion(self):
        for row in (positive(treatment={"n": 39, "successes": 35}),
                    positive(control={"n": 39, "successes": 1}),
                    positive(treatment={"n": 100, "successes": 20},
                             control={"n": 100, "successes": 19}),
                    positive(treatment={"n": True, "successes": True})):
            self.assertFalse(run(row)["proposals"])

    def test_unknown_expired_or_denied_permissions_never_suggest_apply(self):
        cases = [({}, "investigar_equivalencia"),
                 ({"capability": "verified", "permission": "unknown", "checked_on": "2026-10-08"}, "investigar_equivalencia"),
                 ({"capability": "verified", "permission": "verified", "implemented": False, "checked_on": "2026-01-01"}, "investigar_equivalencia"),
                 ({"capability": "unsupported", "permission": "unknown"}, "no_transferible"),
                 ({"permission": "denied"}, "no_transferible")]
        for payload, expected in cases:
            with self.subTest(payload=payload):
                row = positive(targets={"mastodon": payload})
                self.assertEqual(run(row)["proposals"][0]["state"], expected)

    def test_rejected_or_implemented_history_not_repeated(self):
        for decision in ("rejected", "implemented", "under_review"):
            out = run(positive(), history=[{"origin": "bluesky", "target": "mastodon",
                                            "feature": "hashtag_search", "decision": decision}])
            self.assertEqual(out["proposals"], [])
            self.assertEqual(out["suppressed"], 1)

    def test_cross_network_only_and_duplicate_conflicts_fail_closed(self):
        row = positive(targets={"bluesky": {}, "mastodon": {}, "reddit": {}})
        good = run(row)
        self.assertEqual([v["target"] for v in good["proposals"]],
                         ["mastodon", "reddit"])
        duplicate = run(row, row)
        self.assertEqual(duplicate["proposals"], [])
        self.assertEqual(duplicate["duplicate_evidence"], 4)
        self.assertEqual(duplicate["suppressed"], 4)

    def test_maturity_and_population_attestations_required(self):
        for row in (positive(cohort_end="2026-09-25"),
                    positive(cohort_end="2026-99-99"),
                    positive(baseline_nonfollowers_verified=False),
                    positive(assignment_units_unique=False),
                    positive(day14_snapshot_complete=False),
                    positive(mature_days=14.0)):
            self.assertEqual(run(row)["proposals"], [])

    def test_conflicting_targets_cannot_use_input_order_to_promote(self):
        proof_row = positive()
        proof = c._evidence_digest(proof_row, "mastodon")
        denied = positive(targets={"mastodon": {"capability": "unsupported"}})
        for rows in ((proof_row, denied), (denied, proof_row)):
            report = run(*rows, verified={proof})
            self.assertEqual(report["proposals"], [])
            self.assertEqual(report["duplicate_evidence"], 2)

    def test_aware_utc_datetime_not_mistaken_for_madrid_date(self):
        instant = dt.datetime(2026, 10, 8, 22, 30, tzinfo=dt.timezone.utc)
        with self.assertRaises(ValueError):
            run(positive(), date=instant)

    def test_freshness_and_future_dates_fail_closed(self):
        for stamp in ("2026-08-01", "2026-10-10", "not-a-date"):
            self.assertEqual(run(positive(observed_on=stamp))["proposals"], [])
        self.assertEqual(len(run(positive(), date=NOW + dt.timedelta(days=3))["proposals"]), 1)
        self.assertFalse(run(positive(), date=NOW + dt.timedelta(days=30))["proposals"])
        self.assertFalse(run(positive(), date=NOW + dt.timedelta(days=31))["proposals"])

    def test_never_leak_untrusted_personal_data(self):
        row = positive(text="@private_person", profile="https://example.invalid/person",
                       targets={"mastodon": {"capability": "verified", "permission": "verified",
                                              "implemented": False, "checked_on": "2026-10-08",
                                              "token": "secretpassword"}})
        output = repr(run(row))
        for secret in ("@private_person", "example.invalid", "secretpassword"):
            self.assertNotIn(secret, output)

    def test_unhashable_metadata_and_history_fail_closed(self):
        for bad in (positive(feature=["hashtag_search"]),
                    positive(origin={"red": "bluesky"}),
                    positive(targets={3: {}})):
            self.assertEqual(run(bad)["proposals"], [])
        history = [{"origin": [], "feature": {}, "target": ["mastodon"],
                    "decision": "rejected"}]
        self.assertEqual(len(run(positive(), history=history)["proposals"]), 1)

    def test_external_verification_cannot_be_supplied_in_json(self):
        raw = positive(targets={"mastodon": {"capability": "verified",
                          "permission": "verified", "implemented": False,
                          "checked_on": "2026-10-08",
                          "externally_verified": True}})
        self.assertEqual(run(raw)["proposals"][0]["state"],
                         "verificacion_externa_pendiente")
        with self.assertRaises(ValueError):
            run(raw, verified="bluesky:hashtag_search:mastodon")
        with self.assertRaises(ValueError):
            run(raw, verified={("bluesky", "hashtag_search", "mastodon")})

    def test_no_write_to_input_or_other_files(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            path = folder / "aggregates.json"
            path.write_text(json.dumps({"schema": 1, "observations": [positive()]}),
                            encoding="utf-8")
            before = (path.read_bytes(), path.stat().st_mtime_ns)
            with patch("sys.argv", ["tool", "--input", str(path),
                                    "--as-of", "2026-10-09"]):
                self.assertEqual(c.main(), 0)
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
            self.assertEqual([x.name for x in folder.iterdir()], ["aggregates.json"])

    def test_json_nan_or_bool_schema_and_limits_rejected(self):
        with self.assertRaises(ValueError):
            c.review({"schema": True, "observations": []}, today=NOW)
        with self.assertRaises(ValueError):
            c.review({"schema": 1, "observations": [{}] * 101}, today=NOW)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text('{"schema":1,"observations":[{"a":NaN}]}',
                            encoding="utf-8")
            with patch("sys.argv", ["tool", "--input", str(path)]):
                self.assertEqual(c.main(), 2)

    def test_invalid_document_and_bounded_cli_input(self):
        with self.assertRaises(ValueError):
            c.review({"schema": 99, "observations": []}, today=NOW)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fake.json"
            path.write_text(json.dumps({"schema": 1, "observations": [positive()]}), encoding="utf-8")
            with patch("sys.argv", ["tool", "--input", str(path), "--as-of", "2026-10-09"]):
                self.assertEqual(c.main(), 0)
            with patch("sys.argv", ["tool", "--input", str(path), "--as-of", "fecha-falsa"]):
                self.assertEqual(c.main(), 2)
            path.write_text('{"schema":1,"schema":1,"observations":[]}',
                            encoding="utf-8")
            with patch("sys.argv", ["tool", "--input", str(path)]):
                self.assertEqual(c.main(), 2)
            path.write_text("[" * 3000, encoding="utf-8")
            with patch("sys.argv", ["tool", "--input", str(path)]):
                self.assertEqual(c.main(), 2)
            path.write_bytes(b"X" * (c.MAX_INPUT_BYTES + 1))
            with patch("sys.argv", ["tool", "--input", str(path)]):
                self.assertEqual(c.main(), 2)


if __name__ == "__main__":
    unittest.main()
