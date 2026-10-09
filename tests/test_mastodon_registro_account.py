"""mastodon_execute._registro_account (02/10): cuenta correcta en status puenteados."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import mastodon_execute as me


class RegistroAccountTests(unittest.TestCase):
    def test_follow_uses_handle(self):
        self.assertEqual(me._registro_account({"kind": "follow", "handle": "@ana@x.social"}), "ana@x.social")

    def test_mastodon_url_keeps_previous_behaviour(self):
        r = {"kind": "reply", "handle": "ana@x.social", "url": "https://x.social/@ana/123"}
        self.assertEqual(me._registro_account(r), "ana")

    def test_bridged_blog_url_falls_back_to_handle_not_https(self):
        r = {"kind": "favourite", "handle": "blog.com@blog.com", "url": "https://blog.com/2026/09/post/"}
        self.assertEqual(me._registro_account(r), "blog.com@blog.com")


if __name__ == "__main__":
    unittest.main()
