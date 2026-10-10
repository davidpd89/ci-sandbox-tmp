"""Threads WEB: la fecha y la respuesta deben referirse al MISMO post.

Fixtures DOM sintéticas. Ningún navegador, token ni escritura social.
"""
from __future__ import annotations

import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import threads_execute as executor
import threads_interact as interact
from scan_common import ActionTargetNotFound


FRESH = "https://www.threads.com/@lectora/post/ABCD1234"
OLD = "https://www.threads.com/@lectora/post/WXYZ9999"
TEXT = "El mismo comienzo de reseña"


class Links:
    def __init__(self, hrefs):
        self.hrefs = hrefs

    def count(self):
        return len(self.hrefs)

    @property
    def first(self):
        return self.nth(0)

    def nth(self, i):
        return Link(self.hrefs[i])


class Link:
    def __init__(self, href):
        self.href = href

    def get_attribute(self, name):
        assert name == "href"
        return self.href


class Post:
    def __init__(self, links):
        self.links = Links(links)

    def locator(self, selector):
        assert selector == 'a[href^="/@"]'
        return self.links

    def inner_text(self):
        return TEXT


class Containers:
    def __init__(self, *posts):
        self.posts = posts

    def count(self):
        return len(self.posts)

    def nth(self, i):
        return self.posts[i]


class Page:
    def goto(self, *args, **kwargs):
        pass

    def wait_for_timeout(self, ms):
        pass


class Browser:
    def __init__(self):
        self.stopped = False

    def stop(self):
        self.stopped = True


class ThreadsWebTargetBindingTests(unittest.TestCase):
    def test_permalink_and_author_must_match_same_container(self):
        old = Post(["/@lectora", "/@lectora/post/WXYZ9999"])
        fresh = Post(["/@lectora", "/@lectora/post/ABCD1234"])
        other_author = Post(["/@otrapersona", "/@lectora/post/ABCD1234"])
        self.assertFalse(interact._reply_container_matches_permalink(old, FRESH))
        self.assertTrue(interact._reply_container_matches_permalink(fresh, FRESH))
        self.assertFalse(interact._reply_container_matches_permalink(other_author, FRESH))
        self.assertFalse(interact._reply_container_matches_permalink(fresh, FRESH + "/otro"))
        self.assertFalse(interact._reply_container_matches_permalink(fresh, "https://example.test/@lectora/post/ABCD1234"))

    def test_web_preflight_keeps_permalink_of_reply_without_changing_api(self):
        web = {"kind": "reply", "handle": "lectora", "text_fragment": TEXT,
               "text": "Me ha gustado mucho.", "permalink": FRESH, "bank": True}
        api = {"kind": "reply", "handle": "lectora", "reply_to_id": "99",
               "post_text": "¿Qué recomiendas?", "text": "Prueba ese libro.", "bank": True}
        with patch.object(executor.sc, "guard_plan_item"), \
             patch.object(executor.t, "_check_length"), \
             patch.object(executor.t, "_check_spanish_orthography"):
            web_plan = executor._preflight_plan([web])
            api_plan = executor._preflight_plan([api])
        self.assertEqual(web_plan[0]["permalink"], FRESH)
        self.assertEqual(api_plan[0]["reply_to_id"], "99")

    def test_old_post_with_identical_fragment_cannot_open_composer_or_send(self):
        old = Post(["/@lectora", "/@lectora/post/WXYZ9999"])
        posts = Containers(old, Post(["/@lectora", "/@lectora/post/ABCD1234"]))
        browser = Browser()
        with patch.object(interact, "_connect", return_value=(browser, Page())), \
             patch.object(interact, "_post_containers", return_value=posts), \
             patch.object(interact, "_find_container_by_text", return_value=0), \
             patch.object(interact, "_check_length"), \
             patch.object(interact, "_check_spanish_orthography"), \
             patch.object(interact, "_check_bot_warning"), \
             patch.object(interact, "_assert_active_account"), \
             patch.object(interact, "_find_action_button", side_effect=AssertionError("intentó usar el botón")):
            with self.assertRaisesRegex(ActionTargetNotFound, "destino_no_verificado"):
                interact.reply_to(TEXT, "Me ha gustado mucho.",
                                  "https://www.threads.com/@lectora", permalink=FRESH)
        self.assertTrue(browser.stopped)

    def test_missing_permalink_rejected_before_connecting_browser(self):
        with patch.object(interact, "_connect", side_effect=AssertionError("abrió Edge")), \
             patch.object(interact, "_check_length"), \
             patch.object(interact, "_check_spanish_orthography"):
            with self.assertRaisesRegex(ActionTargetNotFound, "destino_no_verificado"):
                interact.reply_to(TEXT, "Me ha gustado.", "https://www.threads.com/@lectora")

    def test_executor_skips_unbound_web_target_but_not_api_transport(self):
        item = {"kind": "reply", "handle": "lectora", "text_fragment": TEXT,
                "text": "Me ha gustado mucho.", "post_created_at": "2026-10-10T09:00:00Z"}
        with patch("reply_writer.require_gpt", side_effect=lambda plan, network: plan), \
             patch("repost_policy.guard", side_effect=lambda plan, _: plan), \
             patch("circuit_breaker.write_preflight", return_value=(True, "ok")), \
             patch("conversation_turn_policy.check_execution", return_value=(True, "edad_ok")), \
             patch.object(executor.t, "reply_to", side_effect=AssertionError("intentó responder")), \
             patch.object(executor.t, "beat", create=True):
            result = executor.run_plan([item], prevalidated=True)
        self.assertEqual(result[0]["resultado"], "saltado_destino_no_verificado")


if __name__ == "__main__":
    unittest.main()
