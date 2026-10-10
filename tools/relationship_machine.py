"""Máquina de estados auditable de relaciones RRSS; solo proyección, sin acciones sociales.

No reemplaza relationship_policy (plazos, reintentos y reciprocidad de mensajes)
ni action_ledger (reservas/confirmaciones). Los adaptadores aportan eventos
confirmados; la máquina nunca ejecuta follow, unfollow ni llamadas de red.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
from typing import Iterable

NETWORKS = frozenset(("x", "threads", "facebook", "pinterest", "reddit",
                     "bluesky", "mastodon", "tiktok", "instagram"))
LANES = frozenset(("WEB", "API", "MOBILE"))
STATES = ("descubierto", "candidato", "seguido", "reciproco", "activo",
          "fiel", "inactivo", "reactivado", "cerrado")
KINDS = frozenset(("discovered", "qualified", "follow_confirmed",
                   "followback_confirmed", "activity_confirmed",
                   "loyalty_confirmed", "inactivity_confirmed",
                   "reactivation_confirmed", "followback_lost",
                   "unfollow_confirmed", "retry_approved", "closed_confirmed"))


class TransitionError(ValueError):
    """Evento incompatible con el estado o con la evidencia existente."""


class OutOfOrderEvent(TransitionError):
    """Reconciliar el origen: nunca se reordena silenciosamente un historial."""


@dataclass(frozen=True)
class Event:
    network: str
    account: str
    event_id: str
    kind: str
    lane: str
    occurred_at: str


@dataclass(frozen=True)
class Snapshot:
    state: str
    following: bool
    follows_me: bool
    version: int
    last_at: str


@dataclass(frozen=True)
class Decision:
    applied: bool
    before: str | None
    after: str
    version: int


def _timestamp(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("timezone required")
        return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("occurred_at must be timezone-aware ISO 8601") from exc


def _key(event: Event) -> tuple[str, str, str, str, str, str]:
    net = event.network.strip().casefold() if isinstance(event.network, str) else ""
    # Un identificador opaco del proveedor debe pasarse estable. No se acortan
    # dominios federados ni se fusionan redes o cuentas por nombre parecido.
    account = event.account.strip() if isinstance(event.account, str) else ""
    eid = event.event_id.strip() if isinstance(event.event_id, str) else ""
    if net not in NETWORKS:
        raise ValueError("unknown network")
    if not isinstance(event.account, str) or not isinstance(event.event_id, str):
        raise ValueError("account and event_id must be strings")
    if any(ord(c) < 32 for c in event.account) or any(ord(c) < 32 for c in event.event_id):
        raise ValueError("control character in account or event_id")
    if event.account != account or event.event_id != eid:
        raise ValueError("identity/event IDs must be canonical, without surrounding whitespace")
    if not account or len(account) > 512 or any(ord(c) < 32 for c in account):
        raise ValueError("invalid account identifier")
    if not eid or len(eid) > 256 or any(ord(c) < 32 for c in eid):
        raise ValueError("invalid event_id")
    if event.kind not in KINDS:
        raise ValueError("unknown event kind")
    if event.lane not in LANES:
        raise ValueError("unknown execution lane")
    return net, account, eid, event.kind, event.lane, _timestamp(event.occurred_at)


def step(before: Snapshot | None, kind: str, occurred_at: str) -> Snapshot:
    """Función pura, transiciones explícitas y guardias verificables."""
    when = _timestamp(occurred_at)
    if kind not in KINDS:
        raise TransitionError("unknown transition")
    if before is None:
        if kind != "discovered":
            raise TransitionError("first event must be discovered")
        return Snapshot("descubierto", False, False, 1, when)
    if when < before.last_at:
        raise OutOfOrderEvent("older event: explicit reconciliation required")
    s, following, follows_me = before.state, before.following, before.follows_me
    new = None
    if kind == "qualified" and s == "descubierto":
        new = "candidato"
    elif kind == "follow_confirmed" and s == "candidato" and not following:
        following, new = True, "seguido"
    elif kind == "followback_confirmed" and following and s in ("seguido", "inactivo"):
        follows_me = True
        new = "reciproco" if s == "seguido" else "reactivado"
    elif kind == "activity_confirmed" and following and follows_me and s in ("reciproco", "reactivado"):
        new = "activo"
    elif kind == "loyalty_confirmed" and s == "activo" and following and follows_me:
        new = "fiel"
    elif kind == "inactivity_confirmed" and s in ("seguido", "reciproco", "activo", "fiel", "reactivado"):
        new = "inactivo"
    elif kind == "reactivation_confirmed" and s == "inactivo" and following and follows_me:
        new = "reactivado"
    elif kind == "followback_lost" and s in ("reciproco", "activo", "fiel", "reactivado") and following and follows_me:
        follows_me, new = False, "inactivo"
    elif kind == "unfollow_confirmed" and s in ("seguido", "reciproco", "activo", "fiel", "inactivo", "reactivado") and following:
        following, new = False, "inactivo"
    elif kind == "retry_approved" and s == "inactivo" and not following:
        new = "candidato"
    elif kind == "closed_confirmed" and s != "cerrado":
        new = "cerrado"
    if new is None:
        raise TransitionError(f"impossible transition {s} + {kind}")
    if new in ("reciproco", "activo", "fiel", "reactivado") and not (following and follows_me):
        raise TransitionError("mutuality without both verified follows")
    return Snapshot(new, following, follows_me, before.version + 1, when)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS relation_state (
 network TEXT NOT NULL, account TEXT NOT NULL, state TEXT NOT NULL,
 following INTEGER NOT NULL, follows_me INTEGER NOT NULL,
 version INTEGER NOT NULL, last_at TEXT NOT NULL,
 PRIMARY KEY(network, account)
);
CREATE TABLE IF NOT EXISTS relation_events (
 network TEXT NOT NULL, account TEXT NOT NULL, event_id TEXT NOT NULL,
 kind TEXT NOT NULL, lane TEXT NOT NULL, occurred_at TEXT NOT NULL,
 before_state TEXT, after_state TEXT NOT NULL, version INTEGER NOT NULL,
 PRIMARY KEY(network, account, event_id)
);
CREATE INDEX IF NOT EXISTS relation_events_order
 ON relation_events(network, account, version);
"""


