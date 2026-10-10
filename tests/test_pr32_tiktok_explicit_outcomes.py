"""PR hija de #32: resultados TikTok inequívocos, sin móvil ni escritura."""
import pathlib
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import tiktok_mobile_execute as te
import tiktok_mobile_interact as tm


class FakeAdapter:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def follow(self, handle):
        self.calls.append(("follow", handle))
        return self.outcome

    def like(self, url):
        self.calls.append(("like", url))
        return self.outcome

    def comment(self, url, text):
        self.calls.append(("comment", url, text))
        return self.outcome


class ExplicitOutcomes(unittest.TestCase):
    def test_follow_statuses(self):
        for outcome, expected in (
            ("already", "saltado_ya_seguido"),
            ("followed", "confirmado"),
            ("requested", "pendiente_aprobacion"),
        ):
            with self.subTest(outcome=outcome):
                adapter = FakeAdapter(outcome)
                self.assertEqual(te._one_action(adapter, {
                    "kind": "follow", "handle": "lector"}), expected)
                self.assertEqual(adapter.calls, [("follow", "lector")])

    def test_like_statuses(self):
        for outcome, expected in (("already", "saltado_ya_like"),
                                  ("created", "confirmado")):
            with self.subTest(outcome=outcome):
                self.assertEqual(te._one_action(FakeAdapter(outcome), {
                    "kind": "like", "url": "https://example.test/post"}), expected)

    def test_comment_statuses_and_target_with_gpt_proof(self):
        adapter = FakeAdapter("created")
        item = {"kind": "comment", "url": "https://example.test/post",
                "post_ref": {"ordinal": 2}, "gpt_proof": "signed",
                "text": "Qué lectura tan interesante"}
        self.assertEqual(te._one_action(adapter, item), "confirmado")
        self.assertEqual(adapter.calls[0][1], item["url"])
        self.assertEqual(te._one_action(FakeAdapter("already"), item),
                         "saltado_ya_comentado")

    def test_unknown_statuses_fail_closed_no_repeat_tap(self):
        for kind in ("follow", "like", "comment"):
            for outcome in (None, False, "", "pending", "requested" if kind != "follow" else "mystery"):
                with self.subTest(kind=kind, outcome=outcome):
                    adapter = FakeAdapter(outcome)
                    item = {"kind": kind, "handle": "lector",
                            "url": "https://example.test/post", "text": "lectura"}
                    with self.assertRaises(tm.TikTokWriteUnverified):
                        te._one_action(adapter, item)
                    self.assertEqual(len(adapter.calls), 1)  # jamás repetir tap

    def test_unknown_kind_denied_without_adapter(self):
        adapter = FakeAdapter("created")
        with self.assertRaises(ValueError):
            te._one_action(adapter, {"kind": "unrecognized"})
        self.assertEqual(adapter.calls, [])

    def test_existing_requested_relation_not_reported_as_followed(self):
        import tiktok_mobile_nav as nav
        fake = types.SimpleNamespace(
            _require_writes=lambda kind: None,
            open_profile=lambda handle: None,
        )
        fake_nav = mock.Mock()
        fake_nav.read_profile.return_value = {
            "handle": "lector", "relation": "requested"}
        with mock.patch.object(nav, "TikTokNavigator", return_value=fake_nav), \
             mock.patch.object(tm.time, "sleep"):
            self.assertEqual(tm.TikTokMobileAdapter.follow(fake, "lector"),
                             "requested")
        fake_nav.read_profile.assert_called_once()

    def test_requested_after_tap_stays_pending(self):
        import tiktok_mobile_nav as nav
        fake = types.SimpleNamespace(
            _require_writes=lambda kind: None,
            open_profile=lambda handle: None,
            _hook=lambda name: None,
            client=types.SimpleNamespace(tap=mock.Mock()),
            device=types.SimpleNamespace(id="test_device"),
        )
        first = {"handle": "lector", "relation": "not_following",
                 "relation_element": {"bounds": [1, 1, 4, 4]}}
        pending = {"handle": "lector", "relation": "requested"}
        fake_nav = mock.Mock()
        fake_nav.read_profile.side_effect = [first, first, pending]
        with mock.patch.object(nav, "TikTokNavigator", return_value=fake_nav), \
             mock.patch.object(tm.time, "sleep"), \
             mock.patch.object(tm, "element_center", return_value=(4, 4)):
            self.assertEqual(tm.TikTokMobileAdapter.follow(fake, "lector"),
                             "requested")
        fake.client.tap.assert_called_once()


if __name__ == "__main__":
    unittest.main()
