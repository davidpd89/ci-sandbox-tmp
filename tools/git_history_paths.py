"""Git DAG and changed-path adapter shared by PR and push hygiene checks.

Only Git metadata is read. No blob contents, shell, network, or Git writes.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess

SHA = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")
MAX_COMMITS = 20000


class HistoryError(ValueError):
    """Incomplete or invalid history; never treat as an empty result."""


def git(root: Path, *args: str) -> bytes:
    process = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        capture_output=True, check=False,
    )
    if process.returncode:
        # Git stderr may contain attacker-controlled paths; do not log it.
        raise HistoryError(f"Git {args[0]} failed (exit={process.returncode})")
    return process.stdout


def commit_id(root: Path, sha: str) -> str:
    if not isinstance(sha, str) or not SHA.fullmatch(sha) or set(sha) == {"0"}:
        raise HistoryError("Expected a nonzero full commit SHA")
    oid = sha.lower()
    git(root, "cat-file", "-e", oid + "^{commit}")
    actual = git(root, "rev-parse", "--verify", oid + "^{commit}").decode("ascii").strip()
    if actual.lower() != oid:
        raise HistoryError("Commit SHA does not resolve exactly")
    return oid


def commits_in_range(root: Path, before: str | None, after: str, *, limit: int = MAX_COMMITS):
    """Commits reachable from after and not from before; for a new ref, all ancestors."""
    after = commit_id(root, after)
    if git(root, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise HistoryError("Shallow checkout: full commit history required")
    args = ["rev-list", "--missing=error", "--full-history", "--topo-order",
            "--reverse", "--parents", f"--max-count={limit + 1}", after]
    if before is not None:
        before = commit_id(root, before)
        if len(before) != len(after):
            raise HistoryError("Mixed commit hash formats")
        args.append("^" + before)
    result = git(root, *args).splitlines()
    if not result:
        raise HistoryError("No commits found in push range")
    if len(result) > limit:
        raise HistoryError("Commit range exceeds checked limit")
    rows = []
    for row in result:
        fields = row.decode("ascii").split()
        if not fields or any(not SHA.fullmatch(s) for s in fields):
            raise HistoryError("Invalid rev-list record")
        rows.append((fields[0], fields[1:]))
    return rows


def touched_paths(root: Path, commit: str, parents: list[str]) -> set[str]:
    """A/M/T paths; merges include only changes against *all* parents.

    The intersection excludes unchanged paths inherited from a merge parent,
    while commits newly reachable via that parent are checked individually.
    """
    options = ["-r", "--no-commit-id", "--no-renames", "--no-ext-diff",
               "--no-textconv", "--name-only", "-z", "--diff-filter=AMT"]
    if not parents:
        data = git(root, "diff-tree", "--root", *options, commit)
        return {p.decode("utf-8", "surrogateescape") for p in data.split(b"\0") if p}
    common = None
    for parent in parents:
        data = git(root, "diff-tree", *options, parent, commit)
        paths = {p.decode("utf-8", "surrogateescape") for p in data.split(b"\0") if p}
        common = paths if common is None else common & paths
        if not common:
            break
    return common or set()


def scan_history(root: Path, before: str | None, after: str, forbidden) -> list[tuple[str, int]]:
    findings = []
    for sha, parents in commits_in_range(root, before, after):
        count = sum(bool(forbidden(path)) for path in touched_paths(root, sha, parents))
        if count:
            findings.append((sha, count))
    return findings
