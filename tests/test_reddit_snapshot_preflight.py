"""Pruebas offline del contrato de dos Listings Reddit; sin OAuth ni red."""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from reddit_snapshot_preflight import evaluate  # noqa: E402

FIXTURES = json.loads((ROOT / "tests" / "fixtures" / "reddit_snapshot_preflight.json").read_text(encoding="utf-8"))


def scenario(name=None):
    item = copy.deepcopy(FIXTURES["baseline"])
    if name:
        change = FIXTURES["cases"][name]
        for key in ("plan", "review", "snapshot"):
            if key in change:
                item[key].update(change[key])
        if "post" in change:
            item["snapshot"]["body"][0]["data"]["children"][0]["data"].update(change["post"])
        if "comments" in change:
            item["snapshot"]["body"][1]["data"]["children"] = change["comments"]
    return item


def decision(case=None):
    item = scenario(case)
    at = datetime.fromisoformat(item["now"].replace("Z", "+00:00"))
    return evaluate(item["plan"], item["snapshot"], item["review"], now=at)


class RedditSnapshotPreflightTests(unittest.TestCase):
    def test_valid_synthetic_listing_allows_manual_review_only(self):
        result = decision()
        self.assertTrue(result.allowed, result.reason)
        self.assertIn("revisión manual", result.reason)

    def test_safety_cases_block_inappropriate_comment(self):
        for name in (
            "restricted_subreddit", "automod_removed", "own_reply_removed",
            "http_429", "closed_thread", "quoted_message_missing",
            "stale_thread", "unexpanded_children", "wrong_thread",
            "uncertain_history", "stale_snapshot", "rules_undocumented",
            "cited_deleted",
        ):
            with self.subTest(case=name):
                result = decision(name)
                self.assertFalse(result.allowed, result.reason)

    def test_real_comment_quoted_id_must_be_found_in_listing(self):
        self.assertTrue(decision("quoted_message_valid").allowed)
        self.assertFalse(decision("quoted_message_missing").allowed)
        self.assertFalse(decision("cited_deleted").allowed)

    def test_fields_missing_fail_closed_not_keyerror(self):
        for key in ("id", "subreddit", "locked", "archived", "created_utc", "removed_by_category"):
            with self.subTest(field=key):
                item = scenario()
                del item["snapshot"]["body"][0]["data"]["children"][0]["data"][key]
                result = evaluate(item["plan"], item["snapshot"], item["review"],
                                  now=datetime(2026, 10, 9, 19, 5, tzinfo=timezone.utc))
                self.assertFalse(result.allowed, result.reason)

    def test_url_cannot_point_to_nested_comment_or_other_host(self):
        for url in (
            "https://reddit.com.attacker.invalid/r/libros/comments/abc123/",
            "https://www.reddit.com/r/libros/comments/abc123/titulo/c001/",
            "https://www.reddit.com/r/libros/comments/abc123/?comment=c001",
        ):
            item = scenario()
            item["plan"]["url"] = url
            result = evaluate(item["plan"], item["snapshot"], item["review"],
                              now=datetime(2026, 10, 9, 19, 5, tzinfo=timezone.utc))
            self.assertFalse(result.allowed, url)

    def test_missing_quote_provenance_blocks_markdown_quote(self):
        item = scenario()
        item["plan"]["text"] = "> Mensaje citado\\nMi respuesta"
        result = evaluate(item["plan"], item["snapshot"], item["review"],
                          now=datetime(2026, 10, 9, 19, 5, tzinfo=timezone.utc))
        self.assertFalse(result.allowed)

    def test_cli_blocks_real_write_proceeding_when_429(self):
        item = scenario("http_429")
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for key in ("plan", "snapshot", "review"):
                path = Path(tmp) / (key + ".json")
                path.write_text(json.dumps(item[key]), encoding="utf-8")
                paths.append(str(path))
            result = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "reddit_snapshot_preflight.py"),
                 "--plan", paths[0], "--snapshot", paths[1], "--review", paths[2]],
                capture_output=True, text=True, check=False, timeout=10,
            )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn('"allowed": false', result.stdout.lower())
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
