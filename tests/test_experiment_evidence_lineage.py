"""Contrato v2: todas las entradas y auditorías son fixtures sintéticas."""
import copy
import datetime as dt
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import cross_network_learning as gate
from experiment_evidence_lineage import (
    TrustedRegistry, audit_projection, evidence_digest,
)

NOW = dt.date(2026, 10, 9)


def trial(identity="trial-A001", queue="API"):
    return {
        "feature": "hashtag_search", "origin": "bluesky",
        "metric": "new_follower_day14", "design": "randomized",
        "outcome_link": "audited", "human_reviewed": True,
        "mature_days": 14, "observed_on": "2026-10-08",
        "cohort_end": "2026-09-24",
        "baseline_nonfollowers_verified": True,
        "assignment_units_unique": True, "day14_snapshot_complete": True,
        "treatment": {"n": 100, "successes": 70},
        "control": {"n": 100, "successes": 10},
        "experiment": {
            "id": identity,
            "design_sha256": hashlib.sha256(b"design-v1").hexdigest(),
            "assignment_sha256": hashlib.sha256(identity.encode("ascii")).hexdigest(),
        },
        "targets": {"mastodon": {
            "queue": queue, "capability": "verified",
            "permission": "verified", "implemented": False,
            "checked_on": "2026-10-08",
        }},
    }


def audited(row):
    audit = audit_projection(row, "mastodon")
    digest = evidence_digest(row, "mastodon")
    assert audit is not None and digest is not None
    return {**audit, "evidence_sha256": digest}


def run(*rows, registry=None, schema=2, legacy_proofs=None):
    return gate.review({"schema": schema, "observations": list(rows)},
                       today=NOW, trusted_registry=registry,
                       trusted_verifications=legacy_proofs)


