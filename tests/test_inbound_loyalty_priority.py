"""Contratos sintéticos: PR 69. Ni red, ni estado real ni credenciales."""
import csv
from datetime import date, timedelta
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import inbound_loyalty_priority as loyalty

TODAY = date(2026, 10, 10)


def obs(network="bluesky", handle="ana", kind="like", day="2026-10-09",
        event_id="one", **extras):
    return {"network": network, "handle": handle, "kind": kind,
            "day": day, "event_id": event_id, **extras}


def legacy(network="bluesky", handle="ana", kind="like", day="2026-10-09"):
    return {"network": network, "handle": handle, "kind": kind,
            "day": day, "granularity": "daily_aggregate"}


class InboundLoyaltyTests(unittest.TestCase):
    def build(self, observations=(), **kwargs):
        return loyalty.build(observations, as_of=TODAY, **kwargs)

    def test_nine_networks_and_three_independent_queues(self):
        inputs = [obs(n, f"actor{i}", "comment", event_id=f"id{i}")
                  for i, n in enumerate(loyalty.NETWORKS)]
        result = self.build(inputs)
        self.assertEqual(len(result["metrics"]), 9)
        self.assertEqual(result["observations_unique"], 9)
        self.assertEqual(result["queued_contacts"], 0)  # un comment sin ref no genera respuesta
        self.assertEqual(set(result["queues"]), {"WEB", "API", "MOBILE", "UNASSIGNED"})
        self.assertEqual(result["mode"], "review_only")

    def test_depth_frequency_diversity_recency_and_explainability(self):
        rows = [obs(event_id="like-a"),
                obs(kind="reply", day="2026-10-08", event_id="reply-a"),
                obs(kind="repost", day="2026-10-07", event_id="repost-a")]
        data = self.build(rows)
        item = data["queues"]["API"][0]
        self.assertEqual(item["score"], sum(item["components"].values()))
        self.assertEqual(item["events_recent"], 3)
        self.assertEqual(item["distinct_days"], 3)
        self.assertEqual(item["components"]["recurrence"], 8)
        self.assertIn("thank_review", [p["kind"] for p in item["proposals"]])

    def test_daily_replays_deduplicated_and_id_events_preserved(self):
        rows = [legacy(), legacy()]
        self.assertEqual(self.build(legacy=rows)["observations_unique"], 1)
        self.assertEqual(self.build([obs(event_id="1"), obs(event_id="2")],
                                    legacy=rows)["observations_unique"], 2)

    def test_event_id_collision_rejected(self):
        with self.assertRaisesRegex(ValueError, "colisión"):
            self.build([obs(), obs(handle="otra")])

    def test_event_id_collision_target_rejected(self):
        with self.assertRaisesRegex(ValueError, "colisión"):
            self.build([obs(kind="reply", target_ref="r1"),
                        obs(kind="reply", target_ref="r2")])

    def test_casefold_at_and_cross_network_identity(self):
        rows = [obs(handle="@ANA", actor_id="did:123"),
                obs(handle="ana", actor_id="did:123", event_id="two", day="2026-10-08"),
                obs(network="x", handle="ana", actor_id="did:123", event_id="three")]
        result = self.build(rows)
        self.assertEqual(result["metrics"]["bluesky"]["contacts"], 1)
        self.assertEqual(result["metrics"]["x"]["contacts"], 1)

    def test_alias_link_one_stable_id_not_two(self):
        rows = [obs(actor_id="idA", event_id="a", day="2026-10-08"),
                obs(actor_id="idB", event_id="b", day="2026-10-09")]
        self.assertEqual(self.build(rows, legacy=[legacy()])["metrics"]["bluesky"]["contacts"], 3)
        self.assertEqual(self.build(rows[:1], legacy=[legacy()])["metrics"]["bluesky"]["contacts"], 1)

    def test_repeat_metric_not_inflated_by_same_day(self):
        rows = [obs(event_id="a", day="2026-10-08"),
                obs(event_id="b", day="2026-10-08")]
        result = self.build(rows)
        self.assertEqual(result["metrics"]["bluesky"]["eligible_for_repeat"], 1)
        self.assertEqual(result["metrics"]["bluesky"]["repeated_contacts"], 0)
        self.assertEqual(result["metrics"]["bluesky"]["repeat_rate"], 0.0)

    def test_repeat_rate_unknown_when_no_prior_eligible_contact(self):
        data = self.build([obs(day="2026-10-10")])
        self.assertIsNone(data["metrics"]["bluesky"]["repeat_rate"])
        self.assertEqual(data["metrics"]["bluesky"]["contacts"], 1)

    def test_verified_answered_false_complete_requires_ref(self):
        row = obs(kind="reply", event_id="r", target_ref="at://p",
                  answered=False, context_quality="complete")
        data = self.build([row])
        self.assertEqual(data["queues"]["API"][0]["proposals"][0]["kind"], "reply_review")
        self.assertEqual(data["queues"]["API"][0]["proposals"][0]["target_ref"], "at://p")

    def test_partial_context_yields_context_review(self):
        row = obs(kind="mention", event_id="m", target_ref="urn:mention",
                  answered=False, context_quality="partial")
        self.assertEqual(self.build([row])["queues"]["API"][0]["proposals"][0]["kind"],
                         "context_review")

    def test_missing_answered_ref_or_true_prevents_reply_proposal(self):
        for fields in ({"answered": False}, {"target_ref": "r"},
                       {"answered": True, "target_ref": "r"}):
            with self.subTest(fields=fields):
                row = obs(kind="reply", **fields)
                result = self.build([row])
                self.assertEqual(result["queued_contacts"], 0)

    def test_confirmed_reply_suppresses_exact_target_not_other_thread(self):
        rows = [obs(kind="reply", target_ref="r1", answered=False,
                    context_quality="complete")]
        outbound = [{"network": "bluesky", "handle": "ana", "action": "reply",
                     "target_ref": "r1", "day": "2026-10-10", "confirmed": True}]
        self.assertEqual(self.build(rows, outbound=outbound)["queued_contacts"], 0)
        outbound[0]["target_ref"] = "different"
        self.assertEqual(self.build(rows, outbound=outbound)["queued_contacts"], 1)

    def test_unconfirmed_outbound_never_suppresses(self):
        row = obs(kind="reply", target_ref="r1", answered=False)
        outbound = [{"network": "bluesky", "handle": "ana", "action": "reply",
                     "target_ref": "r1", "day": "2026-10-10", "confirmed": False}]
        self.assertEqual(self.build([row], outbound=outbound)["queued_contacts"], 1)

    def test_recent_verified_post_visit_and_necropost(self):
        rows = [obs(event_id="a"), obs(event_id="b", day="2026-10-08")]
        post = {"network": "bluesky", "handle": "ana", "ref": "at://recent",
                "day": "2026-10-09", "verified": True,
                "original": True, "niche_es": True}
        result = self.build(rows, posts=[post])
        self.assertIn("visit_recent_review",
                      [p["kind"] for p in result["queues"]["API"][0]["proposals"]])
        for change in ({"day": "2026-09-01"}, {"verified": False},
                       {"original": False}, {"niche_es": False},
                       {"day": "2026-10-11"}):
            with self.subTest(change=change):
                changed = post | change
                actions = self.build(rows, posts=[changed])["queues"]["API"][0]["proposals"]
                self.assertFalse(any(p["kind"] == "visit_recent_review" for p in actions))

    def test_confirmed_thank_and_visit_cooldown(self):
        rows = [obs(event_id="a"), obs(event_id="b", day="2026-10-08")]
        post = {"network": "bluesky", "handle": "ana", "ref": "recent",
                "day": "2026-10-09", "verified": True, "original": True, "niche_es": True}
        outbound = [{"network": "bluesky", "handle": "ana", "action": action,
                     "confirmed": True, "day": "2026-10-08"}
                    for action in ("thank", "visit")]
        self.assertEqual(self.build(rows, posts=[post], outbound=outbound)["queued_contacts"], 0)
        for r in outbound:
            r["day"] = "2026-10-01"
        self.assertEqual(self.build(rows, posts=[post], outbound=outbound)["queued_contacts"], 1)

    def test_per_lane_caps_are_independent(self):
        rows = []
        for i, net in enumerate(("x", "bluesky", "tiktok")):
            for j in range(3):
                rows.append(obs(network=net, handle=f"a{i}-{j}", event_id=f"{net}{j}",
                                kind="reply", target_ref=f"target{j}", answered=False))
        data = self.build(rows, per_lane=2)
        self.assertEqual([len(data["queues"][lane]) for lane in ("WEB", "API", "MOBILE")],
                         [2, 2, 2])

    def test_deterministic_under_reorder(self):
        rows = [obs(event_id="b", day="2026-10-08"),
                obs(event_id="c", handle="bea"),
                obs(event_id="a", kind="repost", day="2026-10-07")]
        self.assertEqual(self.build(rows), self.build(list(reversed(rows))))

    def test_bad_dates_and_unknown_types(self):
        for changed in ({"day": ""}, {"day": "10/10/2026"},
                        {"kind": "surprise"}, {"network": "telegram"},
                        {"handle": " "}, {"event_id": None},
                        {"answered": "false"}):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.build([obs() | changed])

    def test_future_and_expired_events_are_not_actionable(self):
        result = self.build([obs(day="2026-10-11"),
                             obs(day="2026-01-01", event_id="old")])
        self.assertEqual(result["observations_unique"], 0)
        self.assertEqual(result["queued_contacts"], 0)

    def test_bad_coverage_and_invalid_confirmations(self):
        with self.assertRaises(ValueError):
            self.build(coverage={"bluesky": "all_seen"})
        with self.assertRaises(ValueError):
            self.build(outbound=[{"network": "x", "handle": "a", "action": "thank",
                                  "day": "2026-10-10", "confirmed": "yes"}])

    def test_coverage_not_assumed_complete_on_empty_source(self):
        data = self.build(coverage={"bluesky": "partial"})
        self.assertEqual(data["metrics"]["bluesky"]["coverage"], "partial")
        self.assertEqual(data["metrics"]["x"]["coverage"], "unknown")

    def test_csv_and_cli_without_implicit_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp = root / "synthetic.csv"
            with inp.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["fecha", "red", "handle", "tipo"])
                writer.writeheader()
                writer.writerow({"fecha": "2026-10-09", "red": "x",
                                 "handle": "lector", "tipo": "like"})
                writer.writerow({"fecha": "2026-10-09", "red": "x",
                                 "handle": "lector", "tipo": "like"})
            cmd = [sys.executable, str(Path(loyalty.__file__)),
                   "--as-of", "2026-10-10", "--legacy-csv", str(inp)]
            cp = subprocess.run(cmd, capture_output=True, text=True, check=True,
                                encoding="utf-8")
            self.assertEqual(json.loads(cp.stdout)["observations_unique"], 1)
            self.assertEqual(list(root.iterdir()), [inp])  # lectura sin estados

    def test_no_x_self_like_or_executable_actions(self):
        rows = [obs(network="x", event_id="a"),
                obs(network="x", event_id="b", day="2026-10-08")]
        result = self.build(rows)
        kinds = [p["kind"] for p in result["queues"]["WEB"][0]["proposals"]]
        self.assertEqual(kinds, ["thank_review"])
        self.assertNotIn("like", json.dumps(result))

    def test_post_data_must_be_explicitly_verified(self):
        rows = [obs(event_id="a"), obs(event_id="b", day="2026-10-08")]
        with self.assertRaises(ValueError):
            self.build(rows, posts=[{"network": "bluesky", "handle": "ana",
                                     "day": "2026-10-09", "ref": "post"}])


if __name__ == "__main__":
    unittest.main()
