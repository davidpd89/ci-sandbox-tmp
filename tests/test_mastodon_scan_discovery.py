"""El scan Mastodon conserva identidad federada y falla suave en search."""
import contextlib
import io
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

# CI offline no instala dependencias HTTP/navegador. El módulo ya dependía de
# requests en producción; aquí se stubbea para que las pruebas sigan siendo
# puramente locales y no oculten llamadas reales.
requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: None
requests_stub.post = lambda *a, **k: None
requests_stub.delete = lambda *a, **k: None
x_stub = types.ModuleType("x_interact")
x_stub._check_spanish_orthography = lambda text: None
sys.modules.setdefault("requests", requests_stub)
sys.modules.setdefault("x_interact", x_stub)
import mastodon_scan as scan


class MastodonScanTests(unittest.TestCase):
    def test_remote_acct_is_not_truncated_to_local_username(self):
        remote = {
            "id": "123",
            "url": "https://example.social/@lectora/999",
            "content": "<p>¿Qué fantasía juvenil estás leyendo?</p>",
            "account": {"acct": "lectora@example.social"},
        }
        with patch.object(scan.m, "health"), \
             patch.object(scan.m, "get_notifications_data", return_value=[]), \
             patch.object(scan.m, "get_follow_notifications_data", return_value=[]), \
             patch.object(scan, "_rotate_hashtags", return_value=["Bookstodon"]), \
             patch.object(scan.m, "get_hashtag_statuses", return_value=[remote]), \
             patch.object(scan, "_rotate_searches", return_value=[]), \
             patch.object(scan.m, "trending_tags", return_value=[]), \
             patch.object(scan.m, "search", return_value={"statuses": []}), \
             patch.object(scan.sc, "known_accounts", return_value={}), \
             patch.object(scan.sc, "discarded_handles", return_value=set()), \
             patch.object(scan.sc, "is_political", return_value=False), \
             patch.object(scan.sc, "invites_conversation", return_value=True), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            scan.scan()
        self.assertIn("@lectora@example.social", output.getvalue())
        self.assertNotIn("@lectora |", output.getvalue())

    def test_status_search_failure_does_not_hide_hashtag_results(self):
        local = {
            "id": "124",
            "url": "https://mastodon.social/@lector/124",
            "content": "<p>Novela fantástica</p>",
            "account": {"acct": "lector"},
        }
        def search(query, kind=None, limit=20, **kwargs):
            if query == "autorademodiaz.com":
                return {"statuses": []}
            raise RuntimeError("indice no disponible")
        with patch.object(scan.m, "health"), \
             patch.object(scan.m, "get_notifications_data", return_value=[]), \
             patch.object(scan.m, "get_follow_notifications_data", return_value=[]), \
             patch.object(scan, "_rotate_hashtags", return_value=["Libros"]), \
             patch.object(scan.m, "get_hashtag_statuses", return_value=[local]), \
             patch.object(scan, "_rotate_searches", return_value=["fantasía juvenil"]), \
             patch.object(scan.m, "trending_tags", return_value=[]), \
             patch.object(scan.m, "search", side_effect=search), \
             patch.object(scan.sc, "known_accounts", return_value={}), \
             patch.object(scan.sc, "discarded_handles", return_value=set()), \
             patch.object(scan.sc, "is_political", return_value=False), \
             patch.object(scan.sc, "invites_conversation", return_value=False), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            scan.scan()
        text = output.getvalue()
        self.assertIn("AVISO search", text)
        self.assertIn("@lector", text)


if __name__ == "__main__":
    unittest.main()
