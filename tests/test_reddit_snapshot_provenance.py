"""Adversarial offline regression tests for Reddit snapshot provenance.

Only synthetic JSON; no network, accounts, credentials or remote writes.
"""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from reddit_snapshot_preflight import evaluate  # noqa: E402

DATA = json.loads((ROOT / "tests" / "fixtures" /
                   "reddit_snapshot_preflight.json").read_text(encoding="utf-8"))["baseline"]
NOW = datetime(2026, 10, 9, 19, 5, tzinfo=timezone.utc)


def load():
    return copy.deepcopy(DATA)


def check(data):
    return evaluate(data["plan"], data["snapshot"], data["review"], now=NOW)


def post(data):
    return data["snapshot"]["body"][0]["data"]["children"][0]["data"]


def comments(data):
    return data["snapshot"]["body"][1]["data"]["children"]


class ProvenanceRegressionTests(unittest.TestCase):
    def test_baseline_fingerprint_and_tree_remain_valid(self):
        self.assertTrue(check(load()).allowed)

    def test_review_cannot_be_reused_for_a_different_text(self):
        data = load()
        data["plan"]["text"] += " Otra conclusión."
        self.assertFalse(check(data).allowed)

    def test_review_cannot_be_reused_for_another_post_in_same_subreddit(self):
        data = load()
        data["plan"]["url"] = "https://www.reddit.com/r/libros/comments/abc124/otro/"
        post(data)["id"] = "abc124"
        comments(data)[0]["data"]["link_id"] = "t3_abc124"
        comments(data)[0]["data"]["parent_id"] = "t3_abc124"
        result = check(data)
        self.assertFalse(result.allowed)
        self.assertIn("revisión", result.reason)

    def test_review_must_follow_snapshot_and_be_fresh(self):
        for value in ("2026-10-09T19:03:59Z",
                      "2026-10-09T19:05:01Z",
                      "2026-10-09T19:04:30"):
            with self.subTest(value=value):
                data = load()
                data["review"]["context_checked_at"] = value
                self.assertFalse(check(data).allowed)

    def test_root_parent_and_link_must_match_post(self):
        for key in ("parent_id", "link_id"):
            with self.subTest(key=key):
                data = load()
                comments(data)[0]["data"][key] = "t3_ffff"
                self.assertFalse(check(data).allowed)

    def test_missing_link_replies_or_body_block(self):
        for field in ("link_id", "replies", "body", "author"):
            with self.subTest(field=field):
                data = load()
                del comments(data)[0]["data"][field]
                self.assertFalse(check(data).allowed)

    def test_duplicate_comment_identity_blocks_even_if_count_matches(self):
        data = load()
        comments(data).append(copy.deepcopy(comments(data)[0]))
        post(data)["num_comments"] = 2
        self.assertFalse(check(data).allowed)

    def test_true_nested_reply_can_be_checked_without_extra_requests(self):
        data = load()
        comments(data)[0]["data"]["replies"] = {
            "kind": "Listing",
            "data": {"children": [{
                "kind": "t1",
                "data": {
                    "id": "c002",
                    "link_id": "t3_abc123",
                    "parent_id": "t1_c001",
                    "author": "lector03",
                    "body": "Otra observación",
                    "replies": "",
                },
            }]},
        }
        post(data)["num_comments"] = 2
        self.assertTrue(check(data).allowed)

    def test_nested_parent_spoof_is_rejected(self):
        data = load()
        original = comments(data)[0]["data"]
        original["replies"] = {
            "kind": "Listing",
            "data": {"children": [{
                "kind": "t1",
                "data": {
                    "id": "c002",
                    "link_id": "t3_abc123",
                    "parent_id": "t1_someone_else",
                    "author": "lector03",
                    "body": "Una respuesta ajena",
                    "replies": "",
                },
            }]},
        }
        post(data)["num_comments"] = 2
        self.assertFalse(check(data).allowed)

    def test_nested_more_children_blocks(self):
        data = load()
        comments(data)[0]["data"]["replies"] = {
            "kind": "Listing",
            "data": {"children": [{"kind": "more", "data": {"count": 10}}]},
        }
        self.assertFalse(check(data).allowed)

    def test_iterative_depth_limit_does_not_crash(self):
        data = load()
        parent = comments(data)[0]["data"]
        for idx in range(65):
            child = {
                "id": f"c{idx+100}",
                "link_id": "t3_abc123",
                "parent_id": "t1_" + parent["id"],
                "author": "lector03",
                "body": "Texto sintético",
                "replies": "",
            }
            parent["replies"] = {
                "kind": "Listing", "data": {"children": [{"kind": "t1", "data": child}]}
            }
            parent = child
        post(data)["num_comments"] = 66
        self.assertFalse(check(data).allowed)

    def test_naive_or_nonfinite_timestamps_never_approve(self):
        for checked_at in ("2026-10-09T19:04:00", float("nan"), float("inf")):
            with self.subTest(checked_at=str(checked_at)):
                data = load()
                data["snapshot"]["retrieved_at"] = checked_at
                self.assertFalse(check(data).allowed)

    def test_wrong_type_http_status_is_not_accepted(self):
        data = load()
        data["snapshot"]["http_status"] = True
        self.assertFalse(check(data).allowed)


if __name__ == "__main__":
    unittest.main()
