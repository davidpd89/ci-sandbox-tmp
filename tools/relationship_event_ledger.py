"""Historial relacional append-only independiente del ActionLedger operativo.

No reserva acciones, no importa credenciales ni ejecuta escrituras en redes.
Python 3.11 / SQLite estándar; los productores entregan identificadores y evidencia.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import datetime, date, time, timezone, timedelta
from pathlib import Path
from contextlib import closing
from typing import Iterable

NETWORKS = frozenset("x threads facebook pinterest reddit bluesky mastodon tiktok instagram".split())
QUEUES = frozenset(("WEB", "API", "MOBILE"))
KINDS = frozenset("follow unfollow like comment reply repost visit followback".split())
OUTCOMES = frozenset("confirmed observed uncertain failed skipped unverified present absent".split())
ACTION_ALIASES = {
    "follow": "follow", "unfollow": "unfollow", "like": "like",
    "favourite": "like", "favorite": "like", "vote": "like",
    "comment": "comment", "reply": "reply",
    "boost": "repost", "repost": "repost", "quote": "repost",
    "visit": "visit",
}
SCHEMA_VERSION = 1
_SCHEMA = """
CREATE TABLE IF NOT EXISTS relationship_events(
 seq INTEGER PRIMARY KEY AUTOINCREMENT,
 event_id TEXT NOT NULL UNIQUE,
 network TEXT NOT NULL,
 queue TEXT NOT NULL,
 subject TEXT NOT NULL,
 kind TEXT NOT NULL,
 outcome TEXT NOT NULL,
 occurred_at TEXT NOT NULL,
 precision TEXT NOT NULL,
 source TEXT NOT NULL,
 source_id TEXT NOT NULL,
 correlation_id TEXT,
 target_id TEXT,
 digest TEXT NOT NULL,
 ingested_at TEXT NOT NULL,
 UNIQUE(network, source, source_id)
);
CREATE INDEX IF NOT EXISTS relationship_history
 ON relationship_events(network, subject, occurred_at, seq);
CREATE INDEX IF NOT EXISTS relationship_kinds
 ON relationship_events(network, kind, outcome, occurred_at);
CREATE TRIGGER IF NOT EXISTS relationship_events_no_update
 BEFORE UPDATE ON relationship_events BEGIN SELECT RAISE(ABORT, 'append-only'); END;
CREATE TRIGGER IF NOT EXISTS relationship_events_no_delete
 BEFORE DELETE ON relationship_events BEGIN SELECT RAISE(ABORT, 'append-only'); END;
