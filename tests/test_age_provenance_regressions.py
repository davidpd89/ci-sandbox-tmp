"""Regresiones offline: la fecha del destino sobrevive hasta el control compartido."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import post_age_policy as age
import threads_api
import pinterest_growth

NOW = dt.datetime(2026, 10, 9, 12, tzinfo=dt.timezone.utc)


def before(days):
    return (NOW - dt.timedelta(days=days)).isoformat()


class UncoveredExecutionPaths(unittest.TestCase):
    def test_threads_api_followup_retains_inbound_timestamp_and_seven_day_limit(self):
        response = {"id": "99", "username": "lectora", "text": "¿Qué lectura recomiendas?",
                    "timestamp": before(6)}
        plan = threads_api.build_plan([response], {
            "actions": [{"id": "99", "text": "Prueba la trilogía."}]})
        self.assertEqual(plan[0]["post_created_at"], before(6))
        self.assertEqual(age.check("threads", plan[0], now=NOW), (True, "edad_ok"))
        response["timestamp"] = before(8)
        old = threads_api.build_plan([response], {
            "actions": [{"id": "99", "text": "Prueba la trilogía."}]})[0]
        self.assertEqual(age.check("threads", old, now=NOW), (False, "post_antiguo"))
        response.pop("timestamp")
        unknown = threads_api.build_plan([response], {
            "actions": [{"id": "99", "text": "Prueba la trilogía."}]})[0]
        self.assertEqual(age.check("threads", unknown, now=NOW), (False, "edad_desconocida"))

    def test_pinterest_pin_time_propagates_to_reaction_save_and_comment(self):
        candidate = {"pins": [{
            "ok": True, "done_react": False, "url": "https://es.pinterest.com/pin/123/",
            "title": "Novelas de fantasía", "desc": "Libros de aventuras",
            "author": "lectora", "board": "Fantasia", "created_at": before(30)
        }], "authors": []}
        plan = pinterest_growth.build_plan(candidate, max_follows=0,
                                           max_saves=1, max_reacts=1, max_comments=1)
        self.assertEqual({p["kind"] for p in plan}, {"react", "save", "comment"})
        for item in plan:
            with self.subTest(kind=item["kind"]):
                self.assertEqual(item["post_created_at"], before(30))
                self.assertEqual(age.check("pinterest", item, now=NOW),
                                 (False, "post_antiguo"))

    def test_x_permalink_overrides_conflicting_newer_queue_target_date(self):
        old = NOW - dt.timedelta(days=60)
        status_id = str((int(old.timestamp() * 1000) - 1288834974657) << 22)
        url = "https://x.com/lectora/status/" + status_id
        for kind in ("reply", "repost", "like"):
            with self.subTest(kind=kind):
                item = {"kind": kind, "url": url, "post_created_at": before(0)}
                self.assertEqual(age.check("x", item, now=NOW),
                                 (False, "post_antiguo"))

    def test_threads_shortcode_only_vetoes_old_text_without_original_timestamp(self):
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

        def shortcode(days):
            instant_ms = int((NOW - dt.timedelta(days=days)).timestamp() * 1000)
            num = (instant_ms - 1314220021721) << 23
            chars = []
            while num:
                num, residue = divmod(num, 64)
                chars.append(alphabet[residue])
            return "".join(reversed(chars))

        for days, expected in ((1, (False, "edad_desconocida")),
                               (15, (False, "post_antiguo"))):
            item = {"kind": "reply", "url": "https://www.threads.com/@lectora/post/" + shortcode(days)}
            with self.subTest(days=days):
                self.assertEqual(age.check("threads", item, now=NOW), expected)
        fresh = {"kind": "reply", "url": "https://www.threads.com/@lectora/post/" + shortcode(1),
                 "post_created_at": before(1)}
        self.assertEqual(age.check("threads", fresh, now=NOW), (True, "edad_ok"))

    def test_pinterest_unknown_remains_labeled_and_text_is_blocked(self):
        for kind in ("react", "save", "comment"):
            item = {"kind": kind, "post_created_at": ""}
            result = age.check("pinterest", item, now=NOW)
            self.assertEqual(result, (kind != "comment", "edad_desconocida"))


if __name__ == "__main__":
    unittest.main()
