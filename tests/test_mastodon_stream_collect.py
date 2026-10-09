"""Pruebas offline del recolector Mastodon SSE."""
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: None
requests_stub.post = lambda *a, **k: None
requests_stub.delete = lambda *a, **k: None
x_stub = types.ModuleType("x_interact")
x_stub._check_spanish_orthography = lambda text: None
sys.modules.setdefault("requests", requests_stub)
sys.modules.setdefault("x_interact", x_stub)

import mastodon_stream_collect as stream


class MastodonStreamTests(unittest.TestCase):
    def test_sse_parser_skips_heartbeats_and_joins_multiline_data(self):
        events = list(stream._sse_events([
            ": heartbeat",
            "event: update",
            'data: {"id":"1",',
            'data: "content":"ok"}',
            "",
            "event: delete",
            "data: 1",
            "",
        ]))
        self.assertEqual(events, [
            ("update", '{"id":"1",\n"content":"ok"}'),
            ("delete", "1"),
        ])

    def test_stream_host_is_discovered_and_validated(self):
        base = stream._stream_base({
            "configuration": {
                "urls": {"streaming": "wss://events.example.social"}
            }
        })
        self.assertEqual(base, "https://events.example.social")
        with self.assertRaisesRegex(RuntimeError, "inválida"):
            stream._stream_base({
                "configuration": {
                    "urls": {"streaming": "https://user:pass@evil.example"}
                }
            })

    def test_only_affine_public_status_is_cached_idempotently(self):
        status = {
            "id": "99",
            "uri": "https://mastodon.social/users/lector/statuses/99",
            "url": "https://mastodon.social/@lector/99",
            "visibility": "public",
            "content": "<p>Estoy leyendo una novela de fantasía juvenil.</p>",
            "created_at": "2026-09-29T10:00:00Z",
            "account": {"acct": "lector@mastodon.social"},
            "tags": [{"name": "Bookstodon"}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            db = stream.init_db(str(pathlib.Path(tmp) / "stream.sqlite3"))
            try:
                self.assertTrue(stream._store_status(db, status, ["fantasía"]))
                self.assertTrue(stream._store_status(db, status, ["fantasía"]))
                db.commit()
                count = db.execute("SELECT COUNT(*) FROM statuses").fetchone()[0]
            finally:
                db.close()
            cached = stream.read_recent(str(pathlib.Path(tmp) / "stream.sqlite3"))
        self.assertEqual(count, 1)
        self.assertEqual(cached[0]["id"], "99")

    def test_delete_event_removes_cached_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "stream.sqlite3")
            db = stream.init_db(path)
            status = {
                "id": "101", "uri": "https://mastodon.social/users/lector/statuses/101",
                "url": "https://mastodon.social/@lector/101", "visibility": "public",
                "content": "<p>Novela de fantasía</p>", "account": {"acct": "lector"},
            }
            stream._store_status(db, status, ["fantasía"])
            db.commit()
            deleted = stream._delete_status(db, "101")
            db.commit()
            db.close()
            remaining = stream.read_recent(path)
        self.assertEqual(deleted, 1)
        self.assertEqual(remaining, [])

    def test_non_affine_and_nonpublic_events_are_not_cached(self):
        status = {
            "id": "100",
            "uri": "https://mastodon.social/users/lector/statuses/100",
            "url": "https://mastodon.social/@lector/100",
            "visibility": "private",
            "content": "<p>fantasía juvenil</p>",
            "account": {"acct": "lector"},
        }
        self.assertFalse(stream._matches(status, ["fantasía"]))
        status["visibility"] = "public"
        status["content"] = "<p>reunión de trabajo</p>"
        self.assertFalse(stream._matches(status, ["fantasía"]))


if __name__ == "__main__":
    unittest.main()
