"""mastodon_auto_decide.py (02/10): follow/favourite/boost mecanico, reply aparte."""
import sys
import pathlib
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import mastodon_auto_decide as ad


class AutoDecideTests(unittest.TestCase):
    def test_follow_and_favourite_go_straight_to_actions_boost_does_not(self):
        state = {"shortlist": [{
            "id": "M001", "acct": "autora1", "lane": "community", "score": 5.0,
            "actions": ["follow"],
            "posts": [{"id": "M001-P1", "url": "https://x/1", "text": "hola",
                       "actions": ["favourite", "boost"]}],
        }]}
        actions, reply_pending, boost_pending = ad.build(state)
        kinds = sorted((a.get("candidate") or a.get("post"), a["kind"]) for a in actions)
        self.assertEqual(kinds, [("M001", "follow"), ("M001-P1", "favourite")])
        self.assertEqual(reply_pending, [])
        self.assertEqual(len(boost_pending), 1)
        self.assertEqual(boost_pending[0]["post"], "M001-P1")

    def test_cold_follow_only_if_in_follow_pool(self):
        cold = {"id": "M010", "acct": "fria", "lane": "acquisition", "score": 1.0,
                "actions": ["follow"], "posts": []}
        pooled = {"id": "M011", "acct": "buena", "lane": "acquisition", "score": 1.0,
                  "actions": ["follow"], "posts": []}
        state = {"shortlist": [cold, pooled],
                 "follow_pool": [{"acct": "buena"}, {"acct": "otra"}]}
        actions, _, _ = ad.build(state)
        self.assertEqual(
            actions,
            [{"candidate": "M011", "kind": "follow"}, {"account": "otra", "kind": "follow"}],
        )

    def test_cap_counts_pool_members_found_in_the_shortlist_too(self):
        shortlist = [{"id": f"M{i:03d}", "acct": f"u{i}", "lane": "acquisition", "score": 1.0,
                      "actions": ["follow"], "posts": []} for i in range(5)]
        state = {"shortlist": shortlist, "follow_pool": [{"acct": f"u{i}"} for i in range(10)]}
        actions, _, _ = ad.build(state, max_pool_follows=3)
        self.assertEqual(sum(1 for a in actions if a["kind"] == "follow"), 3)
        community = [{"id": "M100", "acct": "amiga", "lane": "community", "score": 1.0,
                      "actions": ["follow"], "posts": []}]
        actions, _, _ = ad.build({"shortlist": community + shortlist, "follow_pool": state["follow_pool"]}, max_pool_follows=3)
        self.assertEqual(sum(1 for a in actions if a["kind"] == "follow"), 4)  # comunidad no cuenta contra el tope

    def test_pool_follows_are_capped(self):
        state = {"shortlist": [],
                 "follow_pool": [{"acct": f"u{i}"} for i in range(10)]}
        actions, _, _ = ad.build(state, max_pool_follows=3)
        self.assertEqual(len(actions), 3)

    def test_reply_never_auto_decided(self):
        state = {"shortlist": [{
            "id": "M002", "acct": "lector1", "lane": "community", "score": 3.0,
            "actions": [],
            "posts": [{"id": "M002-P1", "url": "https://x/2", "text": "hola?",
                       "actions": ["reply"]}],
        }]}
        actions, reply_pending, boost_pending = ad.build(state)
        self.assertEqual(actions, [])
        self.assertEqual(len(reply_pending), 1)
        self.assertEqual(reply_pending[0]["post"], "M002-P1")
        self.assertEqual(boost_pending, [])

    def test_reply_candidates_sorted_by_score_descending(self):
        state = {"shortlist": [
            {"id": "M003", "acct": "a", "lane": "community", "score": 1.0, "actions": [],
             "posts": [{"id": "M003-P1", "url": "u1", "text": "t1", "actions": ["reply"]}]},
            {"id": "M004", "acct": "b", "lane": "community", "score": 9.0, "actions": [],
             "posts": [{"id": "M004-P1", "url": "u2", "text": "t2", "actions": ["reply"]}]},
        ]}
        _, reply_pending, _ = ad.build(state)
        self.assertEqual([row["post"] for row in reply_pending], ["M004-P1", "M003-P1"])


if __name__ == "__main__":
    unittest.main()
