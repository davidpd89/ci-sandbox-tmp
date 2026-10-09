"""Precarga en lote y registro accion a accion del ejecutor de Mastodon; sin red."""
import pathlib
import sys
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: None
requests_stub.post = lambda *a, **k: None
requests_stub.delete = lambda *a, **k: None
x_stub = types.ModuleType("x_interact")
x_stub._check_spanish_orthography = lambda text: None
sys.modules.setdefault("requests", requests_stub)
sys.modules.setdefault("x_interact", x_stub)

import mastodon_interact as m
import mastodon_execute as ex


class PrefetchTests(unittest.TestCase):
    def setUp(self):
        m._PREFETCH.clear()

    def test_statuses_and_relationships_are_fetched_in_batches(self):
        calls = []

        def fake_get(path, params=None):
            ids = params["id[]"]
            calls.append((path, len(ids)))
            if path == "statuses":
                return [{"id": i, "favourited": False, "reblogged": i == "3"} for i in ids]
            return [{"id": i, "following": i == "9", "requested": False} for i in ids]

        with patch.object(m, "_get", side_effect=fake_get):
            m.prefetch(status_ids=[str(i) for i in range(25)], account_ids=[str(i) for i in range(45)])
        self.assertEqual(calls, [("statuses", 20), ("statuses", 5), ("accounts/relationships", 40), ("accounts/relationships", 5)])
        self.assertTrue(m._prefetched(("status", "3"))["reblogged"])
        self.assertIsNone(m._prefetched(("status", "3")))            # se consume
        self.assertTrue(m._prefetched(("account", "9"))["following"])

    def test_favourite_and_follow_need_only_the_write_when_prefetched(self):
        posted = []
        m._PREFETCH[("status", "55")] = {"favourited": False, "reblogged": False, "t": time.time()}
        m._PREFETCH[("account", "7")] = {"following": False, "requested": False, "t": time.time()}

        def fake_post(path, data=None, extra_headers=None):
            posted.append(path)
            return {"favourited": True, "following": True}

        with patch.object(m, "_get", side_effect=AssertionError("no debe leer")), patch.object(m, "_post", side_effect=fake_post):
            self.assertEqual(m.favourite("55"), "favourited")
            self.assertEqual(m.follow("alguien@masto.es", "7"), "followed")
        self.assertEqual(posted, ["statuses/55/favourite", "accounts/7/follow"])

    def test_prefetched_existing_state_is_never_written_again(self):
        m._PREFETCH[("status", "56")] = {"favourited": True, "reblogged": True, "t": time.time()}
        m._PREFETCH[("account", "8")] = {"following": True, "requested": False, "t": time.time()}
        with patch.object(m, "_get", side_effect=AssertionError("no debe leer")), patch.object(m, "_post", side_effect=AssertionError("no debe escribir")):
            self.assertEqual(m.favourite("56"), "already")
            m._PREFETCH[("status", "56")] = {"favourited": True, "reblogged": True, "t": time.time()}      # el estado precargado se consume en cada uso
            self.assertEqual(m.boost("56"), "already")
            self.assertEqual(m.follow("alguien@masto.es", "8"), "already")

    def test_without_prefetch_the_usual_reads_still_happen(self):
        reads = []

        def fake_get(path, params=None):
            reads.append(path)
            if path.startswith("accounts/lookup"):
                return {"id": "7"}
            if path == "accounts/relationships":
                return [{"id": "7", "following": False}]
            return {"favourited": False}

        with patch.object(m, "_get", side_effect=fake_get), patch.object(m, "_post", return_value={"favourited": True, "following": True}):
            m.favourite("55")
            m.follow("alguien@masto.es")
        self.assertEqual(reads, ["statuses/55", "accounts/lookup", "accounts/relationships"])

    def test_expired_prefetch_is_ignored(self):
        m._PREFETCH[("status", "57")] = {"favourited": True, "reblogged": False, "t": time.time() - m.PREFETCH_TTL - 5}
        self.assertIsNone(m._prefetched(("status", "57")))


class ExecutorPersistenceTests(unittest.TestCase):
    def test_every_result_is_reported_as_it_happens(self):
        seen = []
        plan = [{"kind": "favourite", "handle": "a@x", "status_id": "1", "url": "https://x/@a/1"},
                {"kind": "favourite", "handle": "b@x", "status_id": "2", "url": "https://x/@b/2"},
                {"kind": "favourite", "handle": "c@x", "status_id": "3", "url": "https://x/@c/3"}]

        def fav(status_id):
            if status_id == "2":
                raise RuntimeError("boom")
            return "favourited"

        with patch.object(ex.m, "favourite", side_effect=fav), patch.object(ex, "_pause", lambda *a, **k: None), patch.object(ex, "_pace_for_rate_limit", lambda *a, **k: None), \
                patch.object(ex, "_prefetch_window", lambda items: None), patch.object(ex.sc, "report_plan_style", lambda plan: None):
            results = ex.run_plan(plan, prevalidated=True, on_result=lambda r: seen.append((r["handle"], r["resultado"].split(":")[0])))
        self.assertEqual(seen, [("a@x", "confirmado"), ("b@x", "fallo"), ("c@x", "confirmado")])
        self.assertEqual(len(results), 3)

    def test_prefetch_window_batches_the_next_actions(self):
        captured = {}
        with patch.object(ex.m, "prefetch", side_effect=lambda **kw: captured.update(kw)):
            ex._prefetch_window([{"kind": "favourite", "status_id": "1"}, {"kind": "boost", "status_id": "2"},
                                 {"kind": "follow", "account_id": "9"}, {"kind": "reply", "status_id": "3"}])
        self.assertEqual(captured, {"status_ids": ["1", "2"], "account_ids": ["9"]})

    def test_prefetch_failure_is_not_fatal(self):
        with patch.object(ex.m, "prefetch", side_effect=RuntimeError("500")):
            ex._prefetch_window([{"kind": "favourite", "status_id": "1"}])


if __name__ == "__main__":
    unittest.main()
