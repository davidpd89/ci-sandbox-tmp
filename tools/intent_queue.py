"""Bandeja de intenciones duradera para WEB, API y MOBILE (solo almacenamiento).

Ninguna función realiza solicitudes a redes sociales. Los adaptadores deben
persistir mark_dispatched() *antes* de cualquier I/O externo. Si se pierde
la respuesta, se exige reconciliación remota; no se promete exactly-once.
Python 3.11+, SQLite, sin dependencias adicionales.
"""
from __future__ import annotations

import contextlib
import json
import os
import random
import sqlite3
import time
from dataclasses import dataclass
from typing import Callable

NETWORKS = frozenset((
    "x", "threads", "facebook", "pinterest", "reddit", "bluesky",
    "mastodon", "tiktok", "instagram",
))
CHANNELS = frozenset(("WEB", "API", "MOBILE"))
MAX_PAYLOAD_BYTES = 32_768


class IdempotencyConflict(ValueError):
    """Una clave existente representa otro trabajo: no se sobrescribe."""


class InvalidTransition(RuntimeError):
    """Lease caducado, fence obsoleto o transición de estado ilegal."""


@dataclass(frozen=True)
class Ticket:
    id: int
    channel: str
    network: str
    kind: str
    target: str
    payload: dict
    owner: str
    fence: int
    attempts: int


