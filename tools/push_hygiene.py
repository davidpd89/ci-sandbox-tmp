"""Check all final-tree path changes of a GitHub push using the existing policy.

No network calls, credentials, or repository state changes. GitHub event input
comes from the runner's event file, not an interpolated shell expression.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import repo_hygiene

SHA_RE = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})\Z")


class PushRangeError(ValueError):
    """The required Git snapshot pair cannot be verified."""


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        # Deliberately do not print Git's stderr (which could contain file names).
        raise PushRangeError("objeto o rango Git no disponible (checkout completo requerido)")
    return result.stdout


def push_paths(event: dict, *, root: Path, expected_sha: str) -> list[str]:
    """Diff before..after, or audit the complete snapshot for a new branch.

    Non-fast-forward updates compare before and after *trees* directly. If
    before cannot be fetched, do not silently substitute HEAD^ or HEAD~N.
    """
    if not isinstance(event, dict):
        raise PushRangeError("payload push no es un objeto")
    if event.get("ref") != "refs/heads/main":
        raise PushRangeError("solo se admite push a refs/heads/main")
    before, after = event.get("before"), event.get("after")
    if not isinstance(before, str) or not SHA_RE.fullmatch(before):
        raise PushRangeError("before ausente o no es un SHA valido")
    if not isinstance(after, str) or not SHA_RE.fullmatch(after) or set(after) == {"0"}:
        raise PushRangeError("after ausente, eliminado o no es un SHA valido")
    if len(before) != len(after):
        raise PushRangeError("before y after tienen longitudes incompatibles")
    if not isinstance(expected_sha, str) or after.lower() != expected_sha.lower():
        raise PushRangeError("github.sha no coincide con event.after")
    current_head = _git(root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
    if current_head.lower() != after.lower():
        raise PushRangeError("HEAD del checkout no coincide con event.after")
    if set(before) == {"0"}:
        # First push of this ref: no previous snapshot. Deliberately check all
        # tracked paths; only this situation may audit paths predating the push.
        raw = _git(root, "ls-tree", "-r", "--name-only", "-z", "HEAD")
        return [p.decode("utf-8", "surrogateescape") for p in raw.split(b"\0") if p]
    # Make missing/reaped before explicit even if Git's error wording varies.
    _git(root, "cat-file", "-e", f"{before}^{{commit}}")
    return repo_hygiene.changed_paths(before, root=root)


def main() -> int:
    try:
        filename = os.environ.get("GITHUB_EVENT_PATH")
        if not filename:
            raise PushRangeError("GITHUB_EVENT_PATH no disponible")
        with open(filename, encoding="utf-8") as event_file:
            event = json.load(event_file)
        paths = push_paths(
            event, root=repo_hygiene.ROOT,
            expected_sha=os.environ.get("GITHUB_SHA", ""),
        )
        offenders = repo_hygiene.violations_for_paths(paths)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"HIGIENE PUSH ERROR: {exc}", file=sys.stderr)
        return 2
    if offenders:
        print("HIGIENE PUSH FALLIDA: rutas operativas nuevas o modificadas:", file=sys.stderr)
        for path in offenders:
            print(f"  - {path}", file=sys.stderr)
        return 1
    print("HIGIENE PUSH OK: rutas comprobadas respecto al before real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
