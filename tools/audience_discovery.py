"""Descubrimiento de audiencias por interacciones: núcleo offline multired con reconciliación de snapshots.

Recibe páginas YA LEÍDAS por los escáneres WEB/API/MOBILE; nunca abre sesión
ni ejecuta acciones sociales. Contrato estable con identidades y señales con
procedencia. Compatibilidad Python 3.11 Windows/Linux; solo biblioteca estándar.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Callable, Mapping, Sequence
import re
import sqlite3
import uuid

LANES = {
    "x": "WEB", "threads": "WEB", "facebook": "WEB",
    "pinterest": "WEB", "instagram": "WEB",
    "reddit": "API", "bluesky": "API", "mastodon": "API",
    "tiktok": "MOBILE",
}
KINDS = {"like": 1.0, "comment": 4.0, "reply": 5.0, "repost": 2.0}
# La presencia de contadores agregados nunca equivale a conocer los autores.
# "export" = observaciones del colector específico, no disponibilidad universal.
CAPABILITIES = {
    "bluesky": {"like": "API", "comment": "API", "reply": "API", "repost": "API"},
    "mastodon": {"like": "API", "comment": "API", "reply": "API", "repost": "API"},
    "reddit": {"like": None, "comment": "API", "reply": "API", "repost": None},
    "x": {"like": "WEB/export", "comment": "WEB/export", "reply": "WEB/export", "repost": "WEB/export"},
    "threads": {"like": None, "comment": "API/WEB", "reply": "API/WEB", "repost": None},
    "facebook": {"like": "WEB/export", "comment": "API/WEB", "reply": "API/WEB", "repost": "WEB/export"},
    "pinterest": {"like": None, "comment": "WEB/export", "reply": "WEB/export", "repost": None},
    "instagram": {"like": "WEB/export", "comment": "WEB/export", "reply": "WEB/export", "repost": None},
    "tiktok": {"like": None, "comment": "MOBILE/export", "reply": "MOBILE/export", "repost": None},
}
NICHE = re.compile(r"fantas[ií]a|romantasy|lector(?:a|es)?|lectura|libro|novela|"
                   r"booktok|bookstagram|saga|escritor|drag[oó]n|romance", re.I)


class ObservationError(ValueError):
    """Página o identidad incompleta; no fabricar una observación."""


_CURSOR_UNSET = object()


def timestamp(value: str | datetime | None) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ObservationError("timestamp_invalido") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ObservationError("timestamp_sin_zona")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def actor_fields(network: str, row: Mapping) -> tuple[str, str, bool, str]:
    """ID estable del actor, handle visible y texto de perfil. Nunca usar ID del post."""
    obj = row.get("actor") or row.get("account") or row.get("user") or row.get("from") or row.get("author")
    if isinstance(obj, str):
        obj = {"handle": obj}
    if not isinstance(obj, Mapping):
        raise ObservationError("actor_ausente")
    handle = str(next((obj[k] for k in ("handle", "acct", "username", "screen_name",
                                       "unique_id", "name") if obj.get(k)), "")).strip().lstrip("@")
    profile = str(obj.get("bio") or obj.get("description") or "")[:500]
    ids = ("did", "id", "pk", "rest_id", "sec_uid", "author_fullname")
    stable = str(next((obj[k] for k in ids if obj.get(k) is not None and str(obj[k]).strip()), "")).strip()
    if network == "mastodon" and stable and not stable.startswith("did:"):
        instance = str(row.get("instance") or "").strip().lower()
        # Los IDs numéricos de Mastodon solo son únicos dentro de una instancia.
        if not instance:
            stable = ""
        else:
            stable = instance + ":" + stable
    if network == "bluesky" and stable and not stable.startswith("did:"):
        stable = ""
    if stable:
        return "id:" + stable, handle, True, profile
    if not handle:
        raise ObservationError("identidad_no_resoluble")
    # Provisional: renombrar un handle sin ID NO se interpreta como la misma persona.
    return "handle:" + handle.casefold(), handle, False, profile


@dataclass(frozen=True)
class Observation:
    network: str
    event_key: str
    account_key: str
    handle: str
    stable_identity: bool
    kind: str
    post_key: str
    occurred_at: str | None
    observed_at: str
    post_created_at: str | None
    surface: str
    text: str
    profile: str
    deleted: bool


def normalize(network: str, kind: str, raw: Mapping, *,
              surface: str, post_key: str, observed_at: str,
              post_created_at: str | None = None) -> Observation:
    if network not in LANES or kind not in KINDS:
        raise ObservationError("red_o_senal_desconocida")
    if CAPABILITIES[network].get(kind) is None:
        raise ObservationError("fuente_no_observable")
    if not isinstance(raw, Mapping) or not surface or not post_key:
        raise ObservationError("origen_incompleto")
    account_key, handle, stable, profile = actor_fields(network, raw)
    if network == "mastodon" and raw.get("instance"):
        # Status y comentarios Mastodon usan IDs locales a la instancia.
        post_key = str(raw["instance"]).strip().casefold() + "|" + post_key
    event_id = str(raw.get("event_id") or raw.get("comment_id") or raw.get("uri") or "").strip()
    # Los endpoints de likers/reposters a veces solo devuelven cuentas.
    # La combinación estable de post, tipo y actor identifica ese edge.
    if not event_id and kind in ("like", "repost"):
        event_id = account_key
    if not event_id:
        raise ObservationError("evento_sin_id")
    event_key = "|".join((post_key, kind, event_id))
    return Observation(
        network, event_key, account_key, handle, stable, kind, post_key,
        timestamp(raw.get("occurred_at")), timestamp(observed_at),
        timestamp(post_created_at or raw.get("post_created_at")), surface,
        str(raw.get("text") or "")[:1000], profile,
        raw.get("deleted") is True,
    )


def _age_hours(event_time: str, reference: str) -> float:
    return (datetime.fromisoformat(reference) - datetime.fromisoformat(event_time)).total_seconds() / 3600


class AudienceStore:
    """SQLite separada del estado operativo real; una transacción por página."""
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path, timeout=30)
        self.db.execute("PRAGMA foreign_keys=ON")
        if path != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS audience_accounts (
                network TEXT NOT NULL, account_key TEXT NOT NULL,
                handle TEXT NOT NULL, stable INTEGER NOT NULL, profile TEXT NOT NULL,
                first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
                PRIMARY KEY(network, account_key));
            CREATE TABLE IF NOT EXISTS audience_events (
                network TEXT NOT NULL, event_key TEXT NOT NULL,
                account_key TEXT NOT NULL, kind TEXT NOT NULL, post_key TEXT NOT NULL,
                surface TEXT NOT NULL, occurred_at TEXT, observed_at TEXT NOT NULL,
                post_created_at TEXT, text TEXT NOT NULL, active INTEGER NOT NULL,
                PRIMARY KEY(network, event_key));
            CREATE TABLE IF NOT EXISTS audience_sightings (
                network TEXT NOT NULL, event_key TEXT NOT NULL,
                surface TEXT NOT NULL, seed TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                PRIMARY KEY(network, event_key, surface, seed));
            CREATE TABLE IF NOT EXISTS audience_cursor_history (
                network TEXT NOT NULL, surface TEXT NOT NULL, seed TEXT NOT NULL,
                cursor TEXT NOT NULL,
                PRIMARY KEY(network, surface, seed, cursor));
            CREATE INDEX IF NOT EXISTS idx_audience_events_account
                ON audience_events(network, account_key, active);
            CREATE TABLE IF NOT EXISTS audience_cursors (
                network TEXT NOT NULL, surface TEXT NOT NULL, seed TEXT NOT NULL,
                cursor TEXT, PRIMARY KEY(network, surface, seed));

            CREATE TABLE IF NOT EXISTS audience_snapshots (
                snapshot_id TEXT NOT NULL,
                network TEXT NOT NULL,
                surface TEXT NOT NULL,
                seed TEXT NOT NULL,
                post_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                PRIMARY KEY(snapshot_id));
            CREATE TABLE IF NOT EXISTS audience_snapshot_staging (
                snapshot_id TEXT NOT NULL,
                network TEXT NOT NULL,
                event_key TEXT NOT NULL,
                account_key TEXT NOT NULL,
                kind TEXT NOT NULL,
                post_key TEXT NOT NULL,
                surface TEXT NOT NULL,
                occurred_at TEXT,
                observed_at TEXT NOT NULL,
                post_created_at TEXT,
                text TEXT NOT NULL,
                handle TEXT NOT NULL,
                stable INTEGER NOT NULL,
                profile TEXT NOT NULL,
                deleted INTEGER NOT NULL,
                PRIMARY KEY(snapshot_id, event_key),
                FOREIGN KEY(snapshot_id) REFERENCES audience_snapshots(snapshot_id) ON DELETE CASCADE);
        """)

    def close(self) -> None:
        self.db.close()

    def cursor(self, network: str, surface: str, seed: str) -> str | None:
        row = self.db.execute(
            "SELECT cursor FROM audience_cursors WHERE network=? AND surface=? AND seed=?",
            (network, surface, seed)).fetchone()
        return row[0] if row else None

    def seen_cursor(self, network: str, surface: str, seed: str, cursor: str) -> bool:
        return self.db.execute(
            "SELECT 1 FROM audience_cursor_history "
            "WHERE network=? AND surface=? AND seed=? AND cursor=?",
            (network, surface, seed, cursor)).fetchone() is not None

    def start_snapshot(self, network: str, surface: str, seed: str,
                       post_key: str, kind: str, now: str) -> str:
        if network not in LANES or not surface or not seed or not post_key or kind not in KINDS:
            raise ObservationError("parametros_snapshot_invalidos")
        sid = str(uuid.uuid4())
        now_ts = timestamp(now)
        with self.db:
            self.db.execute(
                "INSERT INTO audience_snapshots(snapshot_id, network, surface, seed, post_key, kind, started_at, status) "
                "VALUES(?,?,?,?,?,?,?,'active')",
                (sid, network, surface, seed, post_key, kind, now_ts))
        return sid

    def stage_snapshot_observations(self, snapshot_id: str, rows: Sequence[Observation]) -> None:
        with self.db:
            snap = self.db.execute(
                "SELECT network, status FROM audience_snapshots WHERE snapshot_id=?",
                (snapshot_id,)).fetchone()
            if not snap or snap[1] != "active":
                raise ObservationError("snapshot_no_activo")
            network = snap[0]
            for row in rows:
                if row.network != network:
                    raise ObservationError("origen_cruzado")
                self.db.execute("""
                    INSERT INTO audience_snapshot_staging
                    (snapshot_id, network, event_key, account_key, kind, post_key, surface,
                     occurred_at, observed_at, post_created_at, text, handle, stable, profile, deleted)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(snapshot_id, event_key) DO UPDATE SET
                        account_key=excluded.account_key,
                        occurred_at=excluded.occurred_at,
                        observed_at=excluded.observed_at,
                        text=excluded.text,
                        handle=excluded.handle,
                        stable=excluded.stable,
                        profile=excluded.profile,
                        deleted=excluded.deleted
                """, (snapshot_id, row.network, row.event_key, row.account_key, row.kind,
                      row.post_key, row.surface, row.occurred_at, row.observed_at,
                      row.post_created_at, row.text, row.handle, int(row.stable_identity),
                      row.profile, int(row.deleted)))

    def commit_snapshot_reconciliation(self, snapshot_id: str, now: str,
                                         max_post_age_hours: float = 168) -> dict[str, int]:
        now_ts = timestamp(now)
        counts = {"new_people": 0, "new_events": 0, "updated_events": 0,
                  "replays": 0, "stale_posts": 0, "unverified_age": 0, "deactivated_events": 0}
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            snap = self.db.execute(
                "SELECT network, surface, seed, post_key, kind, status FROM audience_snapshots WHERE snapshot_id=?",
                (snapshot_id,)).fetchone()
            if not snap or snap[5] != "active":
                raise ObservationError("snapshot_no_activo")
            network, surface, seed, post_key, kind = snap[0], snap[1], snap[2], snap[3], snap[4]

            staged_rows = self.db.execute("""
                SELECT network, event_key, account_key, kind, post_key, surface,
                       occurred_at, observed_at, post_created_at, text, handle, stable, profile, deleted
                FROM audience_snapshot_staging WHERE snapshot_id=?
            """, (snapshot_id,)).fetchall()

            staged_observations = []
            staged_event_keys = set()
            for r in staged_rows:
                staged_event_keys.add(r[1])
                staged_observations.append(Observation(
                    network=r[0], event_key=r[1], account_key=r[2], kind=r[3],
                    post_key=r[4], surface=r[5], occurred_at=r[6], observed_at=r[7],
                    post_created_at=r[8], text=r[9], handle=r[10], stable_identity=bool(r[11]),
                    profile=r[12], deleted=bool(r[13])
                ))

            # Reutilizar lógica de ingesta para consolidar los eventos del snapshot
            ingest_stats = self._ingest_unlocked(
                staged_observations, network=network, surface=surface, seed=seed,
                next_cursor=None, now=now_ts, max_post_age_hours=max_post_age_hours,
                expected_cursor=_CURSOR_UNSET, is_snapshot_commit=True
            )
            for k, v in ingest_stats.items():
                if k in counts:
                    counts[k] += v

            # RECONCILIACIÓN DE BAJAS:
            # Marcar inactivos (active = 0) los eventos previamente activos para este (network, post_key, kind)
            # que NO estuvieron presentes en el snapshot actual.
            existing_active = self.db.execute("""
                SELECT event_key FROM audience_events
                WHERE network=? AND post_key=? AND kind=? AND active=1
            """, (network, post_key, kind)).fetchall()

            for (ekey,) in existing_active:
                if ekey not in staged_event_keys:
                    self.db.execute(
                        "UPDATE audience_events SET active=0 WHERE network=? AND event_key=?",
                        (network, ekey))
                    counts["deactivated_events"] += 1

            self.db.execute(
                "UPDATE audience_snapshots SET status='committed', completed_at=? WHERE snapshot_id=?",
                (now_ts, snapshot_id))
            self.db.execute("DELETE FROM audience_snapshot_staging WHERE snapshot_id=?", (snapshot_id,))
        return counts

    def abort_snapshot(self, snapshot_id: str) -> None:
        with self.db:
            self.db.execute("UPDATE audience_snapshots SET status='aborted' WHERE snapshot_id=?", (snapshot_id,))
            self.db.execute("DELETE FROM audience_snapshot_staging WHERE snapshot_id=?", (snapshot_id,))

    def ingest(self, rows: Sequence[Observation], *, network: str, surface: str,
               seed: str, next_cursor: str | None, now: str,
               max_post_age_hours: float = 168,
               expected_cursor: str | None | object = _CURSOR_UNSET) -> dict[str, int]:
        """Se guardan páginas completas o ninguna. No filtrar likes antiguos por edad del like."""
        if network not in LANES or not surface or not seed or max_post_age_hours <= 0:
            raise ObservationError("lote_invalido")
        now = timestamp(now)
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            return self._ingest_unlocked(rows, network=network, surface=surface, seed=seed,
                                         next_cursor=next_cursor, now=now,
                                         max_post_age_hours=max_post_age_hours,
                                         expected_cursor=expected_cursor)

    def _ingest_unlocked(self, rows: Sequence[Observation], *, network: str, surface: str,
                         seed: str, next_cursor: str | None, now: str,
                         max_post_age_hours: float = 168,
                         expected_cursor: str | None | object = _CURSOR_UNSET,
                         is_snapshot_commit: bool = False) -> dict[str, int]:
        counts = {"new_people": 0, "new_events": 0, "updated_events": 0,
                  "replays": 0, "stale_posts": 0, "unverified_age": 0}
        # Compare-and-swap: la lectura de páginas ocurre fuera del lock.
        # Si otro recolector avanzó, no escribir datos ni retrasar cursor.
        if (expected_cursor is not _CURSOR_UNSET and
                self.cursor(network, surface, seed) != expected_cursor):
            raise ObservationError("cursor_cambiado_durante_fetch")
        for row in rows:
            if row.network != network or row.surface != surface:
                raise ObservationError("origen_cruzado")
            if row.post_created_at:
                if _age_hours(row.post_created_at, now) > max_post_age_hours:
                    counts["stale_posts"] += 1
                    continue
            else:
                counts["unverified_age"] += 1
            previous = self.db.execute(
                "SELECT observed_at, occurred_at, active, account_key FROM audience_events "
                "WHERE network=? AND event_key=?", (network, row.event_key)).fetchone()
            if previous and previous[3] != row.account_key:
                old = self.db.execute(
                    "SELECT handle, stable, first_seen, last_seen, profile "
                    "FROM audience_accounts WHERE network=? AND account_key=?",
                    (network, previous[3])).fetchone()
                if (not row.stable_identity and old and old[1] and
                        old[0].casefold() == row.handle.casefold()):
                    self.db.execute(
                        "INSERT INTO audience_sightings VALUES(?,?,?,?,?) "
                        "ON CONFLICT(network,event_key,surface,seed) "
                        "DO UPDATE SET observed_at=max(observed_at, excluded.observed_at)",
                        (network, row.event_key, surface, seed, row.observed_at))
                    counts["replays"] += 1
                    continue
                if not (row.stable_identity and old and not old[1] and
                        old[0].casefold() == row.handle.casefold()):
                    raise ObservationError("evento_actor_conflictivo")
                current = self.db.execute(
                    "SELECT first_seen, last_seen FROM audience_accounts "
                    "WHERE network=? AND account_key=?",
                    (network, row.account_key)).fetchone()
                if current:
                    self.db.execute(
                        "UPDATE audience_accounts SET first_seen=min(first_seen, ?), "
                        "last_seen=max(last_seen, ?) "
                        "WHERE network=? AND account_key=?",
                        (old[2], old[3], network, row.account_key))
                else:
                    self.db.execute(
                        "INSERT INTO audience_accounts VALUES(?,?,?,?,?,?,?)",
                        (network, row.account_key, row.handle, 1,
                         row.profile or old[4], old[2], max(old[3], row.observed_at)))
                self.db.execute(
                    "UPDATE audience_events SET account_key=? "
                    "WHERE network=? AND account_key=?",
                    (row.account_key, network, previous[3]))
                self.db.execute(
                    "DELETE FROM audience_accounts WHERE network=? AND account_key=?",
                    (network, previous[3]))
            if previous:
                previous_version = previous[1] or previous[0]
                incoming_version = row.occurred_at or row.observed_at
                was_active = previous[2] == 1
                if previous_version >= incoming_version:
                    # En commit de snapshot, si el evento estaba inactivo (was_active=False)
                    # y reaparece en el snapshot (not row.deleted), debe reactivarse (not replay).
                    if was_active or not is_snapshot_commit:
                        self.db.execute(
                            "INSERT INTO audience_sightings VALUES(?,?,?,?,?) "
                            "ON CONFLICT(network,event_key,surface,seed) "
                            "DO UPDATE SET observed_at=max(observed_at, excluded.observed_at)",
                            (network, row.event_key, surface, seed, row.observed_at))
                        counts["replays"] += 1
                        continue
            account = self.db.execute(
                "SELECT last_seen FROM audience_accounts WHERE network=? AND account_key=?",
                (network, row.account_key)).fetchone()
            if not account and not row.deleted:
                self.db.execute(
                    "INSERT INTO audience_accounts VALUES(?,?,?,?,?,?,?)",
                    (network, row.account_key, row.handle, int(row.stable_identity),
                     row.profile, row.observed_at, row.observed_at))
                counts["new_people"] += 1
            elif account and row.observed_at >= account[0] and not row.deleted:
                self.db.execute(
                    "UPDATE audience_accounts SET handle=COALESCE(NULLIF(?,''),handle), profile=COALESCE(NULLIF(?,''),profile), stable=?, last_seen=? "
                    "WHERE network=? AND account_key=?",
                    (row.handle, row.profile, int(row.stable_identity),
                     row.observed_at, network, row.account_key))
            self.db.execute("""
                INSERT INTO audience_events
                (network, event_key, account_key, kind, post_key, surface,
                 occurred_at, observed_at, post_created_at, text, active)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(network,event_key) DO UPDATE SET
                    account_key=excluded.account_key, kind=excluded.kind,
                    post_key=excluded.post_key, surface=excluded.surface,
                    occurred_at=excluded.occurred_at, observed_at=excluded.observed_at,
                    post_created_at=COALESCE(excluded.post_created_at,audience_events.post_created_at),
                    text=COALESCE(NULLIF(excluded.text,''),audience_events.text),
                    active=excluded.active
            """, (network, row.event_key, row.account_key, row.kind, row.post_key,
                  row.surface, row.occurred_at, row.observed_at, row.post_created_at,
                  row.text, int(not row.deleted)))
            self.db.execute(
                "INSERT INTO audience_sightings VALUES(?,?,?,?,?) "
                "ON CONFLICT(network,event_key,surface,seed) "
                "DO UPDATE SET observed_at=max(observed_at, excluded.observed_at)",
                (network, row.event_key, surface, seed, row.observed_at))
            counts["updated_events" if previous else "new_events"] += 1
        if next_cursor is None:
            self.db.execute(
                "DELETE FROM audience_cursor_history "
                "WHERE network=? AND surface=? AND seed=?",
                (network, surface, seed))
        else:
            self.db.execute(
                "INSERT OR IGNORE INTO audience_cursor_history VALUES(?,?,?,?)",
                (network, surface, seed, next_cursor))
        self.db.execute(
            "INSERT INTO audience_cursors(network,surface,seed,cursor) VALUES(?,?,?,?) "
            "ON CONFLICT(network,surface,seed) DO UPDATE SET cursor=excluded.cursor",
            (network, surface, seed, next_cursor))
        return counts

    def ranked(self, network: str, *, limit: int = 50, require_verified_age: bool = True,
               now: str | None = None, max_post_age_hours: float = 168) -> list[dict]:
        if network not in LANES or not 1 <= limit <= 10000 or max_post_age_hours <= 0:
            raise ObservationError("consulta_invalida")
        now = timestamp(now or datetime.now(timezone.utc))
        records = self.db.execute("""
            SELECT a.account_key, a.handle, a.stable, a.profile, e.kind, e.post_key,
                   e.surface, e.text, e.post_created_at, e.event_key
            FROM audience_accounts a JOIN audience_events e
              ON e.network=a.network AND e.account_key=a.account_key
            WHERE a.network=? AND e.active=1
        """, (network,)).fetchall()
        sights: dict[str, set[str]] = {}
        for event_key, surface in self.db.execute(
            "SELECT event_key,surface FROM audience_sightings WHERE network=?",
            (network,)):
            sights.setdefault(event_key, set()).add(surface)
        people: dict[str, dict] = {}
        for key, handle, stable, profile, kind, post, surface, text, age, event_key in records:
            if require_verified_age and (age is None or _age_hours(age, now) > max_post_age_hours):
                continue
            data = people.setdefault(key, {"network": network, "lane": LANES[network],
                "account_key": key, "handle": handle, "stable_identity": bool(stable),
                "score": 0.0, "signals": 0, "posts": set(), "surfaces": set(),
                "scoring_surfaces": set()})
            data["signals"] += 1
            data["score"] += KINDS[kind]
            data["posts"].add(post)
            data["surfaces"].update(sights.get(event_key, {surface}))
            data["scoring_surfaces"].add(surface)
            if NICHE.search(profile + " " + text):
                data["score"] += 2.0
        for rec in people.values():
            rec["score"] += min(6, max(0, len(rec["posts"]) - 1) * 2)
            rec["score"] += min(4, max(0, len(rec["scoring_surfaces"]) - 1) * 2)
            del rec["scoring_surfaces"]
            rec["posts"] = len(rec["posts"])
            rec["surfaces"] = len(rec["surfaces"])
        return sorted(people.values(), key=lambda r: (-r["score"], -r["posts"],
                        r["account_key"]))[:limit]