# Se comprueban también PK, tipos, orden y nulabilidad. INSERT sin lista de
# columnas exige esta forma exacta; aceptar un esquema legado parcialmente
# compatible provocaría errores tardíos o claves idempotentes incorrectas.
_EXPECTED_SCHEMA = {
    "relation_state": (
        ("network", "TEXT", 1, 1), ("account", "TEXT", 1, 2),
        ("state", "TEXT", 1, 0), ("following", "INTEGER", 1, 0),
        ("follows_me", "INTEGER", 1, 0), ("version", "INTEGER", 1, 0),
        ("last_at", "TEXT", 1, 0),
    ),
    "relation_events": (
        ("network", "TEXT", 1, 1), ("account", "TEXT", 1, 2),
        ("event_id", "TEXT", 1, 3), ("kind", "TEXT", 1, 0),
        ("lane", "TEXT", 1, 0), ("occurred_at", "TEXT", 1, 0),
        ("before_state", "TEXT", 0, 0), ("after_state", "TEXT", 1, 0),
        ("version", "INTEGER", 1, 0),
    ),
}


def _validate_sqlite_schema(db, *, require_all: bool = False) -> None:
    """Rechazo preventivo de DB ajena/antigua; nunca migra datos implícitamente."""
    for table, expected in _EXPECTED_SCHEMA.items():
        rows = db.execute(f"PRAGMA table_info({table})").fetchall()
        if not rows:
            if require_all:
                raise ValueError(f"missing relationship SQLite table: {table}")
            continue
        columns = tuple((r[1], str(r[2]).upper(), r[3], r[5]) for r in rows)
        if columns != expected:
            raise ValueError(f"incompatible relationship SQLite schema: {table}")


def _lookup_key(network: str, account: str) -> tuple[str, str]:
    """Aplica también a las lecturas la normalización usada en apply()."""
    net = network.strip().casefold() if isinstance(network, str) else ""
    if net not in NETWORKS:
        raise ValueError("invalid network")
    if (not isinstance(account, str) or not account or len(account) > 512
            or account != account.strip()
            or any(ord(c) < 32 for c in account)):
        raise ValueError("invalid account identifier")
    return net, account


