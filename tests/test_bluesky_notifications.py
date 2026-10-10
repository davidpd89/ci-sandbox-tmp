"""Regresiones de notificaciones Bluesky sin credenciales ni llamadas a red."""
import contextlib
import importlib
import io
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
stub = types.ModuleType("bluesky_interact")
<<<<<<< HEAD
stub._health_check = lambda: (True, "OK", {"handle": "autorademodiaz.bsky.social"})
=======
stub._health_check = lambda: (True, "OK", {"handle": "davidportodiaz.bsky.social"})
>>>>>>> origin/research/public-reuse-parent
stub._get_timeline = lambda: []
stub._search_posts = lambda *args, **kwargs: []
stub._own_reply_parent_uris = lambda: set()
stub._get_notifications = lambda: [
    {"reason": "follow", "author": {"handle": "lectora.bsky.social"}},
    {"reason": "reply", "author": {"handle": "lectora.bsky.social"},
     "uri": "at://did:plc:lector/app.bsky.feed.post/abc1",
     "record": {"text": "¿Qué novela estás leyendo?"}},
    {"reason": "mention", "author": {"handle": "lectora.bsky.social"},
     "uri": "at://did:plc:lector/app.bsky.feed.post/abc2",
     "record": {"text": "También recomiendo este libro"}},
]
with patch.dict(sys.modules, {"bluesky_interact": stub}):
    bs = importlib.import_module("bluesky_scan")