class IntentQueue:
    """Cola opt-in; no modifica ActionLedger, CSV ni estados operativos.

    intent_key es estable y aportada por el productor (nunca generada al reintentar).
    La unicidad es (network, intent_key); la clave debe representar una operación
    lógica, no una ejecución/ventana temporal. El adaptador elige el canal.
    """

    def __init__(self, path: str, clock: Callable[[], float] = time.time,
                 jitter: Callable[[], float] = random.random):
        self.path = os.fspath(path)
        self.clock = clock
        self.jitter = jitter
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with contextlib.closing(self._conn()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS intents (
                    id INTEGER PRIMARY KEY,
                    network TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    intent_key TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    target TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    due REAL NOT NULL,
                    expires_at REAL,
                    owner TEXT,
                    fence INTEGER NOT NULL DEFAULT 0,
                    lease_until REAL,
                    last_evidence TEXT NOT NULL DEFAULT '',
                    created REAL NOT NULL,
                    updated REAL NOT NULL,
                    UNIQUE(network, intent_key)
                );
                CREATE INDEX IF NOT EXISTS intents_ready_idx
                  ON intents(channel, status, due, priority);
                CREATE TABLE IF NOT EXISTS intent_events (
                    seq INTEGER PRIMARY KEY,
                    intent_id INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    evidence TEXT NOT NULL DEFAULT '',
                    at REAL NOT NULL
                );
            """)

    def _conn(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        return db

    @contextlib.contextmanager
    def _tx(self):
        db = self._conn()
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    def _event(self, db, item_id, event, evidence="", now=None):
        db.execute(
            "INSERT INTO intent_events(intent_id,event,evidence,at) VALUES (?,?,?,?)",
            (item_id, event, str(evidence)[:300], self.clock() if now is None else now),
        )

    @staticmethod
    def _required(value, name):
        if not isinstance(value, str) or not value.strip() or len(value) > 500:
            raise ValueError(name + " debe ser una cadena no vacía de <=500 caracteres")
        return value.strip()

    def enqueue(self, *, network: str, channel: str, intent_key: str, kind: str,
                target: str, payload: dict | None = None, priority: int = 0,
                due: float | None = None, expires_at: float | None = None,
                max_attempts: int = 5) -> int:
        if network not in NETWORKS or channel not in CHANNELS:
            raise ValueError("red/canal desconocidos")
        for name, val in (("intent_key", intent_key), ("kind", kind), ("target", target)):
            self._required(val, name)
        if not isinstance(max_attempts, int) or not 1 <= max_attempts <= 100:
            raise ValueError("max_attempts fuera de rango")
        if type(priority) is not int or abs(priority) > 10000:
            raise ValueError("priority fuera de rango")
        payload = {} if payload is None else payload
        if not isinstance(payload, dict):
            raise ValueError("payload debe ser un objeto JSON")
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False)
        if len(serialized.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise ValueError("payload demasiado grande")
        now = self.clock()
        due = now if due is None else float(due)
        expires_at = None if expires_at is None else float(expires_at)
        identity = (network, channel, intent_key, kind, target, serialized,
                    max_attempts, priority, due, expires_at)
        with self._tx() as db:
            old = db.execute(
                "SELECT * FROM intents WHERE network=? AND intent_key=?",
                (network, intent_key),
            ).fetchone()
            if old is not None:
                existing = (old["network"], old["channel"], old["intent_key"],
                            old["kind"], old["target"], old["payload"],
                            old["max_attempts"], old["priority"], old["due"],
                            old["expires_at"])
                if existing != identity:
                    raise IdempotencyConflict("intent_key usado con un contenido distinto")
                return old["id"]
            cur = db.execute(
                """INSERT INTO intents(network,channel,intent_key,kind,target,payload,
                    status,max_attempts,priority,due,expires_at,created,updated)
                    VALUES (?,?,?,?,?,?,'queued',?,?,?,?,?,?)""",
                (network, channel, intent_key, kind, target, serialized,
                 max_attempts, priority, due, expires_at, now, now),
            )
            self._event(db, cur.lastrowid, "enqueued", now=now)
            return cur.lastrowid

    def _recover_locked(self, db, channel, now):
        rows = db.execute(
            """SELECT id,status,attempts,max_attempts,expires_at
               FROM intents WHERE channel=? AND
               ((status IN ('claimed','in_flight') AND lease_until<=?)
                OR (status IN ('queued','claimed') AND expires_at<=?))""",
            (channel, now, now),
        ).fetchall()
        stats = {"requeued": 0, "uncertain": 0, "dead": 0}
        for row in rows:
            expired = row["expires_at"] is not None and row["expires_at"] <= now
            if row["status"] == "in_flight":
                new, event = "uncertain", "lease_expired_after_dispatch"
            elif expired or row["attempts"] >= row["max_attempts"]:
                new, event = "dead", "deadline_or_attempts_exhausted"
            else:
                new, event = "queued", "lease_expired_before_dispatch"
            db.execute(
                """UPDATE intents SET status=?,owner=NULL,lease_until=NULL,updated=?
                   WHERE id=?""",
                (new, now, row["id"]),
            )
            self._event(db, row["id"], event, now=now)
            stats[{"queued": "requeued", "uncertain": "uncertain", "dead": "dead"}[new]] += 1
        return stats

    def recover(self, channel: str) -> dict:
        if channel not in CHANNELS:
            raise ValueError("canal desconocido")
        with self._tx() as db:
            return self._recover_locked(db, channel, self.clock())

    def claim(self, channel: str, owner: str, lease_seconds: float = 120) -> Ticket | None:
        if channel not in CHANNELS:
            raise ValueError("canal desconocido")
        owner = self._required(owner, "owner")
        if not 1 <= lease_seconds <= 86400:
            raise ValueError("lease_seconds fuera de rango")
        now = self.clock()
        with self._tx() as db:
            self._recover_locked(db, channel, now)
            row = db.execute(
                """SELECT * FROM intents WHERE channel=? AND status='queued' AND due<=?
                   AND (expires_at IS NULL OR expires_at>?)
                   ORDER BY priority DESC,due ASC,id ASC LIMIT 1""",
                (channel, now, now),
            ).fetchone()
            if row is None:
                return None
            fence = row["fence"] + 1
            db.execute(
                """UPDATE intents SET status='claimed',owner=?,fence=?,
                   lease_until=?,attempts=attempts+1,updated=? WHERE id=?""",
                (owner, fence, now + lease_seconds, now, row["id"]),
            )
            self._event(db, row["id"], "claimed", now=now)
            return Ticket(row["id"], channel, row["network"], row["kind"],
                          row["target"], json.loads(row["payload"]), owner,
                          fence, row["attempts"] + 1)

    def _owned(self, db, ticket: Ticket, states: tuple[str, ...]):
        row = db.execute("SELECT * FROM intents WHERE id=?", (ticket.id,)).fetchone()
        if row is None or row["owner"] != ticket.owner or row["fence"] != ticket.fence:
            raise InvalidTransition("propietario o fence obsoleto")
        if row["status"] not in states:
            raise InvalidTransition("estado incompatible: " + row["status"])
        return row

    def mark_dispatched(self, ticket: Ticket) -> None:
        """COMMIT antes de la primera llamada externa; luego solo ACK con evidencia."""
        now = self.clock()
        with self._tx() as db:
            row = self._owned(db, ticket, ("claimed",))
            if row["lease_until"] <= now or (
                row["expires_at"] is not None and row["expires_at"] <= now
            ):
                raise InvalidTransition("lease o destino caducado")
            db.execute("UPDATE intents SET status='in_flight',updated=? WHERE id=?",
                       (now, ticket.id))
            self._event(db, ticket.id, "dispatched", now=now)

    def confirm(self, ticket: Ticket, evidence: str) -> None:
        """Solo ACK positivo verificable; admite ACK tardío del mismo fence."""
        evidence = self._required(evidence, "evidence")
        now = self.clock()
        with self._tx() as db:
            self._owned(db, ticket, ("in_flight", "uncertain"))
            db.execute(
                """UPDATE intents SET status='confirmed',owner=NULL,lease_until=NULL,
                   last_evidence=?,updated=? WHERE id=?""",
                (evidence, now, ticket.id),
            )
            self._event(db, ticket.id, "confirmed", evidence, now)

    def _no_effect_locked(self, db, row, evidence, now, base_delay, max_delay):
        if not 0 <= base_delay <= max_delay <= 86400:
            raise ValueError("backoff inválido")
        if row["attempts"] >= row["max_attempts"] or (
            row["expires_at"] is not None and row["expires_at"] <= now
        ):
            status, due = "dead", row["due"]
        else:
            # jitter acotado 0.8..1.2; nunca excede max_delay.
            raw = base_delay * (2 ** min(row["attempts"] - 1, 20))
            noise = 0.8 + 0.4 * self.jitter()
            status, due = "queued", now + min(max_delay, raw * noise)
        db.execute(
            """UPDATE intents SET status=?,due=?,owner=NULL,lease_until=NULL,
               last_evidence=?,updated=? WHERE id=?""",
            (status, due, evidence, now, row["id"]),
        )
        self._event(db, row["id"], "definitive_no_effect_" + status, evidence, now)
        return status

    def no_effect(self, ticket: Ticket, evidence: str,
                  base_delay: float = 5, max_delay: float = 600) -> str:
        """Solo si es demostrable que NO hubo efecto remoto."""
        evidence = self._required(evidence, "evidence")
        now = self.clock()
        with self._tx() as db:
            row = self._owned(db, ticket, ("claimed", "in_flight"))
            return self._no_effect_locked(db, row, evidence, now, base_delay, max_delay)

    def reconcile(self, item_id: int, verdict: str, evidence: str,
                  base_delay: float = 5, max_delay: float = 600) -> str:
        """Verdict remoto: confirmed/not_applied/unknown; nunca interpretar timeout como fallo."""
        if verdict not in ("confirmed", "not_applied", "unknown"):
            raise ValueError("verdict inválido")
        evidence = self._required(evidence, "evidence")
        now = self.clock()
        with self._tx() as db:
            row = db.execute("SELECT * FROM intents WHERE id=?", (item_id,)).fetchone()
            if row is None or row["status"] != "uncertain":
                raise InvalidTransition("solo se reconcilian efectos inciertos")
            if verdict == "unknown":
                self._event(db, item_id, "reconcile_unknown", evidence, now)
                return "uncertain"
            if verdict == "confirmed":
                db.execute(
                    """UPDATE intents SET status='confirmed',owner=NULL,lease_until=NULL,
                       last_evidence=?,updated=? WHERE id=?""",
                    (evidence, now, item_id),
                )
                self._event(db, item_id, "reconcile_confirmed", evidence, now)
                return "confirmed"
            return self._no_effect_locked(db, row, evidence, now, base_delay, max_delay)

    def status(self, item_id: int) -> dict | None:
        with contextlib.closing(self._conn()) as db:
            row = db.execute("SELECT * FROM intents WHERE id=?", (item_id,)).fetchone()
        return dict(row) if row else None

    def events(self, item_id: int) -> list[tuple]:
        with contextlib.closing(self._conn()) as db:
            rows = db.execute(
                "SELECT event,evidence FROM intent_events WHERE intent_id=? ORDER BY seq",
                (item_id,),
            ).fetchall()
        return [(r["event"], r["evidence"]) for r in rows]
