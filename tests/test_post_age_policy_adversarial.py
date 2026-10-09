"""Regresiones adversariales de procedencia y límites de la edad de destino.

Fixtures completamente sintéticas; no importan clientes ni realizan acceso a cuentas.
"""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import post_age_policy as policy

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
NETWORKS = ("x", "threads", "facebook", "pinterest", "reddit",
            "bluesky", "mastodon", "tiktok", "instagram")


def ago(days):
    return (NOW - dt.timedelta(days=days)).isoformat()


def x_id(days):
    instant = NOW - dt.timedelta(days=days)
    return str((int(instant.timestamp() * 1000) - 1288834974657) << 22)


class AgeProvenanceTests(unittest.TestCase):
    def test_queue_created_at_does_not_hide_old_x_target(self):
        for kind in ("reply", "repost", "like"):
            with self.subTest(kind=kind):
                item = {"kind": kind, "created_at": ago(0),
                        "createdAt": ago(0),
                        "url": f"https://x.com/test/status/{x_id(60)}"}
                self.assertEqual(policy.check("x", item, now=NOW),
                                 (False, "post_antiguo"))

    def test_unqualified_queue_time_does_not_make_like_fresh(self):
        for network in NETWORKS:
            with self.subTest(network=network):
                self.assertEqual(policy.check(
                    network, {"kind": "like", "created_at": ago(0),
                              "createdAt": ago(0)}, now=NOW),
                    (True, "edad_desconocida"))

    def test_post_nested_created_at_is_distinct_from_queue_time(self):
        item = {"kind": "reply", "created_at": ago(0),
                "post": {"created_at": ago(9)}}
        self.assertEqual(policy.check("reddit", item, now=NOW),
                         (False, "post_antiguo"))
        item["post"]["created_at"] = ago(1)
        self.assertEqual(policy.check("reddit", item, now=NOW),
                         (True, "edad_ok"))

    def test_atproto_record_createdAt_is_post_time(self):
        item = {"kind": "reply", "createdAt": ago(0),
                "post": {"record": {"createdAt": ago(5)}}}
        self.assertEqual(policy.check("bluesky", item, now=NOW),
                         (False, "post_antiguo"))

    def test_x_url_can_be_used_when_auxiliary_status_id_invalid(self):
        item = {"kind": "reply", "status_id": "notification-not-target",
                "url": f"https://x.com/test/status/{x_id(11)}"}
        self.assertEqual(policy.check("x", item, now=NOW),
                         (False, "post_antiguo"))

    def test_bluesky_invalid_tid_does_not_certify_a_post(self):
        item = {"kind": "reply",
                "_target_uri": "at://did:plc:dummy/app.bsky.feed.post/kkkkkkkkkkkkk"}
        self.assertEqual(policy.check("bluesky", item, now=NOW),
                         (False, "edad_desconocida"))

    def test_limit_exact_and_just_past_boundary(self):
        for kind, max_days in (("comment", 3), ("reply", 3),
                               ("repost", 7), ("like", 21)):
            with self.subTest(kind=kind):
                self.assertEqual(policy.check(
                    "facebook", {"kind": kind, "target_created_at": ago(max_days)},
                    now=NOW), (True, "edad_ok"))
                old = (NOW - dt.timedelta(days=max_days, seconds=1)).isoformat()
                self.assertEqual(policy.check(
                    "facebook", {"kind": kind, "target_created_at": old},
                    now=NOW), (False, "post_antiguo"))

    def test_followup_has_seven_days_across_networks(self):
        for network in NETWORKS:
            item = {"kind": "reply", "reply_to_us": True,
                    "target_created_at": ago(6)}
            with self.subTest(network=network):
                self.assertEqual(policy.check(network, item, now=NOW),
                                 (True, "edad_ok"))
                item["target_created_at"] = ago(8)
                self.assertEqual(policy.check(network, item, now=NOW),
                                 (False, "post_antiguo"))
                item["target_created_at"] = ago(6)

    def test_future_and_invalid_time_do_not_grant_a_reply(self):
        future = (NOW + dt.timedelta(days=1)).isoformat()
        for network in NETWORKS:
            with self.subTest(network=network):
                self.assertEqual(policy.check(
                    network, {"kind": "reply", "target_created_at": future},
                    now=NOW), (False, "fecha_futura_inverosimil"))
                self.assertEqual(policy.check(
                    network, {"kind": "reply", "target_created_at": "invalid"},
                    now=NOW), (False, "edad_desconocida"))

    def test_aggregate_does_not_leak_contents(self):
        plan = [{"kind": "reply", "text": "texto-no-imprimir", "target_created_at": ago(9)},
                {"kind": "reply", "text": "texto-no-imprimir"},
                {"kind": "like", "target_created_at": ago(1)},
                {"kind": "follow"}]
        summary = policy.audit_plan("facebook", plan, now=NOW)
        self.assertEqual((summary["total"], summary["antiguas"],
                          summary["desconocidas_respuesta"], summary["admisibles"]),
                         (3, 1, 1, 1))
        self.assertNotIn("texto-no-imprimir", repr(summary))


if __name__ == "__main__":
    unittest.main()
