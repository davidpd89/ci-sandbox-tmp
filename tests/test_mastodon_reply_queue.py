import datetime
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: None
requests_stub.post = lambda *a, **k: None
requests_stub.delete = lambda *a, **k: None
sys.modules.setdefault("requests", requests_stub)
import mastodon_reply_queue as rq

TODAY = datetime.date(2026, 10, 5)
GOOD = "Acabo de terminar una novela de fantasía que me ha dejado con ganas de más, ¿alguien tiene recomendaciones parecidas?"


def entry(acct, followers, posts, **extra):
    return {"id": "M" + acct[:3], "acct": acct, "followers": followers, "bot": False, "posts": posts, **extra}


def post(pid, text=GOOD, *, actions=("reply", "favourite"), created="2026-10-05T08:00:00Z", language="es", sensitive=False, visibility="public"):
    return {"id": pid, "text": text, "actions": list(actions), "created_at": created, "language": language, "sensitive": sensitive, "visibility": visibility,
            "url": "https://masto.es/@x/" + pid, "status_id": pid.replace("-", ""), "sources": ["hashtag"], "stats": {"replies": 0}}


class ReplyQueueTests(unittest.TestCase):
    def pick(self, shortlist, **kw):
        return rq.candidates({"shortlist": shortlist}, today=TODAY, **kw)

    def test_keeps_recent_spanish_niche_statuses_one_per_account(self):
        rows = self.pick([entry("a@masto.es", 300, [post("A-P1"), post("A-P2", GOOD + " otra vez")])])
        self.assertEqual([r["post"] for r in rows], ["A-P1"])

    def test_filters_language_age_size_links_bots_sensitive_and_off_niche(self):
        shortlist = [
            entry("en@masto.es", 300, [post("E-P1", language="en")]),
            entry("old@masto.es", 300, [post("O-P1", created="2026-09-20T08:00:00Z")]),
            entry("big@masto.es", 90000, [post("B-P1")]),
            entry("bot@masto.es", 300, [post("T-P1")], bot=True),
            entry("link@masto.es", 300, [post("L-P1", GOOD + " https://example.com/novela")]),
            entry("cw@masto.es", 300, [post("C-P1", sensitive=True)]),
            entry("dm@masto.es", 300, [post("D-P1", visibility="direct")]),
            entry("off@masto.es", 300, [post("F-P1", "Hoy hace un día precioso en la ciudad y me voy a pasear un rato por el parque con mi perro")]),
            entry("ok@masto.es", 300, [post("K-P1")]),
        ]
        self.assertEqual([r["acct"] for r in self.pick(shortlist)], ["ok@masto.es"])

    def test_skips_accounts_already_replied_to(self):
        self.assertEqual(self.pick([entry("a@masto.es", 300, [post("A-P1")])], replied=frozenset({"a@masto.es"})), [])

    def test_plan_has_only_the_written_replies(self):
        state = {"shortlist": [entry("a@masto.es", 300, [post("A-P1")])], "auto_plan": [{"kind": "favourite"}]}
        plan = rq.build_plan(state, {"replies": [{"post": "A-P1", "text": "¿Es autoconclusivo?"}]})
        self.assertEqual([(a["kind"], a["handle"]) for a in plan], [("reply", "a@masto.es")])


if __name__ == "__main__":
    unittest.main()
