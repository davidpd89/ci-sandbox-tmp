import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import bluesky_reply_queue as rq

TODAY = datetime.date(2026, 10, 5)


def entry(handle, followers, posts):
    return {"id": "G" + handle[:3], "handle": handle, "profile": {"followers": followers}, "posts": posts}


def post(pid, text, *, actions=("reply", "like"), created="2026-10-05T08:00:00Z", es=True):
    return {"id": pid, "text": text, "actions": list(actions), "created_at": created, "es": es, "url": "https://bsky.app/profile/x/post/" + pid}


GOOD = "Acabo de terminar una novela de fantasía que me ha dejado con ganas de más, ¿alguien tiene recomendaciones parecidas?"


class ReplyQueueTests(unittest.TestCase):
    def pick(self, shortlist, **kw):
        return rq.candidates({"shortlist": shortlist}, today=TODAY, **kw)

    def test_keeps_recent_spanish_niche_posts_and_one_per_account(self):
        rows = self.pick([entry("a.bsky.social", 400, [post("A-P1", GOOD), post("A-P2", GOOD + " otra vez")])])
        self.assertEqual([r["post"] for r in rows], ["A-P1"])

    def test_filters_language_age_size_links_politics_and_off_niche(self):
        shortlist = [
            entry("en.bsky.social", 400, [post("E-P1", GOOD, es=False)]),
            entry("old.bsky.social", 400, [post("O-P1", GOOD, created="2026-09-20T08:00:00Z")]),
            entry("big.bsky.social", 90000, [post("B-P1", GOOD)]),
            entry("tiny.bsky.social", 3, [post("T-P1", GOOD)]),
            entry("link.bsky.social", 400, [post("L-P1", GOOD + " https://example.com/novela")]),
            entry("off.bsky.social", 400, [post("F-P1", "Hoy hace un día precioso en la ciudad y me voy a pasear un rato por el parque con mi perro")]),
            entry("short.bsky.social", 400, [post("S-P1", "Qué libro tan bueno")]),
            entry("noreply.bsky.social", 400, [post("N-P1", GOOD, actions=("like",))]),
            entry("ok.bsky.social", 400, [post("K-P1", GOOD)]),
        ]
        self.assertEqual([r["handle"] for r in self.pick(shortlist)], ["ok.bsky.social"])

    def test_skips_accounts_already_replied_to(self):
        rows = self.pick([entry("a.bsky.social", 400, [post("A-P1", GOOD)])], replied=frozenset({"a.bsky.social"}))
        self.assertEqual(rows, [])

    def test_plan_contains_only_the_written_replies_without_the_mechanical_plan(self):
        state = {"shortlist": [entry("a.bsky.social", 400, [post("A-P1", GOOD)])], "auto_plan": [{"handle": "x", "kind": "like", "url": "u"}]}
        plan = rq.build_plan(state, {"replies": [{"post": "A-P1", "text": "¿Cuál fue?"}]})
        self.assertEqual([(a["kind"], a["handle"]) for a in plan], [("reply", "a.bsky.social")])


if __name__ == "__main__":
    unittest.main()
