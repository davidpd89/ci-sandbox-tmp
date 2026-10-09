import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import starterpack_review as sr

TODAY = datetime.date(2026, 10, 3)


class ClassifyMemberTests(unittest.TestCase):
    def test_active(self):
        self.assertEqual(sr.classify_member({"handle": "a.bsky.social"}, "2026-09-20T10:00:00.000Z", TODAY)[0], "ok")

    def test_inactive(self):
        state, detail = sr.classify_member({"handle": "a.bsky.social"}, "2026-06-01T10:00:00.000Z", TODAY)
        self.assertEqual(state, "inactivo")
        self.assertIn("dias", detail)

    def test_no_posts_and_unresolved(self):
        self.assertEqual(sr.classify_member({"handle": "a.bsky.social"}, None, TODAY)[0], "sin_posts")
        self.assertEqual(sr.classify_member({"handle": "x.invalid"}, None, TODAY)[0], "no_resuelve")
        self.assertEqual(sr.classify_member(None, None, TODAY)[0], "no_resuelve")

    def test_unreadable_date(self):
        self.assertEqual(sr.classify_member({"handle": "a"}, "basura", TODAY)[0], "sin_posts")


if __name__ == "__main__":
    unittest.main()
