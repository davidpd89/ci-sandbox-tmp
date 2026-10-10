"""Synthetic Git DAG tests for PR history hygiene. No network or real state."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import pr_commit_hygiene as h


class PRHistoryTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = pathlib.Path(t.name)
        self.git("init", "-q", "-b", "base")
        self.git("config", "user.name", "Synthetic")
        self.git("config", "user.email", "synthetic@example.invalid")
        self.write("README.md")
        self.commit("init")
        self.initial = self.oid()

    def git(self, *args, check=True):
        return subprocess.run(["git", "-C", str(self.root), *args],
                              capture_output=True, check=check)

    def oid(self):
        return self.git("rev-parse", "HEAD").stdout.decode().strip()

    def write(self, path, value="synthetic\n"):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value, encoding="utf-8")

    def commit(self, msg):
        self.git("add", "-A")
        self.git("commit", "-qm", msg)

    def topic(self):
        self.git("switch", "-qc", "topic")

    def audit(self, base=None):
        return h.scan_pr(base or self.initial, self.oid(), root=self.root)

    def test_added_then_deleted_is_still_reported(self):
        self.topic()
        self.write("secrets/temp.json")
        self.commit("add")
        offending = self.oid()
        (self.root / "secrets/temp.json").unlink()
        self.commit("delete")
        self.assertEqual(self.git("diff", "--name-only", self.initial, "HEAD").stdout, b"")
        self.assertEqual(self.audit(), [(offending, 1)])

    def test_base_existing_path_not_flagged_unless_changed(self):
        self.write("secrets/legacy.json")
        self.commit("baseline")
        base = self.oid()
        self.topic()
        self.write("safe.md")
        self.commit("safe")
        self.assertEqual(self.audit(base), [])
        self.write("secrets/legacy.json", "changed\n")
        self.commit("modify")
        self.assertEqual(self.audit(base), [(self.oid(), 1)])

    def test_delete_of_preexisting_path_is_allowed(self):
        self.write("secrets/legacy.json")
        self.commit("baseline")
        base = self.oid()
        self.topic()
        (self.root / "secrets/legacy.json").unlink()
        self.commit("cleanup")
        self.assertEqual(self.audit(base), [])

    def test_rename_destination_is_a_new_path(self):
        self.topic()
        self.write("ordinary.json")
        self.commit("ordinary")
        self.git("mv", "ordinary.json", "credentials.json")
        self.commit("rename")
        self.assertEqual(self.audit(), [(self.oid(), 1)])

    def test_typechange_is_detected_without_os_symlink(self):
        self.topic()
        self.write("secrets/demo.json")
        self.commit("before")
        first = self.oid()
        blob = self.git("hash-object", "-w", "README.md").stdout.decode().strip()
        self.git("update-index", "--cacheinfo", f"120000,{blob},secrets/demo.json")
        self.git("commit", "-qm", "typechange")
        self.assertEqual(self.audit(), [(first, 1), (self.oid(), 1)])

    def test_spaces_in_real_git_paths_and_newline_in_git_nul_output(self):
        from unittest import mock

        self.topic()
        self.write("folder with space/secrets/ordinary.json")
        self.commit("path")
        self.assertEqual(self.audit(), [(self.oid(), 1)])
        # NTFS cannot create a newline pathname, but Git's -z parser still must
        # handle such raw byte output. This fixture is intentionally synthetic.
        payload = b"folder with space/secrets/odd\\nname.json".replace(b"\\n", bytes([10]))
        payload += bytes([0]) + b"normal.txt" + bytes([0])
        with mock.patch.object(h, "git", return_value=payload):
            parsed = h.changes(self.root, "parent", "commit")
        self.assertEqual(parsed, {"folder with space/secrets/odd\nname.json", "normal.txt"})
        self.assertTrue(all(h.forbidden_path(p) for p in parsed if p != "normal.txt"))

    def test_invalid_utf8_path_fails_closed_even_when_absent_in_final_diff(self):
        from unittest import mock

        # Git supports arbitrary filename bytes on some filesystems. A
        # transient invalid path must not be silently decoded/reclassified.
        raw = b"normal.txt\\0credentials.json\\xff\\0".replace(b"\\0", bytes([0])).replace(b"\\xff", bytes([255]))
        with mock.patch.object(h, "git", return_value=raw):
            with self.assertRaises(UnicodeDecodeError):
                h.changes(self.root, "parent", "commit")

    def test_merging_new_base_does_not_import_false_positive(self):
        self.topic()
        self.write("topic.md")
        self.commit("topic")
        self.git("switch", "base")
        self.write("secrets/from-base.json")
        self.commit("baseline")
        base = self.oid()
        self.git("switch", "topic")
        self.git("merge", "--no-ff", "-qm", "merge baseline", "base")
        self.assertEqual(self.audit(base), [])

    def test_merge_resurrects_secret_from_already_reachable_side_history(self):
        self.git("switch", "-qc", "side")
        self.write("secrets/from-side.json")
        self.commit("old side path")
        self.git("switch", "base")
        self.git("merge", "--no-ff", "-qm", "import side", "side")
        (self.root / "secrets/from-side.json").unlink()
        self.commit("base removes old path")
        base = self.oid()
        self.git("switch", "side")
        self.write("side-safe.txt")
        self.commit("benign side update")
        self.git("switch", "-qc", "topic", base)
        self.write("topic.txt")
        self.commit("benign topic update")
        self.git("merge", "--no-ff", "--no-commit", "side")
        self.git("restore", "--source", "side", "--staged", "--worktree", "secrets/from-side.json")
        self.git("commit", "-qm", "merge resurrects old path")
        self.assertEqual(self.audit(base), [(self.oid(), 1)])

    def test_merge_reverts_modified_sensitive_file_from_old_side_history(self):
        self.git("switch", "-qc", "side")
        self.write("secrets/from-side.json", "old\n")
        self.commit("old side version")
        self.git("switch", "base")
        self.git("merge", "--no-ff", "-qm", "import side", "side")
        self.write("secrets/from-side.json", "current\n")
        self.commit("base updates path")
        base = self.oid()
        self.git("switch", "side")
        self.write("side-safe.txt")
        self.commit("benign side update")
        self.git("switch", "-qc", "topic", base)
        self.write("topic.txt")
        self.commit("benign topic update")
        self.git("merge", "--no-ff", "--no-commit", "side")
        self.git("restore", "--source", "side", "--staged", "--worktree", "secrets/from-side.json")
        self.git("commit", "-qm", "merge reverts sensitive path")
        self.assertEqual(self.audit(base), [(self.oid(), 1)])

    def test_merge_of_old_base_ancestor_is_not_misattributed(self):
        self.topic()
        self.write("topic.txt")
        self.commit("topic")
        self.git("switch", "base")
        self.write("secrets/legacy.json", "version-one\n")
        self.commit("base version one")
        self.git("switch", "topic")
        self.git("merge", "--no-ff", "-qm", "merge earlier base", "base")
        self.git("switch", "base")
        self.write("secrets/legacy.json", "version-two\n")
        self.commit("base version two")
        current_base = self.oid()
        self.git("switch", "topic")
        self.assertEqual(self.audit(current_base), [])

    def test_new_merge_resolution_is_detected(self):
        self.topic()
        self.write("docs/text.txt", "topic\n")
        self.commit("topic")
        self.git("switch", "base")
        self.write("docs/text.txt", "base\n")
        self.commit("base")
        base = self.oid()
        self.git("switch", "topic")
        self.git("merge", "--no-commit", "base", check=False)
        self.write("docs/text.txt", "merged\n")
        self.write("secrets/created-on-merge.json")
        self.commit("resolve")
        self.assertEqual(self.audit(base), [(self.oid(), 1)])

    def test_rebase_when_base_advances(self):
        self.topic()
        self.write("README.md", "topic\n")
        self.commit("topic")
        self.git("switch", "base")
        self.write("secrets/base.json")
        self.commit("advance")
        base = self.oid()
        self.git("switch", "topic")
        self.git("rebase", "base")
        self.assertEqual(self.audit(base), [])

    def test_pr_merge_parents_and_nonmerge_rejection(self):
        with self.assertRaises(ValueError):
            h.pr_parents(self.root)
        self.topic()
        self.write("topic.txt")
        self.commit("topic")
        head = self.oid()
        self.git("switch", "base")
        self.git("merge", "--no-ff", "-qm", "PR synthetic merge", "topic")
        self.assertEqual(h.pr_parents(self.root), (self.initial, head))

    def test_cli_failure_reports_only_commit_and_count(self):
        import contextlib
        import io
        from unittest import mock

        out = io.StringIO()
        with mock.patch.object(h, "pr_parents", return_value=(self.initial, self.initial)):
            with mock.patch.object(h, "scan_pr", return_value=[("a" * 40, 2)]):
                with contextlib.redirect_stderr(out):
                    code = h.main([])
        self.assertEqual(code, 1)
        self.assertIn("aaaaaaaaaaaa", out.getvalue())
        self.assertIn("2 forbidden paths", out.getvalue())
        self.assertNotIn("credentials.json", out.getvalue())

    def test_empty_commit_range_is_not_silently_approved(self):
        with self.assertRaises(ValueError):
            h.scan_pr(self.initial, self.initial, root=self.root)

    def test_add_delete_readd_and_modify_are_each_audited(self):
        self.topic()
        self.write("secrets/repeated.json", "first")
        self.commit("add")
        first = self.oid()
        (self.root / "secrets/repeated.json").unlink()
        self.commit("delete")
        self.write("secrets/repeated.json", "second")
        self.commit("readd")
        second = self.oid()
        self.write("secrets/repeated.json", "third")
        self.commit("modify")
        third = self.oid()
        self.assertEqual(self.audit(), [(first, 1), (second, 1), (third, 1)])

    def test_octopus_merge_resurrects_sensitive_path(self):
        self.git("switch", "-qc", "side1")
        self.write("secrets/old.json")
        self.commit("old path")
        self.git("switch", "base")
        self.git("merge", "--no-ff", "-qm", "old import", "side1")
        (self.root / "secrets/old.json").unlink()
        self.commit("base removes")
        base = self.oid()
        self.git("switch", "side1")
        self.write("side1.txt")
        self.commit("side update")
        side1 = self.oid()
        self.git("switch", "-qc", "side2", self.initial)
        self.write("side2.txt")
        self.commit("other side")
        side2 = self.oid()
        self.git("switch", "-qc", "topic", base)
        self.write("topic.txt")
        self.commit("topic")
        first_parent = self.oid()
        # Create a synthetic three-parent merge with a deliberately restored
        # sensitive path. commit-tree preserves the exact octopus DAG on NTFS.
        self.git("restore", "--source", side1, "--staged", "--worktree", "secrets/old.json")
        tree = self.git("write-tree").stdout.decode().strip()
        merged = self.git("commit-tree", tree, "-p", first_parent,
                          "-p", side1, "-p", side2, "-m", "octopus restore").stdout.decode().strip()
        self.git("reset", "--hard", merged)
        self.assertEqual(self.audit(base), [(merged, 1)])

    def test_merge_from_side_first_parent_does_not_import_base_path(self):
        self.topic()
        self.write("topic.txt")
        self.commit("side first")
        self.git("switch", "base")
        self.write("secrets/from-base.json")
        self.commit("new base")
        base = self.oid()
        self.git("switch", "topic")
        self.git("merge", "--no-ff", "-qm", "import base second", "base")
        self.assertEqual(self.audit(base), [])

    def test_gitlink_to_forbidden_path_detected_without_network(self):
        self.topic()
        self.git("update-index", "--add", "--cacheinfo",
                 f"160000,{self.initial},secrets/submodule")
        self.git("commit", "-qm", "synthetic gitlink")
        self.assertEqual(self.audit(), [(self.oid(), 1)])

    def test_squash_checks_current_dag_not_abandoned_commits(self):
        self.topic()
        self.write("secrets/abandoned.json")
        self.commit("formerly bad")
        (self.root / "secrets/abandoned.json").unlink()
        self.write("safe.txt")
        self.commit("safe final change")
        self.assertEqual(len(self.audit()), 1)
        self.git("reset", "--soft", self.initial)
        self.git("commit", "-qm", "squashed clean current state")
        self.assertEqual(self.audit(), [])
        # Historical remote objects before force-push are outside this
        # *current* DAG. Their absence is not proof they were never exposed.

    def test_unicode_paths_are_kept_distinct_and_processed(self):
        from unittest import mock
        import unicodedata

        nfc = "secrets/caf\u00e9.json"
        nfd = unicodedata.normalize("NFD", nfc)
        self.assertNotEqual(nfc, nfd)
        output = nfc.encode() + bytes([0]) + nfd.encode() + bytes([0])
        with mock.patch.object(h, "git", return_value=output):
            result = h.changes(self.root, "a", "b")
        self.assertEqual(result, {nfc, nfd})
        self.assertTrue(all(h.forbidden_path(p) for p in result))

    def test_commit_limit_is_fail_closed(self):
        self.topic()
        self.write("safe.txt")
        self.commit("one")
        self.write("safe2.txt")
        self.commit("two")
        with self.assertRaisesRegex(ValueError, "limit"):
            h.scan_pr(self.initial, self.oid(), root=self.root, limit=1)
        self.assertEqual(self.audit(), [])
        with self.assertRaisesRegex(ValueError, "Invalid commit limit"):
            h.scan_pr(self.initial, self.oid(), root=self.root, limit=0)

    def test_cli_expected_head_must_match_synthetic_merge(self):
        import contextlib
        import io
        from unittest import mock

        with mock.patch.object(h, "pr_parents", return_value=("a" * 40, "b" * 40)):
            with mock.patch.object(h, "oid", return_value="c" * 40):
                with mock.patch.object(h, "scan_pr") as scan:
                    with contextlib.redirect_stderr(io.StringIO()) as stderr:
                        result = h.main(["--expected-head", "c" * 40])
                    self.assertEqual(result, 2)
                    self.assertIn("event SHA", stderr.getvalue())
                    scan.assert_not_called()
            with mock.patch.object(h, "oid", side_effect=["b" * 40, "a" * 40]):
                with mock.patch.object(h, "scan_pr", return_value=[]):
                    self.assertEqual(h.main(["--expected-head", "b" * 40,
                                             "--expected-base", "a" * 40]), 0)

    def test_bad_ref_and_missing_history_fail_closed(self):
        with self.assertRaises(ValueError):
            h.scan_pr("-danger", self.initial, root=self.root)
        with self.assertRaises(RuntimeError):
            h.scan_pr("0" * 40, self.initial, root=self.root)

    def test_shallow_repository_fails_closed(self):
        self.topic()
        self.write("safe.md")
        self.commit("safe")
        self.assertEqual(self.audit(), [])
        # Simulate a valid Git shallow boundary with full local objects, so
        # even resolvable refs cannot make a partial audit appear complete.
        shallow = pathlib.Path(
            self.git("rev-parse", "--git-path", "shallow").stdout.decode().strip()
        )
        if not shallow.is_absolute():
            shallow = self.root / shallow
        shallow.write_text(self.initial + "\n", encoding="ascii")
        self.assertEqual(
            self.git("rev-parse", "--is-shallow-repository").stdout.strip(), b"true"
        )
        with self.assertRaisesRegex(ValueError, "Shallow history"):
            self.audit()

    def test_git_disables_lazy_fetch_and_replacement_refs(self):
        from unittest import mock

        with mock.patch.object(h.subprocess, "run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = b""
            h.git(self.root, "rev-parse", "HEAD")
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["GIT_NO_LAZY_FETCH"], "1")
        self.assertEqual(env["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")


if __name__ == "__main__":
    unittest.main()
