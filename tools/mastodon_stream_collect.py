"""Escucha opcional Mastodon Streaming API y cachea coincidencias en SQLite.

El host de streaming se descubre desde /api/v2/instance. El listener usa SSE por
HTTP con Authorization header (nunca pasa el token en query params), filtra local
por términos del nicho y no ejecuta escrituras.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from urllib.parse import urlsplit, urlunsplit

sys.path.insert(0, os.path.dirname(__file__))
import mastodon_interact as m
import scan_common as sc

ROOT = os.path.join(os.path.dirname(__file__), "..")
DEFAULT_CONFIG = os.path.join(ROOT, "SISTEMA_DIARIO_MASTODON", "growth_config.json")
DEFAULT_DB = os.path.join(ROOT, "SISTEMA_DIARIO_MASTODON", "cache", "stream.sqlite3")


def _norm(value):
    value = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join("".join(ch for ch in value if not unicodedata.combining(ch)).split())


def _terms(config):
    values = list(config.get("niche_terms") or [])
    for family in config.get("query_families") or []:
        values.extend(family.get("queries") or [])
    values.extend(config.get("hashtags") or [])
    normalized = []
    for value in values:
        term = _norm(value).lstrip("#")
        if len(term) >= 4 and term not in normalized:
            normalized.append(term)
    return normalized


def _matches(status, terms):
    if not isinstance(status, dict) or status.get("visibility") not in {"public", "unlisted"}:
        return False
    if status.get("sensitive") or status.get("spoiler_text"):
        # Conserva el hallazgo cacheable; el scan retirará acciones de interacción.
        pass
    text = _norm(m._plain_text(status.get("content", "")))
    if not text or sc.is_political(text):
        return False
    for tag in status.get("tags") or []:
        if isinstance(tag, dict):
            text += " " + _norm(tag.get("name") or "")
    for raw_term in terms:
        term = _norm(raw_term).lstrip("#")
        if not term:
            continue
        if " " in term:
            if term in text:
                return True
        elif re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", text):
            return True
    return False


def _stream_base(instance):
    config = (instance.get("configuration") or {}).get("urls") or {}
    raw = config.get("streaming")
    if not isinstance(raw, str) or not raw:
        # Fallback del endpoint oficial de discovery: same-host streaming path.
        return m.BASE
    parts = urlsplit(raw)
    if parts.scheme not in {"wss", "https"} or not parts.hostname or parts.username or parts.password:
        raise RuntimeError("URL de streaming Mastodon inválida")
    path = parts.path.rstrip("/")
    if path.endswith("/api/v1/streaming"):
        path = path[:-len("/api/v1/streaming")]
    return urlunsplit(("https", parts.netloc, path, "", ""))


def _sse_events(lines):
    event_name = None
    data_lines = []
    for raw_line in lines:
        line = raw_line.decode("utf-8", errors="replace") if isinstance(raw_line, bytes) else str(raw_line or "")
        if not line:
            if event_name and data_lines:
                yield event_name, "\n".join(data_lines)
            event_name, data_lines = None, []
        elif line.startswith(":"):
            continue
        elif line.startswith("event:"):
            event_name = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].lstrip())
    if event_name and data_lines:
        yield event_name, "\n".join(data_lines)


def init_db(path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("""
        CREATE TABLE IF NOT EXISTS statuses (
            uri TEXT PRIMARY KEY,
            status_id TEXT NOT NULL,
            url TEXT NOT NULL,
            acct TEXT NOT NULL,
            created_at TEXT,
            visibility TEXT NOT NULL,
            text TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            collected_at TEXT NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_statuses_created ON statuses(created_at DESC)")
    db.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    db.commit()
    return db


def _store_status(db, status, terms, *, collected_at=None):
    if not _matches(status, terms):
        return False
    account = status.get("account") or {}
    uri = str(status.get("uri") or "")
    status_id = str(status.get("id") or "")
    url = str(status.get("url") or "")
    acct = str(account.get("acct") or "").casefold()
    if not uri or not status_id or not url or not acct:
        return False
    text = m._plain_text(status.get("content", ""))
    db.execute("""
        INSERT INTO statuses(uri,status_id,url,acct,created_at,visibility,text,payload_json,collected_at)
        VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(uri) DO UPDATE SET
            status_id=excluded.status_id,url=excluded.url,acct=excluded.acct,
            created_at=excluded.created_at,visibility=excluded.visibility,
            text=excluded.text,payload_json=excluded.payload_json,
            collected_at=excluded.collected_at
    """, (
        uri, status_id, url, acct, status.get("created_at"),
        status.get("visibility"), text,
        json.dumps(status, ensure_ascii=False),
        collected_at or dt.datetime.now(dt.timezone.utc).isoformat(),
    ))
    return True


def _delete_status(db, status_id):
    cursor = db.execute(
        "DELETE FROM statuses WHERE status_id = ?",
        (str(status_id),),
    )
    return max(0, int(cursor.rowcount or 0))


def prune(db, retention_hours):
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=max(1, int(retention_hours)))
    cur = db.execute("DELETE FROM statuses WHERE collected_at < ?", (cutoff.isoformat(),))
    return max(0, int(cur.rowcount or 0))