class NotificationTests(unittest.TestCase):
    def test_two_distinct_posts_from_same_author_both_remain(self):
        with patch.object(bs.sc, "known_accounts", return_value={}), \
             patch.object(bs.sc, "already_interacted_urls", return_value=set()), \
             patch.object(bs.sc, "discarded_handles", return_value=set()), \
             patch.object(bs, "_pick_least_recent", return_value=[]), \
             patch.object(bs, "_pick_seeds", return_value=[]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            bs.scan()
        text = output.getvalue()
        self.assertIn("/post/abc1", text)
        self.assertIn("/post/abc2", text)
        self.assertEqual(text.count("sugerido=reply | @lectora.bsky.social"), 2)

    def test_discarded_handle_and_own_handle_are_case_insensitive(self):
<<<<<<< HEAD
        own = {"reason": "reply", "author": {"handle": "AUTORADEMODIAZ.BSKY.SOCIAL"},
=======
        own = {"reason": "reply", "author": {"handle": "DAVIDPORTODIAZ.BSKY.SOCIAL"},
>>>>>>> origin/research/public-reuse-parent
               "uri": "at://did:plc:author/app.bsky.feed.post/own",
               "record": {"text": "Mi respuesta"}}
        blocked = {"reason": "reply", "author": {"handle": "lectora.bsky.social"},
                   "uri": "at://did:plc:reader/app.bsky.feed.post/block",
                   "record": {"text": "Mensaje descartado"}}
        with patch.object(bs.b, "_get_notifications", return_value=[own, blocked]), \
             patch.object(bs.sc, "known_accounts", return_value={}), \
             patch.object(bs.sc, "already_interacted_urls", return_value=set()), \
             patch.object(bs.sc, "discarded_handles",
                          return_value={"LECTORA.BSKY.SOCIAL"}), \
             patch.object(bs, "_pick_least_recent", return_value=[]), \
             patch.object(bs, "_pick_seeds", return_value=[]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            bs.scan()
        self.assertIn("CANDIDATOS FILTRADOS: 0", output.getvalue())

    def test_content_source_without_permalink_is_omitted(self):
        malformed = {
            "author": {"handle": "lectora.bsky.social"},
            "record": {"text": "Un post sin URI no debe producir una acción"},
        }
        with patch.object(bs.b, "_get_notifications", return_value=[]), \
             patch.object(bs.b, "_get_timeline", return_value=[]), \
             patch.object(bs.b, "_search_posts", return_value=[malformed]), \
             patch.object(bs.sc, "known_accounts", return_value={}), \
             patch.object(bs.sc, "already_interacted_urls", return_value=set()), \
             patch.object(bs.sc, "discarded_handles", return_value=set()), \
             patch.object(bs, "_pick_least_recent", return_value=[]), \
             patch.object(bs, "_pick_seeds", return_value=[]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            bs.scan()
        self.assertIn("CANDIDATOS FILTRADOS: 0", output.getvalue())


    def test_reply_already_answered_in_own_repo_is_downgraded_to_like(self):
        raw_uri = "at://did:plc:lector/app.bsky.feed.post/abc1"
        with patch.object(bs.b, "_own_reply_parent_uris", return_value={raw_uri}), \
             patch.object(bs.sc, "known_accounts", return_value={}), \
             patch.object(bs.sc, "already_interacted_urls", return_value=set()), \
             patch.object(bs.sc, "discarded_handles", return_value=set()), \
             patch.object(bs, "_pick_least_recent", return_value=[]), \
             patch.object(bs, "_pick_seeds", return_value=[]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            bs.scan()
        text = output.getvalue()
        self.assertIn("sugerido=like | @lectora.bsky.social", text)
        self.assertNotIn(
            "sugerido=reply | @lectora.bsky.social | notif:contenido | "
            "https://bsky.app/profile/lectora.bsky.social/post/abc1",
            text,
        )

    def test_short_closure_notification_is_like_not_forced_reply(self):
        closure = [{
            "reason": "reply",
            "author": {"handle": "lectora.bsky.social"},
            "uri": "at://did:plc:lector/app.bsky.feed.post/close1",
            "record": {"text": "Exactamente 😄"},
        }]
        with patch.object(bs.b, "_get_notifications", return_value=closure), \
             patch.object(bs.sc, "known_accounts", return_value={}), \
             patch.object(bs.sc, "already_interacted_urls", return_value=set()), \
             patch.object(bs.sc, "discarded_handles", return_value=set()), \
             patch.object(bs, "_pick_least_recent", return_value=[]), \
             patch.object(bs, "_pick_seeds", return_value=[]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            bs.scan()
        self.assertIn("sugerido=like", output.getvalue())
        self.assertNotIn("sugerido=reply", output.getvalue())

    def test_prepare_for_ai_keeps_only_nonmechanical_cases(self):
        candidates = [
            {
                "source": "notif:contenido",
                "handle": "a.bsky.social",
                "url": "https://bsky.app/profile/a.bsky.social/post/1",
                "text": "Exacto",
                "kind": "like",
                "known_date": None,
                "profile": None,
            },
            {
                "source": "search:fantasia",
                "handle": "b.bsky.social",
                "url": "https://bsky.app/profile/b.bsky.social/post/2",
                "text": "Una idea nueva",
                "kind": "like",
                "known_date": None,
                "profile": None,
            },
            {
                "source": "notif:contenido",
                "handle": "c.bsky.social",
                "url": "https://bsky.app/profile/c.bsky.social/post/3",
                "text": "¿Qué opinas?",
                "kind": "reply",
                "known_date": "2026-09-28",
                "profile": None,
            },
        ]
        prepared = bs.prepare_for_ai(candidates)
        self.assertEqual(prepared["counts"], {"candidates": 3, "auto": 1, "needs_ai": 2})
        self.assertEqual(prepared["auto_plan"][0]["handle"], "a.bsky.social")
        self.assertEqual(
            {item["handle"] for item in prepared["needs_ai"]},
            {"b.bsky.social", "c.bsky.social"},
        )


    def test_conversation_closer_is_mechanical_but_question_is_not(self):
        self.assertTrue(bs.sc.is_conversation_closer("😊👌👍"))
        self.assertTrue(bs.sc.is_conversation_closer("Exactamente 😄"))
        self.assertTrue(bs.sc.is_conversation_closer("Te lo diré😉"))
        self.assertFalse(bs.sc.is_conversation_closer("¿Y tú cuál elegirías?"))
        self.assertFalse(bs.sc.is_conversation_closer("Exactamente, por eso no funciona"))
        self.assertFalse(
            bs.sc.is_conversation_closer(
                "Exactamente, y además el cambio de ritmo altera toda la escena."
            )
        )

    def test_query_rotation_uses_oldest_real_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            history = pathlib.Path(tmp) / "query_history.csv"
            history.write_text(
                "fecha,query\n"
                "2026-09-29,q:a|es\n"
                "2026-09-28,q:b|es\n",
                encoding="utf-8",
            )
            pool = [("a", "es"), ("b", "es"), ("c", "es")]
            with patch.object(bs, "QUERY_HISTORY_CSV", str(history)):
                chosen = bs._pick_least_recent(pool, 2, "q")
            self.assertEqual(chosen[0], ("c", "es"))
            self.assertEqual(chosen[1], ("b", "es"))

    def test_notification_uri_requires_real_permalink(self):
        self.assertIsNone(bs._post_url_from_uri("invalid", "lectora.bsky.social"))
        self.assertIsNone(bs._post_url_from_uri(None, "lectora.bsky.social"))


if __name__ == "__main__":
    unittest.main()
