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

    def test_bad_ref_and_missing_history_fail_closed(self):
        with self.assertRaises(ValueError):
            h.scan_pr("-danger", self.initial, root=self.root)
        with self.assertRaises(RuntimeError):
            h.scan_pr("0" * 40, self.initial, root=self.root)


if __name__ == "__main__":
    unittest.main()
