"""Verify and run a pinned upstream actionlint release. Python 3.11+, no deps."""

from __future__ import annotations

import argparse
import hashlib
import io
import platform
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "1.7.12"
BASE_URL = f"https://github.com/rhysd/actionlint/releases/download/v{VERSION}"
MAX_ARCHIVE = 16 * 1024 * 1024
MAX_BINARY = 32 * 1024 * 1024
# SHA256 verified against GitHub's release-asset digests (2026-10-09).
RELEASES = {
    ("linux", "x86_64"): (
        f"actionlint_{VERSION}_linux_amd64.tar.gz",
        "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
        "actionlint",
    ),
    ("windows", "x86_64"): (
        f"actionlint_{VERSION}_windows_amd64.zip",
        "6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9",
        "actionlint.exe",
    ),
}


def release_spec(os_name: str | None = None, arch: str | None = None):
    os_name = (os_name or platform.system()).lower()
    arch = (arch or platform.machine()).lower()
    arch = "x86_64" if arch in {"amd64", "x86_64"} else arch
    try:
        return RELEASES[(os_name, arch)]
    except KeyError as exc:
        raise ValueError(f"Unsupported actionlint runner architecture: {os_name}/{arch}") from exc


def extract_verified(archive: bytes, *, filename: str, digest: str, executable: str) -> bytes:
    if len(archive) > MAX_ARCHIVE or hashlib.sha256(archive).hexdigest() != digest:
        raise ValueError("actionlint archive SHA256/size check failed")
    if filename.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            member = bundle.getinfo(executable)
            if member.is_dir() or stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("actionlint executable is not a regular file")
            if member.file_size > MAX_BINARY:
                raise ValueError("actionlint binary is too large")
            result = bundle.read(member)
    else:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            member = bundle.getmember(executable)
            if not member.isfile() or member.size > MAX_BINARY:
                raise ValueError("actionlint executable is not a bounded regular file")
            stream = bundle.extractfile(member)
            if stream is None:
                raise ValueError("actionlint executable missing")
            result = stream.read(MAX_BINARY + 1)
    if not result or len(result) > MAX_BINARY:
        raise ValueError("actionlint binary is empty or too large")
    return result


def install(target_dir: Path, *, archive_file: Path | None = None) -> Path:
    filename, digest, executable = release_spec()
    if archive_file is None:
        request = urllib.request.Request(f"{BASE_URL}/{filename}", headers={"User-Agent": "ci-actionlint/1"})
        with urllib.request.urlopen(request, timeout=30) as response:
            archive = response.read(MAX_ARCHIVE + 1)
    else:
        with archive_file.open("rb") as stream:
            archive = stream.read(MAX_ARCHIVE + 1)
    binary_content = extract_verified(archive, filename=filename, digest=digest, executable=executable)
    binary = target_dir / executable
    binary.write_bytes(binary_content)
    if sys.platform != "win32":
        binary.chmod(0o700)
    return binary


def run_lint(binary: Path, paths: list[Path]) -> subprocess.CompletedProcess[str]:
    if not paths:
        raise ValueError("No workflow YAML files found; refusing a vacuous check")
    return subprocess.run(
        [str(binary), "-shellcheck=", "-pyflakes=", *(str(path) for path in paths)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40,
        check=False,
    )


VALID = "name: example\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"
# The unpinned action is intentionally ACCEPTED by actionlint; not its scope.
CASES = {
    "valid": (VALID, True),
    "invalid_event": (VALID.replace("on: [push]", "on:\n  push:\n    unexpected: foo"), False),
    "invalid_expression": (VALID.replace("echo ok", 'echo "${{ runner.unknown_property }}"'), False),
    "unknown_job_field": (VALID.replace("runs-on: ubuntu-latest", "runs-on: ubuntu-latest\n    invented_key: bad"), False),
    "invalid_yaml": (VALID.replace("on: [push]", "on: [push"), False),
    "unpinned_action_is_not_checked": (
        VALID.replace("- run: echo ok", "- uses: actions/checkout@v4"), True
    ),
}


def selftest(binary: Path, directory: Path) -> bool:
    ok = True
    for name, (content, expected_ok) in CASES.items():
        fixture = directory / (name + ".yml")
        fixture.write_text(content, encoding="utf-8")
        outcome = run_lint(binary, [fixture])
        passed = (outcome.returncode == 0) == expected_ok and outcome.returncode in {0, 1}
        print(f"{'PASS' if passed else 'FAIL'} synthetic/{name} (exit {outcome.returncode})")
        if not passed:
            print(outcome.stdout, outcome.stderr, file=sys.stderr)
            ok = False
    return ok


def discover_workflows(root: Path) -> list[Path]:
    directory = root / ".github" / "workflows"
    return sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Use a local release archive; SHA256 is still enforced")
    parser.add_argument("--selftest", action="store_true", help="Also run synthetic valid/invalid YAML cases")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    workflows = discover_workflows(root)
    if not workflows:
        print("No workflows found", file=sys.stderr)
        return 2
    try:
        with tempfile.TemporaryDirectory(prefix="ci-actionlint-") as temp:
            temporary = Path(temp)
            binary = install(temporary, archive_file=args.archive)
            version = subprocess.run([str(binary), "-version"], capture_output=True,
                                     text=True, timeout=10, check=False)
            if version.returncode != 0 or VERSION not in version.stdout:
                raise RuntimeError("actionlint executable version mismatch")
            print(f"actionlint v{VERSION}; {len(workflows)} workflows")
            outcome = run_lint(binary, workflows)
            if outcome.stdout:
                print(outcome.stdout)
            if outcome.stderr:
                print(outcome.stderr, file=sys.stderr)
            ok = outcome.returncode == 0
            if args.selftest:
                ok = selftest(binary, temporary) and ok
            return 0 if ok else 1
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired,
            urllib.error.URLError, tarfile.TarError, zipfile.BadZipFile, KeyError) as exc:
        print(f"actionlint unavailable/verification failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
