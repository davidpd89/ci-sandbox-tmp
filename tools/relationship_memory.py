"""Historial de no reciprocidad multired, sin acciones externas ni E/S implícita.

Los eventos CSV son evidencia, no instrucciones de follow/unfollow. La proyección
pura sirve a discovery; SQLite es una materialización optativa y reversible.
"""
from __future__ import annotations

import csv
import contextlib
import datetime as dt
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

OK = frozenset({"confirmado", "publicado"})
NETWORKS = frozenset({"x", "threads", "facebook", "pinterest", "reddit", "bluesky", "mastodon", "tiktok", "instagram"})


def norm(value):
    """Conservar el dominio del handle federado; nunca fusionar redes."""
    value = str(value or "").strip().lstrip("@").strip().casefold()
    return "" if not value or value.startswith(("https:", "http:")) else value


@dataclass(frozen=True)
class Event:
    network: str
    account: str
    date: dt.date
    kind: str  # follow | nonreciprocal | permanent | reciprocated
    reason: str
    evidence: str

    def __post_init__(self):
        object.__setattr__(self, "account", norm(self.account))
        if self.network not in NETWORKS or not self.account:
            raise ValueError("red o cuenta inválida")
        if self.kind not in {"follow", "nonreciprocal", "permanent", "reciprocated"}:
            raise ValueError("evento desconocido")
        if not isinstance(self.date, dt.date) or isinstance(self.date, dt.datetime):
            raise ValueError("fecha inválida")


@dataclass(frozen=True)
class Policy:
    initial_days: int = 21
    multiplier: int = 2
    cap_days: int = 84
    max_failures: int = 3
    ban_days: int | None = None  # None conserva la exclusión de 3 intentos
    lookback_days: int | None = None
    penalty_per_failure: float = 1.5

    def __post_init__(self):
        if (self.initial_days < 0 or self.multiplier < 1 or
                self.cap_days < self.initial_days or self.max_failures < 1 or
                (self.ban_days is not None and self.ban_days < 0) or
                (self.lookback_days is not None and self.lookback_days < 0) or
                self.penalty_per_failure < 0):
            raise ValueError("política inválida")


def events_from_rows(rows, network, *, source="registro.csv"):
    """Extrae solo operaciones verificadas; conserva número de fila como evidencia.

    No supone fallo por ausencia de follower: exige un unfollow por
    no reciprocidad confirmado. Follows fallidos no cuentan.
    """
    if network not in NETWORKS:
        raise ValueError("red desconocida")
    events = []
    for line, row in enumerate(rows, start=2):
        status = str(row.get("resultado") or "").strip().casefold()
        kind = str(row.get("tipo") or "").strip().casefold()
        if status not in OK and not (status == "saltado_ya_no_seguido" and kind in {"block", "unfollow"}):
            continue
        account = norm(row.get("cuenta"))
        if not account:
            continue
        try:
            date = dt.date.fromisoformat(str(row.get("fecha") or "")[:10])
        except ValueError:
            if kind in {"block", "unfollow"} and "no devuelve" not in str(row.get("notas") or "").casefold():
                date = dt.date.min  # exclusión permanente heredada sin fecha
            else:
                continue
        notes = str(row.get("notas") or "").casefold()
        if "follow" in kind.split("+"):
            event_kind, reason = "follow", "outbound_confirmed"
        elif kind == "unfollow" and "no devuelve" in notes and status in OK:
            event_kind, reason = "nonreciprocal", "no_followback"
        elif kind == "unfollow" and "no devuelve" in notes:
            continue  # sin confirmación no hay fracaso ni exclusión permanente
        elif kind in {"unfollow", "block"}:
            event_kind, reason = "permanent", "block" if kind == "block" else "other_unfollow"
        elif kind in {"reciprocated", "followback_verified"}:
            event_kind, reason = "reciprocated", "inbound_confirmed"
        else:
            continue
        events.append(Event(network, account, date, event_kind, reason, f"{source}:{line}"))
    return events


