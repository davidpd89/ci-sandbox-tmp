import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import mastodon_budget as mb

NOW = dt.datetime(2026, 10, 6, 12, 0, tzinfo=dt.timezone.utc)


def window(remaining, seconds=120):
    return {"remaining": remaining, "limit": 300, "reset": NOW + dt.timedelta(seconds=seconds)}


class BudgetTests(unittest.TestCase):
    def test_scan_stops_at_its_reserve_but_tools_keep_going(self):
        state = window(60)
        self.assertGreater(mb.seconds_to_wait("scan", state, None, NOW), 100)
        self.assertEqual(mb.seconds_to_wait("normal", state, None, NOW), 0)
        self.assertEqual(mb.seconds_to_wait("priority", state, None, NOW), 0)

    def test_priority_tool_waits_only_when_almost_empty(self):
        self.assertGreater(mb.seconds_to_wait("priority", window(2), None, NOW), 100)
        self.assertEqual(mb.seconds_to_wait("priority", window(4), None, NOW), 0)

    def test_expired_window_never_waits(self):
        self.assertEqual(mb.seconds_to_wait("scan", window(0, seconds=-5), window(0, seconds=-5), NOW), 0)

    def test_shared_state_from_another_process_is_respected(self):
        self.assertGreater(mb.seconds_to_wait("scan", window(250), window(50), NOW), 100)

    def test_wait_is_capped(self):
        self.assertLessEqual(mb.seconds_to_wait("scan", window(0, seconds=5000), None, NOW), mb.MAX_WAIT_SECONDS + 2)

    def test_publish_keeps_lowest_remaining_of_same_window(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "sub", "ratelimit.json")
            reset = NOW + dt.timedelta(seconds=100)
            mb.publish(40, 300, reset, path)
            mb.publish(200, 300, reset, path)            # respuesta atrasada de otro proceso: no sube el margen
            self.assertEqual(mb.read(path)["remaining"], 40)
            mb.publish(290, 300, reset + dt.timedelta(seconds=300), path)      # ventana nueva
            self.assertEqual(mb.read(path)["remaining"], 290)

    def test_wait_for_budget_sleeps_and_logs(self):
        slept, logs = [], []
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "r.json")
            mb.publish(10, 300, NOW + dt.timedelta(seconds=30), path)
            waited = mb.wait_for_budget("scan", None, sleep=slept.append, log=logs.append, path=path, now=NOW)
        self.assertEqual(slept, [waited])
        self.assertTrue(logs)

    def test_missing_file_is_harmless(self):
        self.assertIsNone(mb.read(os.path.join(tempfile.gettempdir(), "no-existe-rrss.json")))


if __name__ == "__main__":
    unittest.main()