def read_recent(path, limit=200):
    if not os.path.exists(path):
        return []
    db = sqlite3.connect(path)
    try:
        rows = db.execute(
            "SELECT payload_json FROM statuses ORDER BY created_at DESC, collected_at DESC LIMIT ?",
            (max(1, int(limit)),),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]
    finally:
        db.close()


def _next_retry(delay):
    return min(60.0, max(1.0, float(delay) * 2.0))


def collect(*, db_path, minutes, config_path=DEFAULT_CONFIG):
    with open(config_path, encoding="utf-8") as stream:
        config = json.load(stream)
    # Listener read-only pero tokenizado: verificar que se conecta la cuenta
    # prevista y no enviar credenciales a un host suministrado por CLI.
    m._assert_expected_account()
    instance = m.instance_info()
    stream_base = _stream_base(instance)
    base_parts = urlsplit(stream_base)
    if base_parts.scheme != "https" or not base_parts.hostname:
        raise ValueError("endpoint streaming debe ser HTTPS/WSS descubierto")
    url = urlunsplit(("https", base_parts.netloc, base_parts.path.rstrip("/") + "/api/v1/streaming/public", "", ""))
    terms = _terms(config)
    db = init_db(db_path)
    retention_hours = int((config.get("streaming") or {}).get("retention_hours", 72))
    pruned = prune(db, retention_hours)
    deadline = time.monotonic() + max(1.0, float(minutes) * 60.0)
    counts = {"received": 0, "matched": 0, "deleted": 0, "reconnects": 0, "errors": 0}
    last_error = None
    retry = 1.0
    try:
        while time.monotonic() < deadline:
            connected_at = None
            response = None
            try:
                timeout = max(5.0, min(65.0, deadline - time.monotonic() + 2.0))
                response = m.requests.get(
                    url,
                    headers={**m._headers(), "Accept": "text/event-stream"},
                    stream=True,
                    timeout=(10, timeout),
                )
                if response.status_code == 429:
                    retry_after = (getattr(response, "headers", {}) or {}).get("Retry-After")
                    raise m.MastodonRateLimitExceeded(
                        "GET streaming/public", 429, (response.text or "")[:200],
                        retry_after=retry_after,
                    )
                if response.status_code != 200:
                    raise m.MastodonAPIError(
                        "GET streaming/public", response.status_code,
                        (response.text or "")[:200],
                    )
                connected_at = time.monotonic()
                for event_name, data_text in _sse_events(
                    response.iter_lines(decode_unicode=True)
                ):
                    if time.monotonic() >= deadline:
                        break
                    if event_name == "delete":
                        counts["deleted"] += _delete_status(db, data_text)
                        continue
                    if event_name not in {"update", "status.update"}:
                        continue
                    try:
                        status = json.loads(data_text)
                    except json.JSONDecodeError:
                        continue
                    counts["received"] += 1
                    if isinstance(status, dict) and _store_status(db, status, terms):
                        counts["matched"] += 1
                    if counts["received"] % 100 == 0:
                        db.commit()
                db.commit()
                if time.monotonic() < deadline:
                    counts["reconnects"] += 1
                    if connected_at and time.monotonic() - connected_at >= 60:
                        retry = 1.0
                    time.sleep(retry)
                    retry = _next_retry(retry)
            except m.MastodonRateLimitExceeded:
                raise
            except m.MastodonAPIError:
                raise
            except Exception as exc:
                counts["errors"] += 1
                last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
                if time.monotonic() < deadline:
                    counts["reconnects"] += 1
                    time.sleep(retry)
                    retry = _next_retry(retry)
            finally:
                if response is not None:
                    try:
                        response.close()
                    except Exception:
                        pass
        db.commit()
    finally:
        db.close()
    return {
        **counts,
        "pruned": pruned,
        "terms": len(terms),
        "last_error": last_error,
        "stream_url_host": base_parts.hostname,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--db")
    parser.add_argument("--minutes", type=float, default=20)
    args = parser.parse_args(argv)
    with open(args.config, encoding="utf-8") as stream:
        config = json.load(stream)
    stream_cfg = config.get("streaming") or {}
    db_path = args.db or os.path.join(ROOT, stream_cfg.get("db_path", "SISTEMA_DIARIO_MASTODON/cache/stream.sqlite3"))
    try:
        result = collect(
            db_path=db_path,
            minutes=args.minutes,
            config_path=args.config,
        )
    except m.MastodonRateLimitExceeded as exc:
        print(json.dumps({
            "error": str(exc),
            "retry_after": exc.retry_after,
        }, ensure_ascii=False))
        return 2
    except Exception as exc:
        print(json.dumps({
            "error": f"{type(exc).__name__}: {exc}",
        }, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
