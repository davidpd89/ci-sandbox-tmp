"""PR153: fechas de origen en fidelización, sin red ni estado de cuentas."""
import datetime as dt
import pathlib
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import loyalty

NOW = dt.datetime.now(dt.timezone.utc)
RECENT = (NOW - dt.timedelta(days=1)).isoformat()
NOTIFICATION_TIME = NOW.isoformat()


class LoyaltyTargetDateTests(unittest.TestCase):
    def test_bluesky_notification_date_is_not_target_post_date(self):
        notification = {
            "reason": "reply",
            "uri": "at://did:plc:lector/app.bsky.feed.post/example",
            "author": {"did": "did:plc:lector", "handle": "lectora.bsky.social"},
            "record": {"text": "¿Qué libro recomiendas?", "createdAt": RECENT},
            "indexedAt": NOTIFICATION_TIME,
        }
        fake = types.SimpleNamespace(AUTH_BASE="api", _session=lambda: {"did": "did:plc:own"},
                                     _get=lambda *_args, **_kw: {
                                         "notifications": [notification], "cursor": None})
        with mock.patch.dict(sys.modules, {"bluesky_interact": fake}):
            rows = loyalty.harvest_bluesky()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["post_created_at"], RECENT)
        self.assertNotEqual(rows[0]["post_created_at"], NOTIFICATION_TIME)

    def test_mastodon_status_date_is_not_notification_date(self):
        event = {"type": "mention", "created_at": NOTIFICATION_TIME,
                 "account": {"acct": "lectora@example.test", "id": "author1"},
                 "status": {"id": "12345", "url": "https://example.test/@lectora/1",
                            "created_at": RECENT, "content": "<p>Hola</p>"}}
        fake = types.SimpleNamespace(
            notifications=lambda *_args, **_kw: [event],
            _plain_text=lambda value: str(value).replace("<p>", "").replace("</p>", ""),
        )
        with mock.patch.dict(sys.modules, {"mastodon_interact": fake}):
            rows = loyalty.harvest_mastodon()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["post_created_at"], RECENT)
        self.assertNotEqual(rows[0]["post_created_at"], NOTIFICATION_TIME)

    def test_mastodon_favourite_plan_carries_last_status_date(self):
        latest = {"url": "https://example.test/@lectora/4",
                  "status_id": "123", "text": "Hoy comparto una novela",
                  "post_created_at": RECENT}
        with mock.patch.object(loyalty, "loyal_accounts",
                               return_value={"lectora@example.test": {"like": 1}}), \
             mock.patch.object(loyalty, "_done", return_value=(set(), set())), \
             mock.patch.dict(loyalty.LATEST, {"mastodon": lambda *_: latest}), \
             mock.patch.object(loyalty.rp, "outbound_comments", return_value=0), \
             mock.patch("repost_policy.done_today", return_value=3):
            plan = loyalty.build_plan("mastodon", [
                {"handle": "lectora@example.test", "kind": "like"}],
                write=False, replies=False)
        favourites = [item for item in plan if item["kind"] == "favourite"]
        self.assertEqual(len(favourites), 1)
        self.assertEqual(favourites[0]["post_created_at"], RECENT)


if __name__ == "__main__":
    unittest.main()
