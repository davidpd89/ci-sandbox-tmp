"""Fully offline installer/runner regressions for the pinned third-party linter."""

import hashlib
import io
import stat
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import ci_actionlint as lint


def make_zip(name="actionlint.exe", payload=b"synthetic executable", *, symlink=False):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as output:
        member = zipfile.ZipInfo(name)
        if symlink:
            member.create_system = 3
            member.external_attr = (stat.S_IFLNK | 0o777) << 16
        output.writestr(member, payload)
    return buffer.getvalue()


def make_tar(name="actionlint", payload=b"synthetic executable", *, symlink=False):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as output:
        member = tarfile.TarInfo(name)
        member.size = len(payload)
        if symlink:
            member.type = tarfile.SYMTYPE
            member.linkname = "/tmp/outside"
        output.addfile(member, io.BytesIO(payload) if not symlink else None)
    return buffer.getvalue()


class ActionlintInstallerTests(unittest.TestCase):
    def test_pinned_release_names_and_checksums(self):
        for _, (archive, checksum, executable) in lint.RELEASES.items():
            self.assertIn(lint.VERSION, archive)
            self.assertEqual(len(checksum), 64)
            self.assertTrue(executable.startswith("actionlint"))
        self.assertTrue(lint.BASE_URL.endswith("/v" + lint.VERSION))

    def test_linux_and_windows_platforms(self):
        self.assertEqual(lint.release_spec("Linux", "AMD64")[2], "actionlint")
        self.assertEqual(lint.release_spec("Windows", "x86_64")[2], "actionlint.exe")
        with self.assertRaises(ValueError):
            lint.release_spec("darwin", "x86_64")

    def test_verified_zip_and_tar_only_extract_expected_binary(self):
        for name, factory in [("actionlint.exe", make_zip), ("actionlint", make_tar)]:
            package = factory(name)
            self.assertEqual(lint.extract_verified(package, filename="a.zip" if name.endswith("exe") else "a.tar.gz",
                                 digest=hashlib.sha256(package).hexdigest(), executable=name), b"synthetic executable")

    def test_reject_digest_mismatch_traversal_and_symlink(self):
        package = make_zip()
        with self.assertRaises(ValueError):
            lint.extract_verified(package, filename="a.zip", digest="0" * 64, executable="actionlint.exe")
        for name, factory, archive_name in [("actionlint.exe", make_zip, "a.zip"),
                                            ("actionlint", make_tar, "a.tar.gz")]:
            with self.subTest(name=name):
                evil = factory(name, symlink=True)
                with self.assertRaises(ValueError):
                    lint.extract_verified(evil, filename=archive_name, digest=hashlib.sha256(evil).hexdigest(), executable=name)
                traversal = factory("../" + name)
                with self.assertRaises(KeyError):
                    lint.extract_verified(traversal, filename=archive_name, digest=hashlib.sha256(traversal).hexdigest(), executable=name)

    def test_install_from_file_never_uses_network(self):
        package = make_zip()
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "download.zip"
            source.write_bytes(package)
            with mock.patch.object(lint, "release_spec", return_value=("file.zip", hashlib.sha256(package).hexdigest(), "actionlint.exe")), \
                 mock.patch.object(lint.urllib.request, "urlopen", side_effect=AssertionError("network called")):
                target = lint.install(Path(temp), archive_file=source)
            self.assertEqual(target.read_bytes(), b"synthetic executable")

    def test_workflow_discovery_accepts_yml_and_yaml(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / ".github" / "workflows"
            directory.mkdir(parents=True)
            self.assertEqual(lint.discover_workflows(root), [])
            for filename in ("b.yml", "a.yaml", "ignored.txt"):
                (directory / filename).write_text("name: synthetic\\n", encoding="utf-8")
            (directory / "nested").mkdir()
            (directory / "nested" / "nested.yml").write_text("name: synthetic\\n", encoding="utf-8")
            self.assertEqual([path.name for path in lint.discover_workflows(root)], ["a.yaml", "b.yml"])

    def test_no_workflows_is_a_failure(self):
        with self.assertRaises(ValueError):
            lint.run_lint(Path("fake"), [])

    def test_runner_calls_real_tool_only_with_workflow_paths(self):
        completed = mock.Mock(returncode=1, stdout="diagnostic", stderr="")
        with mock.patch.object(lint.subprocess, "run", return_value=completed) as run:
            self.assertIs(lint.run_lint(Path("binary"), [Path("fixture.yml")]), completed)
        command = run.call_args.args[0]
        self.assertEqual(command[1:3], ["-shellcheck=", "-pyflakes="])
        self.assertEqual(command[-1], "fixture.yml")
        self.assertFalse(run.call_args.kwargs["check"])

    def test_synthetic_cases_include_admitted_pin_gap(self):
        self.assertIn("actions/checkout@v4", lint.CASES["unpinned_action_is_not_checked"][0])
        self.assertTrue(lint.CASES["unpinned_action_is_not_checked"][1])
        self.assertFalse(lint.CASES["invalid_expression"][1])


    def test_untrusted_names_are_arguments_not_shell_commands(self):
        malicious = Path("workflow; echo HACKED.yml")
        with mock.patch.object(lint.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            lint.run_lint(Path("actionlint"), [malicious])
        self.assertEqual(run.call_args.args[0][-1], str(malicious))
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertNotIn("HACKED", " ".join(run.call_args.args[0][:-1]))

    def test_does_not_mutate_operational_fixtures(self):
        with tempfile.TemporaryDirectory() as temp:
            operational = Path(temp) / "state.sqlite"
            operational.write_bytes(b"synthetic-state-untouched")
            before = hashlib.sha256(operational.read_bytes()).digest()
            with mock.patch.object(lint.subprocess, "run", return_value=mock.Mock(returncode=0)):
                lint.run_lint(Path("actionlint"), [Path(temp) / "workflow.yml"])
            self.assertEqual(before, hashlib.sha256(operational.read_bytes()).digest())

    def test_download_or_integrity_failure_cannot_be_suppressed(self):
        with mock.patch.object(lint, "install", side_effect=ValueError("synthetic SHA256 mismatch")):
            self.assertEqual(lint.main([]), 2)

    def test_synthetic_fixtures_have_no_secrets(self):
        for body, _ in lint.CASES.values():
            self.assertNotIn("secrets.", body)
            self.assertNotIn("TOKEN=", body)


if __name__ == "__main__":
    unittest.main()
