"""Regression: combined follow and reply must retain conversational protection."""
import datetime as dt
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import followback_lifecycle as lifecycle
import follow_review
import unfollow_cleanup

TODAY = dt.date(2026, 10, 10)


def event(kind, when="2026-09-01"):
    return {"cuenta": "@ana", "fecha": when, "tipo": kind, "resultado": "confirmado"}


class CombinedFollowReplyTests(unittest.TestCase):
    def test_nine_networks_keep_conversation_for_combined_event(self):
        for network in lifecycle.NETWORKS:
            for kind in ("follow+reply", "reply+follow"):
                with self.subTest(network=network, kind=kind):
                    result = lifecycle.replay(
                        [event(kind)], network=network, today=TODAY,
                        following=["ana"], followers=[], followers_complete=True,
                        following_complete=True,
                    )["ana"]
                    self.assertEqual(result["state"], "engaged_review")
                    self.assertTrue(result["has_conversation"])
                    self.assertFalse(result["eligible"])
                    self.assertEqual(result["follow_cycles"], 1)

    def test_old_conversation_does_not_survive_new_cycle(self):
        rows = [event("follow+reply"), event("unfollow", "2026-09-20"),
                event("follow", "2026-09-22")]
        result = lifecycle.replay(
            rows, network="mastodon", today=TODAY,
            following=["ana"], followers=[], followers_complete=True,
            following_complete=True,
        )["ana"]
        self.assertEqual(result["state"], "eligible")
        self.assertFalse(result["has_conversation"])
        self.assertEqual(result["age_days"], 18)

    def test_cleanup_and_review_also_respect_combined_event(self):
        rows = [event("follow+reply")]
        reviewed = follow_review.review(rows, [], TODAY, days=7, network="bluesky")
        self.assertEqual(reviewed[0]["actions"], "reply")
        with mock.patch.object(unfollow_cleanup, "protected_accounts", return_value=set()):
            candidates = unfollow_cleanup.candidates(
                rows, [], TODAY, following={"ana": ""}, network="bluesky"
            )
        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
