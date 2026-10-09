import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import threads_self_audit as au
import volume_ramp as vr

BASE = {"target": 150, "stage": 1, "likes_per_round": 44, "hours_elapsed": 22, "done_today": 140, "plan": 50, "plan_target": 51, "pool": {"available_now": 400},
        "not_found_rate": 0.01, "attempted": 100, "ui_warnings": 0, "unique_ratio": 0.9, "followers_gain_7d": 10, "done_7d": 600, "replies_7d": 30, "reply_notes": []}


class AuditTests(unittest.TestCase):
    def test_a_healthy_day_has_no_gaps(self):
        self.assertEqual(au.gaps(BASE), [])

    def test_each_problem_is_flagged_with_an_action(self):
        cases = {"volumen": {"done_today": 20}, "OFERTA": {"plan": 10}, "RESERVA": {"pool": {"available_now": 20}}, "ActionTargetNotFound": {"not_found_rate": 0.2},
                 "AVISO": {"ui_warnings": 1}, "objetivos unicos": {"unique_ratio": 0.4}, "crecimiento": {"followers_gain_7d": 0},
                 "replies en 7 dias": {"replies_7d": 3}}
        for needle, change in cases.items():
            found = au.gaps({**BASE, **change})
            self.assertTrue(any(needle in gap for gap, _ in found), (needle, found))
            self.assertTrue(all(action for _, action in found))


class RampTests(unittest.TestCase):
    def test_threads_advances_on_healthy_days_and_goes_down_on_warnings(self):
        healthy = {"rate_limited": 0, "ui_warnings": 0, "unique_ratio": 0.9, "not_found_rate": 0.01, "attempted": 60, "done_today": 100, "target": 150, "hours_elapsed": 23}
        self.assertEqual(vr.decide(healthy, 1, 1, network="threads")[0], "advance")
        self.assertEqual(vr.decide(healthy, 0, 1, network="threads")[0], "hold")                      # hace falta >=1 dia en la etapa
        self.assertEqual(vr.decide({**healthy, "not_found_rate": 0.2}, 3, 1, network="threads")[0], "hold")   # fiabilidad antes que volumen
        self.assertEqual(vr.decide({**healthy, "unique_ratio": 0.3}, 3, 1, network="threads")[0], "hold")
        self.assertEqual(vr.decide({**healthy, "done_today": 10}, 3, 1, network="threads")[0], "hold")  # las rondas ni corrieron: no subir a ciegas
        self.assertEqual(vr.decide(healthy, 3, len(vr.stages("threads")) - 1, network="threads")[0], "hold")
        self.assertEqual(vr.decide({**healthy, "ui_warnings": 1}, 30, 2, network="threads")[0], "regress")

    def test_stage_pauses_shrink_but_never_below_ten_seconds(self):
        pauses = [row["pause"] for row in vr.stages("threads")]
        self.assertEqual(pauses, sorted(pauses, reverse=True))
        self.assertGreaterEqual(min(p[0] for p in pauses), 10)
        self.assertEqual(vr.pause_range(network="threads"), tuple(vr.stages("threads")[0]["pause"]))   # los tests viven en la etapa 0


if __name__ == "__main__":
    unittest.main()
