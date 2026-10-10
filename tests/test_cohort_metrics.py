"""Pruebas sintéticas y offline: mismas semánticas en ocho adaptadores."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from cohort_metrics import (NETWORKS, FollowEvent, FollowerObservation, evaluate,
                            legacy_projection, local_day)

D0 = date(2026, 10, 8)


def follow(net="bluesky", subject="id-1", **kw):
    return FollowEvent(net, subject, D0, "fuente", **({"baseline": "not_follower", "identity": "stable"} | kw))


def seen(net="bluesky", subject="id-1", day=date(2026, 10, 9), **kw):
    return FollowerObservation(net, subject, day, **({"capability": "synthetic", "identity": "stable"} | kw))


def stats(events, observations=(), net="bluesky", window="D+1", as_of=date(2026, 10, 16)):
    return evaluate(events, observations, as_of=as_of)["networks"][net][window].get("fuente")


class CohortTests(unittest.TestCase):
    def test_eight_networks_share_one_calculator(self):
        for net in NETWORKS:
            with self.subTest(net=net):
                row = stats([follow(net)], [seen(net, follows_back=True, coverage="partial")], net)
                self.assertEqual((row["eligible"], row["converted"], row["rate"]), (1, 1, 1.0))

    def test_empty_and_unavailable_not_zero(self):
        result = evaluate([], [], as_of=D0)
        self.assertEqual(set(result["networks"]), set(NETWORKS))
        self.assertEqual(result["networks"]["reddit"]["D+1"], {})
        row = stats([follow()])
        self.assertEqual((row["unknown"], row["not_converted"], row["rate"]), (1, 0, None))

    def test_partial_false_is_unknown_complete_false_is_negative(self):
        row = stats([follow()], [seen(follows_back=False, coverage="partial")])
        self.assertEqual((row["unknown"], row["not_converted"]), (1, 0))
        row = stats([follow()], [seen(follows_back=False, coverage="complete")])
        self.assertEqual((row["unknown"], row["not_converted"], row["rate"]), (0, 1, 0.0))

    def test_late_d4_snapshot_cannot_say_no_at_d1(self):
        row = stats([follow()], [seen(day=date(2026, 10, 12), follows_back=False, coverage="complete")])
        self.assertIsNone(row["rate"])
        self.assertEqual(row["unknown"], 1)

    def test_positive_d4_not_backdated_to_d3_but_in_d7(self):
        obs = [seen(day=date(2026, 10, 12), follows_back=True, coverage="partial")]
        self.assertEqual(stats([follow()], obs, window="D+3")["unknown"], 1)
        self.assertEqual(stats([follow()], obs, window="D+7")["converted"], 1)

    def test_preexisting_and_unconfirmed_excluded(self):
        events = [follow(baseline="preexisting"), follow(subject="new", confirmed=False),
                  follow(subject="notchecked", baseline="unknown")]
        row = stats(events)
        self.assertEqual(row["eligible"], 0)
        self.assertEqual(row["unknown"], 1)
        self.assertIsNone(row["rate"])

    def test_follow_repeat_needs_unfollow_for_new_episode(self):
        events = [follow(), FollowEvent("bluesky", "id-1", date(2026, 10, 8), "fuente", baseline="not_follower", identity="stable"),
                  FollowEvent("bluesky", "id-1", date(2026, 10, 10), kind="unfollow", identity="stable"),
                  FollowEvent("bluesky", "id-1", date(2026, 10, 11), "fuente", baseline="not_follower", identity="stable")]
        row = stats(events, [seen(day=date(2026, 10, 12), follows_back=True, coverage="partial")], window="D+1")
        self.assertEqual((row["eligible"], row["converted"]), (2, 1))

    def test_stable_id_survives_username_change_but_handle_does_not(self):
        row = stats([follow()], [seen(follows_back=True, coverage="complete")])
        self.assertEqual(row["converted"], 1)
        weak = FollowEvent("bluesky", "antiguo", D0, "fuente", identity="handle", baseline="not_follower")
        obs = seen(subject="nuevo", follows_back=True, coverage="complete", identity="handle")
        row = stats([weak], [obs])
        self.assertEqual((row["unknown"], row["weak_identity"]), (1, 1))

    def test_dst_is_local_calendar_not_24_hours(self):
        before = datetime(2026, 10, 24, 23, 30, tzinfo=timezone.utc)
        self.assertEqual(local_day(before), date(2026, 10, 25))
        end = datetime(2026, 10, 26, 0, 10, tzinfo=ZoneInfo("Europe/Madrid"))
        row = stats([FollowEvent("bluesky", "id-1", before, "fuente", baseline="not_follower", identity="stable")],
                    [seen(day=date(2026, 10, 26), follows_back=False, coverage="complete")], as_of=end)
        self.assertEqual(row["not_converted"], 1)

    def test_import_time_distinct_from_capture_time(self):
        delayed = seen(day=date(2026, 10, 9), received_at=date(2026, 10, 15),
                       follows_back=True, coverage="complete")
        self.assertEqual(stats([follow()], [delayed], as_of=date(2026, 10, 10))["unknown"], 1)
        self.assertEqual(stats([follow()], [delayed])["converted"], 1)

    def test_pending_and_censored(self):
        self.assertEqual(stats([follow()], window="D+7", as_of=date(2026, 10, 10))["pending"], 1)
        events = [follow(), FollowEvent("bluesky", "id-1", date(2026, 10, 9), kind="unfollow", identity="stable")]
        self.assertEqual(stats(events, window="D+3")["censored"], 1)

    def test_legacy_projection_is_compatibility_only(self):
        result = evaluate([FollowEvent("tiktok", "id-1", D0, "fuente", baseline="legacy_unverified")],
                          [], as_of=date(2026, 10, 16))
        v2 = result["networks"]["tiktok"]["D+1"]["fuente"]
        self.assertIsNone(v2["rate"])
        self.assertEqual(v2["legacy_unverified"], 1)
        self.assertEqual(legacy_projection(result, "tiktok")["D+1"]["fuente"],
                         {"followed": 1, "back": 0, "rate": 0.0})

    def test_unsupported_capability_or_bad_id_fail_closed(self):
        with self.assertRaises(ValueError):
            stats([follow()], [seen(follows_back=False, coverage="complete", capability="unavailable")])
        with self.assertRaises(ValueError):
            stats([FollowEvent("bluesky", None, D0)], [])
        with self.assertRaises(ValueError):
            stats([follow()], [seen(subject=None, follows_back=None)])

    def test_unicode_source_and_duplicate_event_id(self):
        events = [FollowEvent("mastodon", "opaque", D0, "España — ñ", baseline="not_follower", event_id="a"),
                  FollowEvent("mastodon", "opaque", D0, "España — ñ", baseline="not_follower", event_id="a")]
        result = evaluate(events, [FollowerObservation("mastodon", "opaque", date(2026, 10, 9),
                           follows_back=True, coverage="partial", capability="synthetic")], as_of=date(2026, 10, 16))
        row = result["networks"]["mastodon"]["D+1"]["España — ñ"]
        self.assertEqual((row["eligible"], row["converted"]), (1, 1))

    def test_partially_observed_sample_never_has_official_rate(self):
        events = [follow(subject="converted"), follow(subject="unknown")]
        observations = [seen(subject="converted", follows_back=True, coverage="partial")]
        result = evaluate(events, observations, as_of=date(2026, 10, 16))
        row = result["networks"]["bluesky"]["D+1"]["fuente"]
        self.assertEqual((row["eligible"], row["converted"], row["unknown"]), (2, 1, 1))
        self.assertEqual(row["coverage"], "partial")
        self.assertIsNone(row["rate"])
        self.assertEqual(row["lower_bound"], 0.5)

    def test_duplicate_event_id_with_different_subject_must_fail(self):
        events = [follow(subject="first", event_id="same"),
                  follow(subject="second", event_id="same")]
        with self.assertRaisesRegex(ValueError, "event_id"):
            stats(events)

    def test_same_idempotent_event_repeated_is_still_deduplicated(self):
        events = [follow(event_id="id-unique"), follow(event_id="id-unique")]
        row = stats(events, [seen(follows_back=True, coverage="partial")])
        self.assertEqual((row["eligible"], row["converted"]), (1, 1))

    def test_ordered_events_use_real_time_even_when_input_reversed(self):
        z = ZoneInfo("Europe/Madrid")
        events = [
            FollowEvent("bluesky", "uid", datetime(2026, 10, 8, 20, tzinfo=z),
                        "fuente", "unfollow", identity="stable"),
            FollowEvent("bluesky", "uid", datetime(2026, 10, 8, 8, tzinfo=z),
                        "fuente", baseline="not_follower", identity="stable"),
        ]
        row = stats(events)
        self.assertEqual(row["censored"], 1)
        self.assertEqual(row["eligible"], 0)

    def test_observation_before_follow_same_day_cannot_be_attributed(self):
        z = ZoneInfo("Europe/Madrid")
        events = [FollowEvent("bluesky", "uid", datetime(2026, 10, 8, 20, tzinfo=z),
                              "fuente", baseline="not_follower", identity="stable")]
        observations = [FollowerObservation("bluesky", "uid",
                                             datetime(2026, 10, 8, 9, tzinfo=z),
                                             True, "complete", capability="synthetic", identity="stable")]
        row = stats(events, observations)
        self.assertEqual((row["converted"], row["unknown"]), (0, 1))

    def test_as_of_datetime_does_not_include_later_same_day_snapshot(self):
        z = ZoneInfo("Europe/Madrid")
        event = follow()
        observation = seen(day=datetime(2026, 10, 9, 20, tzinfo=z),
                           follows_back=True, coverage="partial")
        result = evaluate([event], [observation],
                          as_of=datetime(2026, 10, 9, 8, tzinfo=z))
        row = result["networks"]["bluesky"]["D+1"]["fuente"]
        self.assertEqual(row["unknown"], 1)

    def test_receipt_earlier_than_capture_same_day_is_invalid(self):
        z = ZoneInfo("Europe/Madrid")
        ob = seen(day=datetime(2026, 10, 9, 20, tzinfo=z),
                  received_at=datetime(2026, 10, 9, 8, tzinfo=z),
                  follows_back=True, coverage="complete")
        with self.assertRaisesRegex(ValueError, "recepción anterior"):
            stats([follow()], [ob])

    def test_conversion_survives_later_unfollow_at_d3_and_d7(self):
        events = [follow(), FollowEvent("bluesky", "id-1",
                  date(2026, 10, 10), kind="unfollow", identity="stable")]
        observations = [seen(follows_back=True, coverage="partial")]
        self.assertEqual(stats(events, observations, window="D+3")["converted"], 1)
        self.assertEqual(stats(events, observations, window="D+7")["converted"], 1)
        self.assertEqual(stats(events, observations, window="D+7")["censored"], 0)
        self.assertEqual(stats(events, [], window="D+7")["censored"], 1)

    def test_censored_subject_blocks_comparable_rate(self):
        events = [follow(subject="yes"), follow(subject="closed"),
                  FollowEvent("bluesky", "closed", date(2026, 10, 10),
                              kind="unfollow", identity="stable")]
        observations = [seen(subject="yes", follows_back=True, coverage="partial")]
        row = stats(events, observations, window="D+7")
        self.assertEqual((row["converted"], row["censored"]), (1, 1))
        self.assertEqual(row["coverage"], "partial")
        self.assertIsNone(row["rate"])
        self.assertEqual(row["lower_bound"], 0.5)

    def test_dst_autumn_repeated_hour_orders_by_utc(self):
        z = ZoneInfo("Europe/Madrid")
        # 02:45 CEST sucede ANTES de 02:30 CET aunque 02:30 parezca menor.
        followed = datetime(2026, 10, 25, 2, 45, tzinfo=z, fold=0)
        unfollowed = datetime(2026, 10, 25, 2, 30, tzinfo=z, fold=1)
        events = [FollowEvent("bluesky", "uid", unfollowed,
                              "fuente", "unfollow", identity="stable"),
                  FollowEvent("bluesky", "uid", followed,
                              "fuente", baseline="not_follower", identity="stable")]
        row = stats(events, as_of=date(2026, 11, 2), window="D+7")
        self.assertEqual((row["censored"], row["eligible"]), (1, 0))

    def test_bad_inputs_do_not_silently_become_negative(self):
        with self.assertRaises(ValueError):
            evaluate([follow()], [], as_of=datetime(2026, 10, 10))
        with self.assertRaises(TypeError):
            stats([follow()], [seen(follows_back="false", coverage="complete")])
        with self.assertRaises(ValueError):
            stats([follow()], [seen(follows_back=False, coverage="typo")])
        with self.assertRaises(ValueError):
            stats([follow()], [seen(day=date(2026, 10, 10), received_at=date(2026, 10, 9), follows_back=False)])


if __name__ == "__main__":
    unittest.main()
