"""Permalinks Bluesky: no aceptar dominios impostores ni URLs con basura final."""
import ast
import pathlib
import urllib.parse
import re
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "bluesky_interact.py"


class BlueskyPostURLTests(unittest.TestCase):
    def setUp(self):
        node = next(n for n in ast.parse(SOURCE.read_text(encoding="utf-8")).body
                    if isinstance(n, ast.FunctionDef) and n.name == "_url_to_uri")
        self.env = {
            "re": re, "urllib": urllib,
            "_resolve_did": lambda actor: "did:plc:abcdefghij234567" if actor == "lectora.bsky.social" else actor,
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), self.env)

    def test_exact_permalinks(self):
        fn = self.env["_url_to_uri"]
        expected = "at://did:plc:abcdefghij234567/app.bsky.feed.post/3abc"
        self.assertEqual(fn("https://bsky.app/profile/lectora.bsky.social/post/3abc"), expected)
        self.assertEqual(fn(expected), expected)

    def test_rejects_noncanonical_urls(self):
        fn = self.env["_url_to_uri"]
        for value in (
            "https://evil.example/bsky.app/profile/lectora.bsky.social/post/3abc",
            "https://bsky.app.evil.example/profile/lectora.bsky.social/post/3abc",
            "http://bsky.app/profile/lectora.bsky.social/post/3abc",
            "https://bsky.app@evil.example/profile/lectora.bsky.social/post/3abc",
            "https://bsky.app/profile/lectora.bsky.social/post/3abc/extra",
            "https://bsky.app/profile/lectora.bsky.social/post/3abc?redirect=evil",
            "at://did:plc:abcdefghij234567/app.bsky.feed.like/3abc",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fn(value)


if __name__ == "__main__":
    unittest.main()
