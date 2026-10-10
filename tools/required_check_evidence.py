"""Operator-only LIVE source audit of required GitHub Actions checks.

Use AFTER branch protection and trusted workflows are installed. This program
is not itself a required gate; it refuses missing/ambiguous evidence. HTTP GET
only. Supports PR HEAD and merge SHA independently as GitHub may require either.
"""
from __future__ import annotations
import argparse
import re
import sys
from required_check_provenance import Reader, AuditError, OWNERS, SHA, repo_endpoint

class EvidenceUnavailable(AuditError):
    """An otherwise valid run lacks proof tying it to this specific PR."""


DETAILS = re.compile(
    r"^https://github\.com/([^/]+/[^/]+)/actions/runs/([0-9]+)/job/([0-9]+)(?:\?.*)?$"
)


def pages(reader, url, collection, limit=10):
    """Bounded, complete, deduplicated GitHub API paging."""
    all_items, seen = [], set()
    total = None
    for page in range(1, limit + 1):
        suffix = ("&" if "?" in url else "?") + "per_page=100&page=" + str(page)
        obj = reader.get(url + suffix)
        if collection is None:
            if not isinstance(obj, list):
                raise AuditError("invalid paginated status response")
            batch = obj
        else:
            if not isinstance(obj, dict) or not isinstance(obj.get(collection), list):
                raise AuditError("invalid paginated checks response")
            batch = obj[collection]
            reported = obj.get("total_count")
            if type(reported) is not int or reported < 0:
                raise AuditError("missing check count")
            if total is None:
                total = reported
            elif total != reported:
                raise AuditError("check count changed during pagination")
        for item in batch:
            if not isinstance(item, dict) or type(item.get("id")) is not int:
                raise AuditError("check/status missing stable identity")
            if item["id"] in seen:
                raise AuditError("duplicate check/status across API pages")
            seen.add(item["id"])
        all_items.extend(batch)
        if total is not None and len(all_items) > total:
            raise AuditError("check inventory exceeds reported count")
        if total is not None and len(all_items) == total:
            return all_items
        if len(batch) < 100:
            if total is not None and len(all_items) != total:
                raise AuditError("truncated check-run list")
            return all_items
    raise AuditError("check/status pagination limit exceeded")


def verify_live(reader, repo, number, head, base, ref, owners=OWNERS):
    """Validate observed check->job->run provenance using *actual* API records."""
    root = repo_endpoint(repo)
    if (type(number) is not int or number < 1 or not isinstance(ref, str)
        or not SHA.fullmatch(ref) or not SHA.fullmatch(head)
        or not SHA.fullmatch(base)):
        raise AuditError("invalid live evidence arguments")

    def pr_state():
        pr = reader.get(root + "/pulls/" + str(number))
        try:
            if (pr["state"] != "open" or pr["head"]["sha"] != head
                or pr["base"]["sha"] != base
                or pr["base"]["repo"]["full_name"] != repo):
                raise AuditError("stale or wrong PR")
            if ref not in (head, base, pr.get("merge_commit_sha")):
                raise AuditError("SHA is not the current PR head/base/merge")
            return (pr["head"]["sha"], pr.get("merge_commit_sha"))
        except (KeyError, TypeError) as exc:
            raise AuditError("incomplete live PR metadata") from exc

    initial = pr_state()
    checks = pages(reader, root + "/commits/" + ref + "/check-runs", "check_runs")
    statuses = pages(reader, root + "/commits/" + ref + "/statuses", None)
    for status in statuses:
        if isinstance(status, dict) and status.get("context") in owners:
            raise AuditError("commit status collides with required check")
        if not isinstance(status, dict) or not isinstance(status.get("context"), str):
            raise AuditError("invalid commit status evidence")

    verified = []
    for check_name, trusted_path in owners.items():
        named = [c for c in checks if isinstance(c, dict) and c.get("name") == check_name]
        if len(named) != 1:
            raise AuditError("absent/duplicated check on SHA: " + repr(check_name))
        check = named[0]
        if (check.get("status") != "completed" or check.get("conclusion") != "success"
            or check.get("head_sha") != ref
            or not isinstance(check.get("id"), int)
            or not isinstance(check.get("app"), dict)
            or check["app"].get("slug") != "github-actions"):
            raise AuditError("check not a successful GitHub Actions check")
        m = DETAILS.fullmatch(str(check.get("details_url", "")))
        if not m or m.group(1) != repo:
            raise AuditError("check has no canonical Actions job URL")
        run_id, job_id = int(m.group(2)), int(m.group(3))
        run = reader.get(root + "/actions/runs/" + str(run_id))
        job = reader.get(root + "/actions/jobs/" + str(job_id))
        if (not isinstance(run, dict) or not isinstance(job, dict)
            or run.get("id") != run_id or job.get("id") != job_id
            or job.get("run_id") != run_id
            or job.get("name") != check_name
            or job.get("conclusion") != "success"
            or job.get("status", "completed") != "completed"
            or run.get("event") != "pull_request_target"
            or run.get("path") != trusted_path
            or run.get("conclusion") != "success"
            or not isinstance(check.get("check_suite"), dict)
            or run.get("check_suite_id") != check["check_suite"].get("id")
            or str(job.get("check_run_url", "")).rsplit("/", 1)[-1] != str(check["id"])):
            raise AuditError("run/job identity or provenance mismatch")
        # An Actions run must point to the same PR head when GitHub provides
        # PR associations; absent associations cannot prove PR identity.
        associated = run.get("pull_requests")
        if associated == [] or associated is None:
            # Documented live pull_request_target payloads frequently have
            # pull_requests=[] even for a legitimate PR-triggered run.
            # Do not misclassify that absence as malicious or as proof of PR.
            raise EvidenceUnavailable(
                "run.pull_requests empty: origin verified but PR linkage "
                "unverified; inspect trusted run event/log and active ruleset manually"
            )
        if (not isinstance(associated, list) or not any(
            isinstance(p, dict) and p.get("number") == number
            and isinstance(p.get("head"), dict)
            and p["head"].get("sha") == head for p in associated
        )):
            raise AuditError("workflow run is not linked to current PR head")
        verified.append(check_name)

    if pr_state() != initial:
        raise AuditError("PR ref moved while checking evidence")
    return verified


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", type=int, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--ref", required=True, help="observed check SHA (PR head, current merge or base); may need manual verification")
    args = parser.parse_args(argv)
    import os
    try:
        names = verify_live(Reader(os.getenv("GITHUB_TOKEN", "")), args.repo,
                            args.number, args.head, args.base, args.ref)
    except EvidenceUnavailable as exc:
        print("MANUAL PR LINK VERIFICATION REQUIRED: " + repr(str(exc)), file=sys.stderr)
        return 3
    except AuditError as exc:
        print("LIVE CHECK EVIDENCE UNVERIFIED: " + repr(str(exc)), file=sys.stderr)
        return 1
    print("Observed expected Actions run/job origin for " + ", ".join(names))
    print("This is NOT proof that branch protection is enabled; test blocked merge separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