"""


def _timestamp(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("timestamp must be ISO-8601 string with timezone")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp is not ISO-8601") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamp timezone required (never infer DST)")
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _subject(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("subject must be string")
    result = value.strip()
    if not result or len(result) > 512:
        raise ValueError("empty or oversized subject")
    # URL case in paths and AT-URI RKEYs may be significant; never fold them.
    if "://" in result or result.startswith("did:"):
        return result
    canonical = result.lstrip("@").casefold()
    if not canonical:
        raise ValueError("empty normalized subject")
    return canonical


def _clean(value: str, name: str, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be a non-empty string <= {maximum}")
    return value.strip()


def _event(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("event must be a dict")
    network = _clean(data.get("network"), "network").lower()
    queue = _clean(data.get("queue"), "queue").upper()
    kind = _clean(data.get("kind"), "kind").lower()
    outcome = _clean(data.get("outcome"), "outcome").lower()
    if network not in NETWORKS or queue not in QUEUES or kind not in KINDS or outcome not in OUTCOMES:
        raise ValueError("unsupported network, queue, kind or outcome")
    if (kind == "followback") != (outcome in ("present", "absent")):
        raise ValueError("only followback observations can be present/absent")
    if kind == "followback" and data.get("precision", "instant") != "instant":
        raise ValueError("followback snapshot needs an instant")
    precision = data.get("precision", "instant")
    if precision not in ("instant", "day"):
        raise ValueError("precision must be day or instant")
    fields = {
        "network": network, "queue": queue, "subject": _subject(data.get("subject")),
        "kind": kind, "outcome": outcome, "occurred_at": _timestamp(data.get("occurred_at")),
        "precision": precision, "source": _clean(data.get("source"), "source"),
        "source_id": _clean(data.get("source_id"), "source_id", 1024),
        "correlation_id": None, "target_id": None,
    }
    for key in ("correlation_id", "target_id"):
        if data.get(key) is not None:
            fields[key] = _clean(data[key], key, 1024)
    return fields


class RelationshipLedger:
    """One independent SQLite database, not the operational action reservation DB."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory_conn = None
        if self.path == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:", timeout=30, isolation_level=None)
            self._memory_conn.row_factory = sqlite3.Row
        with closing(self._connect()) if self._memory_conn is None else _borrow(self._memory_conn) as conn:
            existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "actions" in existing:
                raise ValueError("use a separate DB; refusing to touch ActionLedger")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise ValueError("unsupported ledger schema version")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def _connect(self):
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _connection(self):
        return _borrow(self._memory_conn) if self._memory_conn is not None else closing(self._connect())

    def append(self, data: dict) -> bool:
        """True on insert, False on an identical replay."""
        return self.append_many([data])["inserted"] == 1

    def append_many(self, events: Iterable[dict]) -> dict:
        """Validate first, commit the entire batch or none of it, idempotently.

        One SQLite connection and writer lock per export, not per row. The
        reservation ledger remains untouched.
        """
        prepared = []
        for raw in events:
            item = _event(raw)
            stable = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()
            identity = json.dumps(
                [item["network"], item["source"], item["source_id"]],
                ensure_ascii=False, separators=(",", ":"),
            )
            event_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            prepared.append((item, digest, event_id))
        stats = {"inserted": 0, "replayed": 0}
        if not prepared:
            return stats
        with self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
                for item, digest, event_id in prepared:
                    old = conn.execute(
                        "SELECT digest FROM relationship_events WHERE event_id=?",
                        (event_id,),
                    ).fetchone()
                    if old is not None:
                        if old["digest"] != digest:
                            raise ValueError(
                                "source event changed after ingestion; new source_id required"
                            )
                        stats["replayed"] += 1
                        continue
                    conn.execute(
                        "INSERT INTO relationship_events("
                        "event_id,network,queue,subject,kind,outcome,occurred_at,precision,"
                        "source,source_id,correlation_id,target_id,digest,ingested_at)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (event_id, *(item[key] for key in (
                            "network", "queue", "subject", "kind", "outcome", "occurred_at",
                            "precision", "source", "source_id", "correlation_id", "target_id")),
                         digest, now),
                    )
                    stats["inserted"] += 1
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return stats

    def history(self, network: str, subject: str) -> list[dict]:
        network = _clean(network, "network").lower()
        if network not in NETWORKS:
            raise ValueError("network")
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM relationship_events WHERE network=? AND subject=? "
                "ORDER BY occurred_at, seq", (network, _subject(subject))
            ).fetchall()
            return [dict(row) for row in rows]

    def count(self) -> int:
        with self._connection() as conn:
            return conn.execute("SELECT count(*) FROM relationship_events").fetchone()[0]

    def conversion(self, network: str, *, as_of: str, min_age_days: int = 2) -> dict:
        """Follow cohorts with latest observed followback; unknown stays UNKNOWN.

        This is descriptive attribution, not causal efficacy. Confirmed unfollow after
        follow excludes the subject from the active cohort.
        """
        if min_age_days < 0:
            raise ValueError("negative min_age_days")
        cutoff = datetime.fromisoformat(_timestamp(as_of)) - timedelta(days=min_age_days)
        as_of = _timestamp(as_of)
        network = _clean(network, "network").lower()
        if network not in NETWORKS:
            raise ValueError("network")
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT subject,kind,outcome,occurred_at,seq FROM relationship_events "
                "WHERE network=? AND occurred_at<=? ORDER BY occurred_at,seq",
                (network, as_of)
            ).fetchall()
        by_person: dict[str, dict] = {}
        for row in rows:
            subject, kind, outcome, at = row["subject"], row["kind"], row["outcome"], row["occurred_at"]
            person = by_person.setdefault(subject, {"follow": None, "unfollow": None, "snapshot": None})
            if kind == "follow" and outcome == "confirmed":
                # Repeated confirmations are not a second follow epoch.
                if person["follow"] is None or person["unfollow"] is not None:
                    person["follow"] = at
                    person["unfollow"] = None
                    person["snapshot"] = None
            elif kind == "unfollow" and outcome == "confirmed" and person["follow"] is not None:
                person["unfollow"] = at
            elif kind == "followback" and person["follow"] is not None and at >= person["follow"]:
                person["snapshot"] = outcome
        stats = {"eligible": 0, "observed": 0, "positive": 0, "negative": 0, "unknown": 0}
        for p in by_person.values():
            if p["follow"] is None or p["unfollow"] is not None:
                continue
            if datetime.fromisoformat(p["follow"]) > cutoff:
                continue
            stats["eligible"] += 1
            if p["snapshot"] in ("present", "absent"):
                stats["observed"] += 1
                stats["positive" if p["snapshot"] == "present" else "negative"] += 1
            else:
                stats["unknown"] += 1
        stats["observed_conversion_rate"] = (
            stats["positive"] / stats["observed"] if stats["observed"] else None
        )
        return stats

    def reconcile_followers(self, *, network: str, queue: str, snapshot_id: str,
                            observed_at: str, tracked: Iterable[str],
                            followers: Iterable[str], complete: bool,
                            source: str = "follower_snapshot") -> dict:
        """No absence from partial feeds. Call only on explicitly captured snapshots."""
        if not isinstance(complete, bool):
            raise ValueError("complete must be bool")
        seen = {_subject(s) for s in followers}
        tracked_ids = {_subject(s) for s in tracked}
        events = []
        unknown = 0
        for subject in sorted(tracked_ids):
            if subject not in seen and not complete:
                unknown += 1
                continue
            status = "present" if subject in seen else "absent"
            key = hashlib.sha256(subject.encode("utf-8")).hexdigest()
            events.append({
                "network": network, "queue": queue, "subject": subject,
                "kind": "followback", "outcome": status, "occurred_at": observed_at,
                "source": source, "source_id": f"{snapshot_id}:{key}",
                "correlation_id": snapshot_id,
            })
        result = self.append_many(events)
        result["unknown"] = unknown
        return result


