"""Synthetic PR metadata only. Neither social state nor credentials are touched."""
from __future__ import annotations

import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import trusted_pr_hygiene as gate


REPO = "davidpd89/ci-sandbox-tmp"
HEAD = "a" * 40
BASE = "b" * 40


class Reader:
    def __init__(self, files, *, mutate=False, count=None):
        self.files = files
        self.mutate = mutate
        self.count = len(files) if count is None else count
        self.snapshots = 0
        self.calls = []

    def get(self, repo, path):
        assert repo == REPO
        self.calls.append(path)
        if path == "pulls/92":
            self.snapshots += 1
            return {
                "number": 92, "state": "open",
                "head": {"sha": "c" * 40 if self.mutate and self.snapshots == 2 else HEAD},
                "base": {"sha": BASE, "repo": {"full_name": REPO}},
                "changed_files": self.count,
            }
        prefix = "pulls/92/files?per_page=100&page="
        assert path.startswith(prefix), path
        page = int(path[len(prefix):])
        return self.files[(page - 1) * 100:page * 100]


def item(path, status="added"):
    return {"filename": path, "status": status}


class TrustedPRHygieneTests(unittest.TestCase):
    def verify(self, files, **kwargs):
        return gate.check_pr(Reader(files, **kwargs), REPO, 92, HEAD, BASE)

    def test_changed_or_deleted_self_checker_cannot_override_trusted_decision(self):
        # Deliberately place malicious PR versions on disk, but never import/run them.
        # Production gate consumes ONLY GitHub file metadata and trusted checkout policy.
        with tempfile.TemporaryDirectory() as directory:
            head = Path(directory)
            (head / "tools").mkdir()
            (head / ".github/workflows").mkdir(parents=True)
            (head / "tools/repo_hygiene.py").write_text(
                "def violations_for_paths(paths): return []\n", encoding="utf-8"
            )
            (head / ".github/workflows/trusted-pr-hygiene.yml").write_text(
                "jobs: {}\n", encoding="utf-8"
            )
            sample = [
                item("tools/repo_hygiene.py", "modified"),
                item(".github/workflows/trusted-pr-hygiene.yml", "modified"),
                item("keys/example.key"),
            ]
            seen, failures = self.verify(sample)
            self.assertEqual(seen, 3)
            self.assertEqual(failures, ["keys/example.key"])
            self.assertNotIn(str(head), str(Path(gate.__file__).resolve()))
            deleted = [
                item("tools/repo_hygiene.py", "removed"),
                item(".github/workflows/trusted-pr-hygiene.yml", "removed"),
                item(".env.local"),
            ]
            self.assertEqual(self.verify(deleted)[1], [".env.local"])

    def test_clean_code_docs_and_template_pass(self):
        self.assertEqual(self.verify([
            item("tools/repo_hygiene.py", "modified"),
            item(".github/workflows/trusted-pr-hygiene.yml", "modified"),
            item(".env.example", "added"),
            item("docs/readme.md"),
        ]), (4, []))

    def test_removed_historical_sensitive_path_does_not_reblock(self):
        self.assertEqual(self.verify([item("credentials.json", "removed")]), (1, []))

    def test_rename_to_sensitive_and_type_change_blocked(self):
        self.assertEqual(self.verify([
            item("safe/credentials.json", "renamed"),
            item("keys/key.pem", "changed"),
            item("src/allowed.py", "copied"),
        ])[1], ["safe/credentials.json", "keys/key.pem"])

    def test_pagination_preserves_entire_large_diff(self):
        files = [item(f"docs/doc_{i}.md") for i in range(205)]
        files[200] = item("cache/session.json")
        reader = Reader(files)
        self.assertEqual(gate.check_pr(reader, REPO, 92, HEAD, BASE),
                         (205, ["cache/session.json"]))
        self.assertEqual(reader.calls.count("pulls/92"), 2)
        self.assertIn("pulls/92/files?per_page=100&page=3", reader.calls)

    def test_fails_closed_on_truncation_and_inconsistent_count(self):
        with self.assertRaises(gate.HygieneError):
            self.verify([item("safe.md")], count=2)
        with self.assertRaises(gate.HygieneError):
            self.verify([item("safe.md")], count=0)
        with self.assertRaises(gate.HygieneError):
            self.verify([], count=3000)

    def test_fails_closed_if_head_moves_mid_scan(self):
        with self.assertRaisesRegex(gate.HygieneError, "changed|mismatch"):
            self.verify([item("README.md")], mutate=True)

    def test_rejects_unknown_file_status_or_records(self):
        for bad in ([{"filename": "safe.md", "status": "mystery"}],
                    [{"filename": "", "status": "added"}],
                    ["invalid"]):
            with self.subTest(bad=bad), self.assertRaises(gate.HygieneError):
                self.verify(bad)

    def test_untrusted_arguments_never_enter_url(self):
        for repo, number, sha in [
            ("evil.io/path/extra", 92, HEAD),
            (REPO, -1, HEAD),
            (REPO, 92, "not-a-sha"),
        ]:
            reader = Reader([])
            with self.assertRaises(gate.HygieneError):
                gate.check_pr(reader, repo, number, sha, BASE)
            self.assertEqual(reader.calls, [])

    def test_denies_reader_error_and_sanitizes_output(self):
        class Failure:
            def get(self, repo, path):
                raise gate.HygieneError("failure\n::warning::spoof")
        with mock.patch.object(gate, "GitHubReader", return_value=Failure()), \
             mock.patch.dict(gate.os.environ, {"GITHUB_TOKEN": "test-only"}):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = gate.main(["--repo", REPO, "--number", "92",
                                  "--head", HEAD, "--base", BASE])
            self.assertEqual(code, 2)
            self.assertNotIn("\n::warning::", err.getvalue())
            self.assertIn(r"\n::warning::spoof", err.getvalue())

    def test_fail_outputs_escaped_path_instead_of_control_characters(self):
        with mock.patch.object(gate, "GitHubReader", return_value=Reader([
            item(".env\n::warning::spoof")
        ])), mock.patch.dict(gate.os.environ, {"GITHUB_TOKEN": "test-only"}):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(gate.main(["--repo", REPO, "--number", "92",
                                            "--head", HEAD, "--base", BASE]), 1)
            self.assertIn(r"\n::warning::spoof", err.getvalue())
            self.assertNotIn("\n::warning::", err.getvalue())

    def test_trusted_workflow_is_not_present_in_untrusted_pr_runs(self):
        trusted = (ROOT / ".github/workflows/trusted-pr-hygiene.yml").read_text("utf-8")
        tests = (ROOT / ".github/workflows/trusted-pr-hygiene-tests.yml").read_text("utf-8")
        self.assertIn("pull_request_target:", trusted)
        self.assertNotIn("  pull_request:", trusted)
        self.assertNotIn("  push:", trusted)
        self.assertNotIn("if: github.event_name", trusted)
        self.assertIn("name: trusted-pr-paths", trusted)
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", trusted)
        self.assertIn("persist-credentials: false", trusted)
        self.assertIn("pull-requests: read", trusted)
        self.assertNotIn("pull-requests: write", trusted)
        self.assertNotIn("github.event.pull_request.head.repo", trusted)
        self.assertNotIn("github.event.pull_request.head.ref", trusted)
        self.assertNotIn("secrets.", trusted)
        self.assertNotIn("pip install", trusted)
        self.assertIn("  pull_request:", tests)
        self.assertIn("windows-latest", tests)
        self.assertIn("ubuntu-latest", tests)
        self.assertNotIn("pull_request_target:", tests)
        self.assertNotIn("name: trusted-pr-paths", tests)


if __name__ == "__main__":
    unittest.main()
