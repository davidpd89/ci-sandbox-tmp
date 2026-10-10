"""Regresión: la elegibilidad de acciones Pinterest es independiente."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import pinterest_growth as growth


class ActionEligibilityTests(unittest.TestCase):
    def pin(self, **kw):
        data = {"url": "https://www.pinterest.com/pin/123/",
                "title": "Libros de fantasía juvenil", "desc": "Lectura de fantasía",
                "author": "lectora", "board": growth.FANTASY, "ok": True,
                "done_react": False, "done_save": False}
        data.update(kw)
        return data

    def test_reacted_pin_still_save_candidate(self):
        plan = growth.build_plan({"pins": [self.pin(done_react=True)], "authors": []},
                                 max_follows=0, max_reacts=10, max_saves=10)
        self.assertEqual([r["kind"] for r in plan], ["save"])

    def test_reacted_pin_still_comment_candidate(self):
        plan = growth.build_plan({"pins": [self.pin(done_react=True, done_save=True)],
                                  "authors": []}, max_follows=0, max_reacts=0,
                                 max_saves=0, max_comments=1)
        self.assertEqual([r["kind"] for r in plan], ["comment"])
        self.assertEqual(plan[0]["text"], growth.PENDING_TEXT)

    def test_each_action_skips_its_own_completed_state(self):
        plan = growth.build_plan({"pins": [self.pin(done_react=True, done_save=True)],
                                  "authors": []}, max_follows=0, max_reacts=10,
                                 max_saves=10, max_comments=0)
        self.assertEqual(plan, [])

    def test_not_ok_blocks_every_action(self):
        plan = growth.build_plan({"pins": [self.pin(ok=False)], "authors": []},
                                 max_follows=0, max_reacts=10, max_saves=10,
                                 max_comments=1)
        self.assertEqual(plan, [])

    def test_candidate_can_be_saved_and_reacted_once(self):
        plan = growth.build_plan({"pins": [self.pin(), self.pin()], "authors": []},
                                 max_follows=0, max_reacts=10, max_saves=10,
                                 max_comments=0)
        self.assertEqual([a["kind"] for a in plan], ["react", "save"])

    def test_comment_registry_still_applies_after_react(self):
        pin = self.pin(done_react=True)
        plan = growth.build_plan({"pins": [pin], "authors": []},
                                 max_follows=0, max_reacts=0, max_saves=0,
                                 max_comments=1,
                                 done_comments=frozenset([pin["url"]]))
        self.assertEqual(plan, [])


if __name__ == "__main__":
    unittest.main()
