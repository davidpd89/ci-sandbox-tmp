"""Synthetic, hermetic chronological replay tests. No real users or network."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import discovery_replay as replay

TRAIN_DAY = dt.date(2026, 10, 9)
FUTURE_DAY = dt.date(2026, 10, 20)


def cohort(key, n, yes, *, network="bluesky", future=False, **overrides):
    row = dict(network=network, source_key=f"{key:024x}",
               eligible_unique=n, following_now=yes,
               unique_actors_verified=True, source_provenance_verified=True,
               source_policy_approved=True, follow_status_verified=True,
               snapshot_complete=True, outcome_kind="follows_us_at_snapshot",
               cohort_start="2026-10-11" if future else "2026-09-26",
               cohort_end="2026-10-13" if future else "2026-10-01",
               snapshot_on="2026-10-20" if future else "2026-10-09")
    row.update(overrides)
    return row


def run(train, future, **kwargs):
    return replay.compare_rankings(train, future, train_as_of=TRAIN_DAY,
                                  holdout_as_of=FUTURE_DAY, **kwargs)


class ReplayTests(unittest.TestCase):
    def test_naive_tiny_perfect_sample_loses_on_synthetic_holdout(self):
        train = [cohort(1, 2, 2), cohort(2, 100, 35)]
        holdout = [cohort(1, 100, 5, future=True),
                   cohort(2, 100, 50, future=True)]
        r = run(train, holdout)["networks"]["bluesky"]
        self.assertEqual(r["status"], "evaluated")
        self.assertEqual(r["baseline_source_keys"], [f"{1:024x}"])
        self.assertEqual(r["conservative_source_keys"], [f"{2:024x}"])
        self.assertAlmostEqual(r["raw_rate_at_k"], 0.05)
        self.assertAlmostEqual(r["conservative_at_k"], 0.5)
        self.assertAlmostEqual(r["difference"], 0.45)

    def test_not_guaranteed_to_win(self):
        t = [cohort(1, 2, 2), cohort(2, 100, 35)]
        h = [cohort(1, 100, 80, future=True),
             cohort(2, 100, 10, future=True)]
        self.assertLess(run(t, h)["networks"]["bluesky"]["difference"], 0)

    def test_order_independent_and_no_cross_network_pool(self):
        t = [cohort(1, 2, 2), cohort(2, 100, 35),
             cohort(1, 90, 45, network="mastodon")]
        h = [cohort(1, 100, 5, future=True),
             cohort(2, 100, 50, future=True),
             cohort(1, 90, 50, network="mastodon", future=True)]
        a = run(t, h)["networks"]
        b = run(list(reversed(t)), list(reversed(h)))["networks"]
        self.assertEqual(a, b)
        self.assertEqual(a["mastodon"]["status"], "evaluated")
        self.assertEqual(a["mastodon"]["difference"], 0)
        self.assertEqual(a["instagram"]["status"], "snapshot_not_instrumented")
        self.assertEqual(len(a), 9)

    def test_empty_holdout_is_unknown_not_zero(self):
        result = run([cohort(1, 100, 40)],
                     [cohort(1, 0, 0, future=True)])["networks"]["bluesky"]
        self.assertEqual(result["status"], "invalid_or_incomplete_cohort")
        self.assertIsNone(result["difference"])

    def test_missing_holdout_never_becomes_zero(self):
        r = run([cohort(1, 2, 2), cohort(2, 100, 35)],
                [cohort(2, 100, 40, future=True)])["networks"]["bluesky"]
        self.assertEqual(r["status"], "missing_holdout")
        self.assertIsNone(r["difference"])

    def test_partial_future_and_duplicate_excluded(self):
        t = [cohort(1, 100, 30)]
        for h in ([cohort(1, 100, 25, future=True, snapshot_complete=False)],
                  [cohort(1, 100, 25, future=True)] * 2,
                  [cohort(1, 100, 25, future=True, source_key="raw_handle")]):
            with self.subTest(holdout=h):
                r = run(t, h)["networks"]["bluesky"]
                self.assertEqual(r["status"], "invalid_or_incomplete_cohort")
                self.assertIsNone(r["raw_rate_at_k"])

    def test_future_not_same_as_training_snapshot(self):
        t = [cohort(1, 100, 40)]
        h = [cohort(1, 100, 40, future=True, cohort_start="2026-10-09")]
        r = run(t, h)["networks"]["bluesky"]
        self.assertEqual(r["status"], "overlapping_or_nonchronological_holdout")

    def test_small_only_is_not_a_result(self):
        r = run([cohort(1, 2, 2)],
                [cohort(1, 100, 50, future=True)])["networks"]["bluesky"]
        self.assertEqual(r["status"], "no_mature_train_cohorts")
        self.assertIsNone(r["difference"])

    def test_fixed_top_k_not_silent_truncation(self):
        r = run([cohort(1, 100, 50)], [cohort(1, 100, 55, future=True)],
                top_k=2)["networks"]["bluesky"]
        self.assertEqual(r["status"], "insufficient_candidates_for_k")

    def test_source_token_only_no_handles_or_queries(self):
        t = [cohort(1, 100, 50, raw_handle="@Someone")]
        h = [cohort(1, 100, 55, future=True, raw_query="fantasía")]
        self.assertNotIn("Someone", repr(run(t, h)))
        self.assertNotIn("fantasía", repr(run(t, h)))

    def test_malformed_unscoped_future_fails_instead_of_misreporting(self):
        with self.assertRaises(ValueError):
            run([cohort(1, 100, 50)],
                [cohort(1, 100, 55, future=True), {"source_key": "unscoped"}])

    def test_immutable_inputs_and_validation(self):
        t = [cohort(1, 100, 50)]
        h = [cohort(1, 100, 50, future=True)]
        before = repr((t, h))
        run(t, h)
        self.assertEqual(before, repr((t, h)))
        for kw in (dict(top_k=0), dict(top_k=True), dict(min_sample=True),
                   dict(min_sample=1), dict(top_k=101),
                   dict(train_as_of=FUTURE_DAY),
                   dict(holdout_as_of=TRAIN_DAY)):
            with self.subTest(kw=kw):
                arguments = dict(train_as_of=TRAIN_DAY, holdout_as_of=FUTURE_DAY)
                arguments.update(kw)
                with self.assertRaises(ValueError):
                    replay.compare_rankings(t, h, **arguments)


if __name__ == "__main__":
    unittest.main()
