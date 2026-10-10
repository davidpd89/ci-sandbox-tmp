"""Check every PR commit for sensitive paths; no file content access."""
from __future__ import annotations
import argparse
import os
import pathlib
import subprocess
import sys

from repo_hygiene import ROOT, forbidden_path

MAX_COMMITS = 20000


def git(root: pathlib.Path, *argv: str) -> bytes:
    env = os.environ.copy()
    env.update({"GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_TERMINAL_PROMPT": "0"})
    proc = subprocess.run(["git", "-C", str(root), *argv],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if proc.returncode:
        raise RuntimeError(f"Git failed: {argv[0]} ({proc.returncode})")
    return proc.stdout


def oid(root: pathlib.Path, ref: str) -> str:
    if not ref or ref.startswith("-"):
        raise ValueError("Invalid ref")
    result = git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode("ascii").strip()
    if len(result) not in (40, 64) or any(c not in "0123456789abcdef" for c in result.lower()):
        raise ValueError("Invalid commit ID")
    return result


def pr_parents(root: pathlib.Path = ROOT, merge: str = "HEAD") -> tuple[str, str]:
    parents = git(root, "rev-list", "--parents", "-n", "1", oid(root, merge)).decode("ascii").split()
    if len(parents) != 3:
        raise ValueError("Expected two-parent synthetic PR merge")
    return parents[1], parents[2]


def changes(root: pathlib.Path, parent: str | None, commit: str, *, statuses: str = "AMT") -> set[str]:
    opts = ("--no-renames", "--no-ext-diff", "--name-only", "-z", f"--diff-filter={statuses}")
    if parent:
        data = git(root, "diff", *opts, parent, commit)
    else:
        data = git(root, "diff-tree", "--root", "-r", "--no-commit-id", *opts, commit)
    # Reject invalid UTF-8 rather than treating a malformed path as benign.
    # The final-tree policy is already strict; transient paths must match it.
    return {s.decode("utf-8") for s in data.split(bytes([0])) if s}


def scan_pr(base: str, head: str, *, root: pathlib.Path = ROOT,
            limit: int = MAX_COMMITS) -> list[tuple[str, int]]:
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("Invalid commit limit")
    if git(root, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("Shallow history: full checkout required")
    base, head = oid(root, base), oid(root, head)
    if not git(root, "merge-base", base, head).strip():
        raise ValueError("Unrelated PR history")
    rows = git(root, "rev-list", "--missing=error", "--parents", "--topo-order", "--reverse", f"--max-count={limit + 1}", f"{base}..{head}").splitlines()
    if len(rows) > limit:
        raise ValueError("PR commit range exceeds bounded audit limit")
    if not rows:
        raise ValueError("No PR commits; check checkout/history")
    findings = []
    for line in rows:
        commit, *parents = line.decode("ascii").split()
        first_parent_paths = changes(root, parents[0] if parents else None, commit)
        paths = set(first_parent_paths)
        for parent in parents[1:]:
            paths.intersection_update(changes(root, parent, commit))
        if len(parents) > 1 and any(
            git(root, "rev-list", "--missing=error", "--max-count=1", f"{base}..{parent}")
            for parent in parents[1:]
        ):
            # An outside side branch can restore an old A/M/T path from an
            # ancestor already in the base, so its side-parent diff is empty.
            # Check first-parent changes against the *current* base. Merges
            # solely from ancestors of the current base remain exempt.
            paths.update(first_parent_paths & changes(root, base, commit))
        count = sum(forbidden_path(p) for p in paths)
        if count:
            findings.append((commit, count))
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-merge", default="HEAD")
    parser.add_argument("--expected-head", help="Expected PR head SHA from event")
    parser.add_argument("--expected-base", help="Expected PR base SHA from event")
    args = parser.parse_args(argv)
    try:
        base, head = pr_parents(merge=args.pr_merge)
        if args.expected_head is not None and oid(ROOT, args.expected_head) != head:
            raise ValueError("Checkout head differs from PR event SHA")
        if args.expected_base is not None and oid(ROOT, args.expected_base) != base:
            raise ValueError("Checkout base differs from PR event SHA")
        findings = scan_pr(base, head)
    except (RuntimeError, ValueError, UnicodeError) as exc:
        print(f"HISTORY ERROR: {exc}", file=sys.stderr)
        return 2
    for sha, count in findings:
        print(f"HISTORY FAIL: commit {sha[:12]}, {count} forbidden paths (names hidden)", file=sys.stderr)
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
