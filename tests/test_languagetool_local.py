"""Pruebas sintéticas sin Java, navegador, red ni cuentas sociales."""
import json
import pathlib
import sys
import unittest
from urllib import error

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from languagetool_local import NETWORKS, audit, _checked_endpoint, _utf16_to_codepoint


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        return self.payload


def fake(payload):
    def transport(req, *, timeout):
        assert req.get_method() == "POST"
        assert req.data is not None and b"language=es-ES" in req.data
        assert timeout > 0
        return FakeResponse(json.dumps(payload).encode("utf-8"))
    return transport


ENDPOINT = "http://127.0.0.1:8081/v2/check"


class TestLanguageToolLocal(unittest.TestCase):
    def test_nine_networks_disabled_without_server(self):
        self.assertEqual(len(NETWORKS), 9)
        for network in NETWORKS:
            result = audit("¿Qué libro recomiendas?", network=network)
            self.assertEqual((result["status"], result["findings"], result["changed"]),
                             ("disabled", [], False))

    def test_server_normalizes_offsets_accents_and_suggestions_nine_networks(self):
        phrase = "🙂 Me gusto el libro."
        # UTF-16: emoji consume 2 unidades y el error empieza en el 6.
        start = phrase.index("gusto")
        offset = start + 1
        payload = {"matches": [{"offset": offset, "length": 5,
                                "rule": {"id": "TILDE", "category": {"id": "TYPOS"}},
                                "replacements": [{"value": "gustó"}]}]}
        for network in NETWORKS:
            result = audit(phrase, network=network, endpoint=ENDPOINT, transport=fake(payload))
            self.assertEqual(result["status"], "ok")
            issue = result["findings"][0]
            self.assertEqual(phrase[issue["start"]:issue["end"]], "gusto")
            self.assertEqual(issue["suggestions"], ["gustó"])
            self.assertFalse(result["changed"])

    def test_protection_quotes_hashtags_urls_and_markdown(self):
        text = '«herror» @herror #herror https://local.test/herror [herror](https://foo.test) herror'
        indices = [i for i in range(len(text)) if text.startswith("herror", i)]
        payload = {"matches": [{"offset": i, "length": 6,
                                "rule": {"id": "SPELL"}} for i in indices]}
        result = audit(text, network="reddit", endpoint=ENDPOINT, transport=fake(payload))
        self.assertEqual(len(result["findings"]), 1)
        self.assertEqual(result["findings"][0]["start"], indices[-1])

    def test_mid_surrogate_and_invalid_ranges_are_dropped(self):
        self.assertIsNone(_utf16_to_codepoint("🙂hola", 1))
        result = audit("🙂hola", network="x", endpoint=ENDPOINT,
                       transport=fake({"matches": [
                           {"offset": 1, "length": 1}, {"offset": 999, "length": 1},
                           {"offset": -1, "length": 1}, {"offset": True, "length": 1},
                           {"offset": 2, "length": 4},
                       ]}))
        self.assertEqual([(m["start"], m["end"]) for m in result["findings"]], [(1, 5)])

    def test_endpoint_must_be_loopback_http_and_never_redirect(self):
        for url in ("https://127.0.0.1:8081/v2/check",
                    "http://example.org:8081/v2/check",
                    "http://127.0.0.1:8081/other",
                    "http://127.0.0.1:8081/v2/check?key=foo",
                    "http://user:pass@127.0.0.1:8081/v2/check",
                    "http://127.0.0.2:8081/v2/check", "http://127.0.0.1/v2/check"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                _checked_endpoint(url)
        self.assertEqual(_checked_endpoint(ENDPOINT), ENDPOINT)

    def test_unavailable_never_blocks_or_logs_text(self):
        def down(req, *, timeout):
            raise error.URLError("private text must not be logged")
        result = audit("Mi texto propio", network="bluesky", endpoint=ENDPOINT, transport=down)
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("Mi texto", repr(result))

    def test_bad_payload_or_response_size_rejected(self):
        for response in (b'{"matches": "wrong"}', b"not json", b"x" * (1024 * 1024 + 1)):
            result = audit("Hola", network="tiktok", endpoint=ENDPOINT,
                           transport=lambda req, *, timeout: FakeResponse(response))
            self.assertEqual(result["status"], "unavailable")

    def test_invalid_inputs_and_empty_text(self):
        with self.assertRaises(TypeError):
            audit(None, network="x")
        with self.assertRaises(ValueError):
            audit("Hola", network="not-a-network")
        self.assertEqual(audit("  ", network="x", endpoint=ENDPOINT)["status"], "disabled")


if __name__ == "__main__":
    unittest.main()