class RelationshipStore:
    """SQLite de proyecciones opt-in. Requiere ruta explícita; NO abre datos reales.

    El inserto de evento y la proyección comparten BEGIN IMMEDIATE. Un evento
    duplicado idéntico es idempotente; reutilizar su ID con otro contenido falla.
    """

    def __init__(self, path: str):
        if not path:
            raise ValueError("explicit isolated database path required")
        self.path = str(path)
        if self.path == ":memory:":
            raise ValueError("SQLite :memory: does not survive per-call connections; use a temporary file")
        with closing(self._connect()) as db:
            _validate_sqlite_schema(db)
            db.executescript(_SCHEMA)
            _validate_sqlite_schema(db, require_all=True)
            db.commit()

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.execute("PRAGMA busy_timeout=15000")
        return db

    @staticmethod
    def _read(db, net, account):
        row = db.execute(
            "SELECT state, following, follows_me, version, last_at "
            "FROM relation_state WHERE network=? AND account=?", (net, account)
        ).fetchone()
        return Snapshot(row[0], bool(row[1]), bool(row[2]), row[3], row[4]) if row else None

    def snapshot(self, network: str, account: str) -> Snapshot | None:
        net, account = _lookup_key(network, account)
        with closing(self._connect()) as db:
            return self._read(db, net, account)

    def apply(self, event: Event) -> Decision:
        net, account, eid, kind, lane, when = _key(event)
        with closing(self._connect()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                old = db.execute(
                    "SELECT kind, lane, occurred_at, before_state, after_state, version "
                    "FROM relation_events WHERE network=? AND account=? AND event_id=?",
                    (net, account, eid)).fetchone()
                if old:
                    if old[:3] != (kind, lane, when):
                        raise TransitionError("event_id collision: divergent payload")
                    result = Decision(False, old[3], old[4], old[5])
                else:
                    before = self._read(db, net, account)
                    after = step(before, kind, when)
                    db.execute(
                        "INSERT INTO relation_events VALUES (?,?,?,?,?,?,?,?,?)",
                        (net, account, eid, kind, lane, when, before.state if before else None,
                         after.state, after.version))
                    db.execute(
                        "INSERT INTO relation_state VALUES (?,?,?,?,?,?,?) "
                        "ON CONFLICT(network, account) DO UPDATE SET "
                        "state=excluded.state, following=excluded.following, "
                        "follows_me=excluded.follows_me, version=excluded.version, "
                        "last_at=excluded.last_at",
                        (net, account, after.state, int(after.following),
                         int(after.follows_me), after.version, after.last_at))
                    result = Decision(True, before.state if before else None,
                                      after.state, after.version)
                db.commit()
                return result
            except BaseException:
                db.rollback()
                raise

    def history(self, network: str, account: str) -> list[Event]:
        net, account = _lookup_key(network, account)
        with closing(self._connect()) as db:
            rows = db.execute(
                "SELECT event_id, kind, lane, occurred_at FROM relation_events "
                "WHERE network=? AND account=? ORDER BY version", (net, account)
            ).fetchall()
        return [Event(net, account, *row) for row in rows]

    def verify_replay(self, network: str, account: str) -> bool:
        """Verifica historia y proyección desde una sola instantánea SQLite."""
        net, account = _lookup_key(network, account)
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            rows = db.execute(
                "SELECT kind, occurred_at, before_state, after_state, version "
                "FROM relation_events WHERE network=? AND account=? ORDER BY version",
                (net, account)).fetchall()
            saved = self._read(db, net, account)
            db.commit()
        current = None
        try:
            for kind, when, old, new, version in rows:
                previous_state = current.state if current else None
                current = step(current, kind, when)
                if (old, new, version) != (previous_state, current.state, current.version):
                    return False
        except ValueError:
            return False
        return current == saved


def settled_action_event(*, network: str, account: str, event_id: str,
                         action: str, outcome: str, lane: str,
                         occurred_at: str, independently_verified: bool = False
                         ) -> Event | None:
    """Adaptador único para productores WEB/API/MOBILE (sin ejecutar acciones).

    Fallo, salto o intención no son prueba de estado. Los estados observados
    (followback/inactividad/fidelidad) requieren verificación independiente.
    Nunca genera identificadores con timestamps; exige ID estable del origen.
    """
    action_map = {
        "discovery": "discovered", "qualification": "qualified",
        "follow": "follow_confirmed", "unfollow": "unfollow_confirmed",
        "block": "closed_confirmed", "followback": "followback_confirmed",
        "activity": "activity_confirmed", "loyalty": "loyalty_confirmed",
        "inactive": "inactivity_confirmed", "reactivation": "reactivation_confirmed",
        "followback_lost": "followback_lost", "retry": "retry_approved",
        "close": "closed_confirmed",
    }
    if action not in action_map:
        raise ValueError("unknown producer action")
    if not isinstance(outcome, str) or outcome.strip().casefold() not in ("confirmado", "publicado", "verified"):
        return None
    observational = {"followback", "activity", "loyalty", "inactive",
                     "reactivation", "followback_lost", "retry"}
    if action in observational and not independently_verified:
        raise TransitionError("observational change requires independently verified evidence")
    event = Event(network, account, event_id, action_map[action], lane, occurred_at)
    _key(event)  # Validar en frontera, antes de incorporar a cualquier proyección.
    return event


def audit_legacy_rows(network: str, rows: Iterable[dict], *, lane="WEB") -> dict:
    """Auditoría conservadora de CSV heredado sin mutaciones ni suposiciones.

    Sólo follow/unfollow/block confirmados. La ausencia de follow previo no se
    fabrica, los likes/comentarios no prueban followback y cada incoherencia
    devuelve número de fila para reparar el productor. No se escribe SQLite.
    """
    if network not in NETWORKS or lane not in LANES:
        raise ValueError("invalid network/lane")
    state: dict[str, Snapshot] = {}
    anomalies = []
    verified = 0
    for index, row in enumerate(rows, 1):
        kind = str(row.get("tipo") or "").strip().casefold()
        outcome = str(row.get("resultado") or "").strip().casefold()
        if kind not in ("follow", "unfollow", "block") or outcome not in ("confirmado", "publicado"):
            continue
        # Misma normalización de handles que la política ya existente.
        from relationship_policy import norm
        account = norm(row.get("cuenta"))
        if not account:
            anomalies.append({"row": index, "reason": "missing account"})
            continue
        try:
            date = str(row.get("fecha") or "")[:10]
            when = _timestamp(date + "T12:00:00+00:00")
            before = state.get(account)
            if before is None:
                before = step(None, "discovered", when)
                before = step(before, "qualified", when)
            event_kind = {"follow": "follow_confirmed",
                          "unfollow": "unfollow_confirmed",
                          "block": "closed_confirmed"}[kind]
            state[account] = step(before, event_kind, when)
            verified += 1
        except (TransitionError, ValueError) as exc:
            anomalies.append({"row": index, "reason": str(exc)})
    return {"network": network, "verified": verified, "accounts": len(state),
            "states": {k: v.state for k, v in sorted(state.items())},
            "anomalies": anomalies}


def mermaid_diagram() -> str:
    """Diagrama textual determinista; sin Graphviz, navegador ni red."""
    edges = (
        ("[*]", "descubierto", "discovered"),
        ("descubierto", "candidato", "qualified"),
        ("candidato", "seguido", "follow_confirmed"),
        ("seguido", "reciproco", "followback_confirmed"),
        ("reciproco", "activo", "activity_confirmed"),
        ("reactivado", "activo", "activity_confirmed"),
        ("activo", "fiel", "loyalty_confirmed"),
        ("inactivo", "reactivado", "reactivation_confirmed / mutual"),
        ("inactivo", "reactivado", "followback_confirmed / following"),
        ("inactivo", "candidato", "retry_approved / !following"),
    )
    lines = ["stateDiagram-v2"]
    lines += [f"    {src} --> {dst}: {kind}" for src, dst, kind in edges]
    for s in ("seguido", "reciproco", "activo", "fiel", "reactivado"):
        lines.append(f"    {s} --> inactivo: inactivity_confirmed")
        lines.append(f"    {s} --> inactivo: unfollow_confirmed")
    for s in ("reciproco", "activo", "fiel", "reactivado"):
        lines.append(f"    {s} --> inactivo: followback_lost")
    for s in STATES[:-1]:
        lines.append(f"    {s} --> cerrado: closed_confirmed")
    return "\n".join(dict.fromkeys(lines)) + "\n"


if __name__ == "__main__":
    print(mermaid_diagram(), end="")
