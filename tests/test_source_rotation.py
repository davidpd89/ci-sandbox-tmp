"""Synthetic, hermetic source rotation and 8-network replay tests."""
import datetime as dt
import os
import multiprocessing as mp
import sqlite3
import sys
import tempfile
import threading
import unittest
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import source_rotation as sr

NOW = dt.datetime(2026, 10, 9, 8, tzinfo=dt.timezone.utc)
NETWORKS = ("bluesky", "mastodon", "x", "threads", "facebook", "pinterest", "reddit", "tiktok")


def _claim_in_process(path, barrier, output):
    barrier.wait()
    claims = sr.claim_sources(path, "x", "search", ["mismo origen"], 1, now=NOW)
    output.put(len(claims))


class TestSourceRotation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "source.sqlite3")

    def pick(self, network="x", sources=("fantasía", "lectura"), n=1, now=NOW, **kwargs):
        return sr.claim_sources(self.path, network, "search", sources, n, now=now, **kwargs)

    def finish(self, claim, network="x", status="ok", now=NOW, **kwargs):
        if status == "ok":
            kwargs.setdefault("elapsed_ms", 100)
        return sr.finish_source(self.path, network, "search", claim,
                                status=status, now=now, **kwargs)

    def test_single_slot_does_not_starve_productive_source(self):
        first = self.pick(sources=["A"], cooldown_seconds=0)[0]
        self.finish(first, candidate_ids=["1"])
        second = self.pick(sources=["A", "B"], now=NOW + dt.timedelta(seconds=1),
                           cooldown_seconds=0)[0]
        self.assertEqual(second.key, "A")
        self.finish(second, candidate_ids=["2"], now=NOW + dt.timedelta(seconds=1))
        third = self.pick(sources=["A", "B"], now=NOW + dt.timedelta(seconds=2),
                          cooldown_seconds=0)[0]
        self.assertEqual(third.key, "B")

    def test_8_networks_are_isolated(self):
        for network in NETWORKS:
            claim = self.pick(network, ("libros",), 1)[0]
            self.assertTrue(self.finish(claim, network, candidate_ids=["id-a", "id-a", "id-b"], elapsed_ms=500))
            self.assertEqual(self.pick(network, ("libros",), 1), [])
        with sqlite3.connect(self.path) as db:
            values = db.execute("SELECT network, attempts, unique_total FROM observations").fetchall()
        self.assertEqual(len(values), 8)
        self.assertTrue(all(a == 1 and u == 2 for _, a, u in values))

    def test_empty_none_invalid_and_dedup(self):
        self.assertEqual(self.pick(sources=[], n=2), [])
        self.assertEqual(len(self.pick(sources=["España", "Espan\u0303a", "españa"], n=3)), 1)
        with self.assertRaises(ValueError):
            self.pick(sources=[None])
        with self.assertRaises(ValueError):
            self.pick(sources="un solo texto")
        with self.assertRaises(ValueError):
            self.pick(n=-1)
        with self.assertRaises(ValueError):
            self.pick(now=dt.datetime(2026, 10, 9))

    def test_cooldown_expiry_and_no_implicit_cycle(self):
        one = self.pick(sources=["A"], cooldown_seconds=3600)[0]
        self.assertEqual(self.pick(sources=["A"], now=NOW + dt.timedelta(minutes=20)), [])
        self.finish(one, candidate_ids=[])
        self.assertEqual(self.pick(sources=["A"], now=NOW + dt.timedelta(minutes=59)), [])
        self.assertEqual(len(self.pick(sources=["A"], now=NOW + dt.timedelta(hours=1))), 1)

    def test_failure_partial_does_not_count_as_zero(self):
        a = self.pick(sources=["A"], cooldown_seconds=0)[0]
        self.assertTrue(self.finish(a, status="partial"))
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT attempts,last_ok FROM observations").fetchone(), (0, None))
        self.assertEqual(len(self.pick(sources=["A"], now=NOW + dt.timedelta(seconds=1))), 1)

    def test_new_vs_productive_and_old(self):
        a = self.pick(sources=["A"], cooldown_seconds=0)[0]
        self.finish(a, candidate_ids=["1", "2", "3"], elapsed_ms=1000)
        later = NOW + dt.timedelta(hours=3)
        picks = self.pick(sources=["A", "B", "C"], n=2, now=later)
        self.assertEqual([x.key for x in picks], ["B", "A"])

    def test_network_wide_429_and_captcha_never_reroute(self):
        a = self.pick(sources=["A"])[0]
        self.finish(a, status="rate_limited", retry_after_seconds=180, now=NOW)
        self.assertEqual(self.pick(sources=["B"], now=NOW + dt.timedelta(seconds=179)), [])
        self.assertEqual(len(self.pick(sources=["B"], now=NOW + dt.timedelta(seconds=181))), 1)
        b = self.pick(sources=["C"], now=NOW + dt.timedelta(seconds=182))[0]
        self.finish(b, status="captcha", now=NOW + dt.timedelta(seconds=182))
        self.assertEqual(self.pick(sources=["D"], now=NOW + dt.timedelta(days=30)), [])
        sr.clear_human_gate(self.path, "x")
        self.assertEqual(len(self.pick(sources=["D"], now=NOW + dt.timedelta(days=30))), 1)

    def test_concurrency_atomic_claim(self):
        claims = []
        barrier = threading.Barrier(2)
        def worker():
            barrier.wait()
            claims.extend(self.pick(sources=["same"], n=1))
        t1, t2 = threading.Thread(target=worker), threading.Thread(target=worker)
        t1.start(); t2.start(); t1.join(); t2.join()
        self.assertEqual(len(claims), 1)

    def test_two_spawned_workers_cannot_duplicate(self):
        # Spawn also works on Windows; this is not merely a thread/GIL test.
        ctx = mp.get_context("spawn")
        barrier, output = ctx.Barrier(2), ctx.Queue()
        procs = [ctx.Process(target=_claim_in_process, args=(self.path, barrier, output)) for _ in range(2)]
        for process in procs:
            process.start()
        try:
            for process in procs:
                process.join(timeout=10)
                self.assertFalse(process.is_alive())
                self.assertEqual(process.exitcode, 0)
            self.assertEqual(sorted([output.get(timeout=2), output.get(timeout=2)]), [0, 1])
        finally:
            for process in procs:
                if process.is_alive():
                    process.terminate()
                process.join(timeout=2)

    def test_dst_madrid_same_instant(self):
        try:
            madrid = ZoneInfo("Europe/Madrid")
        except ZoneInfoNotFoundError:
            self.skipTest("IANA timezone database unavailable")
        utc = dt.datetime(2026, 10, 25, 1, 30, tzinfo=dt.timezone.utc)
        one = self.pick(sources=["A"], now=utc.astimezone(madrid))[0]
        self.assertEqual(self.pick(sources=["A"], now=utc), [])
        self.assertTrue(self.finish(one, candidate_ids=[], now=utc))

    def test_all_networks_empty_new_productive_partial_and_pause(self):
        for network in NETWORKS:
            self.assertEqual(self.pick(network, [], 1), [])
            first = self.pick(network, ["primera"], 1, cooldown_seconds=0)[0]
            self.assertTrue(self.finish(first, network, candidate_ids=["1", "2"], elapsed_ms=200))
            partial = self.pick(network, ["nueva"], 1, cooldown_seconds=0, now=NOW + dt.timedelta(seconds=2))[0]
            self.assertTrue(self.finish(partial, network, status="partial", now=NOW + dt.timedelta(seconds=2)))
            chosen = self.pick(network, ["primera", "nueva"], 2, now=NOW + dt.timedelta(seconds=3), cooldown_seconds=0)
            self.assertEqual({claim.key for claim in chosen}, {"primera", "nueva"})
            self.assertTrue(self.finish(chosen[0], network, status="rate_limited", retry_after_seconds=60, now=NOW + dt.timedelta(seconds=3)))
            self.assertEqual(self.pick(network, ["tercera"], now=NOW + dt.timedelta(seconds=4)), [])

    def test_sqlite_transaction_rollback(self):
        with self.assertRaises(RuntimeError):
            with sr._connect(self.path) as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute("INSERT INTO network_gates(network, until_ts) VALUES ('x', 9999)")
                raise RuntimeError("simulated interrupted write")
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM network_gates").fetchone()[0], 0)

    def test_stale_token_cannot_override_later_work(self):
        a = self.pick(sources=["A"], cooldown_seconds=0, lease_seconds=10)[0]
        b = self.pick(sources=["A"], cooldown_seconds=0, lease_seconds=10,
                      now=NOW + dt.timedelta(seconds=11))[0]
        self.assertFalse(self.finish(a, candidate_ids=["old"], now=NOW + dt.timedelta(seconds=12)))
        self.assertTrue(self.finish(b, candidate_ids=["new"], now=NOW + dt.timedelta(seconds=12)))

    def test_no_production_io_or_timezone_assumptions(self):
        local = NOW.astimezone(dt.timezone(dt.timedelta(hours=2)))
        claims = self.pick(now=local)
        self.assertEqual(len(claims), 1)
        self.assertEqual(self.pick(sources=[claims[0].key], now=NOW), [])

    def test_unknown_429_deadline_needs_review(self):
        claim = self.pick()[0]
        self.finish(claim, status="rate_limited", now=NOW)
        self.assertEqual(self.pick(sources=["never tried"], now=NOW + dt.timedelta(days=7)), [])
        sr.clear_human_gate(self.path, "X")
        self.assertEqual(len(self.pick(sources=["never tried"], now=NOW + dt.timedelta(days=7))), 1)

    def test_corrupt_state_and_missing_directory_fail_closed(self):
        with open(self.path, "wb") as fd:
            fd.write(b"not sqlite")
        with self.assertRaises(sqlite3.DatabaseError):
            self.pick()
        with self.assertRaises(sqlite3.OperationalError):
            sr.claim_sources(os.path.join(self.tmp.name, "missing", "db"), "x", "search", ["a"], 1, now=NOW)

    def test_invalid_result_does_not_increment(self):
        a = self.pick()[0]
        with self.assertRaises(ValueError):
            self.finish(a, candidate_ids=[None])
        with self.assertRaises(ValueError):
            sr.finish_source(self.path, "x", "search", a, candidate_ids=[], now=NOW)
        with self.assertRaises(ValueError):
            sr.finish_source(self.path, "x", "search", a, elapsed_ms=10, now=NOW)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT attempts FROM observations").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
