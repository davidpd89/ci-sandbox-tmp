"""Pruebas offline del recolector Jetstream de Bluesky."""
import asyncio
import json
import pathlib
import tempfile
import time
import unittest
import sys
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import bluesky_jetstream_collect as js


class JetstreamCollectorTests(unittest.TestCase):
    def config(self):
        return {
            "query_families": [
                {"name": "x", "queries": ["lectura", "fantasía juvenil"]}
            ],
            "tag_queries": [{"tag": "BookSky", "query": "libros"}],
            "actor_queries": ["lector", "escritor fantasía"],
            "starter_pack_queries": ["romantasy"],
        }

    def event(self, text="Estoy con una lectura de fantasía", operation="create"):
        return {
            "did": "did:plc:abc",
            "time_us": int(time.time() * 1_000_000),
            "kind": "commit",
            "commit": {
                "operation": operation,
                "collection": "app.bsky.feed.post",
                "rkey": "xyz",
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": text,
                    "langs": ["es"],
                    "createdAt": "2026-09-29T03:00:00Z",
                } if operation != "delete" else None,
            },
        }

    def test_terms_are_deduped_and_use_config_bank(self):
        terms = js.load_terms(self.config())
        self.assertIn("lectura", terms)
        self.assertIn("fantasia juvenil", terms)
        self.assertIn("booksky", terms)
        self.assertIn("romantasy", terms)
        self.assertNotIn("lector", terms)

    def test_match_terms_do_not_match_inside_other_words(self):
        terms = ["book", "fantasia", "lectura"]
        self.assertNotIn("book", js.match_terms("facebook social", terms))
        self.assertIn("book", js.match_terms("book community", terms))
        self.assertIn("lectura", js.match_terms("Mi lectura actual", terms))

    def test_match_terms_filters_politics(self):
        terms = js.load_terms(self.config())
        self.assertIn("lectura", js.match_terms("Mi lectura de hoy", terms))
        self.assertEqual(
            js.match_terms("Lectura sobre elecciones y PSOE", terms),
            [],
        )

    def test_structured_record_tags_can_match_without_text_hashtag(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "cache.sqlite3")
            db = js.init_db(path)
            evt = self.event(text="Una actualización breve")
            evt["commit"]["record"]["tags"] = ["BookSky"]
            stored = js.store_event(db, evt, ["booksky"])
            db.commit()
            count = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            db.close()
        self.assertTrue(stored)
        self.assertEqual(count, 1)

    def test_declared_non_spanish_post_is_not_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "cache.sqlite3")
            db = js.init_db(path)
            evt = self.event(text="fantasy books reading")
            evt["commit"]["record"]["langs"] = ["en"]
            stored = js.store_event(db, evt, ["fantasy", "books"])
            db.commit()
            count = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            db.close()
        self.assertFalse(stored)
        self.assertEqual(count, 0)

    def test_sqlite_is_idempotent_and_delete_removes_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "cache.sqlite3")
            db = js.init_db(path)
            terms = js.load_terms(self.config())
            event = self.event()
            self.assertTrue(js.store_event(db, event, terms))
            self.assertTrue(js.store_event(db, event, terms))
            db.commit()
            count = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            self.assertEqual(count, 1)
            delete = self.event(operation="delete")
            self.assertFalse(js.store_event(db, delete, terms))
            db.commit()
            count = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            db.close()
            self.assertEqual(count, 0)

    def test_recent_matches_return_terms_without_websocket_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "cache.sqlite3")
            db = js.init_db(path)
            terms = js.load_terms(self.config())
            js.store_event(db, self.event(), terms)
            db.commit()
            db.close()
            rows = js.read_recent_matches(path, limit=10)
        self.assertEqual(len(rows), 1)
        self.assertIn("lectura", rows[0]["matched_terms"])

    def test_active_authors_rank_recurring_dids(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "cache.sqlite3")
            db = js.init_db(path)
            terms = js.load_terms(self.config())
            for index in range(3):
                evt = self.event(text="Lectura de fantasía")
                evt["commit"]["rkey"] = f"a{index}"
                evt["did"] = "did:plc:repeat"
                evt["time_us"] += index
                js.store_event(db, evt, terms)
            other = self.event(text="Lectura de fantasía")
            other["commit"]["rkey"] = "solo"
            other["did"] = "did:plc:single"
            js.store_event(db, other, terms)
            db.commit()
            db.close()
            rows = js.read_active_authors(path, min_posts=2, limit=10)
        self.assertEqual([row["did"] for row in rows], ["did:plc:repeat"])
        self.assertEqual(rows[0]["posts"], 3)

    def test_prune_old_keeps_recent_cache_small(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "cache.sqlite3")
            db = js.init_db(path)
            terms = js.load_terms(self.config())
            old = self.event()
            old["time_us"] = int((time.time() - 100 * 3600) * 1_000_000)
            recent = self.event()
            recent["commit"]["rkey"] = "recent"
            recent["time_us"] = int(time.time() * 1_000_000)
            js.store_event(db, old, terms)
            js.store_event(db, recent, terms)
            removed = js.prune_old(db, 72)
            db.commit()
            count = db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            db.close()
        self.assertEqual(removed, 1)
        self.assertEqual(count, 1)

    def test_new_cache_starts_with_short_lookback(self):
        now_us = 2_000_000_000_000_000
        cursor = js._resume_cursor(
            is_v2=True,
            initial_lookback_minutes=30,
            now_us=now_us,
        )
        self.assertEqual(cursor, now_us - 30 * 60 * 1_000_000)

    def test_saved_seq_beats_lookback_on_v2(self):
        cursor = js._resume_cursor(
            is_v2=True,
            saved_seq="12345",
            saved_time="1999999999999999",
            initial_lookback_minutes=30,
            now_us=2_000_000_000_000_000,
        )
        self.assertEqual(cursor, 12345)

    def test_legacy_time_resume_keeps_overlap(self):
        cursor = js._resume_cursor(
            is_v2=False,
            saved_time="2000000000000000",
            overlap_seconds=5,
            initial_lookback_minutes=30,
            now_us=2_100_000_000_000_000,
        )
        self.assertEqual(cursor, 2_000_000_000_000_000 - 5_000_000)

    def test_lookback_is_capped_to_server_recent_window(self):
        now_us = 2_000_000_000_000_000
        cursor = js._resume_cursor(
            is_v2=True,
            initial_lookback_minutes=99999,
            now_us=now_us,
        )
        self.assertEqual(cursor, now_us - 36 * 60 * 60 * 1_000_000)

    def test_reconnect_backoff_grows_and_is_capped(self):
        self.assertEqual(js._next_retry_delay(1), 2.0)
        self.assertEqual(js._next_retry_delay(16), 32.0)
        self.assertEqual(js._next_retry_delay(32), 60.0)

    def test_idle_stream_keeps_one_connection_until_deadline(self):
        class Socket:
            async def recv(self):
                await asyncio.sleep(10)

        class Connection:
            async def __aenter__(self):
                return Socket()

            async def __aexit__(self, *_):
                return False

        class Websockets:
            calls = 0

            def connect(self, *_args, **_kwargs):
                self.calls += 1
                return Connection()

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "config.json"
            db_path = pathlib.Path(tmp) / "cache.sqlite3"
            config_path.write_text(json.dumps(self.config()), encoding="utf-8")
            fake_websockets = Websockets()
            with patch.dict(sys.modules, {"websockets": fake_websockets}):
                result = asyncio.run(js.collect(
                    db_path=str(db_path),
                    config_path=str(config_path),
                    endpoint=js.DEFAULT_ENDPOINT,
                    minutes=0.001,
                    resume_overlap_seconds=5,
                ))

        self.assertEqual(fake_websockets.calls, 1)
        self.assertEqual(result["reconnects"], 0)
        self.assertEqual(result["connection_errors"], 0)

    def test_stream_url_legacy_uses_old_filter_names(self):
        url = js._stream_url("wss://jetstream2.us-east.bsky.network/subscribe", 123)
        self.assertIn("wantedCollections=app.bsky.feed.post", url)
        self.assertIn("cursor=123", url)

    def test_stream_url_v2_can_target_dids_and_like_collection(self):
        endpoint = (
            "wss://jetstream.us-east.bsky.network/"
            "xrpc/network.bsky.jetstream.subscribeEvents"
        )
        url = js._stream_url(
            endpoint,
            456,
            collections=["app.bsky.feed.like"],
            dids=["did:plc:a", "did:plc:b"],
        )
        self.assertIn("collections=app.bsky.feed.like", url)
        self.assertIn("dids=did%3Aplc%3Aa", url)
        self.assertIn("dids=did%3Aplc%3Ab", url)
        self.assertIn("kinds=commit", url)
        self.assertIn("cursor=456", url)

    def test_stream_url_v2_uses_collections_kinds_and_seq_cursor(self):
        endpoint = (
            "wss://jetstream.us-east.bsky.network/"
            "xrpc/network.bsky.jetstream.subscribeEvents"
        )
        url = js._stream_url(endpoint, 456)
        self.assertIn("collections=app.bsky.feed.post", url)
        self.assertIn("kinds=commit", url)
        self.assertIn("cursor=456", url)
        self.assertNotIn("wantedCollections", url)

    def test_v2_frame_normalizes_to_existing_store_shape(self):
        frame = {
            "$type": "message",
            "cursor": 101,
            "payload": {
                "$type": "network.bsky.jetstream.subscribeEvents#commit",
                "seq": 101,
                "did": "did:plc:abc",
                "time": "2026-09-29T06:00:00Z",
                "operation": "create",
                "collection": "app.bsky.feed.post",
                "rkey": "xyz",
                "cid": "bafy",
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": "Lectura de fantasía",
                    "createdAt": "2026-09-29T06:00:00Z",
                },
            },
        }
        event, cursor, mode = js._normalize_frame(frame)
        self.assertEqual(mode, "v2")
        self.assertEqual(cursor, 101)
        self.assertEqual(event["kind"], "commit")
        self.assertEqual(event["commit"]["collection"], "app.bsky.feed.post")
        self.assertGreater(event["time_us"], 0)

    def test_default_endpoint_is_v2(self):
        self.assertTrue(js._is_v2_endpoint(js.DEFAULT_ENDPOINT))
        self.assertIn("network.bsky.jetstream.subscribeEvents", js.DEFAULT_ENDPOINT)


    def test_v2_replay_does_not_resurrect_deleted_post(self):
        """Reproducción: un frame antiguo puede volver a crear un post borrado."""
        with tempfile.TemporaryDirectory() as tmp:
            db = js.init_db(str(pathlib.Path(tmp) / "cache.sqlite3"))
            terms = ["lectura"]
            original = self.event()
            newer_delete = self.event(operation="delete")
            seq = None
            stored, seq, replayed = js._apply_frame(
                db, original, 100, "v2", terms, seq
            )
            self.assertEqual((stored, replayed, seq), (True, False, 100))
            stored, seq, replayed = js._apply_frame(
                db, newer_delete, 102, "v2", terms, seq
            )
            self.assertEqual((stored, replayed, seq), (False, False, 102))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 0)

            # Baseline anterior: almacenar sin comprobar secuencia resucita 1 fila.
            js.store_event(db, original, terms)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 1)
            js.store_event(db, newer_delete, terms)
            stored, seq, replayed = js._apply_frame(
                db, original, 101, "v2", terms, seq
            )
            self.assertEqual((stored, replayed, seq), (False, True, 102))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 0)
            db.close()

    def test_v2_restart_uses_persisted_high_water_and_skips_inclusive_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp) / "cache.sqlite3")
            db = js.init_db(path)
            terms = ["lectura"]
            first = self.event()
            stored, seq, replayed = js._apply_frame(
                db, first, 200, "v2", terms, None
            )
            js.set_state(db, "last_seq", seq)
            db.commit()
            db.close()
            db = js.init_db(path)
            high_water = int(js.get_state(db, "last_seq"))
            replayed_frame = self.event()
            replayed_frame["commit"]["record"]["text"] = "Lectura cambiada"
            stored, seq, replayed = js._apply_frame(
                db, replayed_frame, 200, "v2", terms, high_water
            )
            self.assertEqual((stored, seq, replayed), (False, 200, True))
            self.assertEqual(
                db.execute("SELECT text FROM posts").fetchone()[0],
                first["commit"]["record"]["text"],
            )
            db.close()

    def test_v2_invalid_seq_does_not_mutate_cache_or_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = js.init_db(str(pathlib.Path(tmp) / "cache.sqlite3"))
            for invalid in (0, -1, None):
                with self.assertRaises(ValueError):
                    js._apply_frame(
                        db, self.event(), invalid, "v2", ["lectura"], None
                    )
            self.assertEqual(db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 0)
            self.assertIsNone(js.get_state(db, "last_seq"))
            db.close()

    def test_v1_still_accepts_timestamp_based_replays(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = js.init_db(str(pathlib.Path(tmp) / "cache.sqlite3"))
            stored, seq, replayed = js._apply_frame(
                db, self.event(), 2000000000000000, "v1", ["lectura"], None
            )
            self.assertEqual((stored, seq, replayed), (True, None, False))
            db.close()

    def test_v2_stream_reconnect_skip_inclusive_duplicate_and_apply_delete(self):
        """WebSocket sintético: fallo, reconexión inclusiva, borrado y checkpoint."""
        def frame(seq, operation):
            record = {
                "$type": "app.bsky.feed.post",
                "text": "Mi lectura de fantasía",
                "langs": ["es"],
                "createdAt": "2026-10-09T09:00:00Z",
            }
            return {
                "$type": "message",
                "cursor": seq,
                "payload": {
                    "$type": "network.bsky.jetstream.subscribeEvents#commit",
                    "seq": seq,
                    "did": "did:plc:synthetic",
                    "time": "2026-10-09T09:00:00Z",
                    "operation": operation,
                    "collection": "app.bsky.feed.post",
                    "rkey": "synthetic",
                    "record": record if operation != "delete" else None,
                },
            }

        class Socket:
            def __init__(self, messages):
                self.messages = list(messages)

            async def recv(self):
                if self.messages:
                    item = self.messages.pop(0)
                    if isinstance(item, Exception):
                        raise item
                    return json.dumps(item)
                await asyncio.sleep(20)

        class Connection:
            def __init__(self, socket):
                self.socket = socket

            async def __aenter__(self):
                return self.socket

            async def __aexit__(self, *_args):
                return False

        class Websockets:
            def __init__(self):
                self.calls = []
                self.sockets = [
                    Socket([frame(100, "create"), OSError("synthetic drop")]),
                    Socket([frame(100, "create"), frame(102, "delete")]),
                ]

            def connect(self, url, **kwargs):
                self.calls.append(url)
                return Connection(self.sockets.pop(0) if self.sockets else Socket([]))

        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "config.json"
            db_path = pathlib.Path(tmp) / "cache.sqlite3"
            config_path.write_text(json.dumps(self.config()), encoding="utf-8")
            sockets = Websockets()
            with patch.dict(sys.modules, {"websockets": sockets}):
                result = asyncio.run(js.collect(
                    db_path=str(db_path),
                    config_path=str(config_path),
                    endpoint=js.DEFAULT_ENDPOINT,
                    minutes=0.045,
                    resume_overlap_seconds=5,
                ))
            db = js.init_db(str(db_path))
            self.assertEqual(js.get_state(db, "last_seq"), "102")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM posts").fetchone()[0], 0)
            db.close()
        self.assertGreaterEqual(len(sockets.calls), 2)
        self.assertIn("cursor=100", sockets.calls[1])
        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["stored"], 1)
        self.assertGreaterEqual(result["connection_errors"], 1)

    def test_v2_rejects_http_400_without_retry_or_cursor_reset(self):
        """Un CursorTooOld/400 no se resuelve repitiendo la misma suscripción."""
        class HandshakeFailure(Exception):
            def __init__(self):
                self.response = type("Response", (), {"status_code": 400})()
                super().__init__("synthetic bad cursor")

        class Websockets:
            calls = 0

            def connect(self, *_args, **_kwargs):
                self.calls += 1
                raise HandshakeFailure()

        self.assertIsNone(js._fatal_stream_status(
            type("Throttle", (Exception,), {
                "response": type("Response", (), {"status_code": 429})()
            })()
        ))
        with tempfile.TemporaryDirectory() as tmp:
            config_path = pathlib.Path(tmp) / "config.json"
            db_path = pathlib.Path(tmp) / "cache.sqlite3"
            config_path.write_text(json.dumps(self.config()), encoding="utf-8")
            sockets = Websockets()
            with patch.dict(sys.modules, {"websockets": sockets}):
                with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
                    asyncio.run(js.collect(
                        db_path=str(db_path), config_path=str(config_path),
                        endpoint=js.DEFAULT_ENDPOINT, minutes=0.001,
                        resume_overlap_seconds=5,
                    ))
            self.assertEqual(sockets.calls, 1)
            db = js.init_db(str(db_path))
            self.assertIsNone(js.get_state(db, "last_seq"))
            db.close()

if __name__ == "__main__":
    unittest.main()
