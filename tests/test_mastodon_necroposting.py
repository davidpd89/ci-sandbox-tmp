"""Mastodon: las IDs de estados federados son OPACAS; la edad exige created_at."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import exec_common as ec
import mastodon_execute as mx


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


class AgeTests(unittest.TestCase):
    def test_opaque_status_id_cannot_supply_a_creation_date(self):
        now = now_utc()
        self.assertIsNone(ec.mastodon_post_age_days("113017480417112277", now=now))
        self.assertIsNone(ec.mastodon_post_age_days("12345", now=now))
        self.assertTrue(ec.post_too_old("reply", "12345", now=now))

    def test_legacy_incident_ids_are_not_trusted_without_created_at(self):
        now = now_utc()
        for status_id in ("113017480417112277", "115327192558736542",
                          "117367744897450061"):
            with self.subTest(status_id=status_id):
                self.assertTrue(ec.post_too_old("reply", status_id, now=now))
                self.assertAlmostEqual(
                    ec.mastodon_post_age_days(
                        status_id, (now - dt.timedelta(days=9)).isoformat(), now=now),
                    9, places=2)

    def test_explicit_created_at_overrides_an_opaque_id(self):
        now = now_utc()
        self.assertTrue(ec.post_too_old("reply", "12345",
                                        (now - dt.timedelta(days=30)).isoformat(),
                                        now=now))
        self.assertFalse(ec.post_too_old("reply", "12345",
                                         (now - dt.timedelta(hours=3)).isoformat(),
                                         now=now))

    def test_unknown_text_fails_closed_reactions_keep_separate_policy(self):
        now = now_utc()
        for opaque in ("12345", "9" * 20):
            self.assertTrue(ec.post_too_old("reply", opaque, now=now))
            self.assertFalse(ec.post_too_old("favourite", opaque, now=now))
        self.assertFalse(ec.post_too_old("follow", "12345", now=now))

    def test_per_kind_limits(self):
        now = now_utc()
        created = (now - dt.timedelta(days=5)).isoformat()
        self.assertTrue(ec.post_too_old("reply", "12345", created, now=now))
        self.assertFalse(ec.post_too_old("favourite", "12345", created, now=now))
        self.assertFalse(ec.post_too_old("follow", "12345", created, now=now))


class PreflightTests(unittest.TestCase):
    def test_old_reply_is_omitted_and_recent_kept(self):
        now = now_utc()
        old = {"kind": "reply", "status_id": "123450001",
               "created_at": (now - dt.timedelta(days=5)).isoformat(),
               "text": "Qué buena recomendación, apunto ese título para más tarde."}
        new = {"kind": "reply", "status_id": "123450002",
               "created_at": (now - dt.timedelta(hours=3)).isoformat(),
               "text": "Me ha gustado mucho esa forma de contar el inicio de la historia."}
        skipped = []
        kept = mx._preflight_plan([old, new], skipped=skipped)
        self.assertEqual([item["status_id"] for item in kept], [new["status_id"]])
        self.assertEqual([item["resultado"] for item in skipped],
                         ["saltado_preflight_post_antiguo"])


if __name__ == "__main__":
    unittest.main()
