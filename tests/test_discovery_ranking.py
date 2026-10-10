"""Standalone synthetic ranking tests: no network, files, env or live accounts."""
import datetime as dt
import pathlib
import sys
import unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import discovery_ranking as rank


TODAY = dt.date(2026, 10, 9)


def ranking(cohorts, **opts):
    opts.setdefault("as_of", TODAY)
    return rank.rank_cohorts(cohorts, **opts)


def row(network="bluesky", key=1, n=100, back=20, **changes):
    d = {"network": network, "source_key": f"{key:024x}",
         "eligible_unique": n, "following_now": back,
         "outcome_kind": "follows_us_at_snapshot", "unique_actors_verified": True,
         "source_provenance_verified": True, "source_policy_approved": True,
         "follow_status_verified": True,
         "snapshot_complete": True, "cohort_start": "2026-09-26",
         "cohort_end": "2026-10-01",
         "snapshot_on": "2026-10-09"}
    d.update(changes)
    return d


class RankingTests(unittest.TestCase):
    def test_tiny_perfect_source_never_outranks_mature_sample(self):
        result = ranking([row(key=1, n=2, back=2), row(key=2, n=100, back=40)])
        net = result["networks"]["bluesky"]
        self.assertEqual([x["source_key"] for x in net["ranked"]], [f"{2:024x}"])
        self.assertEqual(net["unranked"][0]["reason"], "insufficient_sample")

    def test_score_is_conservative_and_tie_order_is_stable(self):
        data = [row(key=3), row(key=2), row(key=1, n=100, back=70)]
        report = ranking(data)["networks"]["bluesky"]["ranked"]
        self.assertEqual([x["source_key"] for x in report], [f"{1:024x}", f"{2:024x}", f"{3:024x}"])
        self.assertLess(report[0]["lower_bound"], report[0]["observed_rate"])

    def test_exploration_slots_are_reserved_not_actions(self):
        r = ranking([row()], scan_slots={"bluesky": 11, "mastodon": 1})
        self.assertEqual(r["networks"]["bluesky"]["exploration_slots_reserved"], 3)
        self.assertEqual(r["networks"]["mastodon"]["exploration_slots_reserved"], 1)
        self.assertIsNone(r["networks"]["pinterest"]["ranking_slots_available"])
        self.assertNotIn("plan", repr(r))

    def test_two_networks_never_have_pooled_rates(self):
        r = ranking([row(), row("mastodon", 1, n=50, back=5)])
        self.assertEqual(len(r["networks"]["mastodon"]["ranked"]), 1)
        self.assertEqual(len(r["networks"]["bluesky"]["ranked"]), 1)
        self.assertEqual(r["networks"]["reddit"]["capability"], "not_instrumented")
        self.assertEqual(r["networks"]["instagram"]["capability"], "not_instrumented")

    def test_partial_and_unverified_are_never_interpreted_as_zero_successes(self):
        candidates = [row(key=1, snapshot_complete=False), row(key=2, unique_actors_verified=False),
                      row(key=3, outcome_kind="new_handles"), row(key=4, n=50, back=51),
                      row(key=5, cohort_end="2026-10-08"), row(key=6, n=0, back=0)]
        r = ranking(candidates)["networks"]["bluesky"]
        self.assertEqual(r["ranked"], [])
        self.assertEqual({x["reason"] for x in r["unranked"]},
                         {"snapshot_incomplete", "identity_unverified", "outcome_not_observed",
                          "invalid_denominator", "immature_or_invalid_date", "insufficient_sample"})

    def test_duplicate_source_fails_closed(self):
        r = ranking([row(), row(n=500, back=400)])["networks"]["bluesky"]
        self.assertEqual(r["ranked"], [])
        self.assertEqual(r["unranked"][0]["reason"], "duplicate_source_cohort")

    def test_no_raw_sources_and_all_networks_are_present(self):
        r = ranking([row(source_key="@personal"), row("threads")])
        self.assertEqual(set(r["networks"]), set(rank.NETWORKS))
        self.assertNotIn("@personal", repr(r))
        self.assertEqual(r["networks"]["threads"]["unranked"][0]["reason"],
                         "snapshot_adapter_unverified")

    def test_malformed_parameters_rejected(self):
        for kw in ({"min_sample": 0}, {"min_age_days": -1}, {"min_sample": True},
                   {"exploration_fraction": float("nan")}, {"exploration_fraction": 1.01},
                   {"scan_slots": {"x": -1}}, {"scan_slots": {"ghost": 20}},
                   {"scan_slots": {"bluesky": True}}):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError):
                    ranking([], **kw)

    def test_malformed_rows_are_not_successful(self):
        data = [None, [], "foo", {}, row(eligible_unique=True), row(following_now=False),
                row(snapshot_on="2026-99-99"), row(cohort_end="2026-10-10")]
        r = ranking(data)
        self.assertEqual(r["networks"]["bluesky"]["ranked"], [])
        self.assertEqual(r["rejected_without_network"], 4)

    def test_future_stale_and_clock_injection(self):
        self.assertEqual(ranking([row(snapshot_on="2026-10-10")],
            as_of=dt.date(2026, 10, 9))["networks"]["bluesky"]["unranked"][0]["reason"],
            "immature_or_invalid_date")
        self.assertEqual(ranking([row()], as_of=dt.date(2026, 10, 30))[
            "networks"]["bluesky"]["unranked"][0]["reason"], "stale_snapshot")
        self.assertEqual(len(ranking([row()], as_of=dt.date(2026, 10, 9))[
            "networks"]["bluesky"]["ranked"]), 1)

    def test_valid_and_invalid_duplicate_rejected_together(self):
        good, bad = row(), row(snapshot_complete=False)
        r = ranking([good, bad])["networks"]["bluesky"]
        self.assertEqual(r["ranked"], [])
        self.assertEqual(r["unranked"][0]["reason"], "duplicate_source_cohort")

    def test_provenance_and_follow_confirmation_required(self):
        sources = [row(key=3, source_provenance_verified=False),
                   row(key=4, follow_status_verified=False)]
        result = ranking(sources)["networks"]["bluesky"]
        self.assertEqual(result["ranked"], [])
        self.assertEqual({r["reason"] for r in result["unranked"]},
                         {"provenance_unverified", "follow_status_unverified"})

    def test_exploration_candidates_only_from_safe_small_cohorts(self):
        values = [row(key=1, n=2, back=2), row(key=2, n=5, back=4),
                  row(key=3, n=3, back=3, source_provenance_verified=False),
                  row(key=4, n=100, back=60)]
        result = ranking(values, scan_slots={"bluesky": 10},
                         exploration_cursor={"bluesky": 0})["networks"]["bluesky"]
        self.assertEqual(result["exploration_slots_reserved"], 2)
        self.assertEqual(result["exploration_candidates"], [f"{1:024x}", f"{2:024x}"])
        self.assertEqual(len(result["ranked"]), 1)

    def test_zero_exploration_never_requires_cursor(self):
        cases = (
            {"scan_slots": {"bluesky": 0}},
            {"scan_slots": {"bluesky": 10}, "exploration_fraction": 0},
        )
        for opts in cases:
            with self.subTest(opts=opts):
                net = ranking([row()], **opts)["networks"]["bluesky"]
                self.assertEqual(net["exploration_slots_reserved"], 0)
                self.assertFalse(net["exploration_cursor_required"])
                self.assertEqual(net["exploration_candidates"], [])

    def test_unreasonably_large_read_budget_rejected(self):
        with self.assertRaises(ValueError):
            ranking([], scan_slots={"bluesky": 10_001})

    def test_exposure_windows_must_be_comparable(self):
        values = [row(key=1), row(key=2, cohort_start="2026-09-28"),
                  row("mastodon", 3, n=60, back=20)]
        result = ranking(values)
        self.assertEqual(result["networks"]["bluesky"]["ranked"], [])
        self.assertEqual(
            [e["reason"] for e in result["networks"]["bluesky"]["unranked"]],
            ["incomparable_cohort_windows"] * 2)
        self.assertEqual(len(result["networks"]["mastodon"]["ranked"]), 1)

    def test_invalid_cohort_start_fails_closed(self):
        bad = [row(key=1, cohort_start=None),
               row(key=2, cohort_start="2026-10-02"),
               row(key=3, cohort_start="2026-10-09"),
               row(key=4, cohort_start="2026-09-99")]
        report = ranking(bad)["networks"]["bluesky"]
        self.assertEqual(report["ranked"], [])
        self.assertEqual([r["reason"] for r in report["unranked"]],
                         ["immature_or_invalid_date"] * 4)

    def test_exploration_requires_external_cursor_and_rotates(self):
        samples = [row(key=i, n=2, back=1) for i in range(1, 6)]
        without_cursor = ranking(samples, scan_slots={"bluesky": 10})
        self.assertTrue(without_cursor["networks"]["bluesky"]["exploration_cursor_required"])
        self.assertIsNone(without_cursor["networks"]["bluesky"]["exploration_candidates"])
        seen = set()
        for i in range(5):
            result = ranking(samples, scan_slots={"bluesky": 10},
                             exploration_cursor={"bluesky": i})
            selected = result["networks"]["bluesky"]["exploration_candidates"]
            self.assertEqual(len(selected), 2)
            seen.update(selected)
        self.assertEqual(len(seen), 5)

    def test_unsupported_scan_budget_and_malformed_cursor_fail_closed(self):
        for kwargs in (
            {"scan_slots": {"threads": 1}},
            {"scan_slots": {"reddit": 30}},
            {"exploration_cursor": {"bluesky": 0}},
            {"scan_slots": {"bluesky": 5}, "exploration_cursor": {"threads": 0}},
            {"scan_slots": {"bluesky": 5}, "exploration_cursor": {"bluesky": -1}},
            {"scan_slots": {"bluesky": 5}, "exploration_cursor": {"bluesky": True}},
            {"scan_slots": {"bluesky": 5}, "exploration_cursor": {"bluesky": 1000001}},
        ):
            with self.subTest(params=kwargs):
                with self.assertRaises(ValueError):
                    ranking([], **kwargs)

    def test_policy_gate_rejects_non_literary_or_prohibited_source(self):
        report = ranking([row(key=1, n=150, back=149,
                              source_policy_approved=False)])
        net = report["networks"]["bluesky"]
        self.assertEqual(net["ranked"], [])
        self.assertEqual(net["unranked"][0]["reason"], "source_policy_unapproved")

    def test_invalid_huge_cohort_is_rejected_not_exception(self):
        report = ranking([row(key=1, n=10 ** 400, back=10 ** 399)])
        self.assertEqual(report["networks"]["bluesky"]["ranked"], [])
        self.assertEqual(report["networks"]["bluesky"]["unranked"][0]["reason"],
                         "invalid_denominator")

    def test_cursor_must_match_budget_network(self):
        with self.assertRaises(ValueError):
            ranking([], scan_slots={"bluesky": 5},
                    exploration_cursor={"mastodon": 0})

    def test_wilson_bound_never_exceeds_observed_rate(self):
        # Float cancellation can yield a tiny positive bound for 0 successes.
        self.assertEqual(rank._wilson_lower(0, 44), 0.0)
        for n in range(40, 500):
            for successes in (0, 1, n // 2, n - 1, n):
                with self.subTest(n=n, successes=successes):
                    score = rank._wilson_lower(successes, n)
                    self.assertLessEqual(score, successes / n)
                    self.assertGreaterEqual(score, 0.0)

    def test_zero_input_no_invented_conversion(self):
        r = ranking([])
        self.assertEqual(r["metric"], "observed_followers_at_snapshot_not_incremental_conversion")
        self.assertEqual(r["networks"]["bluesky"]["ranked"], [])


if __name__ == "__main__":
    unittest.main()
