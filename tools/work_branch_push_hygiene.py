"""Audit GitHub push events on non-main branches via PR #93's shared Git core.

Metadata and paths only; never read blobs. PR #93 is an integration prerequisite.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

_CORE = Path(__file__).resolve().parents[1] / ".ci97-pr93-core" / "tools"
if _CORE.is_dir():
    sys.path.append(str(_CORE))

import git_history_paths as history  # provided by PR #93
import repo_hygiene  # provided by PR #2/#93

ZERO = {"0"}
DEFAULT_BASE_REF = "refs/remotes/origin/main"
ROOT = Path(__file__).resolve().parents[1]


class WorkPushError(history.HistoryError):
    """Unverifiable branch event or incomplete history."""


def _required_bool(event: dict, key: str) -> bool:
    flag = event.get(key)
    if type(flag) is not bool:
        raise WorkPushError(f"Missing or invalid push flag: {key}")
    return flag


def _valid_oid(raw: object, label: str, *, zero_allowed: bool = False) -> str:
    if not isinstance(raw, str) or not history.SHA.fullmatch(raw):
        raise WorkPushError(f"Invalid {label} commit SHA")
    oid = raw.lower()
    if set(oid) == ZERO and not zero_allowed:
        raise WorkPushError(f"Unexpected zero {label} commit SHA")
    return oid


def _git_predicate(root: Path, *args: str) -> tuple[int, bytes]:
    # history.git raises on nonzero; these predicates legitimately exit 1.
    env = os.environ.copy()
    env.update({"GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_TERMINAL_PROMPT": "0"})
    process = subprocess.run(
        ["git", "--no-optional-locks", "-C", str(root), *args],
        capture_output=True, check=False, env=env,
    )
    if process.returncode not in (0, 1):
        raise WorkPushError(f"Git {args[0]} query failed")
    return process.returncode, process.stdout


def _ancestor(root: Path, older: str, newer: str) -> bool:
    code, _ = _git_predicate(root, "merge-base", "--is-ancestor", older, newer)
    return code == 0


def _new_ref_baseline(root: Path, after: str, default_ref: str) -> str | None:
    # A newly created ref is not necessarily a newly created history.
    if not default_ref.startswith("refs/remotes/origin/"):
        raise WorkPushError("Default base must be a remote-tracking branch ref")
    history.git(root, "check-ref-format", default_ref)
    upstream = history.git(root, "rev-parse", "--verify",
                           default_ref + "^{commit}").decode("ascii").strip()
    upstream = history.commit_id(root, upstream)
    code, data = _git_predicate(root, "merge-base", after, upstream)
    if code == 1:  # Orphan history, audit from root.
        return None
    return history.commit_id(root, data.decode("ascii").strip())


def scan_work_push(event: dict, *, root: Path, expected_sha: str,
                   default_ref: str = DEFAULT_BASE_REF) -> tuple[str, list[tuple[str, int]]]:
    """Classify and scan one actual push; fail closed for missing Git objects."""
    if not isinstance(event, dict):
        raise WorkPushError("Expected GitHub push event object")
    ref = event.get("ref")
    if not isinstance(ref, str) or not ref.startswith("refs/heads/") or ref == "refs/heads/main":
        raise WorkPushError("Expected a non-main branch push")
    history.git(root, "check-ref-format", ref)
    before = _valid_oid(event.get("before"), "before", zero_allowed=True)
    after = _valid_oid(event.get("after"), "after", zero_allowed=True)
    expected = _valid_oid(expected_sha, "GITHUB_SHA")
    if len(before) != len(after) or len(after) != len(expected):
        raise WorkPushError("Mixed commit hash formats")
    created = _required_bool(event, "created")
    deleted = _required_bool(event, "deleted")
    _required_bool(event, "forced")
    if created and deleted:
        raise WorkPushError("Event cannot create and delete the same ref")
    if created != (set(before) == ZERO) or deleted != (set(after) == ZERO):
        raise WorkPushError("Push lifecycle flags contradict before/after")
    if not created and not deleted and before == after:
        raise WorkPushError("No changed commit in a purported update push")
    head = history.git(root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip().lower()
    if head != expected:
        raise WorkPushError("Checkout HEAD != GITHUB_SHA")
    if history.git(root, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise WorkPushError("Shallow checkout: full history required")
    if deleted:
        # GitHub uses the default branch SHA for a deleted branch run.
        default = history.git(root, "rev-parse", "--verify",
                              default_ref + "^{commit}").decode("ascii").strip().lower()
        if expected != default:
            raise WorkPushError("Deletion checkout is not at default branch tip")
        history.commit_id(root, before)
        return "deleted", []
    if after != expected:
        raise WorkPushError("event.after != GITHUB_SHA")
    history.commit_id(root, after)
    if created:
        baseline = _new_ref_baseline(root, after, default_ref)
        if baseline == after:
            return "created-existing", []
        classification = "created" if baseline else "created-orphan"
    else:
        history.commit_id(root, before)
        baseline = before
        classification = "fast-forward" if _ancestor(root, before, after) else "rewrite"
        if classification == "rewrite" and _ancestor(root, after, before):
            # A rewind introduces no commits, but may restore a sensitive path
            # from an earlier tree. Compare the before/after trees explicitly.
            paths = history.touched_paths(root, after, [before])
            count = sum(bool(repo_hygiene.forbidden_path(path)) for path in paths)
            return "rewrite", [(after, count)] if count else []
    return classification, history.scan_history(root, baseline, after, repo_hygiene.forbidden_path)


def main() -> int:
    try:
        path = os.environ.get("GITHUB_EVENT_PATH")
        if not path:
            raise WorkPushError("GITHUB_EVENT_PATH missing")
        with open(path, encoding="utf-8") as handle:
            event = json.load(handle)
        classification, findings = scan_work_push(
            event, root=ROOT, expected_sha=os.environ.get("GITHUB_SHA", ""),
            default_ref=os.environ.get("WORK_PUSH_DEFAULT_REF", DEFAULT_BASE_REF),
        )
    except (OSError, UnicodeError, ValueError, RuntimeError) as exc:
        print(f"WORK PUSH ERROR: {exc}", file=sys.stderr)
        return 2
    if findings:
        for sha, count in findings[:30]:
            print(f"WORK PUSH FAIL ({classification}): {sha[:12]}: {count} sensitive paths (hidden)", file=sys.stderr)
        if len(findings) > 30:
            print(f"WORK PUSH FAIL: {len(findings)-30} more affected commits (hidden)", file=sys.stderr)
        return 1
    print(f"WORK PUSH OK ({classification}): inspected introduced Git paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
