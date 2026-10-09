"""volume_shape.py (03/10): volumen alto pero variable."""
import datetime
import pathlib
import random
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import volume_shape as vs


def plan(n_likes, n_follows):
    return ([{"kind": "like", "i": i} for i in range(n_likes)]
            + [{"kind": "follow", "i": i} for i in range(n_follows)])


class FactorTests(unittest.TestCase):
    def test_day_factor_is_deterministic_bounded_and_varies_between_days(self):
        day = datetime.date(2026, 10, 3)
        self.assertEqual(vs.day_factor(day, "bluesky"), vs.day_factor(day, "bluesky"))
        factors = {vs.day_factor(day + datetime.timedelta(days=i), "bluesky") for i in range(40)}
        self.assertGreater(len(factors), 20)
        self.assertTrue(all(0.2 <= f <= 1.5 for f in factors))
        self.assertTrue(any(f < 0.5 for f in factors))  # aparecen dias flojos

    def test_run_cap_scales_with_daily_target_and_has_noise(self):
        day = datetime.date(2026, 10, 3)
        caps = {vs.run_cap("bluesky", day, random.Random(seed)) for seed in range(30)}
        self.assertGreater(len(caps), 10)
        small = vs.run_cap("bluesky", day, random.Random(1), daily=60)
        big = vs.run_cap("bluesky", day, random.Random(1), daily=6000)
        self.assertLess(small, big)
        self.assertGreaterEqual(small, 10)


class ShapeTests(unittest.TestCase):
    def test_plan_that_fits_is_untouched(self):
        p = plan(5, 2)
        self.assertEqual(vs.shape_plan(p, 100), p)

    def test_cap_respected_follow_share_limited_and_order_preserved(self):
        p = plan(300, 200)
        shaped = vs.shape_plan(p, 100, random.Random(3))
        self.assertEqual(len(shaped), 100)
        follows = sum(1 for a in shaped if a["kind"] == "follow")
        self.assertLessEqual(follows, 25)
        likes = [a["i"] for a in shaped if a["kind"] == "like"]
        self.assertEqual(likes, sorted(likes))               # orden original (por score)
        self.assertEqual(likes[:18], list(range(18)))        # elite (25 %) siempre entra
        self.assertGreater(max(likes), 100)                  # y hay exploracion del resto lejano

    def test_weighted_zone_favours_better_ranked_candidates(self):
        counts = [0] * 400
        for seed in range(300):
            for a in vs.shape_plan(plan(400, 0), 100, random.Random(seed)):
                counts[a["i"]] += 1
        self.assertGreater(sum(counts[25:100]), sum(counts[300:375]))  # mas probables los de arriba...
        self.assertGreater(sum(counts[300:400]), 0)                    # ...pero los de abajo tambien entran

    def test_hard_follow_cap_and_dropped_list(self):
        p = plan(10, 200)
        shaped, dropped = vs.shape_plan(p, 100, random.Random(1), with_dropped=True)
        self.assertLessEqual(sum(1 for a in shaped if a["kind"] == "follow"), 40)
        self.assertEqual(len(shaped) + len(dropped), len(p))

    def test_duplicate_objects_in_plan_keep_their_own_positions(self):
        action = {"kind": "like", "i": 0}
        p = [action, action] + [{"kind": "like", "i": n} for n in range(1, 10)]
        shaped = vs.shape_plan(p, 8, random.Random(2))
        self.assertEqual(len(shaped), 8)

    def test_two_runs_choose_different_samples(self):
        p = plan(400, 0)
        a = vs.shape_plan(p, 100, random.Random(1))
        b = vs.shape_plan(p, 100, random.Random(2))
        self.assertNotEqual([x["i"] for x in a], [x["i"] for x in b])


class StructureTests(unittest.TestCase):
    def test_week_factor_persists_through_the_iso_week(self):
        monday = datetime.date(2026, 10, 5)
        week = {vs.week_factor(monday + datetime.timedelta(days=i), "bluesky") for i in range(7)}
        self.assertEqual(len(week), 1)
        self.assertTrue(0.8 <= vs.week_factor(monday, "mastodon") <= 1.2)

    def test_run_seed_is_reproducible_and_distinct(self):
        day = datetime.date(2026, 10, 3)
        self.assertEqual(vs.run_seed(day, "bluesky", 10), vs.run_seed(day, "bluesky", 10))
        self.assertNotEqual(vs.run_seed(day, "bluesky", 10), vs.run_seed(day, "bluesky", 15))
        self.assertNotEqual(vs.run_seed(day, "bluesky", 10), vs.run_seed(day, "mastodon", 10))