class VersionedEvidenceTests(unittest.TestCase):
    def test_two_trials_with_equal_aggregates_cannot_share_approval(self):
        a, b = trial(), trial("trial-B002")
        self.assertEqual(a["treatment"], b["treatment"])
        self.assertEqual(a["control"], b["control"])
        self.assertEqual(gate._evidence_digest(a, "mastodon"),
                         gate._evidence_digest(b, "mastodon"))
        self.assertNotEqual(evidence_digest(a, "mastodon"),
                            evidence_digest(b, "mastodon"))
        approved = TrustedRegistry([audited(a)])
        self.assertEqual(run(a, registry=approved)["proposals"][0]["state"],
                         "proponer_ensayo_manual")
        self.assertEqual(run(b, registry=approved)["proposals"][0]["state"],
                         "verificacion_externa_pendiente")
        both = run(a, b, registry=approved)
        self.assertEqual(both["proposals"], [])
        self.assertEqual(both["duplicate_evidence"], 2)
        self.assertFalse(both["writes"])

    def test_self_declared_identifier_never_promotes(self):
        row = trial()
        for registry in (None, TrustedRegistry([])):
            with self.subTest(registry=registry):
                result = run(row, registry=registry)
                self.assertEqual(result["proposals"][0]["state"],
                                 "verificacion_externa_pendiente")
                self.assertFalse(result["proposals"][0]["externally_verified"])
        with self.assertRaises(ValueError):
            run(row, registry={"entries": [audited(row)]})

    def test_legacy_inputs_readable_but_no_legacy_approval(self):
        row = trial()
        original = gate._evidence_digest(row, "mastodon")
        for supplied in (None, {original}):
            result = run(row, schema=1, legacy_proofs=supplied,
                         registry=TrustedRegistry([audited(row)]))
            self.assertEqual(result["identity_contract"], "legacy_read_only")
            self.assertEqual(result["schema"], 1)
            self.assertEqual(result["proposals"][0]["state"],
                             "verificacion_externa_pendiente")

    def test_wrong_queue_or_target_permission_requires_new_audit(self):
        row = trial()
        proof = TrustedRegistry([audited(row)])
        for mutation in (
            lambda x: x["targets"]["mastodon"].update(queue="WEB"),
            lambda x: x["targets"]["mastodon"].update(queue="MOBILE"),
            lambda x: x["targets"]["mastodon"].update(checked_on="2026-10-07"),
            lambda x: x["treatment"].update(successes=71),
            lambda x: x["experiment"].update(design_sha256="f" * 64),
            lambda x: x["experiment"].update(assignment_sha256="e" * 64),
        ):
            changed = copy.deepcopy(row)
            mutation(changed)
            self.assertEqual(run(changed, registry=proof)["proposals"][0]["state"],
                             "verificacion_externa_pendiente")
        changed = copy.deepcopy(row)
        changed["targets"]["mastodon"]["checked_on"] = "2026-01-01"
        self.assertEqual(run(changed, registry=proof)["proposals"][0]["state"],
                         "investigar_equivalencia")
        changed = copy.deepcopy(row)
        changed["targets"]["mastodon"]["permission"] = "denied"
        self.assertEqual(run(changed, registry=proof)["proposals"][0]["state"],
                         "no_transferible")

    def test_duplicate_and_replayed_evidence_never_promotes(self):
        row = trial()
        report = run(row, copy.deepcopy(row), registry=TrustedRegistry([audited(row)]))
        self.assertEqual(report["proposals"], [])
        self.assertEqual(report["duplicate_evidence"], 2)

    def test_registry_rejects_ambiguous_assignments_and_duplicates(self):
        a = audited(trial())
        with self.assertRaises(ValueError):
            TrustedRegistry([a, a])
        b = audited(trial("trial-B002"))
        b["assignment_sha256"] = a["assignment_sha256"]
        with self.assertRaises(ValueError):
            TrustedRegistry([a, b])

    def test_reviewed_manifest_mismatch_is_not_approved(self):
        row = trial()
        r = audited(row)
        for key, value in (("assignment_count", 201),
                           ("origin", "x"),
                           ("assignment_sha256", "e" * 64),
                           ("design_sha256", "f" * 64),
                           ("evidence_sha256", "0" * 64)):
            bad = dict(r, **{key: value})
            result = run(row, registry=TrustedRegistry([bad]))
            self.assertEqual(result["proposals"][0]["state"],
                             "verificacion_externa_pendiente")

    def test_malformed_identity_fails_closed_no_echo(self):
        secret = "private_user_name_must_not_appear"
        row = trial()
        for experiment in (None, {}, {"id": secret},
                           {**row["experiment"], "id": "../private"},
                           {**row["experiment"], "assignment_sha256": "BAD"},
                           {**row["experiment"], "design_sha256": ["invalid"]},
                           {**row["experiment"], "unexpected": "value"}):
            changed = copy.deepcopy(row)
            changed["experiment"] = experiment
            report = run(changed, registry=TrustedRegistry([audited(row)]))
            text = json.dumps(report)
            self.assertNotIn(secret, text)
            self.assertNotIn("proponer_ensayo_manual", text)

    def test_no_reuse_across_all_network_pairs_and_queues(self):
        row = trial()
        registry = TrustedRegistry([audited(row)])
        for queue in ("WEB", "MOBILE"):
            changed = trial(queue=queue)
            self.assertEqual(run(changed, registry=registry)["proposals"][0]["state"],
                             "verificacion_externa_pendiente")
        for origin in gate.NETWORKS:
            for target in gate.NETWORKS:
                if origin == target:
                    continue
                candidate = trial()
                candidate["origin"] = origin
                candidate["targets"] = {target: dict(row["targets"]["mastodon"])}
                result = run(candidate, registry=registry)
                self.assertEqual(result["proposals"][0]["state"],
                                 "proponer_ensayo_manual" if
                                 (origin, target) == ("bluesky", "mastodon")
                                 else "verificacion_externa_pendiente")

    def test_invalid_json_cli_fails_without_network(self):
        invalid = [
            '{"schema":2,"schema":2,"observations":[]}',
            '{"schema":2,"observations":[NaN]}',
            '{"schema":2,"observations":[{"x":Infinity}]}',
            '{"schema":2,"observations":',
        ]
        for payload in invalid:
            with tempfile.TemporaryDirectory() as folder:
                path = pathlib.Path(folder) / "synthetic.json"
                path.write_text(payload, encoding="utf-8")
                with patch("builtins.print") as output:
                    self.assertEqual(gate.main(["--input", str(path),
                                                "--as-of", "2026-10-09"]), 2)
                self.assertEqual(output.call_args.args[0], "DATOS_NO_VALIDOS")

    def test_digest_domain_and_registry_shapes(self):
        row = trial()
        self.assertEqual(len(evidence_digest(row, "mastodon")), 64)
        self.assertNotEqual(evidence_digest(row, "mastodon"),
                            gate._evidence_digest(row, "mastodon"))
        for invalid in (
            [{"garbage": True}],
            [{**audited(row), "evidence_sha256": False}],
            [{**audited(row), "queue": "UNKNOWN"}],
            [{**audited(row), "assignment_count": True}],
        ):
            with self.assertRaises(ValueError):
                TrustedRegistry(invalid)

    def test_unhashable_queue_or_malformed_targets_never_crashes(self):
        for invalid_queue in ([], {}, ["API"], None, 42):
            row = trial()
            row["targets"]["mastodon"]["queue"] = invalid_queue
            self.assertIsNone(audit_projection(row, "mastodon"))
            self.assertIsNone(evidence_digest(row, "mastodon"))
            report = run(row, registry=TrustedRegistry([]))
            self.assertEqual(report["proposals"][0]["state"], "investigar_equivalencia")
        row = trial()
        row["targets"] = ["API"]
        self.assertIsNone(evidence_digest(row, "mastodon"))
        self.assertEqual(run(row)["proposals"], [])

    def test_approval_requires_explicit_current_audit_and_never_reuses_old_sha(self):
        row = trial()
        registry = TrustedRegistry([audited(row)])
        self.assertTrue(registry.approves(row, "mastodon"))
        # v1 verifier and plain dict cannot smuggle legacy approvals into v2.
        legacy = gate._evidence_digest(row, "mastodon")
        self.assertEqual(run(row, legacy_proofs={legacy})["proposals"][0]["state"],
                         "verificacion_externa_pendiente")
        mutation = copy.deepcopy(row)
        mutation["experiment"]["id"] = "trial-C003"
        self.assertFalse(registry.approves(mutation, "mastodon"))

    def test_no_network_calls_or_user_identity_in_output(self):
        row = trial()
        row["internal_handle"] = "secret-pseudonym"
        row["targets"]["mastodon"]["untrusted_note"] = "secret-pseudonym"
        result = run(row, registry=TrustedRegistry([audited(row)]))
        self.assertTrue(result["proposals"][0]["externally_verified"])
        self.assertNotIn("secret-pseudonym", json.dumps(result))
        self.assertFalse(result["writes"])


if __name__ == "__main__":
    unittest.main()
