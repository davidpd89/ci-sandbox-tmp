"""Offline synthetic Git regression tests, no network or accounts."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.append(str(ROOT / ".ci97-pr93-core" / "tools"))
import work_branch_push_hygiene as work
import git_history_paths as history


class WorkPushTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Synthetic")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.put("README.md")
        self.commit("root")
        self.base = self.head()
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        self.git("switch", "-qc", "ci/work")

    def git(self, *args):
        p = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf8", "replace"))
        return p.stdout.decode("utf8", "replace").strip()

    def head(self):
        return self.git("rev-parse", "HEAD")

    def put(self, path, content="synthetic text"):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf8")

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-qm", msg)
        return self.head()

    def event(self, *, before=None, after=None, ref="refs/heads/ci/work",
              created=False, deleted=False, forced=False):
        return dict(ref=ref, before=before if before is not None else self.base,
                    after=after if after is not None else self.head(),
                    created=created, deleted=deleted, forced=forced)

    def scan(self, event=None, expected=None, default_ref=work.DEFAULT_BASE_REF):
        e = event or self.event()
        return work.scan_work_push(e, root=self.root,
                                   expected_sha=expected or self.head(), default_ref=default_ref)

    def test_one_push_add_then_delete(self):
        self.put("secrets/transient.json")
        bad = self.commit("add forbidden")
        self.git("rm", "-q", "secrets/transient.json")
        self.commit("remove forbidden")
        self.assertEqual(self.git("diff", "--name-only", self.base, "HEAD"), "")
        self.assertEqual(self.scan(), ("fast-forward", [(bad, 1)]))

    def test_multiple_pushes_and_independent_event_ranges(self):
        self.put("docs/first.md"); previous = self.commit("first push")
        self.assertEqual(self.scan(), ("fast-forward", []))
        self.put("cache/interactions.csv"); bad = self.commit("second push")
        self.git("rm", "-q", "cache/interactions.csv"); self.commit("second clean")
        self.assertEqual(self.scan(self.event(before=previous)), ("fast-forward", [(bad, 1)]))
        previous = self.head()
        self.put("docs/third.md"); self.commit("third push")
        self.assertEqual(self.scan(self.event(before=previous)), ("fast-forward", []))

    def test_force_push_preserves_prior_failure_as_separate_event(self):
        self.put("secrets/transient.json"); bad = self.commit("previous exposure")
        self.assertEqual(self.scan(), ("fast-forward", [(bad, 1)]))
        self.git("reset", "--hard", self.base)
        self.put("docs/final.md"); self.commit("new force tip")
        self.assertEqual(self.scan(self.event(before=bad, forced=True)), ("rewrite", []))

    def test_force_missing_old_sha_fails_closed(self):
        self.put("docs/safe.md"); self.commit("new tip")
        with self.assertRaises(history.HistoryError):
            self.scan(self.event(before="f" * 40, forced=True))

    def test_created_from_historical_main_is_not_new_history(self):
        self.git("switch", "main")
        self.put("secrets/old.json"); old_bad = self.commit("old debt")
        self.git("rm", "-q", "secrets/old.json"); self.commit("old cleanup")
        self.git("update-ref", "refs/remotes/origin/main", self.head())
        self.git("switch", "-c", "research/old", old_bad)
        event = self.event(before="0"*40, created=True, ref="refs/heads/research/old")
        self.assertEqual(self.scan(event), ("created-existing", []))

    def test_created_branch_scans_divergence(self):
        self.put("secrets/new.json"); bad = self.commit("bad unpublished")
        self.git("rm", "-q", "secrets/new.json"); self.commit("removed unpublished")
        self.assertEqual(self.scan(self.event(before="0"*40, created=True)),
                         ("created", [(bad, 1)]))

    def test_orphan_root_then_delete(self):
        self.git("checkout", "--orphan", "feature/orphan")
        self.git("rm", "-rfq", ".")
        self.put("secrets/root.json"); bad = self.commit("orphan root")
        self.git("rm", "-q", "secrets/root.json"); self.commit("cleanup")
        event = self.event(before="0"*40, created=True, ref="refs/heads/feature/orphan")
        self.assertEqual(self.scan(event), ("created-orphan", [(bad, 1)]))

    def test_second_merge_parent(self):
        self.git("switch", "-qc", "topic")
        self.put("secrets/merge.json"); bad = self.commit("side forbidden")
        self.git("rm", "-q", "secrets/merge.json"); self.commit("side cleanup")
        self.git("switch", "ci/work")
        self.put("docs/work.md"); before = self.commit("work normal")
        self.git("merge", "--no-ff", "-qm", "merge topic", "topic")
        self.assertEqual(self.scan(self.event(before=before)), ("fast-forward", [(bad, 1)]))

    def test_force_merge_resurrects_already_seen_sensitive_path(self):
        self.git("switch", "-qc", "topic")
        self.put("secrets/returned.json"); self.commit("old side")
        self.git("switch", "ci/work")
        self.git("merge", "--no-ff", "-qm", "old merge", "topic")
        self.git("rm", "-q", "secrets/returned.json"); before = self.commit("clean")
        self.git("reset", "--hard", self.base)
        self.put("docs/new.md"); self.commit("rewrite")
        self.git("merge", "--no-ff", "-qm", "reintroduce", "topic"); merge = self.head()
        self.git("rm", "-q", "secrets/returned.json"); self.commit("clean again")
        self.assertEqual(self.scan(self.event(before=before, forced=True)), ("rewrite", [(merge, 1)]))

    def test_historical_debt_unchanged_and_then_modified(self):
        self.put("secrets/legacy.json"); self.commit("legacy")
        before = self.head()
        self.put("docs/safe.md"); self.commit("safe")
        self.assertEqual(self.scan(self.event(before=before)), ("fast-forward", []))
        self.put("secrets/legacy.json", "changed"); bad = self.commit("modified")
        self.assertEqual(self.scan(self.event(before=before)), ("fast-forward", [(bad, 1)]))

    def test_nul_paths_and_spaces(self):
        self.put("folder with spaces/metricas.csv"); bad = self.commit("spaced path")
        self.assertEqual(self.scan(), ("fast-forward", [(bad, 1)]))
        fake = b"secrets/with\nnewline.json\0safe name.txt\0"
        with patch.object(history, "git", return_value=fake):
            paths = history.touched_paths(self.root, self.head(), [])
        self.assertIn("secrets/with\nnewline.json", paths)
        self.assertIn("safe name.txt", paths)

    def test_deletion_sha_is_default_not_zero(self):
        event = self.event(after="0"*40, deleted=True)
        self.git("switch", "main")
        self.assertEqual(self.scan(event, expected=self.base), ("deleted", []))

    def test_deletion_missing_before_error(self):
        self.git("switch", "main")
        event = self.event(before="f"*40, after="0"*40, deleted=True)
        with self.assertRaises(history.HistoryError):
            self.scan(event, expected=self.base)

    def test_flags_missing_or_contradictory(self):
        e = self.event(); e.pop("created")
        with self.assertRaises(work.WorkPushError): self.scan(e)
        for change in ({"created":True}, {"deleted":True}, {"after":"0"*40},
                       {"before":"0"*40}, {"forced":"yes"}):
            e = self.event(); e.update(change)
            with self.subTest(change=change), self.assertRaises(work.WorkPushError):
                self.scan(e)

    def test_reject_tags_main_and_invalid_ref(self):
        for ref in ("refs/tags/v1", "refs/heads/main", "refs/heads/",
                    "refs/heads/unsafe..ref", None):
            with self.subTest(ref=ref), self.assertRaises(history.HistoryError):
                self.scan(self.event(ref=ref))

    def test_after_github_sha_and_head_must_agree(self):
        self.put("docs/new.md"); self.commit("new")
        with self.assertRaisesRegex(work.WorkPushError, "GITHUB_SHA"):
            self.scan(self.event(), expected=self.base)
        with self.assertRaisesRegex(work.WorkPushError, "event.after"):
            self.scan(self.event(before=self.head(), after=self.base))

    def test_missing_default_ref_error(self):
        with self.assertRaises(history.HistoryError):
            self.scan(self.event(before="0"*40, created=True),
                      default_ref="refs/remotes/origin/absent")

    def test_identical_before_after_invalid_update(self):
        with self.assertRaisesRegex(work.WorkPushError, "No changed"):
            self.scan(self.event(before=self.head()))

    def test_shallow_even_when_base_exists_fails_closed(self):
        self.put("docs/safe.md"); self.commit("two")
        original = history.git
        def proxy(root, *args):
            if args == ("rev-parse", "--is-shallow-repository"):
                return b"true\n"
            return original(root, *args)
        with patch.object(history, "git", side_effect=proxy):
            with self.assertRaisesRegex(history.HistoryError, "Shallow"):
                self.scan()

    def test_failed_ancestry_git_query_not_treated_as_rewrite(self):
        self.put("docs/new.md"); self.commit("new")
        def broken(*args, **kwargs):
            return subprocess.CompletedProcess(args, 128, b"", b"mock git error")
        before, after = self.base, self.head()
        with patch.object(work.subprocess, "run", side_effect=broken):
            with self.assertRaisesRegex(work.WorkPushError, "query"):
                work._ancestor(self.root, before, after)

    def test_failed_merge_base_is_not_classified_as_orphan(self):
        self.put("docs/new.md"); self.commit("new")
        with patch.object(work, "_git_predicate",
                          side_effect=work.WorkPushError("Git merge-base query failed")):
            with self.assertRaisesRegex(work.WorkPushError, "query"):
                self.scan(self.event(before="0"*40, created=True))

    def test_nonexistent_after_commit_error(self):
        with self.assertRaises(history.HistoryError):
            self.scan(self.event(after="e"*40), expected="e"*40)

    def test_invalid_event_file_cli_exit_two_without_paths(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                         encoding="utf8", delete=False) as f:
            f.write("{bad json")
            name = f.name
        self.addCleanup(lambda: os.unlink(name))
        with patch.dict(os.environ, {"GITHUB_EVENT_PATH": name,
                                     "GITHUB_SHA": self.head()}):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                code = work.main()
        self.assertEqual(code, 2)
        self.assertNotIn("secrets/", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
