"""Synthetic, offline regression coverage for the trusted provenance inventory."""
from __future__ import annotations
import base64
import copy
import io
from contextlib import redirect_stderr
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import required_check_provenance as p

REPO = "example/sanitized"
HEAD, BASE = "a" * 40, "b" * 40
A = ".github/workflows/trusted-pr-hygiene.yml"
B = ".github/workflows/required-check-provenance.yml"
C = ".github/workflows/normal.yml"
TEMPLATE = "on: pull_request_target\njobs:\n  main:\n    name: {name}\n    runs-on: ubuntu-latest\n    steps: []\n"


def baseline():
    return {
        A: TEMPLATE.format(name="trusted-pr-paths"),
        B: TEMPLATE.format(name="trusted-check-provenance"),
        C: "on: pull_request\njobs:\n  ordinary:\n    name: normal (test)\n    runs-on: ubuntu-latest\n    steps: []\n",
    }


class FakeReader:
    def __init__(self, workflows, moved=False, truncate=False, changed=(), missing=(),
                 fork=None):
        self.data = workflows
        self.moved = moved
        self.truncate = truncate
        self.changed = set(changed)
        self.missing = set(missing)
        self.fork = fork
        self.snaps = 0
        self.calls = []

    def get(self, path):
        self.calls.append(path)
        if path == "/repos/" + REPO + "/pulls/96":
            self.snaps += 1
            return {
                "state": "open",
                "head": {"sha": ("c" * 40 if self.moved and self.snaps == 2 else HEAD),
                         "repo": {"full_name": self.fork or REPO}},
                "base": {"sha": BASE, "repo": {"full_name": REPO}},
            }
        assert "/contents/" in path, path
        source, suffix = path.split("/contents/", 1)
        ref = HEAD if suffix.endswith("?ref=" + HEAD) else BASE
        assert suffix.endswith("?ref=" + ref), path
        if ref == HEAD and self.fork:
            assert source == "/repos/" + self.fork
        else:
            assert source == "/repos/" + REPO
        name = suffix[:-len("?ref=" + ref)]
        if name == ".github/workflows":
            assert ref == HEAD
            files = [{"type": "file", "path": k} for k in self.data]
            if self.truncate:
                files.append({"type": "dir", "path": ".github/workflows/dummy"})
            return files
        if name in self.missing and ref == HEAD:
            return {"path": name, "type": "file", "sha": None}
        if name in p.PROTECTED_TRUST:
            record = {"path": name, "type": "file",
                      "sha": ("f" if ref == HEAD and name in self.changed else "e") * 40}
            if ref == HEAD and name in self.data:
                record.update({"encoding": "base64",
                               "content": base64.b64encode(self.data[name].encode()).decode()})
            return record
        assert ref == HEAD
        return {
            "type": "file", "path": name, "encoding": "base64",
            "content": base64.b64encode(self.data[name].encode()).decode(),
        }