def collect_pages(store: AudienceStore, *, network: str, surface: str, seed: str,
                  fetch_page: Callable[[str | None], Mapping],
                  observed_at: str, max_pages: int = 10,
                  max_post_age_hours: float = 168,
                  use_snapshot_reconciliation: bool = False) -> dict:
    """Paginador genérico read-only con soporte opcional de reconciliación por snapshot.

    fetch_page -> {items, next_cursor, kind, post_key, ...}.
    Si use_snapshot_reconciliation=True, aísla las observaciones en un snapshot staging.
    Al completarse todas las páginas y confirmarse coverage_complete=True,
    ejecuta el commit de reconciliación que marca inactivos los ausentes.
    """
    if not 1 <= max_pages <= 1000:
        raise ObservationError("max_pages_invalido")
    cursor = store.cursor(network, surface, seed)
    visited = {cursor} if cursor is not None else set()
    totals = {"new_people": 0, "new_events": 0, "updated_events": 0,
              "replays": 0, "stale_posts": 0, "unverified_age": 0, "deactivated_events": 0}
    done = False
    snapshot_id = None

    try:
        for page_num in range(max_pages):
            page = fetch_page(cursor)
            if not isinstance(page, Mapping):
                raise ObservationError("pagina_invalida")
            items = page.get("items")
            if not isinstance(items, (list, tuple)):
                raise ObservationError("items_invalidos")
            nxt = page.get("next_cursor")
            if nxt is not None and (not isinstance(nxt, str) or not nxt.strip()
                                    or nxt == cursor or nxt in visited or
                                    store.seen_cursor(network, surface, seed, nxt)):
                raise ObservationError("cursor_ciclico")

            post_key = str(page.get("post_key") or "")
            kind = str(page.get("kind") or "")

            normalized = [
                normalize(network, kind, item, surface=surface,
                          post_key=post_key, observed_at=observed_at,
                          post_created_at=page.get("post_created_at"))
                for item in items
            ]

            if use_snapshot_reconciliation:
                if snapshot_id is None:
                    snapshot_id = store.start_snapshot(network, surface, seed, post_key, kind, observed_at)
                store.stage_snapshot_observations(snapshot_id, normalized)
            else:
                stats = store.ingest(normalized, network=network, surface=surface, seed=seed,
                                     next_cursor=nxt, now=observed_at,
                                     max_post_age_hours=max_post_age_hours,
                                     expected_cursor=cursor)
                for field in stats:
                    if field in totals:
                        totals[field] += stats[field]

            cursor = nxt
            if nxt is None:
                done = page.get("coverage_complete", True) is True
                break
            visited.add(nxt)

        if use_snapshot_reconciliation and snapshot_id is not None:
            if done:
                recon_stats = store.commit_snapshot_reconciliation(snapshot_id, now=observed_at,
                                                                   max_post_age_hours=max_post_age_hours)
                for field in recon_stats:
                    if field in totals:
                        totals[field] += recon_stats[field]
                # Actualizar cursor únicamente tras el commit exitoso del snapshot
                with store.db:
                    if cursor is None:
                        store.db.execute(
                            "DELETE FROM audience_cursor_history WHERE network=? AND surface=? AND seed=?",
                            (network, surface, seed))
                    else:
                        store.db.execute(
                            "INSERT OR IGNORE INTO audience_cursor_history VALUES(?,?,?,?)",
                            (network, surface, seed, cursor))
                    store.db.execute(
                        "INSERT INTO audience_cursors(network,surface,seed,cursor) VALUES(?,?,?,?) "
                        "ON CONFLICT(network,surface,seed) DO UPDATE SET cursor=excluded.cursor",
                        (network, surface, seed, cursor))
            else:
                # Si el snapshot no terminó con coverage_complete=True, descartar staging sin avanzar cursor
                store.abort_snapshot(snapshot_id)

    except Exception:
        if use_snapshot_reconciliation and snapshot_id is not None:
            store.abort_snapshot(snapshot_id)
        raise

    return {"network": network, "lane": LANES[network],
            "pages": page_num + 1, "complete": done, "next_cursor": cursor, **totals}
