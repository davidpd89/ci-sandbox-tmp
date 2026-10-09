"""Regresiones de privacidad y cierre explícito para tools/cdp_health.py."""
import contextlib
import importlib.util
import io
import pathlib
import sys
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "cdp_health.py"


def load_module():
    spec = importlib.util.spec_from_file_location("cdp_health_under_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CDPHealthTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_social_urls_do_not_print_private_path_query_or_fragment(self):
        targets = [
            {
                "id": "safe-1",
                "type": "page",
                "url": "https://www.instagram.com/direct/t/privado?code=secreto",
            },
            {
                "id": "safe-2",
                "type": "page",
                "url": "https://www.facebook.com/oauth/callback/otro-secreto#fragmento",
            },
            {
                "id": "safe-3",
                "type": "page",
                "url": "https://sitio-ajeno.example/reset/token-privado",
            },
        ]

        def fake_json(path):
            if path == "/json/version":
                return {}
            if path == "/json/list":
                return targets
            raise AssertionError(path)

        out = io.StringIO()
        with patch.object(self.mod, "_cdp_json", side_effect=fake_json), \
             patch.object(sys, "argv", ["cdp_health.py"]), \
             contextlib.redirect_stdout(out):
            self.assertEqual(self.mod.main(), 0)

        printed = out.getvalue()
        for sensitive in (
            "privado",
            "secreto",
            "callback",
            "fragmento",
            "token-privado",
            "/direct/",
            "/oauth/",
            "/reset/",
        ):
            self.assertNotIn(sensitive, printed)
        self.assertIn("www.instagram.com", printed)
        self.assertIn("safe-1", printed)
        self.assertIn("sitio-ajeno.example", printed)

    def test_malformed_url_is_untrusted_and_does_not_leak_path(self):
        parsed = self.mod._split_url_safe("https://[host-malformado/ruta-secreta")
        self.assertEqual(parsed.scheme, "about")
        self.assertIsNone(parsed.hostname)
        label = self.mod._safe_target_label(
            {"url": "https://[host-malformado/ruta-secreta"}
        )
        self.assertNotIn("ruta-secreta", label)
        self.assertFalse(
            self.mod._approved_close_url(
                "https://[host-malformado/ruta-secreta"
            )
        )

    def test_close_policy_requires_exact_https_social_host(self):
        for good in (
            "about:blank",
            "https://x.com/algo",
            "https://www.instagram.com/p/ABC/",
            "https://www.facebook.com/photo/?fbid=1",
        ):
            with self.subTest(good=good):
                self.assertTrue(self.mod._approved_close_url(good))

        for bad in (
            "http://x.com/algo",
            "https://x.com.evil.example/algo",
            "https://evil.example/x.com/algo",
            "https://user:pass@x.com/algo",
            "https://x.com:444/algo",
            "https://x.com:puerto-invalido/algo",
            "javascript://x.com/algo",
            "chrome-extension://x.com/algo",
            "https://example.com/",
        ):
            with self.subTest(bad=bad):
                self.assertFalse(self.mod._approved_close_url(bad))

    def test_explicit_close_revalidates_same_id_and_same_url(self):
        approved = "https://x.com/lector/status/123"
        calls = []

        with patch.object(
            self.mod,
            "_page_targets",
            return_value=[
                {"id": "ABC123", "type": "page", "url": approved}
            ],
        ), patch.object(
            self.mod,
            "_cdp_text",
            side_effect=lambda path: calls.append(path) or "Target is closing",
        ):
            self.mod._close_target_explicit("ABC123", approved)

        self.assertEqual(calls, ["/json/close/ABC123"])

    def test_target_id_is_url_encoded_before_close_endpoint(self):
        approved = "https://x.com/lector/status/123"
        calls = []
        weird_id = "ABC/../json/version?x=1"

        with patch.object(
            self.mod,
            "_page_targets",
            return_value=[
                {"id": weird_id, "type": "page", "url": approved}
            ],
        ), patch.object(
            self.mod,
            "_cdp_text",
            side_effect=lambda path: calls.append(path) or "Target is closing",
        ):
            self.mod._close_target_explicit(weird_id, approved)

        self.assertEqual(
            calls,
            ["/json/close/ABC%2F..%2Fjson%2Fversion%3Fx%3D1"],
        )

    def test_close_aborts_if_url_changed_since_inventory(self):
        approved = "https://x.com/lector/status/123"
        close_calls = []

        with patch.object(
            self.mod,
            "_page_targets",
            return_value=[
                {
                    "id": "ABC123",
                    "type": "page",
                    "url": "https://x.com/otro/status/999",
                }
            ],
        ), patch.object(
            self.mod,
            "_cdp_text",
            side_effect=lambda path: close_calls.append(path),
        ):
            with self.assertRaisesRegex(RuntimeError, "ha navegado"):
                self.mod._close_target_explicit("ABC123", approved)

        self.assertEqual(close_calls, [])

    def test_close_aborts_if_target_missing_or_duplicated(self):
        approved = "https://x.com/lector/status/123"
        for targets in (
            [],
            [
                {"id": "ABC", "type": "page", "url": approved},
                {"id": "ABC", "type": "page", "url": approved},
            ],
        ):
            with self.subTest(targets=targets), \
                 patch.object(self.mod, "_page_targets", return_value=targets), \
                 patch.object(self.mod, "_cdp_text") as close:
                with self.assertRaisesRegex(
                    RuntimeError, "no encontrado o ambiguo"
                ):
                    self.mod._close_target_explicit("ABC", approved)
                close.assert_not_called()

    def test_close_aborts_if_current_url_no_longer_approved(self):
        original = "https://x.com/lector/status/123"
        current = "https://example.com/trabajo"
        with patch.object(
            self.mod,
            "_page_targets",
            return_value=[{"id": "ABC", "type": "page", "url": current}],
        ), patch.object(self.mod, "_cdp_text") as close:
            with self.assertRaisesRegex(RuntimeError, "ha navegado"):
                self.mod._close_target_explicit("ABC", original)
            close.assert_not_called()

    def test_close_requires_cdp_confirmation_text(self):
        approved = "https://x.com/lector/status/123"
        with patch.object(
            self.mod,
            "_page_targets",
            return_value=[
                {"id": "ABC", "type": "page", "url": approved}
            ],
        ), patch.object(
            self.mod, "_cdp_text", return_value="respuesta inesperada"
        ):
            with self.assertRaisesRegex(RuntimeError, "no confirmó"):
                self.mod._close_target_explicit("ABC", approved)

    def test_page_targets_rejects_non_list_response(self):
        with patch.object(self.mod, "_cdp_json", return_value={"oops": True}):
            with self.assertRaisesRegex(RuntimeError, "no devolvió una lista"):
                self.mod._page_targets()


if __name__ == "__main__":
    unittest.main()
