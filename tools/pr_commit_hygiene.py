"""Check every PR commit for sensitive paths; no file content access."""
from __future__ import annotations
import argparse
import os
import pathlib
import subprocess
import sys

from repo_hygiene import ROOT, forbidden_path


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
    return {s.decode("utf-8", "surrogateescape") for s in data.split(bytes([0])) if s}


def scan_pr(base: str, head: str, *, root: pathlib.Path = ROOT) -> list[tuple[str, int]]:
    if git(root, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("Shallow history: full checkout required")
    base, head = oid(root, base), oid(root, head)
    if not git(root, "merge-base", base, head).strip():
        raise ValueError("Unrelated PR history")
    rows = git(root, "rev-list", "--missing=error", "--parents", "--topo-order", "--reverse", f"{base}..{head}").splitlines()
    if not rows:
        raise ValueError("No PR commits; check checkout/history")
    findings = []
    for line in rows:
        commit, *parents = line.decode("ascii").split()
        first_parent_paths = changes(root, parents[0] if parents else None, commit)
        paths = set(first_parent_paths)
        for parent in parents[1:]:
            paths.intersection_update(changes(root, parent, commit))
        if len(parents) > 1:
            # A merge can resurrect a path from an already-reachable side-branch
            # ancestor without changing that path relative to the side parent.
            # Only reintroduced paths absent from the *current base* qualify:
            # importing an advancement of the base itself must remain allowed.
            new_vs_base = changes(root, base, commit, statuses="A")
            paths.update(first_parent_paths & new_vs_base)
        count = sum(forbidden_path(p) for p in paths)
        if count:
            findings.append((commit, count))
    return findings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr-merge", default="HEAD")
    args = parser.parse_args(argv)
    try:
        base, head = pr_parents(merge=args.pr_merge)
        findings = scan_pr(base, head)
    except (RuntimeError, ValueError, UnicodeError) as exc:
        print(f"HISTORY ERROR: {exc}", file=sys.stderr)
        return 2
    for sha, count in findings:
        print(f"HISTORY FAIL: commit {sha[:12]}, {count} forbidden paths (names hidden)", file=sys.stderr)
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
