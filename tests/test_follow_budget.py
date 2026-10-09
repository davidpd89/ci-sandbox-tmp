"""Tope diario de follows (05/10): el 20:15 de Bluesky hizo 350 follows de 678 acciones porque el plan cabia en el tope de la ronda y shape_plan no recortaba nada."""
import csv
import datetime
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import mechanical_round as mr
import volume_shape as vs

TODAY = datetime.date(2026, 10, 5)


def plan(follows, likes):
    return [{"kind": "follow", "handle": f"f{i}"} for i in range(follows)] + [{"kind": "like", "handle": f"l{i}", "url": f"u{i}"} for i in range(likes)]


class FollowBudgetTests(unittest.TestCase):
    def test_budget_is_a_share_of_the_daily_target_minus_what_was_done(self):
        self.assertEqual(vs.follow_budget_left("bluesky", 100, daily=2500), 275)
        self.assertEqual(vs.follow_budget_left("bluesky", 900, daily=2500), 0)

    def test_cap_follows_keeps_the_best_ranked_and_all_other_actions(self):
        kept, dropped = vs.cap_follows(plan(10, 5), 4)
        self.assertEqual(dropped, 6)
        self.assertEqual([a["handle"] for a in kept if a["kind"] == "follow"], ["f0", "f1", "f2", "f3"])
        self.assertEqual(sum(1 for a in kept if a["kind"] == "like"), 5)
        self.assertEqual(vs.cap_follows(plan(3, 3), 0)[1], 3)

    def test_a_plan_that_fits_the_cap_no_longer_escapes_the_follow_share(self):
        big = plan(334, 313)          # el plan real del 20:15: cabe en el tope de 658 pero era un 52 % de follows
        shaped = vs.shape_plan(big, 658, random.Random(3))
        follows = sum(1 for a in shaped if a["kind"] == "follow")
        self.assertLessEqual(follows / len(shaped), vs.HARD_FOLLOW_SHARE_MAX + 0.01)
        self.assertEqual(sum(1 for a in shaped if a["kind"] == "like"), 313)       # no se pierde ningun like

    def test_a_balanced_plan_is_left_alone(self):
        small = plan(10, 90)
        self.assertEqual(vs.shape_plan(small, 200, random.Random(1)), small)


class RegistroCountersTests(unittest.TestCase):
    def registro(self, rows):
        folder = tempfile.mkdtemp()
        os.makedirs(os.path.join(folder, "SD"))
        with open(os.path.join(folder, "SD", "registro_interacciones.csv"), "w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["fecha", "cuenta", "tipo", "post_resumen", "texto_usado", "resultado", "notas"])
            writer.writerows(rows)
        return folder

    def test_mastodon_publicado_rows_count_for_follows_and_per_account_limits(self):
        folder = self.registro([["2026-10-05", "@a", "follow", "", "", "publicado", ""], ["2026-10-05", "@b", "favourite", "", "", "publicado", ""],
                                ["2026-10-05", "@b", "favourite", "", "", "publicado", ""], ["2026-10-04", "@c", "follow", "", "", "publicado", ""],
                                ["2026-10-05", "@d", "follow", "", "", "fallo", ""]])
        original = mr.ROOT
        mr.ROOT = folder
        try:
            cfg = {"dir": "SD"}
            self.assertEqual(mr._follows_today(cfg, TODAY), 1)
            self.assertEqual(mr._cheap_today(cfg, TODAY), {"b": 2})
        finally:
            mr.ROOT = original


if __name__ == "__main__":
    unittest.main()
