"""Contratos del ciclo followback: 9 redes, fechas inyectadas, cero red."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import followback_lifecycle as lc

TODAY = dt.date(2026, 10, 10)


def row(handle, date, kind="follow", result="confirmado", network=None):
    r = {"cuenta": handle, "fecha": date, "tipo": kind, "resultado": result}
    if network:
        r["red"] = network
    return r


class LifecycleTests(unittest.TestCase):
    def calc(self, net, rows, *, followers=(), following=("ana",),
             followers_complete=False, following_complete=True):
        return lc.replay(rows, network=net, today=TODAY, followers=followers,
                         following=following, followers_complete=followers_complete,
                         following_complete=following_complete)["ana"]

    def test_nine_networks_share_state_contract(self):
        for net in lc.NETWORKS:
            with self.subTest(network=net):
                recent = [row("@ANA", "2026-10-07")]
                old = [row("@ANA", "2026-09-30")]
                self.assertEqual(self.calc(net, recent)["state"], "waiting")
                self.assertEqual(self.calc(net, old)["state"], "due_unverified")
                self.assertEqual(self.calc(net, old, followers=("ANA",))["state"], "reciprocal")
                due = self.calc(net, old, followers_complete=True)
                self.assertEqual(due["state"], "eligible")
                self.assertTrue(due["eligible"])
                self.assertEqual(self.calc(net, old, following=(),
                                           followers_complete=True)["state"], "not_following")

    def test_negative_partial_snapshot_not_evidence_and_is_not_eligible(self):
        result = self.calc("threads", [row("ana", "2026-10-01")])
        self.assertEqual(result["observed_back"], None)
        self.assertFalse(result["eligible"])
        self.assertEqual(self.calc("threads", [row("ana", "2026-10-01")],
                                   following=("ana",), following_complete=False,
                                   followers_complete=True)["state"], "eligible")

    def test_follow_requested_is_not_a_confirmed_follow(self):
        result = self.calc("tiktok", [row("ana", "2026-10-01", result="pendiente_aprobacion")],
                           followers_complete=True)
        self.assertEqual(result["state"], "pending_approval")
        self.assertIsNone(result["age_days"])
        self.assertFalse(result["eligible"])

    def test_unfollow_and_refollow_reset_clock_and_cycle_count(self):
        rows = [row("ana", "2026-09-01"),
                row("ana", "2026-09-10", "unfollow"),
                row("ana", "2026-10-07", "follow")]
        result = self.calc("bluesky", rows, followers_complete=True)
        self.assertEqual(result["state"], "waiting")
        self.assertEqual(result["age_days"], 3)
        self.assertEqual(result["follow_cycles"], 2)

    def test_late_reciprocity_then_loss(self):
        rows = [row("ana", "2026-09-20"),
                row("ana", "2026-09-23", "followback_observed"),
                row("ana", "2026-10-08", "followback_lost")]
        result = self.calc("mastodon", rows)
        self.assertEqual(result["state"], "lost_followback")
        self.assertTrue(result["eligible"])
        self.assertEqual(self.calc("mastodon", rows, followers=("ana",))["state"], "reciprocal")

    def test_conversation_retains_review_not_automated_eligibility(self):
        result = self.calc("x", [row("ana", "2026-09-01"),
                                row("ana", "2026-09-05", "reply")],
                           followers_complete=True)
        self.assertEqual(result["state"], "engaged_review")
        self.assertFalse(result["eligible"])

    def test_manual_follow_without_confirmed_age_not_marked_due(self):
        result = self.calc("instagram", [], followers_complete=True)
        self.assertEqual(result["state"], "manual_unknown_age")
        self.assertIsNone(result["since"])

    def test_bad_and_future_events_do_not_modify_state(self):
        rows = [row("ana", "2026-10-30"),
                row("ana", "garbled"),
                row("ana", "2026-09-01", result="fallo"),
                row("ana", "2026-10-01", "unfollow", result="fallo")]
        self.assertEqual(self.calc("pinterest", rows)["state"], "manual_unknown_age")

    def test_network_rows_are_isolated_and_mastodon_server_is_preserved(self):
        out = lc.replay([row("@Ana@example.com", "2026-09-01", network="mastodon"),
                         row("@Ana@example.org", "2026-10-08", network="mastodon"),
                         row("@Ana@example.com", "2026-10-07", network="x")],
                        network="mastodon", today=TODAY,
                        following=("ana@example.com", "ana@example.org"),
                        followers=("ana@example.org",), followers_complete=True)
        self.assertEqual(out["ana@example.com"]["state"], "eligible")
        self.assertEqual(out["ana@example.org"]["state"], "reciprocal")
        self.assertNotIn("ana", out)

    def test_ambiguous_current_following_cannot_be_eligible(self):
        result = self.calc("reddit", [row("ana", "2026-09-01")],
                           followers_complete=True, following=(),
                           following_complete=False)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["state"], "due_unverified")

    def test_clocks_and_negative_grace_are_validated(self):
        with self.assertRaises(ValueError):
            lc.replay([], network="mastodon", today=TODAY, grace_days=-1)
        with self.assertRaises(TypeError):
            lc.replay([], network="x", today=dt.datetime.now())

    def test_declared_wiring_does_not_claim_all_nine_are_automated(self):
        fake_pipes = {"bluesky": {"post": [("python", "tools/unfollow_cleanup.py", "bluesky", "--apply")]},
                      "tiktok": {"post": [("python", "tools/tiktok_reciprocity_audit.py")]}}
        matrix = lc.coverage(pipelines=fake_pipes, cleanup_adapters={"bluesky": object()})
        self.assertEqual(tuple(matrix), lc.NETWORKS)
        self.assertTrue(matrix["bluesky"]["cleanup_scheduled"])
        self.assertFalse(matrix["tiktok"]["cleanup_scheduled"])
        self.assertEqual(matrix["tiktok"]["channel"], "MOBILE")
        self.assertIsNone(matrix["instagram"]["followback_source"])


if __name__ == "__main__":
    unittest.main()
