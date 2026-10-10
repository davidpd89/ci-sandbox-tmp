"""Audit proposed workflow identities as DATA from a trusted default-branch job.

This is an additional collision detector, not proof that branch protection is
configured or that GitHub has enforced a required workflow by identity.
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
import yaml

OWNERS = {
    "trusted-pr-paths": ".github/workflows/trusted-pr-hygiene.yml",
    "trusted-check-provenance": ".github/workflows/required-check-provenance.yml",
}
# Immutable-from-PR trusted sources, including transitively imported policy.
PROTECTED_TRUST = frozenset({
    ".github/workflows/trusted-pr-hygiene.yml",
    ".github/workflows/required-check-provenance.yml",
    "tools/trusted_pr_hygiene.py",
    "tools/repo_hygiene.py",
    "tools/required_check_provenance.py",
    "tools/required_check_evidence.py",
})
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[0-9a-fA-F]{40}$")
EXPR = re.compile(r"\$\{\{.*?\}\}", re.DOTALL)
MAX_FILES = 999
MAX_FILE_BYTES = 250_000


class AuditError(Exception):
    pass


class Loader(yaml.SafeLoader):
    pass


# Prevent YAML 1.1 interpreting the GitHub Actions key 'on' as True.
Loader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in rules if tag != "tag:yaml.org,2002:bool"]
    for key, rules in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def unique_mapping(loader, node):
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, (str, int, float, bool, tuple)):
            raise AuditError("complex mapping key")
        if key in result:
            raise AuditError("duplicate YAML key")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def parse_workflow(raw, path):
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_FILE_BYTES:
        raise AuditError("missing or oversized workflow")
    try:
        doc = yaml.load(raw, Loader=Loader)
    except (yaml.YAMLError, ValueError, TypeError, RecursionError) as exc:
        raise AuditError("invalid YAML in " + repr(path)) from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("jobs"), dict):
        raise AuditError("workflow has no jobs: " + repr(path))
    return doc


def could_be(display, required):
    if not isinstance(display, str):
        raise AuditError("non-string job name")
    display = display.strip().casefold()
    required = required.strip().casefold()
    chunks = EXPR.split(display)
    if len(chunks) == 1:
        if "$" + "{{" in display:
            raise AuditError("malformed dynamic display name")
        return display == required
    regex = ".*".join(re.escape(s) for s in chunks)
    return re.fullmatch(regex, required, re.DOTALL) is not None


def target_only(doc):
    events = doc.get("on")
    if isinstance(events, str):
        names = {events}
    elif isinstance(events, list) and all(isinstance(e, str) for e in events):
        names = set(events)
    elif isinstance(events, dict):
        names = set(events)
    else:
        return False
    if names != {"pull_request_target"}:
        return False
    options = events.get("pull_request_target") if isinstance(events, dict) else None
    if options is None:
        return True
    if not isinstance(options, dict) or set(options) - {"types"}:
        return False
    types = options.get("types")
    return types is None or (
        isinstance(types, list) and all(isinstance(t, str) for t in types)
        and {"opened", "reopened", "synchronize"}.issubset(set(types))
    )


def audit_workflows(workflows, owners=OWNERS):
    """Checks every YAML workflow in the proposed HEAD, not just changed files."""
    if not isinstance(workflows, dict) or not 0 < len(workflows) <= MAX_FILES:
        raise AuditError("incomplete workflow inventory")
    seen = set()
    matches = {name: [] for name in owners}
    for path, raw in sorted(workflows.items()):
        if (not isinstance(path, str) or not path.startswith(".github/workflows/")
            or not path.endswith((".yml", ".yaml"))
            or "/" in path[len(".github/workflows/"):] or path.casefold() in seen):
            raise AuditError("invalid workflow path")
        seen.add(path.casefold())
        doc = parse_workflow(raw, path)
        for job_id, job in doc["jobs"].items():
            if not isinstance(job_id, str) or not isinstance(job, dict):
                raise AuditError("invalid job")
            display = job.get("name", job_id)
            for name in owners:
                if could_be(display, name):
                    matches[name].append((path, job_id))
                    if path == owners[name]:
                        # Reserved checks must materialize as one literal job
                        # name. Matrices and expressions are not unambiguous.
                        if display != name:
                            raise AuditError("required job name is not literal: " + repr(path))
                        if "if" in job:
                            raise AuditError("required job can be skipped: " + repr(path))
                        strategy = job.get("strategy")
                        if strategy is not None and (
                            not isinstance(strategy, dict) or "matrix" in strategy
                        ):
                            raise AuditError("required job has ambiguous matrix: " + repr(path))
        if path in owners.values() and not target_only(doc):
            raise AuditError("trusted workflow has non-target triggers: " + repr(path))
    for name, owner_path in owners.items():
        if len(matches[name]) != 1 or matches[name][0][0] != owner_path:
            raise AuditError("missing, renamed or colliding check: " + repr(name))
    return {name: owner for name, owner in owners.items()}


@dataclass
class Reader:
    token: str
    api: str = "https://api.github.com"

    def get(self, path):
        if not self.token:
            raise AuditError("missing read-only token")
        request = urllib.request.Request(self.api + path, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "required-check-provenance",
        })
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = response.read(2_000_001)
                if response.status != 200 or len(data) > 2_000_000:
                    raise AuditError("invalid API response")
                return json.loads(data)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise AuditError("GitHub API read failed") from exc


def repo_endpoint(repo):
    if not isinstance(repo, str) or not REPO.fullmatch(repo):
        raise AuditError("invalid repository name")
    owner, name = repo.split("/", 1)
    if owner in {".", ".."} or name in {".", ".."}:
        raise AuditError("invalid repository path segment")
    return "/repos/" + repo


def snapshot(reader, repo, number, head, base):
    data = reader.get(repo_endpoint(repo) + "/pulls/" + str(number))
    try:
        if (data["state"] != "open" or data["head"]["sha"] != head
            or data["base"]["sha"] != base
            or data["base"]["repo"]["full_name"] != repo):
            raise AuditError("stale PR head/base or wrong repository")
        head_repo = data["head"]["repo"]["full_name"]
    except (KeyError, TypeError) as exc:
        raise AuditError("incomplete PR snapshot") from exc
    repo_endpoint(head_repo)
    return head_repo


def inventory(reader, head_repo, sha):
    prefix = repo_endpoint(head_repo) + "/contents/"
    ref = "?ref=" + urllib.parse.quote(sha, safe="")
    entries = reader.get(prefix + ".github/workflows" + ref)
    if not isinstance(entries, list) or not 0 < len(entries) <= MAX_FILES:
        raise AuditError("missing or oversized workflow directory")
    result = {}
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise AuditError("invalid workflow directory entry")
        path = entry.get("path")
        if (entry.get("type") != "file" or not isinstance(path, str)
            or not path.startswith(".github/workflows/")
            or "/" in path[len(".github/workflows/"):] or path.casefold() in seen):
            raise AuditError("unexpected workflow directory entry")
        seen.add(path.casefold())
        if not path.endswith((".yml", ".yaml")):
            continue
        record = reader.get(prefix + urllib.parse.quote(path, safe="/") + ref)
        if (not isinstance(record, dict) or record.get("type") != "file"
            or record.get("path") != path or record.get("encoding") != "base64"):
            raise AuditError("cannot read workflow contents")
        try:
            encoded = record["content"]
            if not isinstance(encoded, str):
                raise AuditError("invalid content type")
            raw = base64.b64decode(encoded, validate=False)
            if len(raw) > MAX_FILE_BYTES:
                raise AuditError("oversized workflow contents")
            result[path] = raw.decode("utf-8")
        except (ValueError, TypeError, KeyError, UnicodeError) as exc:
            raise AuditError("invalid workflow content") from exc
    return result


def audit_trusted_sources(reader, repo, head_repo, head, base, paths=PROTECTED_TRUST):
    """Require exact SHA equality with default/base for all trusted dependencies.

    Admin must bootstrap new gates separately before enabling this check.
    Approved gate upgrades need a supervised out-of-band promotion.
    """
    for path in sorted(paths):
        quoted = urllib.parse.quote(path, safe="/")
        def get_sha(source, ref):
            record = reader.get(repo_endpoint(source) + "/contents/" + quoted +
                                "?ref=" + urllib.parse.quote(ref, safe=""))
            if (not isinstance(record, dict) or record.get("path") != path
                or record.get("type") != "file"
                or not isinstance(record.get("sha"), str)
                or not SHA.fullmatch(record["sha"])):
                raise AuditError("missing trusted source: " + repr(path))
            return record["sha"]
        trusted = get_sha(repo, base)
        proposed = get_sha(head_repo, head)
        if trusted != proposed:
            raise AuditError("trusted source modified; independent promotion required: " +
                             repr(path))


def check_pr(reader, repo, number, head, base, owners=OWNERS):
    repo_endpoint(repo)
    if (type(number) is not int or number < 1 or not isinstance(head, str)
        or not isinstance(base, str) or not SHA.fullmatch(head) or not SHA.fullmatch(base)):
        raise AuditError("invalid PR arguments")
    head_repo = snapshot(reader, repo, number, head, base)
    results = audit_workflows(inventory(reader, head_repo, head), owners)
    audit_trusted_sources(reader, repo, head_repo, head, base)
    if snapshot(reader, repo, number, head, base) != head_repo:
        raise AuditError("head repository changed mid-scan")
    return results


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parser.add_argument("--head", required=True)
    parser.add_argument("--base", required=True)
    args = parser.parse_args(argv)
    try:
        results = check_pr(Reader(os.getenv("GITHUB_TOKEN", "")),
                           args.repo, args.number, args.head, args.base)
    except (AuditError, yaml.YAMLError) as exc:
        print("CHECK PROVENANCE FAIL: " + repr(str(exc)), file=sys.stderr)
        return 1
    print("CHECK PROVENANCE OK (workflow inventory): " + ", ".join(sorted(results)))
    print("A separate admin verification of required workflow/check remains mandatory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
