"""PR42: Graph Page inbound, sin red, cookies, tokens ni operaciones reales."""
import copy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import facebook_page_inbound as fb

PAGE = "123456789012"
NOW = dt.datetime(2026, 10, 9, 15, tzinfo=dt.timezone.utc)


def comment(i, author="456789", date="2026-10-09T10:00:00Z", parent=None):
    obj = {"id": f"88_{i}", "from": {"id": author}, "created_time": date,
           "message": "Privado: nombre@ejemplo.invalid"}
    if parent is not None:
        obj["parent"] = {"id": parent}
    return obj


def fixture(*events):
    return {"surface": "page_posts", "page_id": PAGE, "posts": {
        "data": [{"id": PAGE + "_88", "from": {"id": PAGE},
                  "comments": {"data": list(events), "filter": "toplevel",
                               "summary": {"total_count": len(events)}},
                  "reactions": {"summary": {"total_count": 17}}}]}}


def report(payload, *, now=NOW):
    return fb.assess(payload, PAGE, now=now)


class FacebookPageInboundTests(unittest.TestCase):
    def test_direct_page_comments_only_not_private_replies(self):
        raw = fixture(comment(1), comment(2, author=PAGE),
                      comment(3, parent="other_comment"), comment(4))
        result = report(raw)
        self.assertEqual(result["comments_observed_14d"], 2)
        self.assertEqual(result["reactions_aggregate"], 17)
        self.assertEqual(result["page_posts_observed"], 1)
        self.assertEqual(result["status"], "observed_unverified")
        self.assertFalse(result["permission_verified"])
        self.assertFalse(result["can_reward_or_reply"])

    def test_page_id_mismatch_and_group_never_read_as_page(self):
        for raw in (fixture(comment(1)), fixture()):
            raw["surface"] = "groups"
            self.assertEqual(report(raw)["status"], "out_of_scope")
        raw = fixture(comment(1))
        raw["posts"]["data"][0]["from"]["id"] = "9999"
        self.assertEqual(report(raw)["status"], "invalid_post_identity")
        raw = fixture(comment(1))
        raw["posts"]["data"][0]["group_id"] = "42"
        self.assertEqual(report(raw)["status"], "out_of_scope")
        raw = fixture(comment(1))
        raw["page_id"] = "different"
        self.assertEqual(report(raw)["status"], "out_of_scope")

    def test_missing_author_id_or_aware_timestamp_never_zero(self):
        for bad in ("no-date", "2026-10-09T10:00:00", "2026-10-10T10:00:00Z"):
            self.assertEqual(report(fixture(comment(1, date=bad)))["status"], "invalid_comment")
        raw = fixture(comment(1))
        del raw["posts"]["data"][0]["comments"]["data"][0]["from"]
        self.assertIsNone(report(raw)["comments_observed_14d"])
        raw = fixture(comment(1))
        del raw["posts"]["data"][0]["comments"]["filter"]
        self.assertEqual(report(raw)["status"], "incomplete")

    def test_missing_or_paginated_comments_not_zero(self):
        raw = fixture(comment(1))
        raw["posts"]["data"][0]["comments"]["paging"] = {"next": "https://example.invalid/next"}
        self.assertEqual(report(raw)["status"], "incomplete")
        raw = fixture(comment(1))
        raw["posts"]["paging"] = {"next": "https://example.invalid/next"}
        self.assertEqual(report(raw)["status"], "incomplete")
        raw = fixture(comment(1))
        raw["posts"]["data"][0]["comments"]["summary"]["total_count"] = 2
        self.assertEqual(report(raw)["status"], "incomplete")
        raw = fixture(comment(1))
        del raw["posts"]["data"][0]["comments"]
        self.assertEqual(report(raw)["status"], "incomplete")
        raw = fixture(comment(1))
        raw["posts"]["data"][0]["comments"]["paging"] = "ambiguous"
        self.assertEqual(report(raw)["status"], "incomplete")
        raw = fixture(comment(1))
        raw["posts"]["data"][0]["comments"]["paging"] = {"next": ""}
        self.assertEqual(report(raw)["status"], "incomplete")

    def test_stream_or_private_comments_cannot_be_mislabeled_as_toplevel(self):
        raw = fixture(comment(1))
        raw["posts"]["data"][0]["comments"]["filter"] = "stream"
        self.assertEqual(report(raw)["status"], "incomplete")
        raw = fixture(comment(1))
        raw["posts"]["data"][0]["comments"]["data"][0]["is_private"] = True
        self.assertEqual(report(raw)["status"], "incomplete")
        raw = fixture(comment(1))
        raw["posts"]["data"][0]["comments"]["data"][0]["is_hidden"] = True
        self.assertEqual(report(raw)["status"], "incomplete")
        raw = fixture(comment(1))
        raw["posts"]["data"][0]["comments"]["data"][0]["is_private"] = "yes"
        self.assertEqual(report(raw)["status"], "invalid_comment")

    def test_no_comment_field_is_not_no_comments_and_zero_valid_if_explicit(self):
        empty = {"surface": "page_posts", "page_id": PAGE,
                 "posts": {"data": []}}
        self.assertEqual(report(empty)["status"], "empty_unverified")
        self.assertIsNone(report(empty)["comments_observed_14d"])
        result = report(fixture())
        self.assertEqual(result["comments_observed_14d"], 0)
        self.assertEqual(result["status"], "observed_unverified")
        raw = fixture()
        del raw["posts"]["data"][0]["comments"]["summary"]
        self.assertIsNone(report(raw)["comments_observed_14d"])

    def test_duplicate_ids_and_malformed_reactions_fail_closed(self):
        self.assertEqual(report(fixture(comment(1), comment(1)))["status"], "invalid_comment")
        raw = fixture(comment(1))
        raw["posts"]["data"][0]["reactions"]["summary"]["total_count"] = True
        self.assertEqual(report(raw)["status"], "invalid_reactions")
        raw = fixture(comment(1))
        del raw["posts"]["data"][0]["reactions"]
        self.assertIsNone(report(raw)["reactions_aggregate"])
        self.assertEqual(report(raw)["comments_observed_14d"], 1)

    def test_graph_failures_are_not_reported_as_zero(self):
        for code, expected in [(200, "permission_denied"), (10, "permission_denied"),
                               (190, "invalid_token"), (429, "rate_limited"),
                               (613, "rate_limited"),
                               (368, "platform_block"), (700, "api_error")]:
            result = report({"error": {"code": code, "message": "SECRET"}})
            self.assertEqual(result["status"], expected)
            self.assertIsNone(result["comments_observed_14d"])
            self.assertNotIn("SECRET", repr(result))

    def test_age_window_and_aware_clocks(self):
        old = comment(1, date="2026-09-20T10:00:00Z")
        recent = comment(2)
        self.assertEqual(report(fixture(old, recent))["comments_observed_14d"], 1)
        shifted = NOW + dt.timedelta(days=30)
        self.assertEqual(report(fixture(recent), now=shifted)["comments_observed_14d"], 0)
        with self.assertRaises(ValueError):
            report(fixture(recent), now=dt.datetime(2026, 10, 9))
        with self.assertRaises(ValueError):
            fb.assess(fixture(), "page-name", now=NOW)

    def test_no_personal_text_identifiers_or_private_metadata_in_output(self):
        raw = fixture(comment(1))
        raw["private_message"] = "SECRET_PROFILE_PERSON"
        result = report(raw)
        encoded = json.dumps(result)
        for secret in ("SECRET_PROFILE_PERSON", "nombre@ejemplo.invalid", "456789"):
            self.assertNotIn(secret, encoded)
        before = copy.deepcopy(raw)
        report(raw)
        self.assertEqual(raw, before)

    def test_malformed_structures_do_not_crash(self):
        for raw in (None, [], {}, {"surface": "page_posts", "page_id": PAGE,
                                    "posts": {"data": [None]}}):
            self.assertIsNone(report(raw)["comments_observed_14d"])

    def test_cli_is_readonly_and_rejects_duplicate_keys_nan_and_large(self):
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "inbound.json"
            file.write_text(json.dumps(fixture(comment(1))), encoding="utf-8")
            original = (file.read_bytes(), file.stat().st_mtime_ns)
            with patch("sys.argv", ["f", "--input", str(file), "--page-id", PAGE,
                                    "--now", "2026-10-09T15:00:00+00:00"]):
                self.assertEqual(fb.main(), 0)
            self.assertEqual((file.read_bytes(), file.stat().st_mtime_ns), original)
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ["inbound.json"])
            for data in ('{"page_id":1,"page_id":2}', '{"x":NaN}', "{" * 3000):
                file.write_text(data, encoding="utf-8")
                with patch("sys.argv", ["f", "--input", str(file), "--page-id", PAGE]):
                    self.assertEqual(fb.main(), 2)
            link = Path(tmp) / "alias.json"
            try:
                link.symlink_to(file)
            except (OSError, NotImplementedError):
                pass  # Windows sin privilegios de enlaces simbólicos
            else:
                with patch("sys.argv", ["f", "--input", str(link), "--page-id", PAGE]):
                    self.assertEqual(fb.main(), 2)
                link.unlink()
            file.write_bytes(b" " * (fb.MAX_BYTES + 1))
            with patch("sys.argv", ["f", "--input", str(file), "--page-id", PAGE]):
                self.assertEqual(fb.main(), 2)

    def test_no_cross_network_or_writing_capabilities(self):
        result = report(fixture(comment(1)))
        self.assertEqual(result["network"], "facebook")
        self.assertEqual(result["coverage"], "no_live_access_proven")
        self.assertFalse(result["can_reward_or_reply"])


if __name__ == "__main__":
    unittest.main()
