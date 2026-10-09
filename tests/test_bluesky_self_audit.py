import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import bluesky_self_audit as au

TODAY = datetime.date(2026, 10, 5)


def row(account, kind="like", date="2026-10-05", result="confirmado", text=""):
    return {"fecha": date, "cuenta": account, "tipo": kind, "resultado": result, "texto_usado": text}


class PureTests(unittest.TestCase):
    def test_unique_ratio(self):
        rows = [row("@a"), row("@a"), row("@b"), row("@c")]
        ratio, touched = au.unique_ratio(rows)
        self.assertAlmostEqual(ratio, 0.75)
        self.assertAlmostEqual(touched, 0.25)
        self.assertEqual(au.unique_ratio([]), (None, None))

    def test_confirmed_and_write_filters(self):
        rows = [row("@a"), row("@b", result="fallo"), row("@c", date="2026-09-01"), row("@d", kind="comentario")]
        self.assertEqual(len(au.write_actions(au.confirmed(rows, TODAY))), 1)

    def test_parse_round_log(self):
        text = ("[bluesky] plan construido: 148 acciones\n[bluesky] volumen del dia x1.38 (semana x0.89); tope de esta ronda 341 (hoy ya 152); "
                "plan 75 -> 73 acciones; 73 likes de cuentas repetidas omitidos; 2 follows apartados\nHTTP 429 Too Many Requests")
        info = au.parse_round_log(text)
        self.assertEqual((info["plan"], info["cap"], info["omitted"]), (148, 341, 73))
        self.assertGreaterEqual(info["rate_limited"], 1)
        self.assertEqual(au.parse_round_log("nada")["plan"], None)

    def test_exhausted_surfaces(self):
        rows = [{"fecha": "2026-10-04", "surface": "tag_search", "fetched": "30", "new_handles": "0"}] * 6 + \
               [{"fecha": "2026-10-04", "surface": "engagers", "fetched": "300", "new_handles": "120"}] * 6 + \
               [{"fecha": "2026-10-04", "surface": "rara", "fetched": "30", "new_handles": "0"}] * 2
        self.assertEqual([e[0] for e in au.exhausted_surfaces(rows, TODAY - datetime.timedelta(days=7))], ["tag_search"])

    def test_seed_coverage(self):
        seeds = {"a": {"type": "editorial", "last_scanned": "2026-10-04", "yield": 5}, "b": {"type": "autor", "last_scanned": None, "yield": None},
                 "c": {"type": "autor", "last_scanned": "2026-09-01", "yield": 0}}
        cov = au.seed_coverage(seeds, TODAY)
        self.assertEqual((cov["total"], cov["scanned_recently"], cov["parked"]), (3, 1, 1))
        self.assertEqual(cov["by_type"], {"editorial": 1, "autor": 2})


class GapTests(unittest.TestCase):
    BASE = {"target": 1500, "done_today": 1400, "stage": 1, "hours_elapsed": 20, "plan": 900, "cap": 1000, "unique_ratio": 0.7, "rate_limited": 0,
            "followback_n": 80, "followback_rate": 0.22, "exhausted": [], "seeds": {"total": 300, "scanned_recently": 200}, "reply_notes": [],
            "follow_ratio": 2.0, "omitted": 10}

    def gaps(self, **changes):
        return [g for g, _ in au.gaps({**self.BASE, **changes})]

    def test_healthy_system_has_no_gaps(self):
        self.assertEqual(self.gaps(), [])

    def test_each_gap_is_detected_with_a_corrective_action(self):
        cases = {
            "volumen": {"done_today": 300},
            "OFERTA": {"plan": 120, "cap": 340},
            "objetivos unicos": {"unique_ratio": 0.39},
            "429": {"rate_limited": 3},
            "follow-back": {"followback_rate": 0.07},
            "fuentes sin handles": {"exhausted": [("tag_search", 6, 30, 0)]},
            "semillas curadas": {"seeds": {"total": 40, "scanned_recently": 40}},
            "semillas recorridas": {"seeds": {"total": 300, "scanned_recently": 50}},
            "replies": {"reply_notes": ["6/10 replies tienen el mismo formato"]},
            "siguiendo/seguidores": {"follow_ratio": 5.2},
            "COLECTOR": {"jetstream_posts_2h": 12},
            "RESERVA": {"pool": {"available_now": 400}},
            "EJECUCION": {"plan_failures": 1},
            "CALIDAD del plan: solo 70 %": {"plan_quality": {"likes": 400, "spanish": 0.7, "niche_post": 0.6}},
            "llevan un termino del nicho": {"plan_quality": {"likes": 400, "spanish": 0.97, "niche_post": 0.2}},
            "sin ningun post": {"shortlist_no_posts": 0.59},
        }
        for needle, change in cases.items():
            found = au.gaps({**self.BASE, **change})
            self.assertTrue(any(needle in g for g, _ in found), (needle, found))
            self.assertTrue(all(action for _, action in found))

    def test_volume_gap_waits_until_late_in_the_day(self):
        self.assertEqual(self.gaps(done_today=100, hours_elapsed=9), [])

    def test_report_renders(self):
        m = {"date": "2026-10-05", "stage": 0, "target": 700, "days_at_stage": 1, "done_today": 10, "mix": {"like": 10}, "done_yesterday": 500,
             "utilization": 0.7, "unique_ratio": None, "plan": 100, "cap": 300, "omitted": 5, "seeds": {"total": 40, "by_type": {}, "scanned_recently": 10},
             "rate_limited": 0, "follow_ratio": 3.3, "followback_rate": None, "followback_n": 0, "by_source": {}}
        text = au.render(m, [("x", "y")])
        self.assertIn("GAP: x", text)
        self.assertIn("n/d", text)


if __name__ == "__main__":
    unittest.main()
