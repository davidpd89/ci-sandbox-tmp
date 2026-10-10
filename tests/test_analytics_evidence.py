"""Regresión adversarial sin cuentas, APIs, secretos ni datos reales."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import analytics_evidence as ev
from experiment_uplift import analyze_experiment

BASE = datetime(2026, 9, 1, tzinfo=timezone.utc)


def ts(day):
    return (BASE + timedelta(days=day)).isoformat().replace("+00:00", "Z")


def exposure(i="a", subject="u", network="bluesky", queue="API",
             cohort="treated", status="confirmed", days=0):
    value = {"id": i, "network": network, "queue": queue, "campaign": "novela",
             "subject": subject, "action": "follow", "cohort": cohort, "status": status,
             "source": "holdout_ledger" if cohort == "control" else "action_ledger",
             "source_ref": "ack_" + i, "occurred_at": ts(days)}
    if cohort != "control":
        value["tracking_id"] = "trk_" + i
        value["utm"] = {"source": network, "medium": "social", "campaign": "novela"}
    return value


def obs(i="o", exp="a", outcome="followback", positive=True, complete=True, day=14):
    value = {"id": i, "exposure_id": exp, "outcome": outcome,
             "positive": positive, "complete": complete, "observed_at": ts(day),
             "source": ev.SOURCES[outcome], "source_ref": "proof_" + i,
             "basis": "identity" if outcome == "followback" else "tracked"}
    if outcome != "followback":
        value["tracking_id"] = "trk_" + exp
    if outcome == "web_visit":
        value["utm"] = {"source": "bluesky", "medium": "social", "campaign": "novela"}
    return value


def payload(exposures=None, observations=None):
    return {"schema_version": 1, "as_of": "2026-10-10T00:00:00Z", "window_days": 14,
            "exposures": [exposure()] if exposures is None else exposures,
            "observations": [] if observations is None else observations}


def cell(report, outcome="followback", cohort="treated"):
    return next(r for r in report["groups"] if r["outcome"] == outcome and r["cohort"] == cohort)


class OfflineEvidenceTests(unittest.TestCase):
    def test_absence_is_unknown_not_zero(self):
        r = cell(ev.analyze(payload()))
        self.assertEqual((r["unknown"], r["negative"], r["rate"]), (1, 0, None))

    def test_partial_or_early_negative_cannot_close_window(self):
        for proof in (obs(positive=False, complete=False, day=14),
                      obs(positive=False, day=3)):
            with self.subTest(proof=proof):
                self.assertEqual(cell(ev.analyze(payload(observations=[proof])))["unknown"], 1)
        r = cell(ev.analyze(payload(observations=[obs(positive=False)])))
        self.assertEqual((r["readiness"], r["negative"], r["rate"]), ("complete", 1, 0.0))

    def test_tracked_web_and_sale_require_evidence_without_funnel_invention(self):
        reports = ev.analyze(payload(observations=[
            obs("web", outcome="web_visit"), obs("receipt", outcome="sale")]))
        self.assertEqual(cell(reports, "web_visit")["positive"], 1)
        self.assertEqual(cell(reports, "sale")["positive"], 1)
        self.assertEqual(cell(reports, "reading")["unknown"], 1)
        for mutation in ({"tracking_id": "wrong"}, {"basis": "guess"},
                         {"utm": {"source": "x", "medium": "social", "campaign": "novela"}}):
            proof = obs(outcome="web_visit")
            proof.update(mutation)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                ev.analyze(payload(observations=[proof]))

    def test_explicit_control_and_no_causal_claim(self):
        control = exposure("b", "control", cohort="control", status="holdout")
        report = ev.analyze(payload([exposure(), control],
                                    [obs(), obs("n", "b", positive=False)]))
        self.assertEqual(cell(report, cohort="treated")["rate"], 1.0)
        self.assertEqual(cell(report, cohort="control")["rate"], 0.0)
        self.assertEqual(report["interpretation"], "descriptive_only_not_causal")
        self.assertNotIn("uplift", report)

    def test_immature_does_not_contribute_to_rate(self):
        r = cell(ev.analyze(payload([exposure(days=35)], [obs(day=39)])))
        self.assertEqual((r["immature"], r["positive"], r["rate"]), (1, 0, None))

    def test_deduplicate_ids_and_subject(self):
        a = exposure()
        result = ev.analyze(payload([a, deepcopy(a), exposure("b", "u", days=1)],
                                    [obs(), obs()]))
        self.assertEqual(cell(result)["eligible"], 1)
        self.assertEqual(result["quality"]["duplicate_observations"], 1)
        self.assertEqual(result["quality"]["duplicate_exposures"], 1)
        self.assertEqual(result["quality"]["repeated_subject_exposures"], 1)

    def test_no_double_credit_or_cross_arm_contamination(self):
        b = exposure("b", "v")
        a_proof, b_proof = obs(outcome="sale"), obs("o2", "b", outcome="sale")
        b_proof["source_ref"] = a_proof["source_ref"]
        with self.assertRaisesRegex(ValueError, "dos veces"):
            ev.analyze(payload([exposure(), b], [a_proof, b_proof]))
        control = exposure("b", "u", cohort="control", status="holdout")
        with self.assertRaisesRegex(ValueError, "tratamiento y control"):
            ev.analyze(payload([exposure(), control]))

    def test_contradictions_and_bad_ack(self):
        with self.assertRaisesRegex(ValueError, "contradictorias"):
            ev.analyze(payload(observations=[obs(day=3), obs("n", positive=False)]))
        wrong = exposure()
        wrong["source"] = "unverified"
        with self.assertRaisesRegex(ValueError, "ACK"):
            ev.analyze(payload([wrong]))

    def test_all_nine_networks_and_three_queues(self):
        items = [exposure(f"e{i}_{j}", f"u{i}_{j}", network=n, queue=q)
                 for i, n in enumerate(sorted(ev.NETWORKS))
                 for j, q in enumerate(sorted(ev.QUEUES))]
        report = ev.analyze(payload(items))
        self.assertEqual(len(report["groups"]), 108)
        self.assertEqual(report["quality"]["networks_without_exposure"], [])
        self.assertTrue(all(r["unknown"] == 1 for r in report["groups"]))

    def test_cli_fixture_is_reproducible_and_redacted(self):
        fixture = Path(__file__).parent / "fixtures" / "analytics_evidence.synthetic.json"
        run = subprocess.run([sys.executable, str(TOOLS / "analytics_evidence.py"), str(fixture)],
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), ev.analyze(json.loads(fixture.read_text(encoding="utf-8"))))
        self.assertNotIn("synthetic_a", run.stdout)
        self.assertNotIn("trk_a", run.stdout)

    def test_json_duplicate_keys_rejected(self):
        with self.assertRaises(ValueError):
            ev._unique_keys([("id", 1), ("id", 2)])


FLAGS = dict(window_days=14, randomized_pre_exposure=True, complete_assignment_log=True,
             fixed_outcome_window=True, no_interference=True, study_finished=True)


def experiment_data(n=120):
    return [{"unit_id": f"{arm}-{i}", "network": "bluesky", "cohort": "cohort2026",
             "arm": arm, "converted": i < (24 if arm == "treatment" else 12),
             "contaminated": False, "followup_days": 14}
            for arm in ("treatment", "control") for i in range(n)]


class ReusedExperimentTests(unittest.TestCase):
    def test_review_only_no_automatic_causal_approval(self):
        report = analyze_experiment(experiment_data(), design=FLAGS)
        self.assertEqual(report["status"], "review_only")
        self.assertFalse(report["causal_claim_approved"])
        self.assertIsNotNone(report["ci_pp"])

    def test_missing_proof_or_contamination_hides_uplift(self):
        fail = analyze_experiment(experiment_data(),
                                  design={**FLAGS, "randomized_pre_exposure": False})
        self.assertEqual(fail["status"], "blocked")
        self.assertIsNone(fail["difference_pp"])
        records = experiment_data()
        records[0]["contaminated"] = True
        self.assertIsNone(analyze_experiment(records, design=FLAGS)["ci_pp"])

    def test_cross_network_mixing_invalid(self):
        records = experiment_data()
        records[0]["network"] = "mastodon"
        with self.assertRaises(ValueError):
            analyze_experiment(records, design=FLAGS)


if __name__ == "__main__":
    unittest.main()
