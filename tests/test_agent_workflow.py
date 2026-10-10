"""Hermetic Python 3.11 tests: all inputs synthetic, never call a social executor."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from agent_workflow import Event, Workflow, WorkflowError, NETWORKS, QUEUES, digest, inspect_pipeline


def build_through_approval(network="x", queue="WEB"):
    w = Workflow("example-run-1", network, queue)
    for stage in ("research", "plan", "write"):
        w = w.append(Event(stage + "-1", stage, digest("synthetic-" + stage), tool_id="skill:" + stage))
    draft = w.events[-1].evidence
    w = w.append(Event("validate-1", "validate", digest("qa-report"), revision=draft))
    w = w.append(Event("approve-1", "approval", digest("approval-reference"), revision=draft, actor="human:reviewer"))
    return w


class WorkflowTests(unittest.TestCase):
    def test_nine_networks_three_queues(self):
        self.assertEqual(len(NETWORKS), 9)
        self.assertEqual(len(QUEUES), 3)
        for network in NETWORKS:
            for queue in QUEUES:
                with self.subTest(network=network, queue=queue):
                    w = build_through_approval(network, queue)
                    self.assertEqual(w.stage, "dispatch")
                    self.assertEqual(Workflow.from_json(w.to_json()), w)
                    self.assertEqual(w.handoff()["queue"], queue)

    def test_handoff_is_data_only_and_receipt_is_tristate(self):
        w = build_through_approval()
        envelope = w.handoff()
        self.assertEqual(set(envelope), {"run_id", "network", "queue", "revision", "idempotency_key"})
        self.assertEqual(len(envelope["idempotency_key"]), 64)
        w = w.append(Event("sent", "dispatch", envelope["idempotency_key"], revision=envelope["revision"]))
        self.assertEqual(w.stage, "verify")
        for outcome in ("confirmed", "failed", "unknown"):
            with self.subTest(outcome=outcome):
                done = w.append(Event("receipt", "verify", digest("receipt"), revision=envelope["revision"], outcome=outcome))
                self.assertEqual(done.stage, {"confirmed": "complete", "failed": "failed", "unknown": "uncertain"}[outcome])
                self.assertEqual(done.result, outcome)
                with self.assertRaises(WorkflowError):
                    done.handoff()
                self.assertEqual(Workflow.from_json(done.to_json()), done)

    def test_out_of_order_approval_and_unvalidated_draft(self):
        w = Workflow("run", "x", "WEB")
        with self.assertRaises(WorkflowError):
            w.append(Event("e1", "approval", digest("a"), actor="human:a"))
        for stage in ("research", "plan", "write"):
            w = w.append(Event(stage, stage, digest(stage)))
        with self.assertRaises(WorkflowError):
            w.append(Event("v1", "validate", digest("qa"), revision=digest("old-draft")))
        w = w.append(Event("v1", "validate", digest("qa"), revision=digest("write")))
        with self.assertRaises(WorkflowError):
            w.append(Event("a1", "approval", digest("ok"), revision=digest("old-draft"), actor="human:reviewer"))
        with self.assertRaises(WorkflowError):
            w.append(Event("a1", "approval", digest("ok"), revision=digest("write"), actor="automated"))

    def test_duplicate_replay_and_conflict(self):
        w = Workflow("run", "bluesky", "API")
        e = Event("unique-event", "research", digest("research"))
        w = w.append(e)
        self.assertIs(w.append(e), w)
        with self.assertRaisesRegex(WorkflowError, "conflicting"):
            w.append(Event("unique-event", "research", digest("different")))

    def test_dispatch_cannot_forge_key_or_revision(self):
        w = build_through_approval()
        with self.assertRaises(WorkflowError):
            w.append(Event("dispatch", "dispatch", digest("random"), revision=w.events[2].evidence))
        with self.assertRaises(WorkflowError):
            w.append(Event("dispatch", "dispatch", w.intent_key(), revision=digest("stale")))

    def test_checkpoint_tamper_and_reorder_detected(self):
        w = build_through_approval()
        raw = json.loads(w.to_json())
        raw["network"] = "mastodon"
        with self.assertRaisesRegex(WorkflowError, "checksum"):
            Workflow.from_json(json.dumps(raw))
        raw = json.loads(w.to_json())
        raw["events"][1]["stage"] = "write"
        raw.pop("checksum")
        raw["checksum"] = digest(json.dumps(raw, sort_keys=True, ensure_ascii=True, separators=(",", ":")))
        with self.assertRaisesRegex(WorkflowError, "transition"):
            Workflow.from_json(json.dumps(raw))

    def test_reject_checkpoint_unknown_fields_schema_version_and_duplicate_keys(self):
        raw = json.loads(build_through_approval().to_json())
        raw["password"] = "must-never-be-stored"
        with self.assertRaises(WorkflowError):
            Workflow.from_json(json.dumps(raw))
        raw = json.loads(build_through_approval().to_json())
        raw["version"] = 2
        with self.assertRaisesRegex(WorkflowError, "version"):
            Workflow.from_json(json.dumps(raw))
        with self.assertRaises(WorkflowError):
            Workflow.from_json("[]")
        with self.assertRaises(WorkflowError):
            Workflow.from_json("broken-json")

    def test_checkpoint_contains_no_text_or_command_arguments(self):
        secret = "test-password-do-not-write"
        w = Workflow("synthetic", "instagram", "MOBILE")
        w = w.append(Event("research", "research", digest(secret)))
        self.assertNotIn(secret, w.to_json())

    def test_reject_invalid_opaque_identifiers_and_evidence(self):
        with self.assertRaises(WorkflowError):
            Workflow("name with spaces", "x", "WEB")
        with self.assertRaises(WorkflowError):
            Workflow("valid", "unknown", "WEB")
        with self.assertRaises(WorkflowError):
            Event("bad name", "research", digest("ok"))
        with self.assertRaises(WorkflowError):
            Event("okay", "research", "not-a-hash")
        with self.assertRaises(WorkflowError):
            Event("okay", "verify", digest("ack"), outcome="successful")

    def test_skills_are_traced_without_content(self):
        w = build_through_approval()
        self.assertEqual([e.tool_id for e in w.events[:3]], ["skill:research", "skill:plan", "skill:write"])
        self.assertNotIn("synthetic-write", w.to_json())
        with self.assertRaises(WorkflowError):
            Event("id", "research", digest("a"), tool_id="../../credential")

    def test_duplicate_json_keys_fail_closed(self):
        raw = build_through_approval().to_json()
        with self.assertRaisesRegex(WorkflowError, "duplicate"):
            Workflow.from_json(raw[:-1] + ',"network":"x"}')

    def test_checkpoint_unknown_does_not_count_as_confirmation(self):
        w = build_through_approval()
        w = w.append(Event("sent", "dispatch", w.intent_key(), revision=w.events[2].evidence))
        w = w.append(Event("receipt", "verify", digest("missing"), revision=w.events[2].evidence, outcome="unknown"))
        self.assertNotEqual(w.result, "confirmed")


class InspectorTests(unittest.TestCase):
    def test_preview_static_commands_without_arguments(self):
        pipeline = {"x": {"browser": True,
            "pre": [["python", "tools/x_scan.py", "secret-handle"], ["python", "tools/x_build_plan.py"]],
            "execute": ["python", "tools/x_execute.py", "session-token"], "post": []}}
        preview = inspect_pipeline("x", pipeline)
        self.assertEqual(preview["queue"], "WEB")
        self.assertEqual(preview["steps"]["prepare"], ["x_scan.py", "x_build_plan.py"])
        self.assertNotIn("secret", json.dumps(preview))
        self.assertNotIn("session", json.dumps(preview))

    def test_api_mobile_and_windows_paths(self):
        b = {"bluesky": {"pre": [], "build": ["python", "tools\\bluesky_build_plan.py"],
                           "execute": ["python", "tools\\bluesky_execute.py"]},
             "tiktok": {"phone": True, "pre": [], "execute": ["python", "tools/tiktok_growth_flow.py"]}}
        self.assertEqual(inspect_pipeline("bluesky", b)["queue"], "API")
        self.assertEqual(inspect_pipeline("bluesky", b)["steps"]["plan"], ["bluesky_build_plan.py"])
        self.assertEqual(inspect_pipeline("tiktok", b)["queue"], "MOBILE")
        with self.assertRaises(WorkflowError):
            inspect_pipeline("reddit", b)


if __name__ == "__main__":
    unittest.main()