class _borrow:
    """Do not close an in-memory connection between operations."""
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *exc):
        return False


def legacy_outcome(value: str) -> str:
    s = str(value or "").strip().lower()
    if "incierto" in s or "pendiente_verificacion" in s:
        return "uncertain"
    if s in ("confirmado", "publicado"):
        return "confirmed"
    if s.startswith("saltado_ya_"):
        return "observed"
    if s.startswith("saltado_"):
        return "skipped"
    if s.startswith(("fallo", "error", "parada_")):
        return "failed"
    return "unverified"


def legacy_time(value: str) -> tuple[str, str]:
    text = _clean(value, "fecha")
    try:
        day = date.fromisoformat(text)
        return datetime.combine(day, time(12, tzinfo=timezone.utc)).isoformat(), "day"
    except ValueError:
        return _timestamp(text), "instant"


def import_legacy_csv(ledger: RelationshipLedger, csv_path: str | Path, *,
                      network: str, queue: str, source_id: str) -> dict:
    """Read-only migration of one vertical's registro_interacciones.csv.

    Stable source_id refers to a *versioned immutable export*; reusing it with
    edited/reordered rows raises a collision rather than silently changing history.
    No free-form text (including texto_usado) is persisted.
    """
    source_id = _clean(source_id, "source_id")
    events = []
    ignored = 0
    with open(csv_path, encoding="utf-8-sig", newline="") as handle:
        for line_no, row in enumerate(csv.DictReader(handle), start=2):
            kind_str = str(row.get("tipo") or "").strip().lower()
            pieces = kind_str.split("+")
            if not pieces or any(p not in ACTION_ALIASES for p in pieces):
                ignored += 1
                continue
            subject = row.get("cuenta") or row.get("handle")
            if not subject:
                ignored += 1
                continue
            occurred_at, precision = legacy_time(row.get("fecha"))
            for idx, part in enumerate(pieces):
                events.append({
                    "network": network, "queue": queue, "subject": subject,
                    "kind": ACTION_ALIASES[part],
                    "outcome": legacy_outcome(row.get("resultado")),
                    "occurred_at": occurred_at, "precision": precision,
                    "source": "legacy_registro_interacciones",
                    "source_id": f"{source_id}:row{line_no}:part{idx}",
                    "correlation_id": f"{source_id}:row{line_no}",
                    "target_id": (row.get("url") or "").strip() or None,
                })
    stats = ledger.append_many(events)
    stats["ignored"] = ignored
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Import legacy CSV, without social actions")
    parser.add_argument("--db", required=True, help="independent SQLite file, never action ledger")
    parser.add_argument("--csv", required=True, help="offline CSV export; read-only")
    parser.add_argument("--network", required=True, choices=sorted(NETWORKS))
    parser.add_argument("--queue", required=True, choices=sorted(QUEUES))
    parser.add_argument("--source-id", required=True, help="immutable export identifier")
    args = parser.parse_args()
    ledger = RelationshipLedger(args.db)
    print(json.dumps(import_legacy_csv(
        ledger, args.csv, network=args.network, queue=args.queue, source_id=args.source_id
    ), sort_keys=True))


if __name__ == "__main__":
    main()