class HoldoutTests(unittest.TestCase):
    def test_holdout_withholds_only_non_elite_follows_never_other_kinds(self):
        p = plan(50, 100)
        kept, held = vs.split_holdout(p, random.Random(5), share=0.08)
        self.assertEqual(len(held), 8)
        self.assertTrue(all(a["kind"] == "follow" for a in held))
        follows = [a["i"] for a in p if a["kind"] == "follow"]
        elite = set(follows[:25])
        self.assertTrue(all(a["i"] not in elite for a in held))
        self.assertEqual(len(kept) + len(held), len(p))

    def test_no_follows_no_holdout(self):
        kept, held = vs.split_holdout(plan(10, 0), random.Random(1))
        self.assertEqual((len(kept), held), (10, []))


class PerTargetTests(unittest.TestCase):
    def test_cheap_actions_per_account_are_limited_but_other_kinds_untouched(self):
        p = ([{"kind": "like", "handle": "ana", "i": i} for i in range(6)]
             + [{"kind": "follow", "handle": "ana"}, {"kind": "reply", "handle": "ana"}]
             + [{"kind": "favourite", "handle": f"u{i}"} for i in range(20)])
        for seed in range(30):
            out = vs.limit_per_target(p, random.Random(seed))
            ana_likes = [a for a in out if a["kind"] == "like"]
            self.assertTrue(1 <= len(ana_likes) <= 3)
            self.assertEqual([a["i"] for a in ana_likes], list(range(len(ana_likes))))  # se queda lo mejor
            self.assertEqual(sum(1 for a in out if a["kind"] in ("follow", "reply")), 2)
            self.assertEqual(sum(1 for a in out if a["kind"] == "favourite"), 20)

    def test_distribution_is_mostly_one_or_two(self):
        p = [{"kind": "like", "handle": f"u{n}", "i": i} for n in range(300) for i in range(3)]
        out = vs.limit_per_target(p, random.Random(11))
        per = {}
        for a in out:
            per[a["handle"]] = per.get(a["handle"], 0) + 1
        ones = sum(1 for v in per.values() if v == 1)
        threes = sum(1 for v in per.values() if v == 3)
        self.assertGreater(ones, threes * 3)


class GapTests(unittest.TestCase):
    def test_gap_is_mostly_short_with_occasional_long_pauses(self):
        rng = random.Random(7)
        gaps = [vs.human_gap(rng) for _ in range(3000)]
        self.assertTrue(all(g >= 1.5 for g in gaps))
        self.assertLess(sorted(gaps)[len(gaps) // 2], 5.0)       # mediana corta
        self.assertGreater(max(gaps), 40)                        # algun paron
        self.assertGreater(sum(g > 8 for g in gaps), 150)        # y dudas intermedias



class RemainingCapTests(unittest.TestCase):
    def test_cap_unchanged_when_budget_is_far(self):
        self.assertEqual(vs.remaining_cap(200, 100, 600), 200)

    def test_cap_drops_when_day_is_already_over_budget(self):
        self.assertEqual(vs.remaining_cap(200, 700, 600), 80)
        self.assertEqual(vs.remaining_cap(200, 900, 600), 10)

    def test_daily_budget_uses_week_and_day_factors(self):
        today = datetime.date(2026, 10, 3)
        expected = vs.BASE_DAILY['bluesky'] * vs.week_factor(today, 'bluesky') * vs.day_factor(today, 'bluesky')
        self.assertAlmostEqual(vs.daily_budget('bluesky', today), expected)
        self.assertAlmostEqual(vs.daily_budget('bluesky', today, 100), 100 * vs.week_factor(today, 'bluesky') * vs.day_factor(today, 'bluesky'))


class LimitAlreadyTests(unittest.TestCase):
    def test_accounts_already_touched_today_count_towards_the_limit(self):
        plan = [{'kind': 'like', 'handle': 'ana', 'uri': str(i)} for i in range(3)]
        plan += [{'kind': 'like', 'handle': 'bea', 'uri': 'b'}]
        for seed in range(30):
            out = vs.limit_per_target(plan, random.Random(seed), weights=((1, 1.0),), already={'ana': 1})
            self.assertEqual([a['handle'] for a in out], ['bea'])


if __name__ == "__main__":
    unittest.main()