def decision(events, network, account, *, today=None, policy=None):
    """Proyección estable en fecha y orden original, con causa y siguiente revisión."""
    today = today or dt.date.today()
    policy = policy or Policy()
    account = norm(account)
    relevant = [e for e in events if e.network == network and e.account == account and e.date <= today]
    if policy.lookback_days is not None:
        start = today - dt.timedelta(days=policy.lookback_days)
        relevant = [e for e in relevant if e.date >= start or e.kind == "permanent"]
    relevant.sort(key=lambda e: e.date)
    failures = 0
    active = False
    seen_follow = False
    orphan_dates = set()
    last_failure = None
    last_evidence = None
    permanent = False
    for event in relevant:
        if event.kind == "permanent":
            permanent = True
            last_evidence = event.evidence
        elif event.kind == "reciprocated":
            failures = 0
            last_failure = None
            active = False
            seen_follow = False
            orphan_dates.clear()
        elif event.kind == "follow":
            active = True
            seen_follow = True
        elif event.kind == "nonreciprocal":
            # Los CSV anteriores registraban un unfollow sin el follow de origen.
            # Distintos dias son ciclos historicos; filas duplicadas del mismo
            # dia no deben crear nuevos fracasos.
            if active or (not seen_follow and event.date not in orphan_dates):
                failures += 1
                if not active:
                    orphan_dates.add(event.date)
                active = False
                last_failure = event.date
                last_evidence = event.evidence
    status = "eligible"
    retry_on = None
    if permanent:
        status = "permanent"
    elif failures >= policy.max_failures:
        if policy.ban_days is None:
            status = "exhausted"
        elif last_failure is not None:
            retry_on = last_failure + dt.timedelta(days=policy.ban_days)
            if today < retry_on:
                status = "exhausted"
    elif last_failure is not None:
        length = min(policy.cap_days, policy.initial_days * policy.multiplier ** (failures - 1))
        retry_on = last_failure + dt.timedelta(days=length)
        if today < retry_on:
            status = "cooldown"
    # Desprioriza sólo nuevos follows, no comentarios u otras acciones.
    return {"status": status, "allowed": status == "eligible", "failures": failures,
            "retry_on": retry_on, "rank_delta": -policy.penalty_per_failure * failures,
            "evidence": last_evidence}


def decisions_from_rows(rows, network, *, today=None, policy=None):
    events = events_from_rows(rows, network)
    # Agrupar primero evita recorrer todos los eventos por cada cuenta:
    # los registros largos pasan de O(cuentas * eventos) a O(eventos).
    by_account = {}
    for event in events:
        by_account.setdefault(event.account, []).append(event)
    return {account: decision(account_events, network, account,
                              today=today, policy=policy)
            for account, account_events in by_account.items()}


class RelationshipMemory:
    """Materialización SQLite explícita. No abre registros reales por defecto."""

    def __init__(self, path):
        self.path = os.fspath(path)

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def initialize(self):
        with contextlib.closing(self._connect()) as conn, conn:
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError("versión de memoria desconocida")
            conn.execute("""CREATE TABLE IF NOT EXISTS relation_events (
                network TEXT NOT NULL, source TEXT NOT NULL, source_line INTEGER NOT NULL,
                account TEXT NOT NULL, date TEXT NOT NULL, kind TEXT NOT NULL,
                reason TEXT NOT NULL, evidence TEXT NOT NULL,
                PRIMARY KEY(network, source, source_line))""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_relation_lookup ON relation_events(network, account, date)")
            conn.execute("PRAGMA user_version=1")

    def replace_source(self, network, source, events):
        """Migración idempotente y atómica: sustituye sólo un origen."""
        if network not in NETWORKS or not source:
            raise ValueError("red u origen inválidos")
        events = list(events)
        if any(e.network != network for e in events):
            raise ValueError("se mezclaron redes")
        self.initialize()
        with contextlib.closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM relation_events WHERE network=? AND source=?", (network, source))
            conn.executemany("INSERT INTO relation_events VALUES (?,?,?,?,?,?,?,?)",
                             [(e.network, source, i, e.account, e.date.isoformat(), e.kind,
                               e.reason, e.evidence) for i, e in enumerate(events)])
        return len(events)

    def import_csv(self, network, csv_path, *, source=None):
        source = source or Path(csv_path).name
        with open(csv_path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            required = {"fecha", "cuenta", "tipo", "notas", "resultado"}
            if not required.issubset(set(reader.fieldnames or ())):
                raise ValueError("registro CSV incompleto; no se sustituye la memoria")
            rows = list(reader)
        events = events_from_rows(rows, network, source=source)
        return self.replace_source(network, source, events)

    def events(self, network, account=None):
        if network not in NETWORKS:
            raise ValueError("red desconocida")
        self.initialize()
        query = "SELECT network, account, date, kind, reason, evidence FROM relation_events WHERE network=?"
        params = [network]
        if account is not None:
            query += " AND account=?"
            params.append(norm(account))
        query += " ORDER BY date, source, source_line"
        with contextlib.closing(self._connect()) as conn:
            return [Event(net, acct, dt.date.fromisoformat(date), kind, reason, evidence)
                    for net, acct, date, kind, reason, evidence in conn.execute(query, params)]

    def lookup(self, network, account, *, today=None, policy=None):
        return decision(self.events(network, account), network, account, today=today, policy=policy)
