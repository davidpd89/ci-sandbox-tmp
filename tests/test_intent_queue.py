"""Regresiones offline: tres colas, nueve redes, crash y fences Windows/Linux."""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile
import threading

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from intent_queue import (CHANNELS, NETWORKS, IdempotencyConflict,
                          IntentQueue, InvalidTransition)

class Clock:
    now = 1000.0
    def __call__(self):
        return self.now

@pytest.fixture
def env(tmp_path):
    clock = Clock()
    return IntentQueue(str(tmp_path / "intent.sqlite3"), clock=clock,
                       jitter=lambda: 0.5), clock

def put(q, network="bluesky", channel="API", intent_key="task-1", **kwargs):
    return q.enqueue(network=network, channel=channel, intent_key=intent_key,
                     kind="reply", target=kwargs.pop("target", "post/42"),
                     payload={"text": "Prueba sintética"}, **kwargs)

def test_nine_networks_three_independent_channels(env):
    q, _ = env
    names = sorted(NETWORKS)
    assert len(names) == 9
    channels = sorted(CHANNELS)
    for i, name in enumerate(names):
        put(q, network=name, channel=channels[i % 3], intent_key="logical")
    for channel in channels:
        tickets = []
        while t := q.claim(channel, "worker-" + channel):
            assert t.channel == channel
            tickets.append(t)
        assert len(tickets) == 3
        for t in tickets:
            q.mark_dispatched(t)
            q.confirm(t, "remote-id/fixture")
    for n in names:
        with pytest.raises(IdempotencyConflict):
            put(q, network=n, channel="WEB", intent_key="logical", priority=2)

def test_enqueue_idempotent_and_conflict_immutable(env):
    q, _ = env
    ident = put(q)
    assert put(q) == ident
    assert [x[0] for x in q.events(ident)] == ["enqueued"]
    with pytest.raises(IdempotencyConflict):
        put(q, target="other")
    with pytest.raises(ValueError):
        put(q, network="not_a_network")
    with pytest.raises(ValueError):
        put(q, max_attempts=0)

def test_double_process_claim_fence(env):
    q, _ = env
    ident = put(q)
    results = []
    barrier = threading.Barrier(10)
    def worker(i):
        other = IntentQueue(q.path, clock=q.clock, jitter=lambda: 0.5)
        barrier.wait()
        results.append(other.claim("API", str(i)))
    workers = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in workers: t.start()
    for t in workers: t.join(timeout=15)
    assert not any(t.is_alive() for t in workers)
    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    q.mark_dispatched(winners[0])
    q.confirm(winners[0], "remote-confirmed")
    assert q.status(ident)["status"] == "confirmed"

def test_claim_expired_before_dispatch_safe_requeue_stale_fence(env):
    q, clock = env
    ident = put(q)
    first = q.claim("API", "worker-A", lease_seconds=10)
    clock.now += 11
    second = q.claim("API", "worker-B", lease_seconds=10)
    assert second.id == ident and first.fence != second.fence
    with pytest.raises(InvalidTransition):
        q.mark_dispatched(first)
    with pytest.raises(InvalidTransition):
        q.no_effect(first, "did-not-send")
    q.mark_dispatched(second)
    q.confirm(second, "remote/confirmed")

def test_dispatch_boundary_crash_requires_reconciliation(env):
    q, clock = env
    ident = put(q)
    ticket = q.claim("API", "worker-A", lease_seconds=10)
    q.mark_dispatched(ticket)
    clock.now += 11
    assert q.claim("API", "worker-B") is None
    assert q.status(ident)["status"] == "uncertain"
    assert q.reconcile(ident, "unknown", "remote-inconclusive") == "uncertain"
    assert q.claim("API", "worker-B") is None
    assert q.reconcile(ident, "confirmed", "remote-post-42") == "confirmed"
    assert q.status(ident)["status"] == "confirmed"

def test_ack_after_lease_expiry_remains_valid_with_same_fence(env):
    q, clock = env
    ident = put(q)
    t = q.claim("API", "A", lease_seconds=10)
    q.mark_dispatched(t)
    clock.now += 11
    q.recover("API")
    q.confirm(t, "remote-ack")
    assert q.status(ident)["status"] == "confirmed"
    with pytest.raises(InvalidTransition):
        q.confirm(t, "duplicate")

def test_verified_not_applied_retry_and_dead_letters(env):
    q, clock = env
    ident = put(q, max_attempts=2)
    first = q.claim("API", "A")
    q.mark_dispatched(first)
    clock.now += 200
    q.recover("API")
    assert q.reconcile(ident, "not_applied", "remote-search-negative",
                       base_delay=10, max_delay=10) == "queued"
    assert q.claim("API", "B") is None
    clock.now += 10
    second = q.claim("API", "B")
    assert second.attempts == 2
    assert q.no_effect(second, "not_dispatched", base_delay=10,
                       max_delay=10) == "dead"
    assert q.claim("API", "C") is None

def test_priority_delayed_and_target_expiration(env):
    q, clock = env
    old = put(q, intent_key="old", expires_at=1001, priority=999)
    put(q, intent_key="later", due=1010, priority=100)
    active = put(q, intent_key="now", priority=1)
    clock.now = 1002
    t = q.claim("API", "worker")
    assert t.id == active
    assert q.status(old)["status"] == "dead"
    assert q.claim("API", "worker") is None
    clock.now = 1011
    assert q.claim("API", "worker").id != old

