"""Bluesky: facets UTF-8 y filtros de búsqueda oficiales, sin red real."""
import ast
import pathlib
import re
import types
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "bluesky_interact.py"


def load_functions(names):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    wanted = set(names) | {"_raise_if_rate_limited"}
    nodes = [
        n for n in tree.body
        if (
            isinstance(n, ast.FunctionDef) and n.name in wanted
        ) or (
            isinstance(n, ast.ClassDef) and n.name == "RateLimitExceeded"
        )
    ]
    env = {"re": re, "requests": types.SimpleNamespace(), "PUBLIC_BASE": "https://public.api.bsky.app/xrpc",
           "AUTH_BASE": "https://bsky.social/xrpc"}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), env)
    return env


class RichTextTests(unittest.TestCase):
    def test_hashtag_and_url_get_utf8_facets(self):
        env = load_functions({"_utf8_slice", "_richtext_facets"})
<<<<<<< HEAD
        text = "Fantasía #BookSky https://autorademodiaz.com/libro/."
=======
        text = "Fantasía #BookSky https://davidportodiaz.com/libro/."
>>>>>>> origin/research/public-reuse-parent
        facets = env["_richtext_facets"](text)
        self.assertEqual(len(facets), 2)
        tag = next(f for f in facets if f["features"][0]["$type"].endswith("#tag"))
        link = next(f for f in facets if f["features"][0]["$type"].endswith("#link"))
        self.assertEqual(tag["features"][0]["tag"], "BookSky")
<<<<<<< HEAD
        self.assertEqual(link["features"][0]["uri"], "https://autorademodiaz.com/libro/")
=======
        self.assertEqual(link["features"][0]["uri"], "https://davidportodiaz.com/libro/")
>>>>>>> origin/research/public-reuse-parent
        start = tag["index"]["byteStart"]
        end = tag["index"]["byteEnd"]
        self.assertEqual(text.encode("utf-8")[start:end].decode("utf-8"), "#BookSky")

    def test_real_handle_mention_becomes_did_facet(self):
        env = load_functions({
            "_utf8_slice", "_richtext_facets", "_mention_facets", "_add_richtext"
        })
        env["_resolve_did"] = lambda handle: (
            "did:plc:reader123" if handle == "lectora.bsky.social" else None
        )
        record = env["_add_richtext"]({
            "text": "Gracias @lectora.bsky.social por leer #BookSky"
        })
        features = [
            feature
            for facet in record["facets"]
            for feature in facet["features"]
        ]
        mention = next(
            feature for feature in features
            if feature["$type"].endswith("#mention")
        )
        self.assertEqual(mention["did"], "did:plc:reader123")

    def test_unresolvable_handle_fails_closed(self):
        env = load_functions({
            "_utf8_slice", "_richtext_facets", "_mention_facets", "_add_richtext"
        })
        env["_resolve_did"] = lambda handle: (_ for _ in ()).throw(
            RuntimeError("sin DID")
        )
        with self.assertRaisesRegex(RuntimeError, "No se pudo resolver"):
            env["_add_richtext"]({"text": "Hola @noexiste.bsky.social"})

    def test_hash_fragment_inside_url_is_not_tag(self):
        env = load_functions({"_utf8_slice", "_richtext_facets"})
        facets = env["_richtext_facets"]("https://ejemplo.es/#capitulo #Lectura")
        tags = [f["features"][0]["tag"] for f in facets
                if f["features"][0]["$type"].endswith("#tag")]
        self.assertEqual(tags, ["Lectura"])


class SearchTests(unittest.TestCase):
    def test_get_merges_custom_headers_without_credentials(self):
        env = load_functions({"_get", "_headers"})
        env["APP_PASSWORD"] = ""
        env["_session_cache"] = {}
        captured = {}

        class Resp:
            status_code = 200
            text = ""
            headers = {}
            def json(self):
                return {"ok": True}

        def fake_get(url, params=None, headers=None, timeout=None):
            captured.update({
                "url": url,
                "headers": dict(headers or {}),
                "params": params,
            })
            return Resp()

        env["requests"] = types.SimpleNamespace(get=fake_get)
        env["get_with_retry"] = lambda url, **kwargs: fake_get(url, **kwargs)  # reintentos: ver test_http_retry
        out = env["_get"](
            "https://example.invalid/xrpc",
            "app.bsky.unspecced.getSuggestedUsersForExplore",
            {"limit": 10},
            auth=False,
            extra_headers={
                "Accept-Language": "es",
                "x-atproto-bsky-topics": "books,fantasy",
            },
        )
        self.assertEqual(out, {"ok": True})
        self.assertEqual(captured["headers"]["Accept-Language"], "es")
        self.assertEqual(
            captured["headers"]["x-atproto-bsky-topics"],
            "books,fantasy",
        )

    def test_advanced_filters_are_sent_to_public_appview(self):
        env = load_functions({"_search_posts"})
        captured = {}
        class Resp:
            status_code = 200
            text = ""
            def json(self):
                return {"posts": [{"uri": "at://x"}]}
        def fake_get(url, params=None, timeout=None):
            captured.update({"url": url, "params": params, "timeout": timeout})
            return Resp()
        env["requests"] = types.SimpleNamespace(get=fake_get)
        out = env["_search_posts"](
            "fantasía", "es", 20, tag=["BookSky"], sort="top",
<<<<<<< HEAD
            domain="autorademodiaz.com", author="autor.bsky.social",
=======
            domain="davidportodiaz.com", author="autor.bsky.social",
>>>>>>> origin/research/public-reuse-parent
            since="2026-09-01",
        )
        self.assertEqual(out, [{"uri": "at://x"}])
        self.assertEqual(captured["params"]["tag"], ["BookSky"])
        self.assertEqual(captured["params"]["sort"], "top")
<<<<<<< HEAD
        self.assertEqual(captured["params"]["domain"], "autorademodiaz.com")
=======
        self.assertEqual(captured["params"]["domain"], "davidportodiaz.com")
>>>>>>> origin/research/public-reuse-parent
        self.assertEqual(captured["params"]["author"], "autor.bsky.social")
        self.assertEqual(captured["params"]["since"], "2026-09-01")

    def test_public_search_429_is_a_stop_not_a_fallback(self):
        env = load_functions({"_search_posts"})
        class Resp:
            status_code = 429
            text = "rate limited"
            headers = {"Retry-After": "12"}
        env["requests"] = types.SimpleNamespace(get=lambda *a, **k: Resp())
        env["_require_credentials"] = lambda: self.fail(
            "429 no debe degradarse a búsqueda autenticada"
        )
        with self.assertRaises(env["RateLimitExceeded"]):
            env["_search_posts"]("libros")

    def test_public_auth_failure_falls_back_once_to_authenticated_search(self):
        env = load_functions({"_search_posts"})
        class Resp:
            status_code = 403
            text = "forbidden"
        env["requests"] = types.SimpleNamespace(get=lambda *a, **k: Resp())
        calls = []
        env["_require_credentials"] = lambda: calls.append("credentials")
        env["_get"] = lambda base, path, params, auth: calls.append(
            (base, path, params, auth)) or {"posts": ["ok"]}
        self.assertEqual(env["_search_posts"]("libros"), ["ok"])
        self.assertEqual(calls[0], "credentials")
        self.assertEqual(calls[1][1], "app.bsky.feed.searchPosts")


if __name__ == "__main__":
    unittest.main()
