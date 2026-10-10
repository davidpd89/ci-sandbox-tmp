"""Opt-in, offline-safe exploration planner. No network calls or action execution.

One source = (network, surface, normalized query/seed). Observations here concern
unique discovered IDs, never estimated follow-backs. An unfinished scan remains
unknown. Existing scanners retain their selection until explicitly integrated.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import os
import secrets
import sqlite3
import unicodedata


@dataclass(frozen=True)
class Claim:
    key: str
    token: str


def _ts(now):
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("now must be a timezone-aware datetime")
    value = now.timestamp()
    if not math.isfinite(value):
        raise ValueError("invalid clock")
    return value


def _name(value):
    if not isinstance(value, str):
        raise ValueError("network, surface and keys must be strings")
    value = unicodedata.normalize("NFC", " ".join(value.split()))
    if not value or len(value) > 512 or "\x00" in value:
        raise ValueError("empty, oversized or invalid source identifier")
    return value


@contextmanager
def _connect(path):
    if not isinstance(path, (str, os.PathLike)):
        raise ValueError("explicit state path required")
    # Do not create unexpected directories. Caller owns state placement.
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout = 5000")
        db.execute("""CREATE TABLE IF NOT EXISTS observations (
            network TEXT NOT NULL, surface TEXT NOT NULL, source TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            unique_total INTEGER NOT NULL DEFAULT 0,
            elapsed_total_ms INTEGER NOT NULL DEFAULT 0,
            last_ok REAL,
            eligible_after REAL NOT NULL DEFAULT 0,
            lease_token TEXT,
            lease_until REAL NOT NULL DEFAULT 0,
            PRIMARY KEY(network,surface,source))""")
        db.execute("""CREATE TABLE IF NOT EXISTS network_gates (
            network TEXT PRIMARY KEY, until_ts REAL NOT NULL DEFAULT 0,
            human_review INTEGER NOT NULL DEFAULT 0)""")
        db.execute("""CREATE TABLE IF NOT EXISTS selection_turn (
            network TEXT NOT NULL, surface TEXT NOT NULL, turn INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(network,surface))""")
        with db:
            yield db
    finally:
        db.close()


def claim_sources(path, network, surface, sources, limit, *, now=None,
                  cooldown_seconds=3600, lease_seconds=900, exploration_slots=1):
    """Atomically select sources, avoiding two workers claiming the same key.

    A reservation blocks automatic retries for at least the cooldown, including
    if a worker crashes. Empty eligibility returns [] (no bypass/fallback).
    """
    network, surface = _name(network).casefold(), _name(surface).casefold()
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
        raise ValueError("limit must be a nonnegative integer")
    if not isinstance(exploration_slots, int) or not 0 <= exploration_slots <= limit:
        raise ValueError("exploration_slots invalid")
    if not (isinstance(cooldown_seconds, (int, float)) and
            isinstance(lease_seconds, (int, float)) and
            math.isfinite(cooldown_seconds) and math.isfinite(lease_seconds) and
            cooldown_seconds >= 0 and lease_seconds > 0):
        raise ValueError("invalid cooldown or lease")
    current = _ts(now)
    if isinstance(sources, (str, bytes)) or sources is None:
        raise ValueError("sources must be an iterable of source strings")
    unique = {}
    for source in sources:
        original = _name(source)
        normalized = original.casefold()
        unique.setdefault(normalized, original)
    if limit == 0 or not unique:
        return []
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        gate = db.execute("SELECT until_ts, human_review FROM network_gates WHERE network=?", (network,)).fetchone()
        if gate and (gate[1] or gate[0] > current):
            return []
        available = []
        for norm, original in unique.items():
            row = db.execute("""SELECT attempts, unique_total, elapsed_total_ms,
                last_ok, eligible_after, lease_until FROM observations
                WHERE network=? AND surface=? AND source=?""", (network, surface, norm)).fetchone()
            if row and (row[4] > current or row[5] > current):
                continue
            if row is None or row[0] == 0:
                available.append((True, 0.0, norm, original))
            else:
                attempts, found, elapsed, last_ok, _, _ = row
                yield_per_call = found / attempts
                mean_seconds = elapsed / max(1, attempts) / 1000
                freshness = min(max(0.0, (current - (last_ok or current)) / 3600), 72) / 72
                utility = yield_per_call / (1 + mean_seconds / 20) + freshness * 0.4
                available.append((False, utility, norm, original))
        unexplored = sorted((r for r in available if r[0]), key=lambda r: r[2])
        observed = sorted((r for r in available if not r[0]), key=lambda r: (-r[1], r[2]))
        # One exploratory slot is a default, not an assumed optimal 80/20 mix.
        turn_row = db.execute("SELECT turn FROM selection_turn WHERE network=? AND surface=?",
                              (network, surface)).fetchone()
        turn = turn_row[0] if turn_row else 0
        if limit == 1 and unexplored and observed:
            chosen = [observed[0] if turn % 2 else unexplored[0]]
        else:
            chosen = unexplored[:exploration_slots] + observed[:max(0, limit - min(exploration_slots, len(unexplored)))]
        used = {r[2] for r in chosen}
        for row in observed + unexplored:
            if len(chosen) >= limit:
                break
            if row[2] not in used:
                chosen.append(row)
                used.add(row[2])
        if chosen:
            db.execute("""INSERT INTO selection_turn(network,surface,turn) VALUES(?,?,1)
                ON CONFLICT(network,surface) DO UPDATE SET turn=turn+1""", (network, surface))
        result = []
        for _, _, norm, original in chosen:
            token = secrets.token_hex(16)
            db.execute("""INSERT INTO observations(network,surface,source,eligible_after,lease_token,lease_until)
                VALUES(?,?,?,?,?,?) ON CONFLICT(network,surface,source) DO UPDATE SET
                eligible_after=excluded.eligible_after, lease_token=excluded.lease_token,
                lease_until=excluded.lease_until""",
                (network, surface, norm, current + cooldown_seconds, token, current + lease_seconds))
            result.append(Claim(original, token))
        return result


def finish_source(path, network, surface, claim, *, candidate_ids=None,
                  elapsed_ms=None, status="ok", retry_after_seconds=0, now=None):
    """Acknowledge a matching lease; partial/error is not a successful scan.

    Returns False on a stale token. A 429 applies network-wide, not per query.
    A captcha/anti-bot warning requires an explicit human reset.
    """
    network, surface = _name(network).casefold(), _name(surface).casefold()
    if not isinstance(claim, Claim) or not claim.token:
        raise ValueError("valid claim required")
    if status not in ("ok", "error", "partial", "rate_limited", "captcha"):
        raise ValueError("unknown scan status")
    if status == "ok" and (not isinstance(elapsed_ms, int) or isinstance(elapsed_ms, bool) or elapsed_ms < 0):
        raise ValueError("successful scans require measured nonnegative elapsed_ms")
    if not isinstance(retry_after_seconds, (int, float)) or not math.isfinite(retry_after_seconds) or retry_after_seconds < 0:
        raise ValueError("invalid retry_after_seconds")
    if status == "rate_limited" and retry_after_seconds == 0:
        # Unknown reset deadline is not permission to try a different source.
        status = "captcha"  # manual review gate, not an inferred expiry
    count = 0
    if status == "ok":
        if candidate_ids is None:
            raise ValueError("successful scans require observed candidate IDs; use [] for zero")
        ids = tuple(candidate_ids)
        if any(not isinstance(v, str) or not v.strip() for v in ids):
            raise ValueError("candidate_ids must be nonempty stable strings")
        count = len(set(ids))
    current = _ts(now)
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        norm = _name(claim.key).casefold()
        row = db.execute("""SELECT lease_token FROM observations
            WHERE network=? AND surface=? AND source=?""", (network, surface, norm)).fetchone()
        if not row or row[0] != claim.token:
            return False
        if status == "ok":
            db.execute("""UPDATE observations SET attempts=attempts+1,
                unique_total=unique_total+?, elapsed_total_ms=elapsed_total_ms+?,
                last_ok=?, lease_token=NULL, lease_until=0
                WHERE network=? AND surface=? AND source=?""",
                (count, elapsed_ms, current, network, surface, norm))
        else:
            db.execute("""UPDATE observations SET lease_token=NULL, lease_until=0,
                eligible_after=max(eligible_after, ?) WHERE network=? AND surface=? AND source=?""",
                (current + retry_after_seconds, network, surface, norm))
            if status in ("rate_limited", "captcha"):
                db.execute("""INSERT INTO network_gates(network,until_ts,human_review)
                    VALUES(?,?,?) ON CONFLICT(network) DO UPDATE SET
                    until_ts=max(until_ts, excluded.until_ts),
                    human_review=max(human_review, excluded.human_review)""",
                    (network, current + retry_after_seconds, int(status == "captcha")))
        return True


def clear_human_gate(path, network):
    """Supervised reset only; never called automatically by the planner."""
    network = _name(network).casefold()
    with _connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM network_gates WHERE network=? AND human_review=1", (network,))
