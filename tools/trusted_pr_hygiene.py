"""Trusted pull-request *path* gate.

Run ONLY from the repository's trusted default-branch checkout. The PR is
fetched as metadata via GitHub's read-only API, NEVER checked out/executed.
Uses the existing repo_hygiene policy of that trusted checkout.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

from repo_hygiene import violations_for_paths

_SHA = re.compile(r"[0-9a-fA-F]{40}\Z")
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
_ACTIVE = frozenset({"added", "modified", "renamed", "copied", "changed"})
_MAX_FILES = 3000
_MAX_RESPONSE = 4_000_000


class HygieneError(Exception):
    """Fail closed on uncertain, incomplete or inconsistent PR metadata."""


class GitHubReader:
    """Read-only REST reader; responses are bounded and never logged."""

    def __init__(self, token: str):
        if not token:
            raise HygieneError("GitHub read-only token not configured")
        self._token = token

    def get(self, repo: str, path: str):
        url = f"https://api.github.com/repos/{repo}/{path}"
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "trusted-pr-hygiene",
        })
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read(_MAX_RESPONSE + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise HygieneError("GitHub metadata request failed") from exc
        if len(raw) > _MAX_RESPONSE:
            raise HygieneError("GitHub metadata response too large")
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise HygieneError("Invalid GitHub metadata response") from exc


def _snapshot(reader, repo: str, number: int, head: str, base: str) -> int:
    data = reader.get(repo, f"pulls/{number}")
    if not isinstance(data, dict):
        raise HygieneError("Unexpected pull request metadata")
    try:
        valid = (
            data["number"] == number
            and data["state"] == "open"
            and data["head"]["sha"].lower() == head.lower()
            and data["base"]["sha"].lower() == base.lower()
            and data["base"]["repo"]["full_name"] == repo
        )
        count = data["changed_files"]
    except (KeyError, AttributeError, TypeError) as exc:
        raise HygieneError("Incomplete pull request metadata") from exc
    if not valid:
        raise HygieneError("Pull request head/base changed or repository mismatch")
    if type(count) is not int or not 1 <= count < _MAX_FILES:
        raise HygieneError("Changed-file count invalid or exceeds API completeness limit")
    return count


def check_pr(reader, repo: str, number: int, head: str, base: str) -> tuple[int, list[str]]:
    """Return (number of paths inspected, forbidden paths).

    Read all pages; verify stable head/base and exact file count afterward.
    GitHub's list-files endpoint stops at 3000 paths, so refuse >=3000.
    """
    if not isinstance(repo, str) or not _REPO.fullmatch(repo):
        raise HygieneError("Invalid repository identifier")
    if type(number) is not int or not 1 <= number <= 2_147_483_647:
        raise HygieneError("Invalid pull request number")
    if not isinstance(head, str) or not _SHA.fullmatch(head):
        raise HygieneError("Invalid head SHA")
    if not isinstance(base, str) or not _SHA.fullmatch(base):
        raise HygieneError("Invalid base SHA")

    count = _snapshot(reader, repo, number, head, base)
    active = []
    unique_paths = set()
    seen = 0
    page = 1
    while seen < count:
        batch = reader.get(repo, f"pulls/{number}/files?per_page=100&page={page}")
        if not isinstance(batch, list) or not 1 <= len(batch) <= 100:
            raise HygieneError("Missing or malformed file-list page")
        for item in batch:
            if not isinstance(item, dict):
                raise HygieneError("Invalid file-list record")
            path, status = item.get("filename"), item.get("status")
            if not isinstance(path, str) or not path or len(path) > 4096:
                raise HygieneError("Invalid changed filename")
            if not isinstance(status, str) or status not in _ACTIVE | {"removed"}:
                raise HygieneError("Unexpected changed-file status")
            if path in unique_paths:
                raise HygieneError("Duplicate changed filename in PR metadata")
            unique_paths.add(path)
            if status != "removed":
                active.append(path)
        seen += len(batch)
        if seen > count:
            raise HygieneError("File-list count exceeds pull request metadata")
        page += 1
    if seen != count or _snapshot(reader, repo, number, head, base) != count:
        raise HygieneError("Pull request changed during evaluation")
    return seen, violations_for_paths(active)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Trusted GitHub PR path gate (read-only)")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parser.add_argument("--head", required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args(argv)
    try:
        seen, forbidden = check_pr(
            GitHubReader(os.environ.get("GITHUB_TOKEN", "")),
            args.repo, args.number, args.head, args.base,
        )
    except HygieneError as exc:
        print(f"TRUSTED HIGIENE ERROR: {str(exc)!r}", file=sys.stderr)
        return 2
    if forbidden:
        print("TRUSTED HIGIENE FAILED: forbidden added/modified/type-changed paths:", file=sys.stderr)
        for path in forbidden:
            print(f"  - {path!r}", file=sys.stderr)
        return 1
    print(f"TRUSTED HIGIENE OK: {seen} changed paths evaluated using trusted policy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
