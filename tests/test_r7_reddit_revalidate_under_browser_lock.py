"""R7 Reddit: el plan se revalida tras esperar por segunda vez al Edge.

Reproductor integrado de main() con Playwright fingido. No visita Reddit.
"""
import contextlib
import datetime
import json
import os
import tempfile
import pathlib
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reddit_publish as rp
import action_ledger

ITEM = {"id": "p1", "sub": "libros", "title": "¿Qué os ha gustado leer?", "body": ""}
TODAY = datetime.date.today()


class RedditRevalidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.intent_path = os.path.join(self.temp.name, "reddit_post_intents.json")

    def tearDown(self):
        self.temp.cleanup()

    def scenario(self, *, published_while_waiting=False, blocked_while_waiting=False,
                 record_fails=False, empty_url=False, null_url=False, wrong_sub_url=False, preflight_fails=False,
                 busy_first=False, busy_second=False, blocked_corrupt_second=False,
                 bank_removed_while_waiting=False, apply=True):
        events = []
        state = {"turn": 0}
        page = mock.MagicMock()
        browser = mock.MagicMock()
        browser.contexts = [mock.MagicMock(new_page=lambda: page)]
        session = mock.MagicMock()
        session.chromium.connect_over_cdp.return_value = browser
        playwright = types.ModuleType("playwright")
        sync_api = types.ModuleType("playwright.sync_api")
        sync_api.sync_playwright = lambda: mock.Mock(start=lambda: session)
        playwright.sync_api = sync_api

        @contextlib.contextmanager
        def lock(*args, **kwargs):
            state["turn"] += 1
            if (busy_second and state["turn"] == 2) or (busy_first and state["turn"] == 1):
                raise action_ledger.RoundBusy("Edge ya reservado por otra ronda")
            events.append(f"acquire_{state['turn']}")
            try:
                yield
            finally:
                events.append(f"release_{state['turn']}")

        def load_bank():
            return [] if state["turn"] >= 2 and bank_removed_while_waiting else [ITEM]

        def read_log():
            if state["turn"] >= 2 and published_while_waiting:
                return [{"id": "p1", "sub": "libros", "when": TODAY}]
            return []

        def read_blocked():
            if state["turn"] >= 2 and blocked_corrupt_second:
                raise rp.RedditPublishError("JSON corrupto; no publicar")
            return {"libros": "moderación"} if state["turn"] >= 2 and blocked_while_waiting else {}

        def publish(item, apply=False, before_submit=None):
            if preflight_fails:
                raise rp.RedditPublishError("falta el flair antes de pulsar")
            if apply and before_submit is not None:
                before_submit()  # simula justo el instante anterior a button.click()
            events.append("publish")
            url = "https://www.reddit.com/r/libros/comments/a1b2c3/ejemplo/"
            if empty_url:
                url = ""
            if null_url:
                url = None
            if wrong_sub_url:
                url = "https://www.reddit.com/r/escritura/comments/a1b2c3/ejemplo/"
            return url, None

        with mock.patch.dict(sys.modules, {
                "playwright": playwright, "playwright.sync_api": sync_api}), \
             mock.patch.object(action_ledger, "browser_session", side_effect=lock), \
             mock.patch.object(rp, "load_bank", side_effect=load_bank), \
             mock.patch.object(rp, "INTENTS", self.intent_path), \
             mock.patch.object(rp, "read_log", side_effect=read_log), \
             mock.patch.object(rp, "read_blocked", side_effect=read_blocked), \
             mock.patch.object(rp, "eligible_subs", return_value={"libros"}), \
             mock.patch.object(rp, "my_recent_posts", return_value=[]), \
             mock.patch.object(rp, "refresh_blocked", side_effect=lambda posts,titles,blocked: blocked), \
             mock.patch.object(rp, "write_blocked"), \
             mock.patch.object(rp, "publish_post", side_effect=publish) as publisher, \
             mock.patch.object(rp, "record", side_effect=(PermissionError("CSV ocupado") if record_fails else lambda item,url: events.append("record"))):
            result = rp.main(["--apply"] if apply else [])
        return result, events, publisher.call_count

    def test_post_published_during_edge_wait_cannot_be_published_twice(self):
        result, events, count = self.scenario(published_while_waiting=True)
        self.assertEqual(result, 0)
        self.assertEqual(count, 0)
        self.assertNotIn("record", events)

    def test_newly_blocked_community_cannot_be_published_during_wait(self):
        result, events, count = self.scenario(blocked_while_waiting=True)
        self.assertEqual(result, 0)
        self.assertEqual(count, 0)

    def test_editorially_removed_question_during_wait_is_not_sent(self):
        result, events, count = self.scenario(bank_removed_while_waiting=True)
        self.assertEqual(result, 0)
        self.assertEqual(count, 0)
        self.assertNotIn("publish", events)
        self.assertNotIn("record", events)

    def test_valid_post_is_recorded_while_edge_is_still_held(self):
        result, events, count = self.scenario()
        self.assertEqual(result, 0)
        self.assertEqual(count, 1)
        self.assertLess(events.index("record"), events.index("release_2"))

    def test_record_failure_after_remote_success_never_reposts(self):
        first, events, count = self.scenario(record_fails=True)
        self.assertEqual(first, 2)
        self.assertEqual(count, 1)
        with open(self.intent_path, encoding="utf-8") as stream:
            saved = json.load(stream)
        self.assertEqual(saved["p1"]["state"], "confirmed")
        self.assertNotIn(ITEM["title"], json.dumps(saved, ensure_ascii=False))
        second, events, count = self.scenario()
        self.assertEqual(second, 0)
        self.assertEqual(count, 0)

    def test_preflight_error_before_click_does_not_leave_stale_intent(self):
        with self.assertRaises(rp.RedditPublishError):
            self.scenario(preflight_fails=True)
        self.assertFalse(os.path.exists(self.intent_path))
        recovered, events, count = self.scenario()
        self.assertEqual(recovered, 0)
        self.assertEqual(count, 1)

    def test_empty_remote_url_is_uncertain_not_confirmed(self):
        result, events, count = self.scenario(empty_url=True)
        self.assertEqual(result, 2)
        self.assertEqual(count, 1)
        self.assertNotIn("record", events)
        with open(self.intent_path, encoding="utf-8") as stream:
            saved = json.load(stream)
        self.assertEqual(saved["p1"]["state"], "uncertain")

    def test_null_remote_url_stays_uncertain(self):
        result, events, count = self.scenario(null_url=True)
        self.assertEqual((result, count), (2, 1))
        self.assertNotIn("record", events)
        with open(self.intent_path, encoding="utf-8") as stream:
            self.assertEqual(json.load(stream)["p1"]["state"], "uncertain")

    def test_wrong_subreddit_permalink_stays_uncertain(self):
        result, events, count = self.scenario(wrong_sub_url=True)
        self.assertEqual((result, count), (2, 1))
        self.assertNotIn("record", events)

    def test_busy_second_edge_turn_exits_cleanly_without_post(self):
        result, events, count = self.scenario(busy_second=True)
        self.assertEqual(result, 0)
        self.assertEqual(count, 0)
        self.assertNotIn("record", events)

    def test_busy_first_edge_turn_exits_without_trace_or_post(self):
        result, events, count = self.scenario(busy_first=True)
        self.assertEqual(result, 0)
        self.assertEqual(count, 0)

    def test_preview_excludes_uncertain_attempt_even_without_csv(self):
        with open(self.intent_path, "w", encoding="utf-8") as stream:
            json.dump({"p1": {"state": "uncertain", "url": ""}}, stream)
        with mock.patch("builtins.print") as output:
            result, events, count = self.scenario(apply=False)
        self.assertEqual((result, count), (0, 0))
        self.assertFalse(events)
        self.assertTrue(any("no se publica" in str(call) for call in output.call_args_list))

    def test_corrupt_blocked_file_after_wait_prevents_remote_click(self):
        with self.assertRaises(rp.RedditPublishError):
            self.scenario(blocked_corrupt_second=True)

    def test_corrupt_intent_file_fails_closed_before_publication(self):
        with open(self.intent_path, "w", encoding="utf-8") as stream:
            stream.write('{"p1":')  # truncado; no se interpreta como cola vacía
        with self.assertRaises(rp.RedditPublishError):
            self.scenario()
        with open(self.intent_path, encoding="utf-8") as stream:
            self.assertEqual(stream.read(), '{"p1":')

    def test_eligibility_missing_or_corrupt_fails_closed(self):
        missing = os.path.join(self.temp.name, "missing.json")
        self.assertEqual(rp.eligible_subs(missing), set())
        corrupt = os.path.join(self.temp.name, "broken.json")
        with open(corrupt, "w", encoding="utf-8") as stream:
            stream.write('{"libros":')
        self.assertEqual(rp.eligible_subs(corrupt), set())
        with open(corrupt, "w", encoding="utf-8") as stream:
            stream.write('["libros"]')  # esquema incorrecto
        self.assertEqual(rp.eligible_subs(corrupt), set())

    def test_empty_eligibility_never_selects_reddit_post(self):
        selected, why = rp.choose([ITEM], [], allowed=set())
        self.assertIsNone(selected)
        self.assertIn("no queda", why)

    def test_preview_does_not_publish_or_lock_browser(self):
        result, events, count = self.scenario(apply=False)
        self.assertEqual(result, 0)
        self.assertEqual(count, 0)
        self.assertFalse(events)


if __name__ == "__main__":
    unittest.main()
