import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from bluesky_archive_observations import normalize_archive_events

DID = "did:plc:" + "a" * 24
BASE = {"did": DID, "rkey": "3k4test", "record": {
    "text": "Acabo de leer romantasy", "createdAt": "2026-10-10T08:00:00Z", "langs": ["es"], "tags": ["romantasy"]}}


class ArchiveTests(unittest.TestCase):
    def test_posts_only_is_standard_observation(self):
        result = normalize_archive_events([BASE])
        row, = result["observations"]
        self.assertEqual(row["post_id"], f"at://{DID}/app.bsky.feed.post/3k4test")
        self.assertEqual(row["source"], "ruggsea_jetstream_archive")
        self.assertEqual(row["network"], "bluesky")
        self.assertEqual(row["created_at"], "2026-10-10T08:00:00+00:00")

    def test_all_records_same_post_deduped(self):
        duplicate = {"did": DID, "kind": "commit", "commit": {
            "collection": "app.bsky.feed.post", "operation": "create",
            "rkey": BASE["rkey"], "record": BASE["record"]}}
        r = normalize_archive_events([BASE, duplicate])
        self.assertEqual(len(r["observations"]), 1)
        self.assertEqual(r["diagnostics"]["duplicates"], 1)

    def test_conflicting_duplicate_is_discarded(self):
        changed = dict(BASE, record=dict(BASE["record"], text="Otro post"))
        r = normalize_archive_events([BASE, changed])
        self.assertEqual(r["observations"], [])
        self.assertEqual(r["diagnostics"]["conflicts"], 1)

    def test_delete_wins_regardless_of_order(self):
        deletion = {"did": DID, "kind": "commit", "commit": {
            "collection": "app.bsky.feed.post", "operation": "delete", "rkey": BASE["rkey"]}}
        self.assertEqual(normalize_archive_events([BASE, deletion])["observations"], [])
        self.assertEqual(normalize_archive_events([deletion, BASE])["observations"], [])

    def test_unknown_language_not_spanish_inferred(self):
        unknown = dict(BASE, record=dict(BASE["record"], langs=[]))
        self.assertEqual(normalize_archive_events([unknown])["observations"], [])
        english = dict(BASE, record=dict(BASE["record"], langs=["en-US"]))
        self.assertEqual(normalize_archive_events([english])["diagnostics"]["non_spanish_or_unknown"], 1)

    def test_bad_dates_ids_and_other_collections(self):
        other = {"did": DID, "kind": "commit", "commit": {
            "collection": "app.bsky.feed.like", "operation": "create", "rkey": "a", "record": BASE["record"]}}
        invalid = dict(BASE, record=dict(BASE["record"], createdAt="2026-10-10T10:00:00"))
        bad_did = dict(BASE, did="someone.example")
        r = normalize_archive_events([other, invalid, bad_did])
        self.assertEqual(r["observations"], [])
        self.assertEqual(r["diagnostics"]["invalid"], 3)

    def test_bounded_input_and_not_data_frame_or_network_call(self):
        with self.assertRaises(ValueError):
            normalize_archive_events((row for row in [BASE]))
        with self.assertRaises(ValueError):
            normalize_archive_events([BASE] * 10001)


if __name__ == "__main__":
    unittest.main()
