"""http_retry.py (03/10): reintentos de lecturas ante fallos transitorios."""
import pathlib
import sys
import types
import unittest

import requests

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import http_retry as hr


def resp(code):
    return types.SimpleNamespace(status_code=code)


class RetryTests(unittest.TestCase):
    def run_with(self, outcomes):
        calls, sleeps = [], []

        def get(url, **kwargs):
            calls.append(url)
            outcome = outcomes[len(calls) - 1]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        result = hr.get_with_retry("u", get=get, sleeper=sleeps.append)
        return result, calls, sleeps

    def test_transient_500_is_retried_then_succeeds(self):
        result, calls, sleeps = self.run_with([resp(500), resp(502), resp(200)])
        self.assertEqual((result.status_code, len(calls), len(sleeps)), (200, 3, 2))

    def test_connection_errors_and_timeouts_are_retried(self):
        result, calls, _ = self.run_with([requests.ConnectionError("x"), requests.Timeout("y"), resp(200)])
        self.assertEqual((result.status_code, len(calls)), (200, 3))

    def test_429_and_404_are_never_retried(self):
        for code in (429, 404, 401):
            result, calls, _ = self.run_with([resp(code)])
            self.assertEqual((result.status_code, len(calls)), (code, 1))

    def test_gives_up_after_the_last_attempt_returning_or_raising(self):
        result, calls, _ = self.run_with([resp(500)] * 4)
        self.assertEqual((result.status_code, len(calls)), (500, 4))
        with self.assertRaises(requests.Timeout):
            self.run_with([requests.Timeout("t")] * 4)


if __name__ == "__main__":
    unittest.main()
