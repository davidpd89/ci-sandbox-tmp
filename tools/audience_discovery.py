"""Descubrimiento de audiencias por interacciones: núcleo offline multired.

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
    event_id = str(raw.get("event_id") or raw.get("comment_id") or raw.get("uri") or "").strip()
    # Los endpoints de likers/reposters a veces solo devuelven cuentas.
    # La combinación estable de post, tipo y actor identifica ese edge.
    if not event_id and kind in ("like", "repost"):
        event_id = account_key
    if not event_id:
        raise ObservationError("evento_sin_id")
    event_key = "|".join((surface, post_key, kind, event_id))
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
            CREATE INDEX IF NOT EXISTS idx_audience_events_account
                ON audience_events(network, account_key, active);
            CREATE TABLE IF NOT EXISTS audience_cursors (
                network TEXT NOT NULL, surface TEXT NOT NULL, seed TEXT NOT NULL,
                cursor TEXT, PRIMARY KEY(network, surface, seed));
        """)

    def close(self) -> None:
        self.db.close()

    def cursor(self, network: str, surface: str, seed: str) -> str | None:
        row = self.db.execute(
            "SELECT cursor FROM audience_cursors WHERE network=? AND surface=? AND seed=?",
            (network, surface, seed)).fetchone()
        return row[0] if row else None

    def ingest(self, rows: Sequence[Observation], *, network: str, surface: str,
               seed: str, next_cursor: str | None, now: str,
               max_post_age_hours: float = 168) -> dict[str, int]:
        """Se guardan páginas completas o ninguna. No filtrar likes antiguos por edad del like."""
        if network not in LANES or not surface or not seed or max_post_age_hours <= 0:
            raise ObservationError("lote_invalido")
        now = timestamp(now)
        counts = {"new_people": 0, "new_events": 0, "updated_events": 0,
                  "replays": 0, "stale_posts": 0, "unverified_age": 0}
        with self.db:
            # BEGIN IMMEDIATE serializa escritores de las tres colas sin bloquear
            # lecturas SQLite; evita dos inserciones concurrentes de una cuenta.
            self.db.execute("BEGIN IMMEDIATE")
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
                if previous:
                    # En eventos de flujo con tiempo de suceso, ese tiempo ordena
                    # create/delete aunque un replay antiguo se observe más tarde.
                    # En listados sin tiempo de suceso manda la hora de lectura.
                    previous_version = previous[1] or previous[0]
                    incoming_version = row.occurred_at or row.observed_at
                    if previous_version >= incoming_version:
                        counts["replays"] += 1
                        continue
                # Una observación posterior puede retirar un like/repost. No lo resucita un replay.
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
                        "UPDATE audience_accounts SET handle=?, profile=?, stable=?, last_seen=? "
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
                        post_created_at=excluded.post_created_at, text=excluded.text,
                        active=excluded.active
                """, (network, row.event_key, row.account_key, row.kind, row.post_key,
                      row.surface, row.occurred_at, row.observed_at, row.post_created_at,
                      row.text, int(not row.deleted)))
                counts["updated_events" if previous else "new_events"] += 1
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
                   e.surface, e.text, e.post_created_at
            FROM audience_accounts a JOIN audience_events e
              ON e.network=a.network AND e.account_key=a.account_key
            WHERE a.network=? AND e.active=1
        """, (network,)).fetchall()
        people: dict[str, dict] = {}
        for key, handle, stable, profile, kind, post, surface, text, age in records:
            if require_verified_age and (age is None or _age_hours(age, now) > max_post_age_hours):
                continue
            data = people.setdefault(key, {"network": network, "lane": LANES[network],
                "account_key": key, "handle": handle, "stable_identity": bool(stable),
                "score": 0.0, "signals": 0, "posts": set(), "surfaces": set()})
            data["signals"] += 1
            data["score"] += KINDS[kind]
            data["posts"].add(post)
            data["surfaces"].add(surface)
            if NICHE.search(profile + " " + text):
                data["score"] += 2.0
        for rec in people.values():
            rec["score"] += min(6, max(0, len(rec["posts"]) - 1) * 2)
            rec["score"] += min(4, max(0, len(rec["surfaces"]) - 1) * 2)
            rec["posts"] = len(rec["posts"])
            rec["surfaces"] = len(rec["surfaces"])
        return sorted(people.values(), key=lambda r: (-r["score"], -r["posts"],
                        r["account_key"]))[:limit]


def collect_pages(store: AudienceStore, *, network: str, surface: str, seed: str,
                  fetch_page: Callable[[str | None], Mapping],
                  observed_at: str, max_pages: int = 10,
                  max_post_age_hours: float = 168) -> dict:
    """Paginador genérico read-only: fetch_page -> {items,next_cursor,kind,post_key,...}.

    La función llamadora aporta un fetcher de SOLO LECTURA (o un fixture).
    Cualquier error en una página mantiene el cursor de la última página válida.
    """
    if not 1 <= max_pages <= 1000:
        raise ObservationError("max_pages_invalido")
    cursor = store.cursor(network, surface, seed)
    visited = {cursor} if cursor is not None else set()
    totals = {"new_people": 0, "new_events": 0, "updated_events": 0,
              "replays": 0, "stale_posts": 0, "unverified_age": 0}
    done = False
    for page_num in range(max_pages):
        page = fetch_page(cursor)
        if not isinstance(page, Mapping):
            raise ObservationError("pagina_invalida")
        items = page.get("items")
        if not isinstance(items, (list, tuple)):
            raise ObservationError("items_invalidos")
        nxt = page.get("next_cursor")
        if nxt is not None and (not isinstance(nxt, str) or not nxt.strip()
                                or nxt == cursor or nxt in visited):
            raise ObservationError("cursor_ciclico")
        normalized = [
            normalize(network, str(page.get("kind") or ""), item, surface=surface,
                      post_key=str(page.get("post_key") or ""), observed_at=observed_at,
                      post_created_at=page.get("post_created_at"))
            for item in items
        ]
        stats = store.ingest(normalized, network=network, surface=surface, seed=seed,
                             next_cursor=nxt, now=observed_at,
                             max_post_age_hours=max_post_age_hours)
        for field in totals:
            totals[field] += stats[field]
        cursor = nxt
        if nxt is None:
            done = True
            break
        visited.add(nxt)
    return {"network": network, "lane": LANES[network],
            "pages": page_num + 1, "complete": done, "next_cursor": cursor, **totals}
