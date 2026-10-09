"""Recolector opcional de Jetstream para Bluesky.

Escucha posts durante una ventana temporal, filtra localmente por el banco de términos
de growth_config.json y guarda solo coincidencias en SQLite. No usa la IA ni escribe
en la cuenta.

Requiere únicamente para este comando:
    pip install "websockets>=12"

Uso:
    python tools/bluesky_jetstream_collect.py
    python tools/bluesky_jetstream_collect.py --minutes 30
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(__file__))
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..")
DEFAULT_CONFIG = os.path.join(ROOT, "SISTEMA_DIARIO_BLUESKY", "growth_config.json")
DEFAULT_ENDPOINT = (
    "wss://jetstream.us-east.bsky.network/"
    "xrpc/network.bsky.jetstream.subscribeEvents"
)


def _norm(value):
    value = " ".join(str(value or "").casefold().split())
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def load_config(path=DEFAULT_CONFIG):
    with open(path, encoding="utf-8") as stream:
        return json.load(stream)


def load_terms(config):
    terms = []
    for family in config.get("query_families") or []:
        terms.extend(family.get("queries") or [])
    for item in config.get("tag_queries") or []:
        tag = item.get("tag")
        query = item.get("query")
        if tag:
            terms.append(str(tag))
        if query:
            terms.append(str(query))
    terms.extend(config.get("actor_queries") or [])
    terms.extend(config.get("starter_pack_queries") or [])
    terms.extend(config.get("mined_terms") or [])   # 05/10: vocabulario descubierto por bluesky_vocab_miner.py

    # Evitar términos de una sola letra/palabras demasiado genéricas como "autor"
    # cuando aparecen aisladas; el resto del banco ya aporta señales más específicas.
    normalized = []
    seen = set()
    for term in terms:
        key = _norm(term)
        if len(key) < 4 or key in {"autor", "autora", "lector", "lectora"}:
            continue
        if key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def _term_matches(value, term):
    """Evita falsos positivos de substring (p.ej. "book" dentro de "facebook")."""
    if not value or not term:
        return False
    if " " in term or not term.replace("_", "").isalnum():
        return term in value
    tokens = set(re.findall("[a-z0-9_]+", value))
    return term in tokens


SPANISH_WORDS = frozenset("el la los las un una unos unas de del que y en es por con para se su sus lo al mas muy pero como esta este ese eso "
                          "mi tu me te nos ya hay fue son ser ha han he sin sobre entre cuando todo todos tengo estoy quiero leyendo libro".split())


def looks_spanish(text):
    """Los posts sin etiqueta de idioma (`langs` vacio) llegaban sin filtro: un parlamentario noruego en ingles casaba con 'terror' (05/10)."""
    words = re.findall(r"[a-záéíóúüñ]+", str(text or "").casefold())
    if len(words) < 4:
        return False
    hits = sum(1 for word in words if word in SPANISH_WORDS)
    return hits >= 2 and hits / len(words) >= 0.18


def match_terms(text, terms):
    value = _norm(text)
    if not value or sc.is_political(text):
        return []
    return [term for term in terms if _term_matches(value, term)]


def init_db(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    try:
        db.execute("PRAGMA journal_mode=WAL")   # dos recolectores comparten fichero (05/10): WAL + espera evitan 'database is locked'
    except sqlite3.OperationalError:
        pass   # otro proceso tiene el fichero abierto en modo diario: se sigue sin cambiar el modo (el recolector de gustos fallaba aqui)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            uri TEXT PRIMARY KEY,
            did TEXT NOT NULL,
            rkey TEXT NOT NULL,
            text TEXT NOT NULL,
            langs_json TEXT NOT NULL,
            created_at TEXT,
            time_us INTEGER NOT NULL,
            matched_terms TEXT NOT NULL,
            match_count INTEGER NOT NULL,
            reply_parent TEXT,
            reply_root TEXT,
            collected_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_posts_time ON posts(time_us DESC)"
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_posts_match ON posts(match_count DESC, time_us DESC)"
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    db.commit()
    return db


def prune_old(db, retention_hours):
    floor_us = int(
        (time.time() - max(1, int(retention_hours)) * 3600) * 1_000_000
    )
    cursor = db.execute(
        "DELETE FROM posts WHERE time_us < ?",
        (floor_us,),
    )
    return int(cursor.rowcount or 0)


def get_state(db, key):
    row = db.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_state(db, key, value):
    db.execute(
        """
        INSERT INTO state(key, value) VALUES(?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, str(value)),
    )


