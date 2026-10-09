"""Pruebas offline del listener de gustos dirigido de Bluesky."""
import json
import pathlib
import tempfile
import time
import unittest
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import bluesky_taste_collect as taste


class TasteCollectorTests(unittest.TestCase):
    def event(self, did, rkey, subject, operation="create"):
        return {
            "did": did,
            "time_us": int(time.time() * 1_000_000),
            "kind": "commit",
            "commit": {
                "operation": operation,
                "collection": "app.bsky.feed.like",
                "rkey": rkey,
                "record": {
                    "$type": "app.bsky.feed.like",
                    "createdAt": "2026-09-29T08:00:00Z",
                    "subject": {"uri": subject, "cid": "bafy"},
                } if operation != "delete" else None,
            },
        }

    def test_load_listener_dids_dedupes_and_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "state.json"
            path.write_text(json.dumps({
                "taste_listener_dids": [
                    {"did": "did:plc:a", "reason": "co_liker"},
                    {"did": "did:plc:a", "reason": "following"},
                    {"did": "did:plc:b", "reason": "co_liker"},
                    {"did": "invalid"},
                ]
            }), encoding="utf-8")
            dids = taste.load_listener_dids(str(path), limit=2)
        self.assertEqual(dids, ["did:plc:a", "did:plc:b"])

    def test_like_store_is_idempotent_and_delete_uses_rkey(self):
        subject = "at://did:plc:author/app.bsky.feed.post/post1"
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "cache.sqlite3")
            db = taste.init_db(path)
            event = self.event("did:plc:liker", "like1", subject)
            self.assertTrue(taste.store_like_event(db, event))
            self.assertFalse(taste.store_like_event(db, event))
            db.commit()
            count = db.execute(
                "SELECT COUNT(*) FROM taste_likes"
            ).fetchone()[0]
            self.assertEqual(count, 1)

            delete = self.event(
                "did:plc:liker", "like1", subject, operation="delete"
            )
            self.assertFalse(taste.store_like_event(db, delete))
            db.commit()
            count = db.execute(
                "SELECT COUNT(*) FROM taste_likes"
            ).fetchone()[0]
            db.close()
        self.assertEqual(count, 0)

    def test_update_is_counted_only_when_like_record_changes(self):
        subject = "at://did:plc:author/app.bsky.feed.post/post1"
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "cache.sqlite3")
            db = taste.init_db(path)
            event = self.event("did:plc:liker", "like1", subject)
            self.assertTrue(taste.store_like_event(db, event))
            changed = json.loads(json.dumps(event))
            changed["time_us"] += 1
            changed["commit"]["operation"] = "update"
            self.assertTrue(taste.store_like_event(db, changed))
            self.assertFalse(taste.store_like_event(db, changed))
            db.close()

    def test_candidates_reward_independent_like_paths(self):
        subject = "at://did:plc:author/app.bsky.feed.post/post1"
        other = "at://did:plc:other/app.bsky.feed.post/post2"
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "cache.sqlite3")
            db = taste.init_db(path)
            for index, did in enumerate(
                ["did:plc:a", "did:plc:b", "did:plc:c"]
            ):
                evt = self.event(did, f"like{index}", subject)
                evt["time_us"] += index
                taste.store_like_event(db, evt)
            taste.store_like_event(
                db, self.event("did:plc:d", "single", other)
            )
            db.commit()
            db.close()
            rows = taste.read_candidate_posts(
                path, limit=10, min_paths=1, max_age_hours=24
            )
        self.assertEqual(rows[0]["uri"], subject)
        self.assertEqual(rows[0]["paths"], 3)

    def test_changed_listener_set_changes_fingerprint(self):
        one = taste.listener_fingerprint(
            ["did:plc:a"], "wss://example.invalid"
        )
        two = taste.listener_fingerprint(
            ["did:plc:a", "did:plc:b"], "wss://example.invalid"
        )
        self.assertNotEqual(one, two)


if __name__ == "__main__":
    unittest.main()
