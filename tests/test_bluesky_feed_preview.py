"""Contract tests 100% offline for a Bluesky feed preview of Jetstream cache."""
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import bluesky_feed_preview as preview


NOW = 1_790_000_000_000_000


def uri(did, rkey):
    return f"at://did:plc:{did}/app.bsky.feed.post/{rkey}"


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = pathlib.Path(self.temp.name) / "jetstream.sqlite3"
        with sqlite3.connect(self.path) as db:
            # Columnas reales de bluesky_jetstream_collect.init_db
            db.execute("""
                CREATE TABLE posts(
                  uri TEXT PRIMARY KEY, did TEXT NOT NULL, rkey TEXT NOT NULL,
                  text TEXT NOT NULL, langs_json TEXT NOT NULL, created_at TEXT,
                  time_us INTEGER NOT NULL, matched_terms TEXT NOT NULL,
                  match_count INTEGER NOT NULL, reply_parent TEXT,
                  reply_root TEXT, collected_at TEXT NOT NULL
                )
            """)

    def add(self, did, rkey, time_us=None, *, age_hours=1, matches=2,
            langs=("es",), reply_parent=None, created_at=None):
        stamp = NOW - 3_600_000_000 if time_us is None else time_us
        if created_at is None:
            import datetime as dt
            created_at = dt.datetime.fromtimestamp(
                (NOW - age_hours * 3_600_000_000) / 1_000_000,
                dt.timezone.utc
            ).isoformat()
        with sqlite3.connect(self.path) as db:
            db.execute("""
                INSERT INTO posts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                uri(did, rkey), f"did:plc:{did}", rkey,
                "Mi lectura de fantasía y romantasy", json.dumps(langs),
                created_at, stamp, '["fantasia", "romantasy"]', matches,
                reply_parent, None, "2026-10-10",
            ))

    def page(self, **kw):
        return preview.feed_page(self.path, now_us=NOW, **kw)

    def test_schema_skeleton_and_deterministic_cursor_pagination(self):
        # Empates de timestamp: desempate por URI para no perder ni repetir.
        for did in ("abc", "def", "ghi", "jkl", "mno"):
            self.add(did, "rkey")
        first = self.page(limit=2)
        second = self.page(limit=2, cursor=first["cursor"])
        third = self.page(limit=2, cursor=second["cursor"])
        fourth = self.page(limit=2, cursor=third["cursor"])
        uris = [item["post"] for page in (first, second, third, fourth)
                for item in page["feed"]]
        self.assertEqual(len(uris), len(set(uris)))
        self.assertEqual(len(uris), 5)
        self.assertEqual(fourth, {"cursor": "eof", "feed": []})
        self.assertEqual(self.page(cursor="eof"), fourth)
        self.assertEqual(set(first), {"cursor", "feed"})
        self.assertEqual(uris, sorted(uris, reverse=True))

    def test_only_recent_originals_in_spanish_with_niche_signal(self):
        self.add("recent", "fresh")
        self.add("old", "historic", age_hours=400)
        self.add("replay", "archive", time_us=NOW - 500 * 3_600_000_000)
        self.add("future", "scheduled", time_us=NOW + 900_000_000)
        self.add("english", "words", langs=("en",))
        self.add("regional", "regional", langs=("es-ES",))
        self.add("reply", "thread", reply_parent=uri("other", "parent"))
        self.add("weak", "onlyone", matches=1)
        result = self.page(min_matches=2)
        self.assertEqual([x["post"] for x in result["feed"]],
                         [uri("regional", "regional"), uri("recent", "fresh")])

    def test_updates_and_deletes_are_visible_next_page(self):
        self.add("abc", "one")
        self.add("def", "two")
        self.assertEqual(len(self.page()["feed"]), 2)
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM posts WHERE uri = ?", (uri("abc", "one"),))
        self.assertEqual(self.page()["feed"], [{"post": uri("def", "two")}])

    def test_empty_and_missing_cache_are_not_masked(self):
        self.assertEqual(self.page(), {"cursor": "eof", "feed": []})
        missing = pathlib.Path(self.temp.name) / "missing.db"
        with self.assertRaises(FileNotFoundError):
            preview.feed_page(missing, now_us=NOW)
        self.assertFalse(missing.exists())

    def test_invalid_cursor_and_config_fail_closed(self):
        for cursor in ("", "broken", "x::" + uri("abc", "one"), 
                       "0::" + uri("abc", "one"), "7::not-a-uri",
                       "7::at://did:plc:a/app.bsky.feed.post/"):
            with self.subTest(cursor=cursor):
                with self.assertRaises(ValueError):
                    self.page(cursor=cursor)
        for kw in ({"limit": 0}, {"limit": 101}, {"limit": True},
                   {"max_age_hours": 0}, {"max_age_hours": 169},
                   {"min_matches": False}, {"min_matches": -1},
                   {"now_us": 0}):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError):
                    self.page(**kw)

    def test_read_only_and_no_network(self):
        self.add("abc", "one")
        with sqlite3.connect(self.path) as db:
            before = db.execute("SELECT * FROM posts").fetchall()
        self.page(limit=1)
        with sqlite3.connect(self.path) as db:
            after = db.execute("SELECT * FROM posts").fetchall()
        self.assertEqual(before, after)
        source = pathlib.Path(preview.__file__).read_text("utf-8")
        self.assertNotIn("requests.", source)
        self.assertNotIn("client.login", source)
        self.assertNotIn("publish_feed", source.split('def main(')[-1])


if __name__ == "__main__":
    unittest.main()