def _post_uri(did, rkey):
    return f"at://{did}/app.bsky.feed.post/{rkey}"


def store_event(db, event, terms):
    if event.get("kind") != "commit":
        return False
    commit = event.get("commit") or {}
    if commit.get("collection") != "app.bsky.feed.post":
        return False
    did = event.get("did")
    rkey = commit.get("rkey")
    if not did or not rkey:
        return False
    uri = _post_uri(did, rkey)
    operation = commit.get("operation")

    if operation == "delete":
        db.execute("DELETE FROM posts WHERE uri = ?", (uri,))
        return False
    if operation not in {"create", "update"}:
        return False

    record = commit.get("record") or {}
    text = record.get("text") or ""
    langs = [
        str(lang).casefold()
        for lang in (record.get("langs") or [])
        if isinstance(lang, str)
    ]
    not_spanish = (
        not any(lang == "es" or lang.startswith("es-") for lang in langs) if langs else not looks_spanish(text)
    )
    if not_spanish:
        if operation == "update":
            db.execute("DELETE FROM posts WHERE uri = ?", (uri,))
        return False

    structured_tags = [
        str(tag).strip().lstrip("#")
        for tag in (record.get("tags") or [])
        if isinstance(tag, str) and str(tag).strip()
    ]
    haystack = " ".join([text] + [f"#{tag}" for tag in structured_tags])
    matched = match_terms(haystack, terms)
    if not matched:
        # Una actualización puede dejar de ser relevante.
        if operation == "update":
            db.execute("DELETE FROM posts WHERE uri = ?", (uri,))
        return False

    reply = record.get("reply") if isinstance(record.get("reply"), dict) else {}
    parent = reply.get("parent") if isinstance(reply.get("parent"), dict) else {}
    root = reply.get("root") if isinstance(reply.get("root"), dict) else {}
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    db.execute(
        """
        INSERT INTO posts(
            uri, did, rkey, text, langs_json, created_at, time_us,
            matched_terms, match_count, reply_parent, reply_root, collected_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(uri) DO UPDATE SET
            text=excluded.text,
            langs_json=excluded.langs_json,
            created_at=excluded.created_at,
            time_us=excluded.time_us,
            matched_terms=excluded.matched_terms,
            match_count=excluded.match_count,
            reply_parent=excluded.reply_parent,
            reply_root=excluded.reply_root,
            collected_at=excluded.collected_at
        """,
        (
            uri,
            did,
            rkey,
            text,
            json.dumps(record.get("langs") or [], ensure_ascii=False),
            record.get("createdAt"),
            int(event.get("time_us") or 0),
            json.dumps(matched, ensure_ascii=False),
            len(matched),
            parent.get("uri"),
            root.get("uri"),
            now,
        ),
    )
    return True


def read_recent_matches(path, limit=75, max_age_hours=36):
    if not os.path.exists(path):
        return []
    db = sqlite3.connect(path, timeout=30)
    try:
        floor_us = int(
            (time.time() - max(1, int(max_age_hours)) * 3600) * 1_000_000
        )
        rows = db.execute(
            """
            SELECT uri, did, rkey, text, langs_json, created_at, time_us,
                   matched_terms, match_count, reply_parent, reply_root
            FROM posts
            WHERE time_us >= ?
            ORDER BY match_count DESC, time_us DESC
            LIMIT ?
            """,
            (floor_us, max(1, int(limit))),
        ).fetchall()
    finally:
        db.close()
    keys = (
        "uri", "did", "rkey", "text", "langs_json", "created_at", "time_us",
        "matched_terms", "match_count", "reply_parent", "reply_root",
    )
    out = []
    for row in rows:
        item = dict(zip(keys, row))
        item["langs"] = json.loads(item.pop("langs_json") or "[]")
        item["matched_terms"] = json.loads(item["matched_terms"] or "[]")
        out.append(item)
    return out


def _is_v2_endpoint(endpoint):
    return (
        "network.bsky.jetstream.subscribeEvents" in str(endpoint)
        or "://jetstream.us-" in str(endpoint)
    )


