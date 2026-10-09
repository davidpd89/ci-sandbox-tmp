"""Synthetic live Checks API payloads, never a real account or status mutation."""
from __future__ import annotations
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import required_check_evidence as e
import required_check_provenance as p

REPO = "demo/sanitized"
HEAD, BASE, MERGE = "a" * 40, "b" * 40, "c" * 40


def fixtures():
    checks = []
    records = {}
    for i, (name, path) in enumerate(p.OWNERS.items(), 1):
        run_id, job_id, check_id, suite_id = 200 + i, 300 + i, 400 + i, 500 + i
        checks.append({
            "id": check_id, "name": name, "status": "completed", "conclusion": "success",
            "head_sha": MERGE, "app": {"slug": "github-actions"},
            "check_suite": {"id": suite_id},
            "details_url": "https://github.com/" + REPO + "/actions/runs/" +
                           str(run_id) + "/job/" + str(job_id),
        })
        records["/repos/" + REPO + "/actions/runs/" + str(run_id)] = {
            "id": run_id, "event": "pull_request_target", "path": path,
            "conclusion": "success", "check_suite_id": suite_id,
            "pull_requests": [{"number": 96, "head": {"sha": HEAD}}],
        }
        records["/repos/" + REPO + "/actions/jobs/" + str(job_id)] = {
            "id": job_id, "run_id": run_id, "name": name, "conclusion": "success",
            "check_run_url": "https://api.github.com/repos/" + REPO +
                             "/check-runs/" + str(check_id),
        }
    return checks, records


class SyntheticReader:
    def __init__(self, *, mutate=None):
        self.checks, self.records = fixtures()
        self.statuses = []
        self.pr = {
            "state": "open", "head": {"sha": HEAD},
            "base": {"sha": BASE, "repo": {"full_name": REPO}},
            "merge_commit_sha": MERGE,
        }
        self.mutate = mutate
        self.calls = []

    def get(self, path):
        self.calls.append(path)
        if path == "/repos/" + REPO + "/pulls/96":
            if self.mutate and self.calls.count(path) == 2:
                self.pr["head"]["sha"] = "d" * 40
            return copy.deepcopy(self.pr)
        if "/check-runs?" in path:
            return {"total_count": len(self.checks), "check_runs": copy.deepcopy(self.checks)}
        if "/statuses?" in path:
            return copy.deepcopy(self.statuses)
        return copy.deepcopy(self.records[path])


class LiveEvidenceTests(unittest.TestCase):
    def verify(self, reader=None, ref=MERGE):
        return e.verify_live(reader or SyntheticReader(), REPO, 96, HEAD, BASE, ref)

    def test_valid_observed_run_job_and_latest_merge(self):
        self.assertEqual(self.verify(), list(p.OWNERS))
        with self.assertRaisesRegex(p.AuditError, "SHA"):
            self.verify(ref="f" * 40)

    def test_other_events_workflows_and_jobs_rejected(self):
        for field, value in (("event", "pull_request"), ("path", ".github/workflows/fake.yml"),
                             ("conclusion", "skipped"), ("check_suite_id", -1)):
            with self.subTest(field=field):
                reader = SyntheticReader()
                reader.records["/repos/" + REPO + "/actions/runs/201"][field] = value
                with self.assertRaises(p.AuditError):
                    self.verify(reader)
        r = SyntheticReader()
        r.records["/repos/" + REPO + "/actions/jobs/301"]["name"] = "renamed"
        with self.assertRaises(p.AuditError):
            self.verify(r)

    def test_checks_skipped_neutral_or_stale_blocked(self):
        for field, value in (("conclusion", "skipped"), ("conclusion", "neutral"),
                             ("status", "in_progress"), ("head_sha", HEAD),
                             ("app", {"slug": "custom-app"})):
            with self.subTest(field=field):
                r = SyntheticReader()
                r.checks[0][field] = value
                with self.assertRaises(p.AuditError):
                    self.verify(r)

    def test_collisions_missing_and_status_context(self):
        r = SyntheticReader()
        r.checks += [copy.deepcopy(r.checks[0])]
        with self.assertRaisesRegex(p.AuditError, "duplicated"):
            self.verify(r)
        r = SyntheticReader()
        r.checks.pop()
        with self.assertRaises(p.AuditError):
            self.verify(r)
        r = SyntheticReader()
        r.statuses.append({"context": "trusted-pr-paths", "state": "success"})
        with self.assertRaisesRegex(p.AuditError, "collides"):
            self.verify(r)

    def test_pr_association_required_and_head_movement(self):
        r = SyntheticReader()
        r.records["/repos/" + REPO + "/actions/runs/201"]["pull_requests"] = []
        with self.assertRaisesRegex(p.AuditError, "linked"):
            self.verify(r)
        with self.assertRaisesRegex(p.AuditError, "stale"):
            self.verify(SyntheticReader(mutate=True))

    def test_malformed_and_bounded_pagination(self):
        class Short:
            def __init__(self, response):
                self.response = response
            def get(self, path):
                return self.response
        for response in ({"total_count": 5, "check_runs": []},
                         {"total_count": 1, "check_runs": [1] * 100}):
            with self.subTest(response=str(response)[:20]), self.assertRaises(p.AuditError):
                e.pages(Short(response), "/x", "check_runs", limit=1)
        with self.assertRaises(p.AuditError):
            e.pages(Short({"check_runs": []}), "/x", "check_runs")

    def test_invalid_arguments_no_network(self):
        reader = SyntheticReader()
        with self.assertRaises(p.AuditError):
            e.verify_live(reader, REPO, 0, HEAD, BASE, MERGE)
        self.assertEqual(reader.calls, [])


if __name__ == "__main__":
    unittest.main()
