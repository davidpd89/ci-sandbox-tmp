"""PR #58: cookies, temporización CDP y errores sin secretos; no red/Edge."""
import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import chatgpt_edge as ce


class FakeWS:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.sent = []
        self.timeouts = []

    def send(self, data):
        self.sent.append(data)

    def settimeout(self, seconds):
        self.timeouts.append(seconds)

    def recv(self):
        return json.dumps(next(self.answers))


def raw_cdp(replies):
    cdp = ce._Cdp.__new__(ce._Cdp)  # evita conexión WebSocket real
    cdp._json = json
    cdp.ws = FakeWS(replies)
    cdp.n = 0
    return cdp


class CookieScopeTests(unittest.TestCase):
    def test_exact_and_subdomain_cookies_only(self):
        for domain in ("chatgpt.com", ".chatgpt.com", "cdn.chatgpt.com",
                       ".openai.com", "oaistatic.com"):
            with self.subTest(domain=domain):
                self.assertTrue(ce._is_chatgpt_cookie({"domain": domain}))
        for domain in ("fakechatgpt.com", "not-openai.com", "otheropenai.com",
                       "chatgpt.com.ejemplo.invalid", "", None):
            with self.subTest(domain=domain):
                self.assertFalse(ce._is_chatgpt_cookie({"domain": domain}))

    def test_malformed_cookie_refused(self):
        self.assertFalse(ce._is_chatgpt_cookie(None))
        self.assertFalse(ce._is_chatgpt_cookie([]))


class RawCDPTests(unittest.TestCase):
    def test_unrelated_events_cannot_extend_deadline_forever(self):
        client = raw_cdp([{"method": "Target.targetCreated"}] * 3)
        with mock.patch.object(ce.time, "monotonic", side_effect=[0, 0.1, 11]):
            with self.assertRaisesRegex(TimeoutError, "plazo"):
                client.call("Storage.getCookies")
        self.assertEqual(len(client.ws.sent), 1)
        self.assertEqual(len(client.ws.timeouts), 1)

    def test_valid_response_retrieved_without_retries(self):
        client = raw_cdp([{"method": "targetCreated"}, {"id": 1, "result": {"cookies": []}}])
        with mock.patch.object(ce.time, "monotonic", side_effect=[0, 0.5, 0.8]):
            self.assertEqual(client.call("Storage.getCookies"), {"cookies": []})
        self.assertEqual(len(client.ws.sent), 1)

    def test_error_does_not_echo_remote_cookie_or_token(self):
        client = raw_cdp([{"id": 1, "error": {"message": "sk-synthetic-private-token"}}])
        with mock.patch.object(ce.time, "monotonic", side_effect=[0, 0.1]):
            with self.assertRaisesRegex(RuntimeError, "error remoto") as ctx:
                client.call("Storage.getCookies")
        self.assertNotIn("synthetic-private-token", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
