import datetime
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import circuit_breaker as cb

T0 = datetime.datetime(2026, 10, 3, 12, 0)


class DetectTests(unittest.TestCase):
    def test_signals(self):
        self.assertEqual(cb.detect("API error 429 Too Many Requests"), "rate")
        self.assertEqual(cb.detect("HTTP 401 ExpiredToken"), "auth")
        self.assertEqual(cb.detect("Your account has been suspended"), "auth")
        self.assertEqual(cb.detect("We detected unusual activity on your account"), "auth")
        self.assertEqual(cb.detect("Your account is temporarily restricted"), "auth")
        self.assertIsNone(cb.detect("Something went wrong. Try again later"))   # fallo pasajero de X, no un aviso
        self.assertEqual(cb.worst([None, "rate", "auth"]), "auth")
        self.assertEqual(cb.worst([None, "rate"]), "rate")
        self.assertIsNone(cb.worst([None]))

    def test_ordinary_book_text_is_not_a_signal(self):
        for text in ("una novela de locked room", "blocked users list", "los 429 libros que leí", "todo ok"):
            self.assertIsNone(cb.detect(text), text)


class BreakerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_closed_by_default_and_success_resets(self):
        self.assertEqual(cb.check(self.dir, T0), (True, ""))
        cb.record(self.dir, False, now=T0)
        cb.record(self.dir, True, now=T0)
        self.assertEqual(cb.load(self.dir)["fails"], 0)

    def test_rate_limit_opens_for_three_hours_then_closes_itself(self):
        cb.record(self.dir, False, signal="rate", now=T0)
        allowed, why = cb.check(self.dir, T0 + datetime.timedelta(hours=2))
        self.assertFalse(allowed)
        self.assertIn("pausada hasta", why)
        self.assertTrue(cb.check(self.dir, T0 + datetime.timedelta(hours=3, minutes=1))[0])

    def test_auth_pauses_twelve_hours(self):
        cb.record(self.dir, False, signal="auth", now=T0)
        self.assertFalse(cb.check(self.dir, T0 + datetime.timedelta(hours=11))[0])
        self.assertTrue(cb.check(self.dir, T0 + datetime.timedelta(hours=12, minutes=1))[0])

    def test_three_plain_failures_open_and_extra_failures_double_the_pause(self):
        for _ in range(2):
            cb.record(self.dir, False, now=T0)
        self.assertTrue(cb.check(self.dir, T0)[0])
        cb.record(self.dir, False, now=T0)
        self.assertFalse(cb.check(self.dir, T0 + datetime.timedelta(hours=5))[0])
        self.assertTrue(cb.check(self.dir, T0 + datetime.timedelta(hours=6, minutes=1))[0])
        cb.record(self.dir, False, now=T0)   # 4o fallo: 12 h
        self.assertFalse(cb.check(self.dir, T0 + datetime.timedelta(hours=11))[0])
        for _ in range(3):                   # el tope es 24 h
            cb.record(self.dir, False, now=T0)
        self.assertFalse(cb.check(self.dir, T0 + datetime.timedelta(hours=23))[0])
        self.assertTrue(cb.check(self.dir, T0 + datetime.timedelta(hours=24, minutes=1))[0])


if __name__ == "__main__":
    unittest.main()
