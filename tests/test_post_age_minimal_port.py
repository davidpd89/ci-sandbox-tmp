"""Port mínimo de regresiones de antigüedad sobre la base operativa sincronizada.

Solo datos sintéticos. No hay navegadores, cuentas ni escrituras sociales.
"""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import pinterest_growth
import post_age_policy as age
import threads_api

NOW = dt.datetime(2026, 10, 10, 12, tzinfo=dt.timezone.utc)


def before(days):
    return (NOW - dt.timedelta(days=days)).isoformat()


def x_status(days):
    when = NOW - dt.timedelta(days=days)
    return str((int(when.timestamp() * 1000) - 1288834974657) << 22)


def threads_shortcode(days):
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    instant_ms = int((NOW - dt.timedelta(days=days)).timestamp() * 1000)
    value = (instant_ms - 1314220021721) << 23
    chars = []
    while value:
        value, residue = divmod(value, 64)
        chars.append(alphabet[residue])
    return "".join(reversed(chars))


class MinimalAgePortTests(unittest.TestCase):
    def test_job_timestamps_never_certify_original_post_age_on_nine_networks(self):
        networks = ("x", "threads", "facebook", "pinterest", "reddit",
                    "bluesky", "mastodon", "tiktok", "instagram")
        for network in networks:
            for kind in ("reply", "like"):
                for field in ("created_at", "createdAt"):
                    with self.subTest(network=network, kind=kind, field=field):
                        item = {"kind": kind, field: before(1)}
                        expected = (kind == "like", "edad_desconocida")
                        self.assertEqual(age.check(network, item, now=NOW), expected)

    def test_explicit_target_date_and_nested_record_remain_supported(self):
        for kind in ("reply", "like"):
            item = {"kind": kind, "created_at": before(1),
                    "post_created_at": before(30)}
            self.assertEqual(age.check("reddit", item, now=NOW),
                             (False, "post_antiguo"))
        self.assertEqual(
            age.check("bluesky", {"kind": "reply",
                                 "record": {"createdAt": before(1)}}, now=NOW),
            (True, "edad_ok"),
        )

    def test_old_x_permalink_wins_over_recent_auxiliary_timestamp(self):
        for kind in ("reply", "repost", "like"):
            item = {"kind": kind,
                    "url": "https://x.com/lectora/status/" + x_status(60),
                    "status_id": x_status(1), "post_created_at": before(1)}
            with self.subTest(kind=kind):
                self.assertEqual(age.check("x", item, now=NOW),
                                 (False, "post_antiguo"))

    def test_invalid_domain_cannot_forge_executable_x_status_age(self):
        item = {"kind": "reply",
                "url": "https://example.test/lectora/status/" + x_status(60),
                "post_created_at": before(1)}
        self.assertEqual(age.check("x", item, now=NOW), (True, "edad_ok"))

    def test_threads_shortcode_recent_cannot_certify_reply(self):
        for days, expected in ((1, (False, "edad_desconocida")),
                               (15, (False, "post_antiguo"))):
            item = {"kind": "reply",
                    "url": "https://www.threads.com/@lectora/post/" +
                           threads_shortcode(days)}
            with self.subTest(days=days):
                self.assertEqual(age.check("threads", item, now=NOW), expected)
        item["post_created_at"] = before(1)
        self.assertEqual(age.check("threads", item, now=NOW),
                         (True, "edad_ok"))

    def test_threads_api_followup_carries_original_inbound_timestamp(self):
        inbound = {"id": "99", "username": "lectora",
                   "text": "¿Qué lectura recomiendas?",
                   "timestamp": before(6),
                   "permalink": "https://www.threads.com/@lectora/post/xyz"}
        decisions = {"actions": [{"id": "99", "text": "Prueba la trilogía."}]}
        action = threads_api.build_plan([inbound], decisions)[0]
        self.assertEqual(action["post_created_at"], before(6))
        self.assertEqual(age.check("threads", action, now=NOW),
                         (True, "edad_ok"))

        inbound["timestamp"] = before(8)
        old = threads_api.build_plan([inbound], decisions)[0]
        self.assertEqual(age.check("threads", old, now=NOW),
                         (False, "post_antiguo"))

        inbound.pop("timestamp")
        unknown = threads_api.build_plan([inbound], decisions)[0]
        self.assertEqual(age.check("threads", unknown, now=NOW),
                         (False, "edad_desconocida"))

    def test_invalid_bluesky_tid_header_is_not_decoded(self):
        self.assertIsNone(age._tid_bluesky("k" + "2" * 12))

    def test_pinterest_source_date_survives_react_save_and_comment(self):
        pin = {"ok": True, "url": "https://es.pinterest.com/pin/123/",
               "title": "Novelas de fantasía", "desc": "Libros de aventuras",
               "author": "lectora", "board": "Fantasía",
               "created_at": before(30)}
        plan = pinterest_growth.build_plan(
            {"pins": [pin], "authors": []},
            max_follows=0, max_saves=1, max_reacts=1, max_comments=1,
        )
        self.assertEqual({item["kind"] for item in plan},
                         {"react", "save", "comment"})
        for item in plan:
            with self.subTest(kind=item["kind"]):
                self.assertEqual(item["post_created_at"], before(30))
                self.assertEqual(age.check("pinterest", item, now=NOW),
                                 (False, "post_antiguo"))

    def test_pinterest_save_window_and_unknown_date_are_explicit(self):
        for kind in ("react", "save", "comment"):
            expected = (kind != "comment", "edad_desconocida")
            self.assertEqual(age.check("pinterest", {"kind": kind}, now=NOW),
                             expected)
        self.assertEqual(age.check("pinterest",
                                  {"kind": "save", "post_created_at": before(8)},
                                  now=NOW), (False, "post_antiguo"))
        self.assertEqual(age.check("pinterest",
                                  {"kind": "save", "post_created_at": before(2)},
                                  now=NOW), (True, "edad_ok"))


if __name__ == "__main__":
    unittest.main()