def read_active_authors(path, *, limit=25, min_posts=2, max_age_hours=72):
    """DIDs que reaparecen en el nicho durante la ventana reciente."""
    if not os.path.exists(path):
        return []
    floor_us = int(
        (time.time() - max(1, int(max_age_hours)) * 3600) * 1_000_000
    )
    db = sqlite3.connect(path, timeout=30)
    try:
        rows = db.execute(
            """
            SELECT did, COUNT(*) AS posts, MAX(time_us) AS last_time_us,
                   SUM(match_count) AS matches
            FROM posts
            WHERE time_us >= ?
            GROUP BY did
            HAVING COUNT(*) >= ?
            ORDER BY posts DESC, matches DESC, last_time_us DESC
            LIMIT ?
            """,
            (floor_us, max(1, int(min_posts)), max(1, int(limit))),
        ).fetchall()
    finally:
        db.close()
    return [
        {
            "did": did,
            "posts": int(posts),
            "matches": int(matches),
            "last_time_us": int(last_time_us),
        }
        for did, posts, last_time_us, matches in rows
    ]


def _stream_url(endpoint, cursor=None, *, collections=None, dids=None):
    collections = list(collections or ["app.bsky.feed.post"])
    dids = list(dict.fromkeys(str(did) for did in (dids or []) if did))
    if _is_v2_endpoint(endpoint):
        params = [("kinds", "commit")]
        params.extend(("collections", value) for value in collections)
        params.extend(("dids", value) for value in dids)
    else:
        # Compatibilidad con las instancias legacy jetstream1/jetstream2.
        params = [("wantedCollections", value) for value in collections]
        params.extend(("wantedDids", value) for value in dids)
    if cursor:
        params.append(("cursor", str(int(cursor))))
    separator = "&" if "?" in endpoint else "?"
    return endpoint + separator + urlencode(params)


def _iso_to_time_us(value):
    if not isinstance(value, str) or not value:
        return 0
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 0
    return int(parsed.timestamp() * 1_000_000)


def _normalize_frame(message):
    """Convierte Jetstream v2 y legacy al mismo evento interno.

    Devuelve (evento_legacy_shape, cursor, mode). En v2 el cursor es seq;
    en v1 sigue siendo time_us.
    """
    if not isinstance(message, dict):
        return {}, 0, "unknown"

    payload = message.get("payload")
    if isinstance(payload, dict):
        ptype = str(payload.get("$type") or "")
        if not ptype.endswith("#commit"):
            return {}, int(payload.get("seq") or message.get("cursor") or 0), "v2"
        event = {
            "did": payload.get("did"),
            "time_us": _iso_to_time_us(payload.get("time")),
            "kind": "commit",
            "commit": {
                "operation": payload.get("operation"),
                "collection": payload.get("collection"),
                "rkey": payload.get("rkey"),
                "record": payload.get("record"),
                "cid": payload.get("cid"),
                "rev": payload.get("rev"),
            },
        }
        cursor = int(payload.get("seq") or message.get("cursor") or 0)
        return event, cursor, "v2"

    return message, int(message.get("time_us") or 0), "v1"


def _resume_cursor(
    *,
    is_v2,
    saved_seq=None,
    saved_time=None,
    overlap_seconds=5,
    initial_lookback_minutes=30,
    now_us=None,
):
    """Elige cursor sin empezar siempre en el instante de conexión.

    v2 prioriza seq persistido. Si solo queda estado legacy usa time_us. En una
    base nueva, un lookback corto recupera actividad inmediatamente sin pedir
    snapshot/replay HTTP ni API key.
    """
    if is_v2 and saved_seq:
        return int(saved_seq)
    if saved_time:
        return max(
            0,
            int(saved_time) - int(float(overlap_seconds) * 1_000_000),
        )
    lookback = max(0.0, min(float(initial_lookback_minutes), 36 * 60.0))
    if lookback <= 0:
        return None
    if now_us is None:
        now_us = int(time.time() * 1_000_000)
    return max(0, int(now_us - lookback * 60.0 * 1_000_000))


def _next_retry_delay(delay):
    """Backoff exponencial acotado para reconexiones de una escucha larga."""
    return min(60.0, max(1.0, float(delay) * 2.0))


