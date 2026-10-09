"""x_build_plan.py (02/10): transcripcion mecanica follow/like, reply aparte."""
import sys
import pathlib
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import x_build_plan as bp


class BuildPlanTests(unittest.TestCase):
    def test_follow_and_like_go_straight_to_plan(self):
        candidates = [
            {"kind": "follow", "handle": "autora1", "url": None},
            {"kind": "like", "handle": "ed1", "url": "https://x.com/ed1/status/1"},
        ]
        plan, pending = bp.build(candidates)
        self.assertEqual(plan, [
            {"kind": "follow", "handle": "autora1"},
            {"kind": "like", "url": "https://x.com/ed1/status/1"},
        ])
        self.assertEqual(pending, [])

    def test_follows_are_capped_but_likes_are_not(self):
        cands = [{"kind": "follow", "handle": f"u{i}"} for i in range(30)] +                 [{"kind": "like", "url": f"https://x.com/a/status/{i}"} for i in range(50)]
        plan, _ = bp.build(cands)
        kinds = [a["kind"] for a in plan]
        self.assertEqual(kinds.count("follow"), 12)
        self.assertEqual(kinds.count("like"), 50)

    def test_reposts_come_only_from_curated_lists_without_politics_and_are_capped(self):
        long_text = "Nueva novela de fantasía editorial con mapa y glosario incluidos ya en librerías"
        cands = [{"kind": "like", "url": f"https://x.com/a/status/{i}", "handle": f"h{i}", "source": "lista:Editoriales",
                  "text": long_text} for i in range(6)]
        cands.append({"kind": "like", "url": "https://x.com/a/status/90", "handle": "h90", "source": "search:#libros",
                      "text": long_text})
        cands.append({"kind": "like", "url": "https://x.com/a/status/91", "handle": "h91", "source": "lista:Editoriales",
                      "text": "Gran debate sobre el gobierno y las elecciones del partido en el congreso esta semana"})
        plan, _ = bp.build(cands)
        reposts = [a for a in plan if a["kind"] == "repost"]
        self.assertEqual(len(reposts), 3)
        self.assertTrue(all("lista" not in a.get("url", "") for a in plan))
        self.assertNotIn("https://x.com/a/status/90", [a["url"] for a in reposts])
        self.assertNotIn("https://x.com/a/status/91", [a["url"] for a in reposts])
        self.assertEqual(sum(1 for a in plan if a["kind"] == "like"), 5)

    def test_reply_never_enters_plan_automatically(self):
        candidates = [
            {"kind": "reply", "handle": "lector1",
             "url": "https://x.com/lector1/status/2", "text": "hola",
             "ya_comentado": False},
        ]
        plan, pending = bp.build(candidates)
        self.assertEqual(plan, [])
        self.assertEqual(len(pending), 1)

    def test_already_commented_reply_is_dropped_not_queued(self):
        candidates = [
            {"kind": "reply", "handle": "lector2",
             "url": "https://x.com/lector2/status/3", "text": "hola",
             "ya_comentado": True},
        ]
        plan, pending = bp.build(candidates)
        self.assertEqual(plan, [])
        self.assertEqual(pending, [])

    def test_dedupes_repeated_handle_or_url(self):
        candidates = [
            {"kind": "follow", "handle": "autora1", "url": None},
            {"kind": "follow", "handle": "autora1", "url": None},
            {"kind": "like", "handle": None, "url": "https://x.com/ed1/status/1"},
            {"kind": "like", "handle": None, "url": "https://x.com/ed1/status/1"},
        ]
        plan, _ = bp.build(candidates)
        self.assertEqual(len(plan), 2)

    def test_missing_handle_or_url_is_skipped_not_crashed(self):
        candidates = [
            {"kind": "follow", "handle": None, "url": None},
            {"kind": "like", "handle": None, "url": None},
        ]
        plan, pending = bp.build(candidates)
        self.assertEqual(plan, [])
        self.assertEqual(pending, [])


class FreshnessTests(unittest.TestCase):
    def test_only_todays_dump_is_fresh(self):
        import datetime
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "c.json")
            open(path, "w").close()
            today = datetime.date.today()
            self.assertTrue(bp.is_fresh(path, today))
            self.assertFalse(bp.is_fresh(path, today + datetime.timedelta(days=1)))


if __name__ == "__main__":
    unittest.main()
