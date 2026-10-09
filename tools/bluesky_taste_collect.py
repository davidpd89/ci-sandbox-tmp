"""Recolector dirigido de gustos para Bluesky.

Adapta el patrón LinkLonk/Graze a una sola cuenta sin indexar todos los likes:
escucha únicamente app.bsky.feed.like de hasta N DIDs seleccionados por el growth
scan anterior. Guarda subject URIs en SQLite y deja que el siguiente scan hidrate
solo los posts con señal.

No escribe en Bluesky ni usa IA.

Uso:
    python tools/bluesky_taste_collect.py --state growth_state.json
    python tools/bluesky_taste_collect.py --state growth_state.json --minutes 5 --lookback-hours 6
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sqlite3
import time

import bluesky_jetstream_collect as js

ROOT = os.path.join(os.path.dirname(__file__), "..")
DEFAULT_CONFIG = os.path.join(ROOT, "SISTEMA_DIARIO_BLUESKY", "growth_config.json")
DEFAULT_ENDPOINT = js.DEFAULT_ENDPOINT


def init_db(path):
    db = js.init_db(path)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS taste_likes (
            liker_did TEXT NOT NULL,
            rkey TEXT NOT NULL,
            subject_uri TEXT NOT NULL,
            created_at TEXT,
            time_us INTEGER NOT NULL,
            collected_at TEXT NOT NULL,
            PRIMARY KEY(liker_did, rkey)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_taste_subject "
        "ON taste_likes(subject_uri, time_us DESC)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_taste_time "
        "ON taste_likes(time_us DESC)"
    )
    db.commit()
    return db


def load_listener_dids(state_path, limit=50):
    with open(state_path, encoding="utf-8") as stream:
        state = json.load(stream)
    rows = state.get("taste_listener_dids") or []
    dids = []
    for row in rows:
        did = row.get("did") if isinstance(row, dict) else row
        if isinstance(did, str) and did.startswith("did:"):
            dids.append(did)
    return list(dict.fromkeys(dids))[: max(1, int(limit))]


def listener_fingerprint(dids, endpoint):
    payload = "\n".join([str(endpoint)] + sorted(set(dids)))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def prune_old(db, retention_hours):
    floor_us = int(
        (time.time() - max(1, float(retention_hours)) * 3600) * 1_000_000
    )
    cur = db.execute("DELETE FROM taste_likes WHERE time_us < ?", (floor_us,))
    return int(cur.rowcount or 0)


def store_like_event(db, event):
    if event.get("kind") != "commit":
        return False
    commit = event.get("commit") or {}
    if commit.get("collection") != "app.bsky.feed.like":
        return False
    did = event.get("did")
    rkey = commit.get("rkey")
    if not did or not rkey:
        return False

    operation = commit.get("operation")
    if operation == "delete":
        db.execute(
            "DELETE FROM taste_likes WHERE liker_did = ? AND rkey = ?",
            (did, rkey),
        )
        return False
    if operation not in {"create", "update"}:
        return False

    record = commit.get("record") or {}
    subject = record.get("subject") or {}
    uri = subject.get("uri")
    if not isinstance(uri, str) or "/app.bsky.feed.post/" not in uri:
        return False

    created_at = record.get("createdAt")
    event_time = int(event.get("time_us") or 0)
    previous = db.execute(
        """
        SELECT subject_uri, created_at, time_us
        FROM taste_likes
        WHERE liker_did = ? AND rkey = ?
        """,
        (did, rkey),
    ).fetchone()
    current = (uri, created_at, event_time)
    if previous == current:
        return False

    now = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat()
    db.execute(
        """
        INSERT INTO taste_likes(
            liker_did, rkey, subject_uri, created_at, time_us, collected_at
        ) VALUES(?,?,?,?,?,?)
        ON CONFLICT(liker_did, rkey) DO UPDATE SET
            subject_uri=excluded.subject_uri,
            created_at=excluded.created_at,
            time_us=excluded.time_us,
            collected_at=excluded.collected_at
        """,
        (did, rkey, uri, created_at, event_time, now),
    )
    return True


def read_candidate_posts(
    path,
    *,
    limit=75,
    min_paths=1,
    max_age_hours=168,
):
    if not os.path.exists(path):
        return []
    floor_us = int(
        (time.time() - max(1, float(max_age_hours)) * 3600) * 1_000_000
    )
    db = sqlite3.connect(path, timeout=30)
    try:
        rows = db.execute(
            """
            SELECT subject_uri,
                   COUNT(DISTINCT liker_did) AS paths,
                   MAX(time_us) AS last_time_us
            FROM taste_likes
            WHERE time_us >= ?
            GROUP BY subject_uri
            HAVING COUNT(DISTINCT liker_did) >= ?
            ORDER BY paths DESC, last_time_us DESC
            LIMIT ?
            """,
            (
                floor_us,
                max(1, int(min_paths)),
                max(1, int(limit)),
            ),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        # 05/10: el recolector de Jetstream comparte fichero con este y crea el SQLite sin la tabla `taste_likes` si este colector nunca corrio;
        # sin esto el scan entero fallaba en cuanto existia el fichero. Sin tabla = sin candidatos de gusto, no un error.
        if "no such table" in str(exc):
            return []
        raise
    finally:
        db.close()
    return [
        {
            "uri": uri,
            "paths": int(paths),
            "last_time_us": int(last_time_us),
        }
        for uri, paths, last_time_us in rows
    ]


async def collect(
    *,
    state_path,
    db_path,
    config_path,
    endpoint,
    minutes,
    lookback_hours,
):
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError(
            'Taste listener requiere el paquete opcional "websockets>=12".'
        ) from exc

    config = js.load_config(config_path)
    budgets = config.get("budgets") or {}
    dids = load_listener_dids(
        state_path,
        limit=int(budgets.get("taste_listener_dids", 50)),
    )
    if not dids:
        return {
            "processed": 0,
            "stored": 0,
            "targets": 0,
            "reason": "sin DIDs de taste_listener en el state",
        }

    db = init_db(db_path)
    retention = float(budgets.get("taste_retention_hours", 168))
    pruned = prune_old(db, retention)
    db.commit()

    fingerprint = listener_fingerprint(dids, endpoint)
    previous = js.get_state(db, "taste_listener_fingerprint")
    same_targets = previous == fingerprint
    saved_seq = js.get_state(db, "taste_last_seq") if same_targets else None
    saved_time = js.get_state(db, "taste_last_time_us") if same_targets else None
    cursor = js._resume_cursor(
        is_v2=js._is_v2_endpoint(endpoint),
        saved_seq=saved_seq,
        saved_time=saved_time,
        overlap_seconds=5,
        initial_lookback_minutes=max(0.0, float(lookback_hours)) * 60.0,
    )

    deadline = time.monotonic() + max(1.0, float(minutes) * 60.0)
    processed = 0
    stored = 0
    last_seq = None
    last_time_us = None

    try:
        while time.monotonic() < deadline:
            url = js._stream_url(
                endpoint,
                cursor,
                collections=["app.bsky.feed.like"],
                dids=dids,
            )
            try:
                kwargs = {
                    "max_size": 2**20,
                    "ping_interval": 20,
                    "ping_timeout": 20,
                    "close_timeout": 5,
                }
                if js._is_v2_endpoint(endpoint):
                    kwargs["subprotocols"] = ["xrpc.v1.json"]
                async with websockets.connect(url, **kwargs) as ws:
                    while time.monotonic() < deadline:
                        timeout = min(
                            30.0,
                            max(0.1, deadline - time.monotonic()),
                        )
                        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                        event, event_cursor, mode = js._normalize_frame(
                            json.loads(raw)
                        )
                        if not event:
                            continue
                        processed += 1
                        event_time = int(event.get("time_us") or 0)
                        if event_time:
                            last_time_us = event_time
                        if event_cursor:
                            cursor = event_cursor
                            if mode == "v2":
                                last_seq = event_cursor
                        if store_like_event(db, event):
                            stored += 1
                            db.commit()      # 06/10: sin esto la transaccion quedaba abierta minutos (pocos eventos entre commits) y bloqueaba al recolector de Jetstream ('database is locked' cada hora)
                        if processed % 100 == 0:
                            if last_seq:
                                js.set_state(db, "taste_last_seq", last_seq)
                            if last_time_us:
                                js.set_state(
                                    db, "taste_last_time_us", last_time_us
                                )
                            db.commit()
            except asyncio.TimeoutError:
                continue
            except Exception:
                await asyncio.sleep(2)
                continue
    finally:
        if last_seq:
            js.set_state(db, "taste_last_seq", last_seq)
        if last_time_us:
            js.set_state(db, "taste_last_time_us", last_time_us)
        js.set_state(db, "taste_listener_fingerprint", fingerprint)
        db.commit()
        db.close()

    return {
        "processed": processed,
        "stored": stored,
        "targets": len(dids),
        "pruned": pruned,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--db")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--minutes", type=float)
    parser.add_argument("--lookback-hours", type=float)
    args = parser.parse_args(argv)

    config = js.load_config(args.config)
    jet = config.get("jetstream") or {}
    budgets = config.get("budgets") or {}
    db_path = args.db or os.path.join(ROOT, jet["db_path"])
    minutes = (
        args.minutes
        if args.minutes is not None
        else float(jet.get("taste_collector_minutes", 5))
    )
    lookback = (
        args.lookback_hours
        if args.lookback_hours is not None
        else float(jet.get("taste_lookback_hours", 6))
    )

    result = asyncio.run(
        collect(
            state_path=args.state,
            db_path=db_path,
            config_path=args.config,
            endpoint=args.endpoint,
            minutes=minutes,
            lookback_hours=lookback,
        )
    )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
