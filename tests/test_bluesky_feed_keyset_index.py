"""Índice keyset de Jetstream, sin red ni escritura en redes."""
from __future__ import annotations

import pathlib
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import bluesky_jetstream_collect as jetstream


class FeedKeysetIndexTests(unittest.TestCase):
    def test_init_db_creates_covering_feed_index_without_removing_old_ones(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(pathlib.Path(folder) / "jetstream.sqlite3")
            db = jetstream.init_db(path)
            try:
                indexes = {row[1] for row in db.execute("PRAGMA index_list(posts)")}
                self.assertTrue(
                    {"idx_posts_time", "idx_posts_match", "idx_posts_feed"} <= indexes
                )
                columns = db.execute("PRAGMA index_xinfo(idx_posts_feed)").fetchall()
                keys = [(row[2], row[3]) for row in columns if row[5]]
                self.assertEqual(keys, [("time_us", 1), ("uri", 1)])
            finally:
                db.close()
            # Reapertura/idempotencia con archivo SQLite real (también Windows).
            db = jetstream.init_db(path)
            try:
                self.assertIn(
                    "idx_posts_feed",
                    {row[1] for row in db.execute("PRAGMA index_list(posts)")},
                )
            finally:
                db.close()

    def test_keyset_order_uses_index_without_temp_sort(self):
        with tempfile.TemporaryDirectory() as folder:
            db = jetstream.init_db(str(pathlib.Path(folder) / "cache.sqlite3"))
            try:
                insert = """INSERT INTO posts(
                    uri,did,rkey,text,langs_json,created_at,time_us,
                    matched_terms,match_count,reply_parent,reply_root,collected_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)"""
                rows = [
                    (f"at://did:plc:demo/app.bsky.feed.post/{i:05d}",
                     "did:plc:demo", f"{i:05d}", "fantasía", '["es"]',
                     "2026-10-10T10:00:00Z", 12345000 + i // 50,
                     '["fantasia"]', 1, None, None, "2026-10-10")
                    for i in range(2000)
                ]
                db.executemany(insert, rows)
                db.commit()
                sql = (
                    "SELECT uri,time_us FROM posts "
                    "WHERE time_us BETWEEN ? AND ? "
                    "ORDER BY time_us DESC, uri DESC LIMIT ?"
                )
                plan = " ".join(str(p[3]) for p in db.execute(
                    "EXPLAIN QUERY PLAN " + sql, (0, 999999999, 30)
                )).upper()
                self.assertIn("IDX_POSTS_FEED", plan)
                self.assertNotIn("TEMP B-TREE", plan)
                result = db.execute(sql, (0, 999999999, 30)).fetchall()
                self.assertEqual(len(result), 30)
                self.assertEqual(result, sorted(result, key=lambda x: (x[1], x[0]), reverse=True))
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