async def collect(
    *,
    db_path,
    config_path,
    endpoint,
    minutes,
    resume_overlap_seconds,
    initial_lookback_minutes=30,
):
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError(
            'Jetstream requiere el paquete opcional "websockets>=12". '
            'Instalarlo solo si se va a usar este recolector.'
        ) from exc

    config = load_config(config_path)
    terms = load_terms(config)
    db = init_db(db_path)
    retention_hours = int(
        (config.get("jetstream") or {}).get("retention_hours", 72)
    )
    try:
        pruned = prune_old(db, retention_hours)
        db.commit()
    except sqlite3.OperationalError:       # otro recolector escribe: se poda en la siguiente ejecucion, no se pierde la ventana entera
        pruned = 0
    stored = 0
    processed = 0
    last_time_us = None
    deadline = time.monotonic() + max(1.0, float(minutes) * 60.0)
    last_commit = time.monotonic()
    reconnects = 0
    connection_errors = 0
    last_error = None
    retry_delay = 1.0

    is_v2 = _is_v2_endpoint(endpoint)
    saved_seq = get_state(db, "last_seq") if is_v2 else None
    saved_time = get_state(db, "last_time_us")
    cursor = _resume_cursor(
        is_v2=is_v2,
        saved_seq=saved_seq,
        saved_time=saved_time,
        overlap_seconds=resume_overlap_seconds,
        initial_lookback_minutes=initial_lookback_minutes,
    )
    last_seq = None

    try:
        while time.monotonic() < deadline:
            url = _stream_url(endpoint, cursor)
            connected_at = None
            try:
                connect_kwargs = {
                    "max_size": 2**20,
                    "ping_interval": 20,
                    "ping_timeout": 20,
                    "close_timeout": 5,
                }
                if is_v2:
                    connect_kwargs["subprotocols"] = ["xrpc.v1.json"]
                async with websockets.connect(url, **connect_kwargs) as ws:
                    connected_at = time.monotonic()
                    while time.monotonic() < deadline:
                        timeout = min(30.0, max(0.1, deadline - time.monotonic()))
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                        except asyncio.TimeoutError:
                            # Una ventana larga y silenciosa no debe reconectar
                            # cada 30s; mantener el socket vivo hasta el deadline.
                            continue
                        decoded = json.loads(raw)
                        event, event_cursor, mode = _normalize_frame(decoded)
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
                        if store_event(db, event, terms):
                            stored += 1
                            if time.monotonic() - last_commit > 5.0:       # 06/10: una transaccion abierta mas de unos segundos bloquea al otro recolector
                                db.commit()
                                last_commit = time.monotonic()
                        if processed % 250 == 0:
                            if last_time_us:
                                set_state(db, "last_time_us", last_time_us)
                            if last_seq:
                                set_state(db, "last_seq", last_seq)
                            db.commit()
                if time.monotonic() < deadline:
                    reconnects += 1
                    if connected_at is not None and time.monotonic() - connected_at >= 60:
                        retry_delay = 1.0
                    await asyncio.sleep(retry_delay)
                    retry_delay = _next_retry_delay(retry_delay)
            except Exception as exc:
                connection_errors += 1
                last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
                if time.monotonic() < deadline:
                    reconnects += 1
                    if connected_at is not None and time.monotonic() - connected_at >= 60:
                        retry_delay = 1.0
                    await asyncio.sleep(retry_delay)
                    retry_delay = _next_retry_delay(retry_delay)
    finally:
        if last_time_us:
            set_state(db, "last_time_us", last_time_us)
        if last_seq:
            set_state(db, "last_seq", last_seq)
        db.commit()
        db.close()

    return {
        "processed": processed,
        "stored": stored,
        "pruned": pruned,
        "terms": len(terms),
        "reconnects": reconnects,
        "connection_errors": connection_errors,
        "last_error": last_error,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--db")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--minutes", type=float)
    parser.add_argument("--lookback-minutes", type=float)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    jet = config.get("jetstream") or {}
    db_path = args.db or os.path.join(ROOT, jet["db_path"])
    minutes = args.minutes if args.minutes is not None else jet.get("collector_minutes", 20)
    overlap = float(jet.get("resume_overlap_seconds", 5))
    lookback = (
        args.lookback_minutes
        if args.lookback_minutes is not None
        else float(jet.get("initial_lookback_minutes", 30))
    )

    result = asyncio.run(
        collect(
            db_path=db_path,
            config_path=args.config,
            endpoint=args.endpoint,
            minutes=minutes,
            resume_overlap_seconds=overlap,
            initial_lookback_minutes=lookback,
        )
    )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
