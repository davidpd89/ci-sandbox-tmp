import datetime
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import volume_ramp as vr

CONFIG = {"budgets": {"max_read_requests": 1800, "max_profiles_to_vet": 120, "actionability_profiles": 150},
          "shortlist": {"profiles": 400, "auto_like_score_min": 10.0, "auto_follow_score_min": 14.0}}
HEALTHY = {"rate_limited": 0, "unique_ratio": 0.7, "followback_rate": 0.2, "followback_n": 60, "utilization": 0.95}


class RampTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "ramp.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_stage_zero_leaves_the_config_untouched_and_higher_stages_scale_it(self):
        self.assertEqual(vr.overlay(CONFIG, self.path), CONFIG)
        vr.save({"stage": 3, "since": "2026-10-05", "history": []}, self.path)
        cfg = vr.overlay(CONFIG, self.path)
        self.assertGreater(cfg["shortlist"]["profiles"], 400)
        self.assertLess(cfg["shortlist"]["auto_like_score_min"], 10.0)
        self.assertGreater(cfg["budgets"]["max_read_requests"], 1800)
        self.assertGreater(cfg["budgets"]["jetstream_cache_posts"], 75)
        self.assertEqual(CONFIG["shortlist"]["profiles"], 400)   # no muta la original
        self.assertEqual(vr.daily_target(self.path), 4000)

    def test_stages_are_monotonic_and_end_near_the_api_limit(self):
        for a, b in zip(vr.STAGES, vr.STAGES[1:]):
            self.assertLess(a["daily"], b["daily"])
            self.assertLessEqual(b["like_min"], a["like_min"])
            self.assertGreaterEqual(b["rounds"], a["rounds"])
        self.assertEqual(vr.STAGES[-1]["daily"], 9000)   # 27.000 puntos = 77 % del limite diario (GPT 05/10: no agotar los 35.000)
        self.assertLess(vr.STAGES[-1]["daily"] * vr.POINTS_PER_CREATE, 0.8 * vr.POINTS_PER_DAY)
        self.assertLess(vr.STAGES[-1]["daily"], vr.API_WRITES_PER_DAY)

    def test_decide(self):
        self.assertEqual(vr.decide(HEALTHY, 2, 1)[0], "advance")
        self.assertEqual(vr.decide(HEALTHY, vr.MIN_DAYS_AT_STAGE - 1, 1)[0], "hold")              # hacen falta MIN_DAYS_AT_STAGE dias
        self.assertEqual(vr.decide({**HEALTHY, "followback_rate": 0.13, "followback_baseline": 0.22}, 5, 2)[0], "regress")   # caida >30 %
        self.assertEqual(vr.decide({**HEALTHY, "follow_ratio": 7.0}, 5, 2)[0], "hold")
        self.assertEqual(vr.decide(HEALTHY, 1, 1)[0], "hold")                                      # poco tiempo en la etapa
        self.assertEqual(vr.decide({**HEALTHY, "rate_limited": 2}, 5, 3)[0], "regress")            # un 429 baja
        self.assertEqual(vr.decide({**HEALTHY, "followback_rate": 0.05, "followback_n": 80}, 5, 3)[0], "regress")
        self.assertEqual(vr.decide({**HEALTHY, "followback_rate": 0.05, "followback_n": 10}, 5, 3)[0], "advance")   # muestra pequena: no frena
        self.assertEqual(vr.decide({**HEALTHY, "unique_ratio": 0.3}, 5, 2)[0], "hold")             # falta oferta
        self.assertEqual(vr.decide({**HEALTHY, "utilization": 0.4}, 5, 2)[0], "advance")           # plan corto = falta oferta: pasar de etapa la arregla
        self.assertEqual(vr.decide({**HEALTHY, "unique_ratio": 0.46}, 5, 1)[0], "advance")         # etapas bajas: 45 %
        self.assertEqual(vr.decide({**HEALTHY, "unique_ratio": 0.46}, 5, 2)[0], "hold")            # para entrar en la 3 se exige 55 % (GPT)
        self.assertEqual(vr.decide({**HEALTHY, "unique_ratio": 0.57}, 5, 2)[0], "advance")
        self.assertEqual(vr.decide(HEALTHY, 9, len(vr.STAGES) - 1)[0], "hold")                     # ya al maximo

    def test_high_stages_shorten_the_doubts_and_stalls_so_the_day_fits(self):
        import random
        import volume_shape as vs
        vr.save({"stage": 1, "since": "2026-10-05", "history": []}, self.path)
        low = vr.pause_doubts(self.path)
        vr.save({"stage": 5, "since": "2026-10-05", "history": []}, self.path)
        high = vr.pause_doubts(self.path)
        self.assertLess(high[0] + high[1], low[0] + low[1])
        rng = random.Random(7)
        mean = lambda doubts, a, b: sum(vs.human_gap(rng, a, b, *doubts) for _ in range(40000)) / 40000
        self.assertGreater(mean(low, 1.5, 5.0), 5.5)
        self.assertLess(mean(high, 1.2, 3.5), 4.5)          # 8.000 acciones x ~4 s + ~0,5 s de escritura caben en ~10 h

    def test_apply_moves_the_stage_within_bounds_and_records_history(self):
        state = {"stage": 0, "since": "2026-10-01", "history": []}
        state = vr.apply(state, "regress", "x", datetime.date(2026, 10, 6))
        self.assertEqual(state["stage"], 0)
        state = vr.apply(state, "advance", "ok", datetime.date(2026, 10, 7))
        self.assertEqual((state["stage"], state["since"]), (1, "2026-10-07"))
        self.assertEqual(state["history"][-1]["to"], 1)
        self.assertEqual(vr.days_at_stage(state, datetime.date(2026, 10, 9)), 2)

    def test_coverage_knobs_grow_with_the_stage(self):
        cfg0 = {"budgets": {}, "shortlist": {}, "coverage": {"post_queries_per_family": 2, "tag_queries_per_round": 5}}
        vr.save({"stage": 4, "since": "2026-10-05", "history": []}, self.path)
        cfg = vr.overlay(cfg0, self.path)
        self.assertEqual(cfg["coverage"]["post_queries_per_family"], 6)
        self.assertEqual(cfg["coverage"]["tag_queries_per_round"], 17)
        self.assertEqual(cfg0["coverage"]["post_queries_per_family"], 2)

    def test_unreadable_file_means_stage_zero(self):
        with open(self.path, "w") as f:
            f.write("{no json")
        self.assertEqual(vr.load(self.path)["stage"], 0)


if __name__ == "__main__":
    unittest.main()
