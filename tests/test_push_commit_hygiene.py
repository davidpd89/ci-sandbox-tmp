"""Synthetic Git DAG regression tests. No accounts, secrets or external network."""
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import git_history_paths as gh
import push_commit_hygiene as push


class PushCommitTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Synthetic")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.write("README.md")
        self.commit("root")
        self.base = self.head()

    def git(self, *args, ok=True):
        proc = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True)
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        return proc.stdout.decode("utf-8", "replace").strip()

    def head(self):
        return self.git("rev-parse", "HEAD")

    def write(self, name, content="synthetic\n"):
        p = self.repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def commit(self, name):
        self.git("add", "-A")
        self.git("commit", "-qm", name)

    def event(self, before=None):
        return {"ref": "refs/heads/main", "before": self.base if before is None else before,
                "after": self.head(), "forced": False}

    def scan(self, before=None):
        return push.scan_push(self.event(before), root=self.repo, expected_sha=self.head())

    def test_added_then_deleted_in_single_push(self):
        self.write("cache/metricas.csv")
        self.commit("add sensitive")
        offender = self.head()
        (self.repo / "cache/metricas.csv").unlink()
        self.commit("remove sensitive")
        self.assertEqual(self.git("diff", "--name-only", self.base, "HEAD"), "")
        self.assertEqual(self.scan(), [(offender, 1)])

    def test_multiple_safe_commits(self):
        for i in range(3):
            self.write(f"docs/safe{i}.md")
            self.commit(f"safe {i}")
        self.assertEqual(self.scan(), [])

    def test_unchanged_historical_debt_and_modified_debt(self):
        self.write("secrets/old.json")
        self.commit("legacy")
        old = self.head()
        self.write("safe.md")
        self.commit("safe")
        self.assertEqual(self.scan(old), [])
        self.write("secrets/old.json", "updated")
        self.commit("modified")
        self.assertEqual(self.scan(old), [(self.head(), 1)])

    def test_rename_into_sensitive_and_deletion_only(self):
        self.write("notes/safe.txt")
        self.commit("safe")
        self.git("mv", "notes/safe.txt", "notes/tokens.json")
        self.commit("rename")
        self.assertEqual(self.scan(), [(self.head(), 1)])
        before = self.head()
        self.git("rm", "notes/tokens.json")
        self.commit("delete")
        self.assertEqual(self.scan(before), [])

    def test_type_change_to_gitlink(self):
        self.write("profile/credentials.json")
        self.commit("legacy")
        before = self.head()
        self.git("update-index", "--add", "--cacheinfo", f"160000,{self.base},profile/credentials.json")
        self.git("commit", "-qm", "type change")
        self.assertEqual(self.scan(before), [(self.head(), 1)])

    def test_new_merge_second_parent_commit_detected(self):
        self.git("switch", "-qc", "topic")
        self.write("secrets/transient.json")
        self.commit("topic unsafe")
        bad = self.head()
        self.git("rm", "secrets/transient.json")
        self.commit("topic clean")
        self.git("switch", "main")
        self.write("docs/main.md")
        self.commit("main safe")
        before = self.head()
        self.git("merge", "--no-ff", "-qm", "merge topic", "topic")
        self.assertEqual(self.scan(before), [(bad, 1)])

    def test_merge_inherited_sensitive_debt_not_flagged(self):
        self.git("switch", "-qc", "topic")
        self.write("secrets/legacy.json")
        self.commit("old debt")
        self.git("switch", "main")
        self.git("merge", "--no-ff", "-qm", "historical merge", "topic")
        before = self.head()
        self.git("switch", "-qc", "feature")
        self.write("safe.txt")
        self.commit("safe feature")
        self.git("switch", "main")
        self.write("docs/main.md")
        self.commit("safe main")
        self.git("merge", "--no-ff", "-qm", "merge feature", "feature")
        self.assertEqual(self.scan(before), [])

    def test_merge_resolution_sensitive_path(self):
        self.git("switch", "-qc", "topic")
        self.write("docs/topic.md")
        self.commit("topic")
        self.git("switch", "main")
        self.write("docs/main.md")
        self.commit("main")
        before = self.head()
        self.git("merge", "--no-commit", "topic")
        self.write("secrets/new-merge.json")
        self.commit("merge with new path")
        self.assertEqual(self.scan(before), [(self.head(), 1)])

    def test_force_merge_resurrects_already_reachable_sensitive_path(self):
        # The old side-branch commit is excluded from after ^ before:
        # only the new merge introduces this transient path to main.
        self.git("switch", "-qc", "historical-topic")
        self.write("secrets/returned.json")
        self.commit("old sensitive branch")
        self.git("switch", "main")
        self.git("merge", "--no-ff", "-qm", "old merge", "historical-topic")
        self.git("rm", "secrets/returned.json")
        self.commit("old cleanup")
        before = self.head()
        self.git("reset", "--hard", self.base)
        self.write("docs/new-tip.md")
        self.commit("divergent tip")
        self.git("merge", "--no-ff", "-qm", "reintroduce old topic", "historical-topic")
        merge = self.head()
        self.git("rm", "secrets/returned.json")
        self.commit("remove transient")
        self.assertEqual(self.git("diff", "--name-only", before, "HEAD"), "docs/new-tip.md")
        self.assertEqual(self.scan(before), [(merge, 1)])

    def test_force_rewind_to_safe_ancestor_is_clean(self):
        self.write("docs/new-safe.md")
        self.commit("safe tip")
        old = self.head()
        self.git("reset", "--hard", self.base)
        self.assertEqual(self.scan(old), [])

    def test_force_rewind_restores_sensitive_path(self):
        self.write("cache/metricas.csv")
        self.commit("historical sensitive")
        restored = self.head()
        self.git("rm", "cache/metricas.csv")
        self.commit("historical cleanup")
        old = self.head()
        self.git("reset", "--hard", restored)
        self.assertEqual(self.scan(old), [(restored, 1)])

    def test_force_divergent_before(self):
        self.write("docs/previous.md")
        self.commit("old tip")
        old = self.head()
        self.git("reset", "--hard", self.base)
        self.write("cache/metricas.csv")
        self.commit("new force tip")
        self.assertEqual(self.scan(old), [(self.head(), 1)])

    def test_force_divergent_safe(self):
        self.write("safe1.md")
        self.commit("old")
        old = self.head()
        self.git("reset", "--hard", self.base)
        self.write("safe2.md")
        self.commit("new")
        self.assertEqual(self.scan(old), [])

    def test_zero_before_scans_transient_ancestry(self):
        self.write("secrets/temporary.json")
        self.commit("sensitive")
        bad = self.head()
        self.git("rm", "secrets/temporary.json")
        self.commit("clean")
        self.assertEqual(self.scan("0" * 40), [(bad, 1)])

    def test_missing_before_fails_closed(self):
        self.write("safe.md")
        self.commit("safe")
        with self.assertRaises(gh.HistoryError):
            self.scan("f" * 40)

    def test_shallow_fails_closed(self):
        self.write("safe.md")
        self.commit("safe")
        original = gh.git
        def fake_git(root, *args):
            if args == ("rev-parse", "--is-shallow-repository"):
                return b"true\n"
            return original(root, *args)
        with patch.object(gh, "git", side_effect=fake_git):
            with self.assertRaisesRegex(gh.HistoryError, "Shallow"):
                self.scan()

    def test_limit_fails_closed(self):
        self.write("safe1.md")
        self.commit("safe1")
        self.write("safe2.md")
        self.commit("safe2")
        with self.assertRaisesRegex(gh.HistoryError, "limit"):
            gh.commits_in_range(self.repo, self.base, self.head(), limit=1)

    def test_malformed_event_and_checkout_mismatch(self):
        for bad in ("HEAD^", "-option", "", "0" * 39, None):
            e = self.event()
            e["before"] = bad
            with self.subTest(bad=bad), self.assertRaises(gh.HistoryError):
                push.scan_push(e, root=self.repo, expected_sha=self.head())
        e = self.event()
        e["after"] = "0" * 40
        with self.assertRaises(push.PushEventError):
            push.scan_push(e, root=self.repo, expected_sha=e["after"])
        with self.assertRaises(push.PushEventError):
            push.scan_push(self.event(), root=self.repo, expected_sha="f" * 40)
        e = self.event()
        e["ref"] = "refs/heads/other"
        with self.assertRaises(push.PushEventError):
            push.scan_push(e, root=self.repo, expected_sha=self.head())

    def test_nul_paths_and_windows_portability(self):
        # NTFS rejects newline filenames: mock the -z data instead.
        fake = b"secrets/with\\nnewline.json\0safe name.txt\0".replace(b"\\n", b"\n")
        with patch.object(gh, "git", return_value=fake):
            paths = gh.touched_paths(self.repo, self.head(), [])
        self.assertIn("secrets/with\nnewline.json", paths)
        self.assertIn("safe name.txt", paths)
        self.write("folder with space/metricas.csv")
        self.commit("space")
        self.assertEqual(self.scan(), [(self.head(), 1)])

    def test_invalid_utf8_git_path_fails_closed(self):
        # Git supports arbitrary path bytes on Unix; Windows cannot construct
        # this fixture directly. Do not silently classify a decoded surrogate.
        malformed = b"credentials.json\\xff\\0".replace(b"\\xff", bytes([255])).replace(b"\\0", bytes([0]))
        with patch.object(gh, "git", return_value=malformed):
            with self.assertRaises(UnicodeDecodeError):
                gh.touched_paths(self.repo, self.head(), [])

    def test_root_commit_sensitive_on_first_push(self):
        # An orphan first push must inspect the root commit, not only its tip.
        self.git("checkout", "--orphan", "first")
        self.git("rm", "-rfq", ".")
        self.write("secrets/root.json")
        self.commit("root sensitive")
        root_sha = self.head()
        self.git("rm", "secrets/root.json")
        self.commit("remove root secret")
        self.assertEqual(self.scan("0" * 40), [(root_sha, 1)])

    def test_force_to_unrelated_orphan_history(self):
        self.git("checkout", "--orphan", "replace")
        self.git("rm", "-rfq", ".")
        self.write("docs/only-safe.md")
        self.commit("unrelated root")
        self.write("cache/metricas.csv")
        self.commit("unrelated sensitive")
        self.assertEqual(self.scan(), [(self.head(), 1)])

    def test_same_sha_before_after_is_not_a_verified_push(self):
        with self.assertRaisesRegex(gh.HistoryError, "No commits"):
            self.scan(self.head())

    def test_real_shallow_clone_fails_closed(self):
        self.write("docs/safe.md")
        self.commit("second commit")
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "shallow"
            proc = subprocess.run(["git", "clone", "-q", "--depth", "1",
                                   "--no-local", self.repo.as_uri(), str(target)],
                                  capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            self.assertEqual(gh.git(target, "rev-parse", "--is-shallow-repository").strip(), b"true")
            with self.assertRaisesRegex(gh.HistoryError, "Shallow"):
                gh.commits_in_range(target, None, self.head())

    def test_sensitive_path_on_unix_casefold(self):
        self.write("SISTEMA_DIARIO_X/METRICAS.CSV")
        self.commit("sensitive uppercase")
        self.assertEqual(self.scan(), [(self.head(), 1)])

    def test_replace_ref_cannot_override_history_truth(self):
        self.write("secrets/replaced.json")
        self.commit("unsafe unreachable commit")
        replacement = self.head()
        self.git("reset", "--hard", self.base)
        self.write("docs/safe.md")
        self.commit("safe commit")
        safe = self.head()
        self.git("replace", safe, replacement)
        self.assertEqual(self.scan(), [])

    def test_git_history_scanner_disables_lazy_fetch(self):
        original = subprocess.run
        observed = []

        def watch(*args, **kwargs):
            observed.append(kwargs.get("env"))
            return original(*args, **kwargs)

        with patch.object(gh.subprocess, "run", side_effect=watch):
            gh.git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(len(observed), 1)
        for key in ("GIT_NO_LAZY_FETCH", "GIT_TERMINAL_PROMPT", "GIT_NO_REPLACE_OBJECTS"):
            self.assertEqual(observed[0].get(key), "1" if key != "GIT_TERMINAL_PROMPT" else "0")

    def test_cli_does_not_leak_path_contents(self):
        self.write("secrets/synthetic-name.json")
        self.commit("bad")
        event_file = self.repo / "push.json"
        event_file.write_text(json.dumps(self.event()), encoding="utf-8")
        output = io.StringIO()
        with patch.object(push.repo_hygiene, "ROOT", self.repo), patch.dict(os.environ, {
            "GITHUB_EVENT_PATH": str(event_file), "GITHUB_SHA": self.head(),
        }), contextlib.redirect_stderr(output):
            self.assertEqual(push.main(), 1)
        self.assertIn("PUSH HISTORY FAIL", output.getvalue())
        self.assertNotIn("synthetic-name", output.getvalue())


if __name__ == "__main__":
    unittest.main()
