import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import bluesky_execute as be


class FakeLedger:
    def __init__(self, n):
        self.n = n

    def count_since(self, since):
        return self.n


class GuardTests(unittest.TestCase):
    def test_no_wait_below_the_limit(self):
        self.assertEqual(be._hourly_guard([1000.0] * 5, FakeLedger(10), sleeper=lambda s: self.fail("no debe esperar"), now=lambda: 1100.0, limit=100), 0)

    def test_waits_in_30_second_steps_until_the_hour_rolls_over(self):
        clock = {"t": 1000.0}
        slept = []

        def sleeper(s):
            slept.append(s)
            clock["t"] += 1000        # tras dormir, el reloj avanza y las escrituras antiguas salen de la ventana de 60 min
        waited = be._hourly_guard([1000.0] * 100, None, sleeper=sleeper, now=lambda: clock["t"], limit=100)
        self.assertEqual(slept, [30, 30, 30, 30][:len(slept)])
        self.assertGreaterEqual(len(slept), 1)
        self.assertEqual(waited, 30 * len(slept))

    def test_other_processes_count_too(self):
        slept = []
        be._hourly_guard([], FakeLedger(100), sleeper=lambda s: slept.append(s), now=lambda: 5000.0, limit=100) if False else None
        # con el ledger al tope y sin escrituras propias se espera hasta que el ledger deje de estar al tope
        class Ledger(FakeLedger):
            calls = 0

            def count_since(self, since):
                Ledger.calls += 1
                return 100 if Ledger.calls < 3 else 0
        slept = []
        be._hourly_guard([], Ledger(0), sleeper=lambda s: slept.append(s), now=lambda: 5000.0, limit=100)
        self.assertEqual(slept, [30, 30])


if __name__ == "__main__":
    unittest.main()
