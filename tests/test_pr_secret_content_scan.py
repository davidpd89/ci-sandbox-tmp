"""Offline + live-binary-on-CI regression tests; fixtures are explicitly synthetic."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import install_gitleaks_ci as installer
import pr_secret_content_scan as scanner

RULE = ROOT / "tests" / "fixtures" / "gitleaks-synthetic.toml"


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, encoding="utf-8", check=True)
    return result.stdout


def merge_repo(*, variant: str) -> tuple[tempfile.TemporaryDirectory, Path]:
    work = tempfile.TemporaryDirectory(prefix="ci87-git-")
    root = Path(work.name)
    git(root, "init", "-b", "main")
    git(root, "config", "user.email", "ci-test@example.invalid")
    git(root, "config", "user.name", "Synthetic CI")
    # Deliberately assembled: no token-shaped credentials anywhere in source.
    sentinel = "CI87_" + "SYNTHETIC_" + "ABCDEFGHJKLM"
    (root / "README.md").write_text("historical marker: " + sentinel + "\n", encoding="utf-8")
    (root / "old.md").write_text("ordinary baseline\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "synthetic baseline")
    git(root, "checkout", "-b", "feature")
    if variant == "new":
        (root / "added.py").write_text("demo = '" + sentinel + "'\n", encoding="utf-8")
    elif variant == "attributes":
        (root / ".gitattributes").write_text("*.py -diff\n", encoding="utf-8")
        (root / "added.py").write_text("demo = '" + sentinel + "'\n", encoding="utf-8")
    elif variant == "ignore":
        (root / ".gitleaksignore").write_text("synthetic/fake/fingerprint\n", encoding="utf-8")
    elif variant == "allow":
        (root / "added.py").write_text("demo = '" + sentinel + "'  # gitleaks:allow\n", encoding="utf-8")
    elif variant == "historical":
        (root / "old.md").write_text("ordinary changed file\n", encoding="utf-8")
    elif variant == "rename":
        git(root, "mv", "README.md", "moved.txt")
    elif variant == "deleted":
        git(root, "rm", "README.md")
    elif variant == "changed":
        (root / "README.md").write_text("historical marker: " + sentinel + "\nnew ordinary text\n", encoding="utf-8")
    else:
        raise ValueError(variant)
    git(root, "add", "-A")
    git(root, "commit", "-m", "synthetic proposed change")
    git(root, "checkout", "main")
    git(root, "merge", "--no-ff", "feature", "-m", "synthetic PR merge")
    return work, root


class InstallerTests(unittest.TestCase):
    def test_archive_checksum_and_executable_name_are_enforced(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("gitleaks.exe", b"stand-in for a test binary")
            z.writestr("../../traversal", b"not executable")
        data = buf.getvalue()
        with patch.dict(installer.ASSETS, {"Windows": ("windows_x64.zip", hashlib.sha256(data).hexdigest())}):
            self.assertEqual(installer.verified_executable(data, system="Windows"), b"stand-in for a test binary")
            with self.assertRaises(ValueError):
                installer.verified_executable(data + b"tampered", system="Windows")
            with self.assertRaises(ValueError):
                installer.verified_executable(b"x" * (installer.MAX_ARCHIVE_SIZE + 1), system="Windows")

    def test_unsupported_platform_is_rejected(self):
        with patch("install_gitleaks_ci.platform.machine", return_value="arm64"):
            with self.assertRaises(RuntimeError):
                installer.executable_path(system="Windows")


class PrDiffTests(unittest.TestCase):
    def test_merge_patch_has_added_lines_not_historical_secret(self):
        for variant, expected in [("new", True), ("attributes", True), ("allow", True), ("historical", False), ("rename", True), ("deleted", False), ("changed", False)]:
            with self.subTest(variant=variant):
                temp, root = merge_repo(variant=variant)
                try:
                    scanner.assert_pr_merge(root)
                    log = git(root, "log", "-p", *scanner.LOG_OPTS.split())
                    added = [line for line in log.splitlines() if line.startswith("+") and not line.startswith("+++")]
                    self.assertEqual(any("CI87_SYNTHETIC_" in line for line in added), expected)
                finally:
                    temp.cleanup()

    def test_gitattributes_cannot_hide_added_content(self):
        temp, root = merge_repo(variant="attributes")
        try:
            options = scanner.LOG_OPTS.split()
            unprotected = git(root, "log", "-p", *[x for x in options if x != "--text"])
            protected = git(root, "log", "-p", *options)
            self.assertNotIn("CI87_SYNTHETIC_", unprotected)
            self.assertIn("CI87_SYNTHETIC_", protected)
        finally:
            temp.cleanup()

    def test_non_merge_is_rejected_not_scanned_as_history(self):
        temp, root = merge_repo(variant="new")
        try:
            git(root, "checkout", "feature")
            with self.assertRaises(ValueError):
                scanner.assert_pr_merge(root)
        finally:
            temp.cleanup()

    def test_pr_supplied_gitleaks_config_cannot_disable_default_rules(self):
        temp, root = merge_repo(variant="new")
        try:
            # Synthetic local override, without any token-shaped credential.
            (root / ".gitleaks.toml").write_text(
                'title = "do not accept PR-controlled rules"\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "no permitidos"):
                scanner.scan(root, executable=Path(__file__))
        finally:
            temp.cleanup()

    def test_repo_gitleaksignore_cannot_hide_findings(self):
        temp, root = merge_repo(variant="ignore")
        try:
            with self.assertRaisesRegex(ValueError, "no permitidos"):
                scanner.scan(root, executable=Path(__file__))
        finally:
            temp.cleanup()

    def test_binary_failure_is_not_reported_as_green_and_does_not_echo_output(self):
        temp, root = merge_repo(variant="new")
        try:
            with patch("pr_secret_content_scan.subprocess.run") as run:
                run.return_value.returncode = 2
                run.return_value.stdout = "DO NOT ECHO BINARY OUTPUT"
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    with patch.dict(os.environ, {"GITLEAKS_CONFIG": "bad.toml",
                                                     "GITLEAKS_CONFIG_TOML": "title = 'override'"}):
                        with patch.object(scanner, "assert_pr_merge"):
                            self.assertEqual(scanner.scan(root, executable=Path(__file__)), 2)
                self.assertNotIn("DO NOT ECHO", stdout.getvalue() + stderr.getvalue())
                self.assertEqual(run.call_args.kwargs["stdout"], subprocess.DEVNULL)
                self.assertEqual(run.call_args.kwargs["stderr"], subprocess.DEVNULL)
                self.assertIn("--ignore-gitleaks-allow", run.call_args.args[0])
                self.assertNotIn("GITLEAKS_CONFIG", run.call_args.kwargs["env"])
                self.assertNotIn("GITLEAKS_CONFIG_TOML", run.call_args.kwargs["env"])
        finally:
            temp.cleanup()


class GitleaksOnCiIntegration(unittest.TestCase):
    @unittest.skipUnless(installer.executable_path().is_file(), "Gitleaks binario solo instalado en CI")
    def test_real_gitleaks_positive_negative_baseline_rename(self):
        for variant, expected in [("new", 1), ("attributes", 1), ("allow", 1), ("historical", 0), ("rename", 1), ("deleted", 0), ("changed", 0)]:
            with self.subTest(variant=variant):
                temp, root = merge_repo(variant=variant)
                try:
                    output, error = io.StringIO(), io.StringIO()
                    with redirect_stdout(output), redirect_stderr(error):
                        status = scanner.scan(root, executable=installer.executable_path(), config=RULE)
                    self.assertEqual(status, expected, output.getvalue() + error.getvalue())
                    self.assertNotIn("ABCDEFGHJKLM", output.getvalue() + error.getvalue())
                finally:
                    temp.cleanup()


if __name__ == "__main__":
    unittest.main()
