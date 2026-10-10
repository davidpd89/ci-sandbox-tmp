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
    TrustedRegistry, MAX_REGISTRY_RECORDS, audit_projection, evidence_digest,
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

    def test_registry_subclass_cannot_override_approval(self):
        class ForgedRegistry(TrustedRegistry):
            def approves(self, row, target):
                return True

        with self.assertRaisesRegex(ValueError, "registro independiente inválido"):
            run(trial(), registry=ForgedRegistry([]))

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

    def test_malformed_identity_cannot_veto_valid_audited_trial(self):
        winner = trial()
        registry = TrustedRegistry([audited(winner)])
        malformed = copy.deepcopy(winner)
        malformed["experiment"] = None
        report = run(winner, malformed, registry=registry)
        self.assertEqual(report["duplicate_evidence"], 0)
        self.assertEqual(report["invalid_or_unproven"], 1)
        self.assertEqual(report["proposals"][0]["state"], "proponer_ensayo_manual")
        # Una réplica negativa VÁLIDA sí veta, aunque no sea favorable.
        negative = trial("trial-B002")
        negative["treatment"]["successes"] = 15
        negative["control"]["successes"] = 25
        veto = run(winner, negative, registry=registry)
        self.assertEqual(veto["proposals"], [])
        self.assertEqual(veto["duplicate_evidence"], 1)
        # v1 sigue contando ensayos sin metadatos de identidad.
        legacy = run(winner, malformed, registry=registry, schema=1)
        self.assertEqual(legacy["proposals"], [])
        self.assertEqual(legacy["duplicate_evidence"], 2)

    def test_duplicate_and_replayed_evidence_never_promotes(self):
        row = trial()
        report = run(row, copy.deepcopy(row), registry=TrustedRegistry([audited(row)]))
        self.assertEqual(report["proposals"], [])
        self.assertEqual(report["duplicate_evidence"], 2)

    def test_registry_capacity_handles_full_multi_network_batch(self):
        # 100 observaciones x 7 destinos: el antiguo tope de 200 fallaba
        # aunque review() admite legítimamente esta cardinalidad.
        rows, records = [], []
        targets = sorted(gate.NETWORKS - {"bluesky"})
        self.assertEqual(len(targets), 7)
        for index in range(100):
            row = trial(identity=f"trial-{index:04d}")
            original = row["targets"]["mastodon"]
            row["targets"] = {target: dict(original) for target in targets}
            rows.append(row)
            for target in targets:
                projection = audit_projection(row, target)
                digest = evidence_digest(row, target)
                self.assertIsNotNone(projection)
                self.assertIsNotNone(digest)
                records.append({**projection, "evidence_sha256": digest})
        self.assertEqual(len(records), 700)
        registry = TrustedRegistry(records)
        self.assertTrue(all(registry.approves(row, target)
                            for row in rows for target in targets))
        with self.assertRaisesRegex(ValueError, "registro de auditoría inválido"):
            TrustedRegistry([{}] * (MAX_REGISTRY_RECORDS + 1))

    def test_registry_rejects_ambiguous_assignments_and_duplicates(self):
        a = audited(trial())
        with self.assertRaises(ValueError):
            TrustedRegistry([a, a])
        b = audited(trial("trial-B002"))
        b["assignment_sha256"] = a["assignment_sha256"]
        with self.assertRaises(ValueError):
            TrustedRegistry([a, b])

    def test_same_experiment_id_cannot_change_audited_identity(self):
        baseline = trial()
        for mutate in (
            lambda x: x["experiment"].update(design_sha256="f" * 64),
            lambda x: x["experiment"].update(assignment_sha256="e" * 64),
            lambda x: x["treatment"].update(n=101),
            lambda x: x.update(origin="x"),
            lambda x: x.update(feature="account_search"),
        ):
            with self.subTest(mutation=str(mutate)):
                other = copy.deepcopy(baseline)
                other["targets"]["mastodon"]["queue"] = "WEB"
                mutate(other)
                with self.assertRaisesRegex(ValueError, "identidad de ensayo inconsistente"):
                    TrustedRegistry([audited(baseline), audited(other)])

    def test_same_identity_may_have_separately_audited_queues(self):
        api, web = trial(), trial(queue="WEB")
        registry = TrustedRegistry([audited(api), audited(web)])
        self.assertTrue(registry.approves(api, "mastodon"))
        self.assertTrue(registry.approves(web, "mastodon"))
        self.assertEqual(run(api, registry=registry)["proposals"][0]["state"],
                         "proponer_ensayo_manual")
        self.assertEqual(run(web, registry=registry)["proposals"][0]["state"],
                         "proponer_ensayo_manual")

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

    def test_registry_snapshot_immutable_and_input_defensively_copied(self):
        source = audited(trial())
        registry = TrustedRegistry([source])
        source["evidence_sha256"] = "0" * 64
        self.assertTrue(registry.approves(trial(), "mastodon"))
        with self.assertRaises(AttributeError):
            registry._entries.clear()
        key = next(iter(registry._entries))
        with self.assertRaises(TypeError):
            registry._entries[key]["evidence_sha256"] = "0" * 64
        with self.assertRaises(AttributeError):
            registry._entries = {}
        with self.assertRaises(AttributeError):
            del registry._entries

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

    def test_evidence_ci_includes_wilson_dependency(self):
        """La CI específica debe dispararse si se cambia el cálculo estadístico."""
        workflow = (pathlib.Path(__file__).resolve().parents[1]
                    / ".github/workflows/experiment-evidence-lineage.yml").read_text(encoding="utf-8")
        push, pull_request = workflow.split("  pull_request:", 1)
        for event_paths in (push, pull_request.split("  workflow_dispatch:", 1)[0]):
            self.assertIn("      - 'tools/growth_attribution.py'", event_paths)
        self.assertIn("tools/discovery_attribution.py tools/growth_attribution.py", workflow)

    def test_distinct_trials_can_share_design_not_assignment(self):
        a, b = trial(), trial("trial-B002")
        self.assertEqual(a["experiment"]["design_sha256"],
                         b["experiment"]["design_sha256"])
        self.assertNotEqual(a["experiment"]["assignment_sha256"],
                            b["experiment"]["assignment_sha256"])
        registry = TrustedRegistry([audited(a), audited(b)])
        self.assertTrue(registry.approves(a, "mastodon"))
        self.assertTrue(registry.approves(b, "mastodon"))
        # Una réplica independiente exige evaluación conjunta; no se
        # promocionan dos propuestas solapadas aunque ambas sean legítimas.
        self.assertEqual(run(a, b, registry=registry)["proposals"], [])

    def test_invalid_arms_cannot_get_direct_registry_approval(self):
        original = trial()
        registry = TrustedRegistry([audited(original)])
        for changes in (
            {"successes": -1}, {"successes": 101},
            {"successes": True}, {"successes": 70.0},
            {"n": True}, {"n": 39}, {"n": -50},
            {"n": 1_000_001},
        ):
            row = copy.deepcopy(original)
            row["treatment"].update(changes)
            with self.subTest(changes=changes):
                self.assertIsNone(audit_projection(row, "mastodon"))
                self.assertIsNone(evidence_digest(row, "mastodon"))
                self.assertFalse(registry.approves(row, "mastodon"))
                self.assertEqual(run(row, registry=registry)["proposals"], [])

    def test_unrelated_metadata_does_not_affect_evidence_commitment(self):
        row = trial()
        registry = TrustedRegistry([audited(row)])
        extra = copy.deepcopy(row)
        extra["internal_label"] = "private-synthetic-metadata"
        extra["targets"]["mastodon"]["note"] = "synthetic"
        extra["targets"]["mastodon"]["experiment_labels"] = ["fiction"]
        self.assertEqual(evidence_digest(row, "mastodon"),
                         evidence_digest(extra, "mastodon"))
        self.assertTrue(registry.approves(extra, "mastodon"))
        self.assertNotIn("synthetic", json.dumps(run(extra, registry=registry)))

    def test_duplicate_record_cannot_override_evidence_digest(self):
        row = trial()
        first = audited(row)
        altered = {**first, "evidence_sha256": "f" * 64}
        with self.assertRaisesRegex(ValueError, "registro duplicado"):
            TrustedRegistry([first, altered])
        # Distintos destinos pueden necesitar hashes distintos, no son
        # duplicados: la clave incluye target y queue.
        cross = copy.deepcopy(row)
        cross["targets"]["reddit"] = dict(cross["targets"]["mastodon"])
        registry = TrustedRegistry([
            first,
            {**audit_projection(cross, "reddit"),
             "evidence_sha256": evidence_digest(cross, "reddit")},
        ])
        self.assertTrue(registry.approves(cross, "reddit"))

    def test_future_target_permission_does_not_promote(self):
        row = trial()
        future = copy.deepcopy(row)
        future["targets"]["mastodon"]["checked_on"] = "2026-10-10"
        registry = TrustedRegistry([audited(future)])
        self.assertEqual(run(future, registry=registry)["proposals"][0]["state"],
                         "investigar_equivalencia")

    def test_registry_limit_counts_records_not_distinct_experiments(self):
        records = [audited(trial(identity=f"trial-{i:04d}")) for i in range(800)]
        registry = TrustedRegistry(records)
        self.assertEqual(len(registry._entries), 800)
        self.assertTrue(registry.approves(trial(identity="trial-0799"),
                                          "mastodon"))
        with self.assertRaisesRegex(ValueError, "registro de auditoría inválido"):
            TrustedRegistry(records + [audited(trial("trial-0800"))])

    def test_digest_is_order_invariant_and_type_sensitive(self):
        row = trial()
        reordered = dict(reversed(list(copy.deepcopy(row).items())))
        reordered["treatment"] = dict(reversed(list(row["treatment"].items())))
        reordered["targets"] = {"mastodon": dict(reversed(list(
            row["targets"]["mastodon"].items())))}
        self.assertEqual(evidence_digest(row, "mastodon"),
                         evidence_digest(reordered, "mastodon"))
        for changed_value in (True, 14.0):
            altered = copy.deepcopy(row)
            altered["mature_days"] = changed_value
            self.assertNotEqual(evidence_digest(row, "mastodon"),
                                evidence_digest(altered, "mastodon"))
            self.assertEqual(run(altered, registry=TrustedRegistry([audited(row)]))
                             ["proposals"], [])

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
