"""Un 5xx puntual de Mastodon ya no para la ronda (06/10/2026: un 503 corto tiro 63 de 82 acciones); sin red."""
import pathlib
import sys
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


def plan(n):
    return [{"kind": "favourite", "status_id": str(i), "url": f"https://x/@a{i}/{i}", "handle": f"a{i}"} for i in range(n)]


class FiveXXTests(unittest.TestCase):
    def run_plan(self, side_effect, n=4):
        with patch.object(m, "favourite", side_effect=side_effect), patch.object(ex, "_pause"), patch.object(ex, "_retry_sleep"), \
                patch.object(ex, "_pace_for_rate_limit", lambda: None), patch.object(ex, "_prefetch_window", lambda items: None), \
                patch("like_context_policy.check_execution", return_value=(True, "test")):  # sin esto, con .env real la barrera de #81 llamaba a la API de verdad
            return ex.run_plan(plan(n), prevalidated=True)

    def test_transient_503_is_retried_and_succeeds(self):
        calls = {"n": 0}

        def flaky(status_id):
            calls["n"] += 1
            if calls["n"] == 1:
                raise m.MastodonAPIError("POST favourite", 503, "")
            return "ok"

        results = self.run_plan(flaky)
        self.assertEqual([r["resultado"] for r in results], ["confirmado"] * 4)

    def test_sustained_503_stops_after_three_actions(self):
        def down(status_id):
            raise m.MastodonAPIError("POST favourite", 503, "")

        results = self.run_plan(down, n=8)
        self.assertEqual(sum(1 for r in results if r["resultado"].startswith("fallo")), 3)
        self.assertEqual(sum(1 for r in results if r["resultado"] == "no_intentado"), 5)

    def test_deleted_status_is_skipped_not_a_stop(self):
        def gone(status_id):
            if status_id == "1":
                raise m.MastodonAPIError("POST favourite", 404, "")
            return "ok"

        results = self.run_plan(gone)
        self.assertEqual([r["resultado"] for r in results], ["confirmado", "saltado_api_404", "confirmado", "confirmado"])

    def test_rate_limit_waits_and_retries_the_same_action(self):
        # 06/10 (David: «da igual lo que tarde»): un 429 ya no para el lote
        calls = {"n": 0}

        def limited_once(status_id):
            calls["n"] += 1
            if calls["n"] == 1:
                raise m.MastodonRateLimitExceeded("POST favourite", 429, "", retry_after="1")
            return "ok"

        with patch.object(m._time, "sleep") as slept:
            results = self.run_plan(limited_once)
        self.assertEqual([r["resultado"] for r in results], ["confirmado"] * 4)
        self.assertTrue(slept.called)

    def test_sustained_rate_limit_stops_after_the_waits(self):
        def limited(status_id):
            raise m.MastodonRateLimitExceeded("POST favourite", 429, "", retry_after="1")

        with patch.object(m._time, "sleep"):
            results = self.run_plan(limited)
        self.assertTrue(results[0]["resultado"].startswith("parada"))
        self.assertEqual(results[-1]["resultado"], "no_intentado")


if __name__ == "__main__":
    unittest.main()