class InventoryTests(unittest.TestCase):
    def test_legitimate_unrelated_workflows_preserved(self):
        self.assertEqual(p.audit_workflows(baseline()), p.OWNERS)
        f = baseline()
        f[C] += "  second:\n    name: completely unrelated\n    runs-on: windows-latest\n    steps: []\n"
        self.assertEqual(p.audit_workflows(f), p.OWNERS)

    def test_forged_status_from_pull_request_same_name(self):
        f = baseline()
        f[C] = "on: pull_request\njobs:\n  forged:\n    name: trusted-pr-paths\n    runs-on: ubuntu-latest\n    steps: []\n"
        with self.assertRaisesRegex(p.AuditError, "colliding"):
            p.audit_workflows(f)

    def test_whitespace_or_case_ambiguous_reserved_names(self):
        for name in ('" trusted-pr-paths "', '"TRUSTED-PR-PATHS"'):
            with self.subTest(name=name):
                workflows = baseline()
                workflows[C] = TEMPLATE.format(name=name)
                with self.assertRaises(p.AuditError):
                    p.audit_workflows(workflows)

    def test_forged_status_from_pull_request_target(self):
        f = baseline()
        f[C] = "on: pull_request_target\njobs:\n  forged:\n    name: trusted-check-provenance\n    runs-on: ubuntu-latest\n    steps: []\n"
        with self.assertRaisesRegex(p.AuditError, "colliding"):
            p.audit_workflows(f)

    def test_cross_event_push_merge_group_workflow_dispatch(self):
        for event in ("push", "merge_group", "workflow_dispatch", "workflow_call"):
            with self.subTest(event=event):
                f = baseline()
                f[C] = TEMPLATE.format(name="trusted-pr-paths").replace(
                    "pull_request_target", event)
                with self.assertRaises(p.AuditError):
                    p.audit_workflows(f)

    def test_duplicate_names_in_file_and_between_files(self):
        f = baseline()
        f[B] += "  duplicate:\n    name: trusted-pr-paths\n    runs-on: ubuntu-latest\n    steps: []\n"
        with self.assertRaises(p.AuditError):
            p.audit_workflows(f)

    def test_renamed_missing_owner_and_missing_job_name_fallback(self):
        for scenario in ("renamed", "missing"):
            with self.subTest(scenario=scenario):
                f = baseline()
                if scenario == "renamed":
                    f[A] = f[A].replace("trusted-pr-paths", "renamed")
                else:
                    del f[A]
                with self.assertRaises(p.AuditError):
                    p.audit_workflows(f)
        f = baseline()
        f[C] = "on: push\njobs:\n  trusted-pr-paths:\n    runs-on: ubuntu-latest\n    steps: []\n"
        with self.assertRaises(p.AuditError):
            p.audit_workflows(f)

    def test_skipped_gate_and_conditional_event(self):
        f = baseline()
        f[A] = f[A].replace("    runs-on:", "    if: false\n    runs-on:")
        with self.assertRaisesRegex(p.AuditError, "skipped"):
            p.audit_workflows(f)
        f = baseline()
        f[A] = f[A].replace("on: pull_request_target", "on: [pull_request, pull_request_target]")
        with self.assertRaisesRegex(p.AuditError, "non-target"):
            p.audit_workflows(f)
        f = baseline()
        f[A] = f[A].replace("on: pull_request_target", "on:\n  pull_request_target:\n    types: [opened]")
        with self.assertRaises(p.AuditError):
            p.audit_workflows(f)

    def test_dynamic_name_can_equal_required(self):
        for name in ('"DOLLAR_OPEN vars.CHECK }}"',
                     '"DOLLAR_OPEN matrix.name }}"',
                     '"trusted-DOLLAR_OPEN matrix.kind }}"'):
            with self.subTest(name=name):
                f = baseline()
                f[C] = TEMPLATE.format(name=name.replace("DOLLAR_OPEN", "$" + "{{"))
                with self.assertRaises(p.AuditError):
                    p.audit_workflows(f)
        # Fixed prefix/suffix prove it cannot ever become a reserved name.
        f = baseline()
        f[C] = TEMPLATE.format(name='"other (DOLLAR_OPEN matrix.os }})"'.replace(
            "DOLLAR_OPEN", "$" + "{{"))
        self.assertEqual(p.audit_workflows(f), p.OWNERS)

    def test_reserved_job_rejects_matrix_and_dynamic_name(self):
        for target, reserved in ((A, "trusted-pr-paths"),
                                 (B, "trusted-check-provenance")):
            with self.subTest(target=target, variation="matrix"):
                workflows = baseline()
                workflows[target] += (
                    "    strategy:\n      matrix:\n"
                    "        os: [ubuntu-latest, windows-latest]\n"
                )
                with self.assertRaisesRegex(p.AuditError, "matrix"):
                    p.audit_workflows(workflows)
            with self.subTest(target=target, variation="dynamic"):
                workflows = baseline()
                workflows[target] = workflows[target].replace(
                    "name: " + reserved,
                    'name: "DOLLAR_OPEN vars.GATE }}"'.replace("DOLLAR_OPEN", "$" + "{{")
                )
                with self.assertRaisesRegex(p.AuditError, "literal"):
                    p.audit_workflows(workflows)
            with self.subTest(target=target, variation="matrix-expression"):
                workflows = baseline()
                workflows[target] += (
                    '    strategy: "DOLLAR_OPEN fromJSON(vars.CONFIG) }}"\n'.replace(
                        "DOLLAR_OPEN", "$" + "{{")
                )
                with self.assertRaisesRegex(p.AuditError, "matrix"):
                    p.audit_workflows(workflows)

    def test_yaml_duplicate_keys_invalid_nested_and_on_key(self):
        self.assertIn("on", p.parse_workflow(baseline()[A], A))
        for text in (
            "on: pull_request\non: push\njobs: {}\n",
            "on: push\njobs:\n  a: {}\n  a: {}\n",
            "on: push\njobs: []\n",
            "on: push\njobs:\n  thing: nope\n",
        ):
            f = baseline()
            f[C] = text
            with self.subTest(text=text), self.assertRaises(p.AuditError):
                p.audit_workflows(f)

    def test_casefold_duplicate_workflows_and_oversize(self):
        f = baseline()
        f[".github/workflows/NORMAL.yml"] = f[C]
        with self.assertRaises(p.AuditError):
            p.audit_workflows(f)
        f = baseline()
        f[C] = "X" * (p.MAX_FILE_BYTES + 1)
        with self.assertRaises(p.AuditError):
            p.audit_workflows(f)

    def test_full_remote_inventory_and_current_sha(self):
        reader = FakeReader(baseline())
        self.assertEqual(p.check_pr(reader, REPO, 96, HEAD, BASE), p.OWNERS)
        self.assertEqual(reader.snaps, 2)
        self.assertIn("/repos/" + REPO + "/contents/.github/workflows?ref=" + HEAD,
                      reader.calls)
        for path in baseline():
            self.assertIn("/repos/" + REPO + "/contents/" + path + "?ref=" + HEAD,
                          reader.calls)

    def test_trusted_sources_cannot_be_replaced_by_no_op(self):
        # The job name/event remain unchanged, but executing a replaced gate
        # after merge would be a security regression.
        for protected in sorted(p.PROTECTED_TRUST):
            with self.subTest(file=protected):
                r = FakeReader(baseline(), changed={protected})
                with self.assertRaisesRegex(p.AuditError, "trusted source modified"):
                    p.check_pr(r, REPO, 96, HEAD, BASE)
        with self.assertRaisesRegex(p.AuditError, "missing trusted source"):
            p.check_pr(FakeReader(baseline(), missing={"tools/repo_hygiene.py"}),
                       REPO, 96, HEAD, BASE)

    def test_supervised_run_emits_pr_head_base_identity_from_trusted_event(self):
        root = Path(__file__).resolve().parents[1]
        yaml_text = (root / ".github/workflows/required-check-provenance.yml").read_text("utf-8")
        self.assertIn("trusted-event run_id=%s pr=%s head=%s base=%s", yaml_text)
        self.assertIn("AUDIT_HEAD: DOLLAR_OPEN github.event.pull_request.head.sha }}".replace(
            "DOLLAR_OPEN", "$" + "{{"), yaml_text)
        self.assertIn('"$GITHUB_RUN_ID"', yaml_text)
        self.assertNotIn("github.event.pull_request.head.repo.clone_url", yaml_text)

    def test_fork_reads_proposed_files_from_head_repository(self):
        reader = FakeReader(baseline(), fork="contributor/fork")
        self.assertEqual(p.check_pr(reader, REPO, 96, HEAD, BASE), p.OWNERS)
        self.assertIn("/repos/contributor/fork/contents/.github/workflows?ref=" + HEAD,
                      reader.calls)
        self.assertIn("/repos/" + REPO + "/contents/tools/repo_hygiene.py?ref=" + BASE,
                      reader.calls)

    def test_head_changes_between_snapshot_reads(self):
        with self.assertRaisesRegex(p.AuditError, "stale"):
            p.check_pr(FakeReader(baseline(), moved=True), REPO, 96, HEAD, BASE)

    def test_fail_closed_unsupported_inventory(self):
        with self.assertRaisesRegex(p.AuditError, "unexpected"):
            p.check_pr(FakeReader(baseline(), truncate=True), REPO, 96, HEAD, BASE)

    def test_validate_before_network(self):
        for repo, number, head in ((REPO, 0, HEAD), ("evil/path/extra", 96, HEAD), ("../repo", 96, HEAD),
                                   (REPO, 96, "not-a-sha")):
            reader = FakeReader(baseline())
            with self.subTest(repo=repo, number=number), self.assertRaises(p.AuditError):
                p.check_pr(reader, repo, number, head, BASE)
            self.assertEqual(reader.calls, [])

    def test_reader_missing_token_and_no_leak(self):
        with self.assertRaisesRegex(p.AuditError, "missing"):
            p.Reader("").get("/test")
        class Broken:
            def get(self, path):
                raise p.AuditError("remote unavailable")
        with patch.object(p, "Reader", return_value=Broken()):
            with patch.dict(p.os.environ, {"GITHUB_TOKEN": "synthetic-only"}):
                output = io.StringIO()
                with redirect_stderr(output):
                    self.assertEqual(p.main(["--repo", REPO, "--number", "96",
                                             "--head", HEAD, "--base", BASE]), 1)
                self.assertNotIn("synthetic-only", output.getvalue())


if __name__ == "__main__":
    unittest.main()
