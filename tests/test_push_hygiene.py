"""Git-only, synthetic push-range regression tests (Windows and Ubuntu)."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import push_hygiene as ph
import repo_hygiene as rh


class PushHygieneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic CI")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.write("README.md", "root\n")
        self.commit("root")
        self.first = self.sha()

    def git(self, *args):
        p = subprocess.run(["git", "-C", str(self.root), *args], text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def sha(self):
        return self.git("rev-parse", "HEAD")

    def write(self, name, content="synthetic fixture\n"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def event(self, before=None, after=None):
        return {"ref": "refs/heads/main", "before": before or self.first,
                "after": after or self.sha(), "forced": False, "created": False}

    def offenders(self, event):
        return rh.violations_for_paths(ph.push_paths(event, root=self.root, expected_sha=event["after"]))

    def test_multicommit_including_sensitive_second_commit(self):
        self.write("docs/update.md")
        self.commit("safe first")
        self.write("nested/metricas.csv")
        self.commit("unsafe second")
        self.assertEqual(self.offenders(self.event()), ["nested/metricas.csv"])
        self.write("tools/new_script.py")
        self.commit("safe third")
        self.assertEqual(self.offenders(self.event()), ["nested/metricas.csv"])

    def test_historic_unchanged_forbidden_path_is_not_rejected(self):
        self.write("legacy/metricas.csv")
        self.commit("existing historical debt")
        before = self.sha()
        self.write("tools/hello.py")
        self.commit("legitimate change")
        self.assertEqual(self.offenders(self.event(before)), [])

    def test_first_push_scans_tracked_tree(self):
        self.write("profile/credentials.json")
        self.commit("new branch snapshot")
        ev = self.event("0" * 40)
        self.assertEqual(self.offenders(ev), ["profile/credentials.json"])

    def test_first_push_without_sensitive_files_passes(self):
        self.assertEqual(self.offenders(self.event("0" * 40)), [])

    def test_force_update_uses_two_trees_even_when_unrelated(self):
        self.write("safe.txt")
        self.commit("old tip")
        old_tip = self.sha()
        self.git("reset", "--hard", self.first)
        self.write("accounts/answers.json")
        self.commit("force rewritten tip")
        self.assertEqual(self.offenders(self.event(old_tip)), ["accounts/answers.json"])

    def test_missing_before_fails_closed(self):
        self.write("safe.txt")
        self.commit("tip")
        with self.assertRaisesRegex(ph.PushRangeError, "no disponible"):
            self.offenders(self.event("f" * 40))

    def test_invalid_before_missing_or_injection_fails(self):
        for bad in [None, "", "HEAD^1", "--bad", "0" * 39, "x" * 40]:
            event = self.event()
            event["before"] = bad
            with self.subTest(bad=bad), self.assertRaises(ph.PushRangeError):
                self.offenders(event)

    def test_after_or_checkout_mismatch_fails(self):
        event = self.event()
        event["after"] = "e" * 40
        with self.assertRaisesRegex(ph.PushRangeError, "no coincide"):
            ph.push_paths(event, root=self.root, expected_sha=self.sha())
        with self.assertRaisesRegex(ph.PushRangeError, "no coincide"):
            ph.push_paths(self.event(), root=self.root, expected_sha="b" * 40)

    def test_push_only_main_and_deleted_event_rejected(self):
        event = self.event()
        event["ref"] = "refs/heads/feature"
        with self.assertRaises(ph.PushRangeError):
            self.offenders(event)
        event = self.event()
        event["after"] = "0" * 40
        with self.assertRaises(ph.PushRangeError):
            self.offenders(event)

    def test_windows_style_names_and_rename_into_forbidden(self):
        self.write("notes/regular.txt")
        self.commit("safe")
        self.git("mv", "notes/regular.txt", "notes/tokens.json")
        self.commit("rename")
        self.assertEqual(self.offenders(self.event()), ["notes/tokens.json"])

    def test_deleted_forbidden_path_not_part_of_final_tree(self):
        self.write("legacy/pending.json")
        self.commit("old")
        before = self.sha()
        self.git("rm", "legacy/pending.json")
        self.commit("deleted")
        self.assertEqual(self.offenders(self.event(before)), [])

    def test_cli_reads_event_file_and_checks_expected_sha(self):
        self.write("new/answers.json")
        self.commit("unsafe")
        event_file = Path(self.temp.name) / "event.json"
        event_file.write_text(json.dumps(self.event()), encoding="utf-8")
        with patch.object(rh, "ROOT", self.root), patch.dict(os.environ, {
                "GITHUB_EVENT_PATH": str(event_file), "GITHUB_SHA": self.sha()}), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ph.main(), 1)
        with patch.object(rh, "ROOT", self.root), patch.dict(os.environ, {
                "GITHUB_EVENT_PATH": str(event_file), "GITHUB_SHA": "f" * 40}), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ph.main(), 2)

    def test_missing_event_file_fails_closed(self):
        with patch.dict(os.environ, {"GITHUB_EVENT_PATH": ""}), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ph.main(), 2)


class WorkflowPushContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/validate-social-tools.yml").read_text(encoding="utf-8")

    def test_event_scopes_and_explicit_manual_semantics(self):
        self.assertIn("  pull_request:", self.workflow)
        self.assertIn("    branches: [main]", self.workflow)
        self.assertIn("  workflow_dispatch:", self.workflow)
        self.assertIn("if: github.event_name == 'push'", self.workflow)
        self.assertIn("python tools/push_hygiene.py", self.workflow)
        self.assertIn("if: github.event_name == 'pull_request'", self.workflow)
        self.assertIn('repo_hygiene.py --base "HEAD^1"', self.workflow)

    def test_before_never_replaced_by_first_parent(self):
        self.assertIn("fetch-depth: 0", self.workflow)
        self.assertIn("fetch-depth: 2", self.workflow)
        self.assertLess(self.workflow.index("python tools/push_hygiene.py"),
                        self.workflow.index("python -m pip install"))
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertIn("contents: read", self.workflow)
        self.assertNotIn("pull_request_target", self.workflow)
        self.assertNotIn("secrets.", self.workflow)


if __name__ == "__main__":
    unittest.main()
