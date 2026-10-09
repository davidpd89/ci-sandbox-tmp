import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import round_queue as q


class NextWebTest(unittest.TestCase):
    def test_picks_largest_remaining_fraction(self):
        targets = {"x": 8, "threads": 10, "facebook": 6, "pinterest": 5}
        self.assertEqual(q.next_web({}, targets), "x")
        self.assertEqual(q.next_web({"x": 1}, targets), "threads")
        self.assertEqual(q.next_web({"x": 1, "threads": 1}, targets), "facebook")
        self.assertIsNone(q.next_web({"x": 8, "threads": 10, "facebook": 6, "pinterest": 5}, targets))

    def test_summary_regex(self):
        found = q.SUMMARY.findall("[x] 41 confirmadas {'like': 38, 'repost': 3}, 9 saltadas, 1 fallos")
        self.assertEqual(found[0][1], "41")
        self.assertEqual(found[0][4], "1")


if __name__ == "__main__":
    unittest.main()


class RepostPolicyTests(unittest.TestCase):
    def test_only_curated_and_capped(self):
        import repost_policy as rp
        plan = [{"kind": "like"}, {"kind": "repost", "curated": False}, {"kind": "repost", "curated": True}, {"kind": "boost", "curated": True},
                {"kind": "quote", "curated": True}, {"kind": "repost", "curated": True}]
        kept, dropped = rp.filter_plan(plan, already=1)
        self.assertEqual([i["kind"] for i in kept], ["like", "repost", "boost"])
        self.assertEqual(dropped, 3)
        self.assertEqual(rp.filter_plan([{"kind": "repost", "curated": True}], already=3)[0], [])