def test_failed_transaction_does_not_mutate_idempotency(env):
    q, _ = env
    ident = put(q)
    with pytest.raises(IdempotencyConflict):
        put(q, priority=9)
    assert q.status(ident)["priority"] == 0
    assert q.events(ident) == [("enqueued", "")]

def test_jitter_bounded_and_retry_until_max(env):
    q, clock = env
    ident = put(q)
    t = q.claim("API", "A")
    q.no_effect(t, "not-dispatched", base_delay=100, max_delay=100)
    assert q.status(ident)["due"] == 1100.0
    assert q.claim("API", "B") is None
    clock.now = 1100
    t = q.claim("API", "B")
    q.mark_dispatched(t)
    q.no_effect(t, "definitive-remote-rejection", base_delay=10, max_delay=10)
    assert q.status(ident)["status"] == "queued"

def test_recover_is_idempotent_and_channel_isolated(env):
    q, clock = env
    a = put(q, channel="WEB", network="x", intent_key="web")
    b = put(q, channel="MOBILE", network="tiktok", intent_key="mobile")
    q.claim("WEB", "W", lease_seconds=10)
    q.claim("MOBILE", "M", lease_seconds=10)
    clock.now += 11
    assert q.recover("WEB")["requeued"] == 1
    assert q.status(a)["status"] == "queued"
    assert q.status(b)["status"] == "claimed"
    assert q.recover("WEB")["requeued"] == 0
    assert q.recover("MOBILE")["requeued"] == 1

def test_crash_in_new_python_process(tmp_path):
    path = str(tmp_path / "crash.sqlite")
    clock = Clock()
    q = IntentQueue(path, clock=clock)
    ids = [put(q, intent_key="crash-before"),
           put(q, intent_key="crash-after")]
    source = str(pathlib.Path(__file__).resolve().parents[1] / "tools")
    # Subprocesos reales, os._exit salta finally; no networking.
    for after in (False, True):
        script = ("import os,sys;sys.path.insert(0,sys.argv[1]);"
                  "from intent_queue import IntentQueue;"
                  "q=IntentQueue(sys.argv[2],clock=lambda:1000.0);"
                  "t=q.claim('API','crasher',lease_seconds=10);"
                  + ("q.mark_dispatched(t);" if after else "")
                  + "os._exit(0)")
        proc = subprocess.run([sys.executable, "-c", script, source, path],
                              capture_output=True, timeout=15, check=True)
        assert proc.returncode == 0
        clock.now += 11
        q.recover("API")
        if not after:
            # Cerrar el primer trabajo sin dispatch y dar prioridad al segundo.
            first = q.claim("API", "resolver")
            assert first.id == ids[0]
            q.no_effect(first, "no-dispatch", base_delay=100, max_delay=100)
    # Segundo claim de subproceso toma la segunda tarea por due original.
    assert q.status(ids[1])["status"] == "uncertain"
    assert q.status(ids[0])["status"] == "queued"
    assert q.reconcile(ids[1], "unknown", "not-enough-evidence") == "uncertain"

def test_invalid_non_finite_schedules_and_bool_attempts(env):
    q, _ = env
    with pytest.raises(ValueError):
        put(q, due=float("nan"))
    with pytest.raises(ValueError):
        put(q, expires_at=float("inf"))
    with pytest.raises(ValueError):
        put(q, max_attempts=True)
    assert q.claim("API", "A") is None

def test_restarted_queue_preserves_evidence_and_unique_intent(env):
    q, clock = env
    ident = put(q)
    ticket = q.claim("API", "owner", lease_seconds=10)
    q.mark_dispatched(ticket)
    q2 = IntentQueue(q.path, clock=clock)
    assert q2.status(ident)["status"] == "in_flight"
    clock.now += 11
    assert q2.claim("API", "other") is None
    assert q2.reconcile(ident, "confirmed", "remote-reload") == "confirmed"
    assert q2.enqueue(network="bluesky", channel="API", intent_key="task-1",
                      kind="reply", target="post/42",
                      payload={"text": "Prueba sintética"}) == ident

def test_invalid_jitter_rolls_back_entire_transition(tmp_path):
    q = IntentQueue(str(tmp_path / "jitter.sqlite"), clock=lambda: 1000.0,
                    jitter=lambda: float("nan"))
    ident = put(q)
    t = q.claim("API", "owner")
    with pytest.raises(ValueError):
        q.no_effect(t, "proof")
    assert q.status(ident)["status"] == "claimed"
    assert q.events(ident)[-1][0] == "claimed"

def test_producer_retry_with_implicit_due_does_not_conflict(env):
    q, clock = env
    ident = put(q)
    clock.now += 200
    assert put(q) == ident
    assert q.status(ident)["source_due"] is None
    assert q.status(ident)["due"] == 1000

def test_conflicting_explicit_schedule_is_rejected(env):
    q, clock = env
    ident = put(q, due=1100.0)
    clock.now += 30
    assert put(q, due=1100.0) == ident
    with pytest.raises(IdempotencyConflict):
        put(q, due=1101.0)
    with pytest.raises(IdempotencyConflict):
        put(q)  # el primer emisor pidió una fecha explícita
