"""PR153: contrato de antigüedad por red y auditoría sin IO ni datos reales."""
import datetime as dt
import json
import os
import tempfile
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import post_age_policy as age
import tiktok_growth_scan as tt_scan
import daily_review as review
import reddit_comments as reddit
from unittest import mock

NOW = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)


class PostAgeAuditTests(unittest.TestCase):
    def test_facebook_external_comment_is_not_unbounded(self):
        item = {"kind": "comment_external", "post_created_at": "2026-09-20T09:00:00Z"}
        self.assertEqual(age.check("facebook", item, now=NOW), (False, "post_antiguo"))

    def test_facebook_external_like_max_21_days(self):
        self.assertEqual(age.check("facebook", {
            "kind": "like_external", "created_at": "2026-09-10T00:00:00Z"
        }, now=NOW), (False, "post_antiguo"))

    def test_pinterest_reaction_and_reddit_vote_share_like_age_cap(self):
        recent = "2026-10-08T00:00:00Z"
        old = "2026-09-01T00:00:00Z"
        for network, kind in (("pinterest", "react"), ("reddit", "vote")):
            self.assertEqual(age.check(network, {"kind": kind,
                             "post_created_at": old}, now=NOW), (False, "post_antiguo"))
            self.assertEqual(age.check(network, {"kind": kind,
                             "post_created_at": recent}, now=NOW), (True, "edad_ok"))
            self.assertEqual(age.check(network, {"kind": kind}, now=NOW),
                             (True, "edad_desconocida"))

    def test_reddit_created_utc_is_unix_seconds(self):
        stamp = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc).timestamp()
        self.assertEqual(age.check("reddit", {"kind": "reply", "created_utc": stamp}, now=NOW),
                         (False, "post_antiguo"))

    def test_tiktok_create_time_numeric(self):
        stamp = dt.datetime(2026, 10, 8, tzinfo=dt.timezone.utc).timestamp()
        self.assertEqual(age.check("tiktok", {"kind": "like", "create_time": stamp}, now=NOW),
                         (True, "edad_ok"))

    def test_bluesky_nested_record_created_at(self):
        self.assertEqual(age.check("bluesky", {"kind": "reply",
                         "record": {"createdAt": "2026-10-01T00:00:00Z"}}, now=NOW),
                         (False, "post_antiguo"))

    def test_bluesky_api_post_record_created_at(self):
        item = {"kind": "reply", "post": {
            "uri": "at://did:plc:example/app.bsky.feed.post/unknown",
            "record": {"createdAt": "2026-10-01T00:00:00Z"}}}
        self.assertEqual(age.check("bluesky", item, now=NOW), (False, "post_antiguo"))

    def test_post_wrapper_without_date_does_not_hide_record_date(self):
        item = {"kind": "reply", "post": {"uri": "invalid"},
                "record": {"createdAt": "2026-10-01T00:00:00Z"}}
        self.assertEqual(age.check("bluesky", item, now=NOW), (False, "post_antiguo"))

    def test_unknown_reply_audit_prevents_publication(self):
        item = {"kind":"reply", "url":"https://www.threads.net/example"}
        self.assertEqual(age.check("threads", item, now=NOW), (False,"edad_desconocida"))
        report = age.audit_plan("threads", [item], now=NOW)
        self.assertEqual(report["desconocidas_respuesta"], 1)
        self.assertEqual(report["total"], 1)

    def test_out_of_range_timestamp_does_not_crash_audit(self):
        item = {"kind": "reply", "created_utc": 10**30}
        self.assertEqual(age.check("reddit", item, now=NOW), (False, "edad_desconocida"))
        report = age.audit_plan("reddit", [item], now=NOW)
        self.assertEqual(report["desconocidas_respuesta"], 1)

    def test_boolean_date_never_counts_as_unix_timestamp(self):
        item = {"kind": "comment", "created_utc": True}
        self.assertEqual(age.check("reddit", item, now=NOW), (False, "edad_desconocida"))

    def test_reddit_before_2016_is_old_not_unknown(self):
        record = {"kind": "reply", "created_utc": "2014-06-01T12:00:00Z"}
        self.assertEqual(age.check("reddit", record, now=NOW),
                         (False, "post_antiguo"))

    def test_far_future_date_is_rejected_and_counted_separately(self):
        record = {"kind": "reply", "post_created_at": "2099-01-01T00:00:00Z"}
        self.assertEqual(age.check("bluesky", record, now=NOW),
                         (False, "fecha_futura_inverosimil"))
        stats = age.audit_plan("bluesky", [record], now=NOW)
        self.assertEqual(stats["fechas_inverosimiles"], 1)
        self.assertEqual(stats["edad_desconocida"], 0)
        self.assertEqual(stats["antiguas"], 0)

    def test_epoch_seconds_string_is_parsed_without_1970_fallback(self):
        stamp = str(int(dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc).timestamp()))
        self.assertEqual(age.check("reddit", {"kind": "comment", "created_utc": stamp}, now=NOW),
                         (False, "post_antiguo"))

    def test_unknown_text_never_passes_any_network(self):
        for network in ("x", "threads", "facebook", "pinterest", "reddit",
                        "bluesky", "mastodon", "tiktok", "instagram"):
            for kind in ("reply", "comment", "comment_external", "quote"):
                with self.subTest(network=network, kind=kind):
                    item = {"kind": kind, "url": "https://example.test/unverifiable"}
                    self.assertEqual(age.check(network, item, now=NOW),
                                     (False, "edad_desconocida"))

    def test_local_datetime_without_utc_offset_is_not_a_verified_target(self):
        # Fechas sin huso llegan de UI y pueden estar expresadas en Madrid.
        for value in ("2026-10-08T10:00:00", "2026-10-08",
                      dt.datetime(2026, 10, 8, 10, 0)):
            with self.subTest(value=str(value)):
                self.assertEqual(age.check("threads", {
                    "kind": "reply", "post_created_at": value}, now=NOW),
                    (False, "edad_desconocida"))

    def test_future_date_ten_minutes_ahead_is_not_fresh(self):
        item = {"kind": "comment", "post_created_at": (NOW + dt.timedelta(minutes=10)).isoformat()}
        self.assertEqual(age.check("reddit", item, now=NOW),
                         (False, "fecha_futura_inverosimil"))

    def test_followup_missing_timestamp_is_blocked_even_with_context(self):
        item = {"kind": "reply", "reply_to_us": True, "post_text": "¿Has leído más?",
                "url": "https://example.test/not-verifiable"}
        self.assertEqual(age.check("mastodon", item, now=NOW),
                         (False, "edad_desconocida"))

    def test_bluesky_user_supplied_tid_cannot_certify_reply_age(self):
        # AT Protocol permite rkeys elegidos por el autor. Un TID reciente
        # no acredita createdAt ni evita un necroposting.
        chars = "234567abcdefghijklmnopqrstuvwxyz"
        number = int(NOW.timestamp() * 1_000_000) << 10
        tid = "".join(chars[(number >> shift) & 31]
                      for shift in range(60, -1, -5))
        uri = f"at://did:plc:synthetic/app.bsky.feed.post/{tid}"
        item = {"kind": "reply", "post_uri": uri}
        self.assertIsNotNone(age.post_datetime("bluesky", item))
        self.assertEqual(age.check("bluesky", item, now=NOW),
                         (False, "edad_desconocida"))
        trusted_metadata = {**item, "post_created_at": "2026-10-08T10:00:00Z"}
        self.assertEqual(age.check("bluesky", trusted_metadata, now=NOW),
                         (True, "edad_ok"))
        counts = age.audit_plan("bluesky", [item], now=NOW)
        self.assertEqual(counts["desconocidas_respuesta"], 1)

    def test_recent_plans_metrics_are_isolated_from_real_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "SISTEMA_DIARIO_THREADS" / "threads_plan.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps([
                {"kind": "reply", "post_created_at": "2026-10-08T10:00:00Z"},
                {"kind": "reply"},
                {"kind": "like", "post_created_at": "2026-09-01T10:00:00Z"},
            ]), encoding="utf-8")
            os.utime(path, (NOW.timestamp(), NOW.timestamp()))
            summaries = age.audit_recent_plans(folder, now=NOW)
            self.assertEqual(summaries["threads"]["estado"], "ok")
            self.assertEqual(summaries["threads"]["desconocidas_respuesta"], 1)
            self.assertEqual(summaries["threads"]["antiguas"], 1)
            self.assertEqual(summaries["reddit"]["estado"], "sin_ruta_verificada")
            shown = "\n".join(review.plan_age_summary(folder, now=NOW))
            self.assertIn("threads: 1 respuestas sin fecha", shown)
            self.assertNotIn("2026-10-08T10:00:00Z", shown)

    def test_cli_readonly_audit_recovers_unknown_replies_without_targets(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as folder:
            p = pathlib.Path(folder) / "SISTEMA_DIARIO_THREADS" / "threads_plan.json"
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps([
                {"kind": "reply", "url": "https://synthetic.invalid/private"},
                {"kind": "reply", "post_created_at":
                 (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat()},
            ]), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                self.assertEqual(age.main(["--audit-recent", "--root", folder]), 0)
            data = json.loads(stdout.getvalue())
            self.assertEqual(data["threads"]["desconocidas_respuesta"], 1)
            self.assertEqual(data["reddit"]["estado"], "sin_ruta_verificada")
            self.assertNotIn("synthetic.invalid", stdout.getvalue())
            self.assertNotIn('"url"', stdout.getvalue())

    def test_stale_plan_cannot_masquerade_as_zero_unknown_age(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "bluesky_mech_plan.json"
            path.write_text('[{"kind": "reply"}]', encoding="utf-8")
            os.utime(path, (NOW.timestamp()-48*3600, NOW.timestamp()-48*3600))
            self.assertEqual(age.audit_recent_plans(folder, now=NOW)["bluesky"]["estado"],
                             "plan_no_reciente")

    def test_tiktok_auto_like_keeps_real_timestamp(self):
        row = {"id": "C1", "handle": "lector", "score": 20,
               "lane": "community", "actions": [],
               "posts": [{"id": "P1", "url": "https://example.test/video",
                          "actions": ["like"], "caption": "reseña literaria",
                          "created_at": "2026-10-08T09:00:00Z"}]}
        result = tt_scan.build_auto_plan([row], {"scoring": {"auto_like_score_min": 2}})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["post_created_at"], "2026-10-08T09:00:00Z")

    def test_reddit_plan_preserves_thread_created_at(self):
        data = [{"subreddit": "escribir", "title": "He terminado mi primer borrador",
                 "url": "https://www.reddit.com/r/escribir/comments/fake",
                 "author": "lectora", "comment_count": 1, "post_type": "",
                 "created": "2026-10-08T10:00:00Z"}]
        rows = reddit.build_plan(data, max_comments=2, now=NOW, my_user="mi_cuenta")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["post_created_at"], "2026-10-08T10:00:00Z")

    def test_reddit_reply_enforces_policy_before_touching_page(self):
        item = {"id": "t1_example", "kind": "reply", "text": "Me alegra leer eso",
                "post_text": "Es una historia muy bonita",
                "post_created_at": "2025-10-08T00:00:00Z"}
        with mock.patch.object(reddit.rw, "require_gpt", return_value=True), \
             mock.patch("conversation_turn_policy.check_execution",
                        return_value=(False, "post_antiguo")) as policy:
            result = reddit.reply_in_thread(None, "https://www.reddit.com/r/test/comments/example",
                                            item, log=lambda *_: None)
        self.assertFalse(result)
        policy.assert_called_once()

    def test_reddit_secondary_profile_comment_never_publishes_old_post(self):
        item = {"kind": "comment", "url": "https://www.reddit.com/r/test/comments/fake",
                "post_created_at": "2025-10-08T00:00:00Z", "text": "Qué bien"}
        publisher = mock.Mock()
        with mock.patch.object(reddit.rw, "require_gpt") as provenance:
            allowed = reddit._publish_profile_comment(item, log=lambda *_: None,
                                                      publish=publisher)
        self.assertFalse(allowed)
        publisher.assert_not_called()
        provenance.assert_not_called()

    def test_reddit_secondary_profile_comment_requires_provenance_before_publish(self):
        item = {"kind": "comment", "url": "https://www.reddit.com/r/test/comments/fake",
                "post_created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "text": "Qué bien"}
        publisher = mock.Mock()
        with mock.patch.object(reddit.rw, "require_gpt", return_value=[]):
            self.assertFalse(reddit._publish_profile_comment(item,
                             log=lambda *_: None, publish=publisher))
        publisher.assert_not_called()
        with mock.patch.object(reddit.rw, "require_gpt", return_value=[item]):
            self.assertTrue(reddit._publish_profile_comment(item,
                            log=lambda *_: None, publish=publisher))
        publisher.assert_called_once_with(item["url"], item["text"])

    def test_reddit_dom_fixture_captures_comment_creation(self):
        self.assertIn("created-timestamp", reddit._JS_COMMENTS)

    def test_followup_has_7_days_but_normal_reply_only_3(self):
        item={"kind":"reply","post_created_at":"2026-10-04T00:00:00Z"}
        self.assertFalse(age.check("mastodon", item, now=NOW)[0])
        self.assertTrue(age.check("mastodon", {**item,"reply_to_us":True}, now=NOW)[0])


if __name__ == "__main__":
    unittest.main()
