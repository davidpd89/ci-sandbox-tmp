"""Check sensitive paths in *all commits* introduced by a GitHub push.

Complementary to #88 (final tree) and #89 (PR commit history).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import git_history_paths as history
import repo_hygiene


class PushEventError(history.HistoryError):
    pass


def scan_push(event: dict, *, root: Path, expected_sha: str):
    if not isinstance(event, dict) or event.get("ref") != "refs/heads/main":
        raise PushEventError("Expected a push on refs/heads/main")
    before = event.get("before")
    after = event.get("after")
    if not isinstance(before, str) or not history.SHA.fullmatch(before):
        raise PushEventError("Missing or invalid event.before")
    if not isinstance(after, str) or not history.SHA.fullmatch(after) or set(after) == {"0"}:
        raise PushEventError("Missing, deleted or invalid event.after")
    if not isinstance(expected_sha, str) or after.lower() != expected_sha.lower():
        raise PushEventError("event.after != GITHUB_SHA")
    head = history.git(root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
    if head.lower() != after.lower():
        raise PushEventError("Checkout HEAD != event.after")
    if len(before) != len(after):
        raise PushEventError("Incompatible before and after hash formats")
    first_push = set(before) == {"0"}
    if not first_push:
        # A force-push can rewind main to an ancestor of before, so
        # after ^ before contains no commits even though the tree changed.
        # Check restored A/M/T paths rather than misclassifying a clean
        # rewind as an unverifiable event; missing Git history still errors.
        if before.lower() == after.lower():
            raise PushEventError("No commits changed in push")
        history.commit_id(root, before)
        if history.git(root, "rev-parse", "--is-shallow-repository").strip() != b"false":
            raise PushEventError("Shallow checkout: full commit history required")
        newly_reachable = history.git(
            root, "rev-list", "--missing=error", "--max-count=1",
            after.lower(), "^" + before.lower(),
        )
        if not newly_reachable:
            paths = history.touched_paths(root, after.lower(), [before.lower()])
            count = sum(bool(repo_hygiene.forbidden_path(path)) for path in paths)
            return [(after.lower(), count)] if count else []
    return history.scan_history(root, None if first_push else before,
                                after, repo_hygiene.forbidden_path)


def main() -> int:
    try:
        filename = os.environ.get("GITHUB_EVENT_PATH")
        if not filename:
            raise PushEventError("GITHUB_EVENT_PATH missing")
        with open(filename, encoding="utf-8") as handle:
            event = json.load(handle)
        findings = scan_push(event, root=repo_hygiene.ROOT,
                             expected_sha=os.environ.get("GITHUB_SHA", ""))
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        print(f"PUSH HISTORY ERROR: {exc}", file=sys.stderr)
        return 2
    if findings:
        for sha, count in findings[:30]:
            print(f"PUSH HISTORY FAIL: {sha[:12]}: {count} sensitive paths (hidden)", file=sys.stderr)
        if len(findings) > 30:
            print(f"PUSH HISTORY FAIL: {len(findings)-30} additional commits (hidden)", file=sys.stderr)
        return 1
    print("PUSH HISTORY OK: checked introduced commits and their merge parents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
