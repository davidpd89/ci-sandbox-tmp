"""Bienvenidas de Mastodon (06/10): quien entra, como se compone el texto; sin red."""
import datetime
import pathlib
import random
import sys
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: None
sys.modules.setdefault("requests", requests_stub)
import mastodon_welcome as mw

TODAY = datetime.date(2026, 10, 6)


def status(acct, text, *, created=3, followers=5, language="es", **extra):
    base = {"url": f"https://masto.es/@{acct}/1", "content": f"<p>{text}</p>", "language": language, "visibility": "public", "in_reply_to_id": None, "reblog": None,
            "created_at": (TODAY - datetime.timedelta(days=1)).isoformat() + "T10:00:00Z",
            "account": {"acct": acct, "created_at": (TODAY - datetime.timedelta(days=created)).isoformat() + "T10:00:00Z", "followers_count": followers, "bot": False}}
    base.update(extra)
    return base


GOOD = "Hola, me presento: leo mucha novela de fantasía y me gustaría escribir algún día. #presentacion"


class DiscoverTests(unittest.TestCase):
    def discover(self, statuses):
        return mw.discover(TODAY, getter=lambda url, params: statuses if "/tag/" in url else [], hosts=["masto.es"], tags=["presentacion"])

    def test_new_spanish_reader_is_a_candidate(self):
        self.assertIn("ana@masto.es", self.discover([status("ana", GOOD)]))

    def test_welcome_uses_post_date_not_account_creation_date(self):
        candidates = self.discover([status("ana", GOOD, created=9)])
        row = candidates["ana@masto.es"]
        self.assertEqual(row["created"], 9)
        self.assertEqual(row["post_created_at"], "2026-10-05T10:00:00Z")
        plan = mw.build(candidates, set())
        replies = [item for item in plan if item["kind"] == "reply"]
        self.assertEqual(replies[0]["post_created_at"], row["post_created_at"])

    def test_everyone_else_is_not(self):
        cases = [status("vieja", GOOD, created=200), status("grande", GOOD, followers=5000), status("ingles", "Hi, I am new here and I love fantasy books and reading novels every day #introduction", language="en"),
                 status("sinnicho", "Hola, me presento: me gusta el fútbol, la cerveza y los coches. #presentacion"),
                 status("activista", "Hola, me presento: antifa, libros y novelas de fantasía. #presentacion"),
                 status("respuesta", GOOD, in_reply_to_id="9"), status("privada", GOOD, visibility="private")]
        self.assertEqual(self.discover(cases), {})


class BuildTests(unittest.TestCase):
    found = {f"u{i}@masto.es": {"url": f"https://masto.es/@u{i}/1", "text": GOOD, "created": i, "followers": 3, "host": "masto.es"} for i in range(1, 5)}

    def test_each_account_gets_a_reply_and_a_follow_with_distinct_texts(self):
        plan = mw.build(self.found, set(), random.Random(1), 4)
        replies = [p for p in plan if p["kind"] == "reply"]
        self.assertEqual(len(replies), 4)
        self.assertTrue(all(p["text"] == mw.PENDING_TEXT for p in replies))      # el texto lo escribe ChatGPT despues; nunca una plantilla
        self.assertEqual({p["handle"] for p in plan if p["kind"] == "follow"}, set(self.found))
        for p in replies:
            self.assertNotIn("davidporto", p["text"].casefold())                          # nunca habla de David ni de su web

    def test_known_accounts_and_the_limit_are_respected(self):
        plan = mw.build(self.found, {"u1@masto.es", "u2"}, random.Random(1), 1)
        self.assertEqual({p["handle"] for p in plan}, {"u3@masto.es"})
