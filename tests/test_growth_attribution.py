"""growth_attribution.py (02/10): follow-back por combinacion de acciones."""
import datetime
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import growth_attribution as ga

TODAY = datetime.date(2026, 10, 2)


def row(cuenta, tipo, fecha="2026-09-25", resultado="confirmado"):
    return {"cuenta": cuenta, "tipo": tipo, "fecha": fecha, "resultado": resultado}


class AttributeTests(unittest.TestCase):
    def test_groups_by_combo_and_counts_followbacks(self):
        rows = [row("@a", "follow"), row("@a", "like"), row("@a", "reply"),
                row("@b", "follow"), row("@c", "follow"), row("@c", "favourite")]
        table = ga.attribute(rows, ["a"], TODAY)
        self.assertEqual(table, {"like+reply": [1, 1], "solo_follow": [1, 0], "like": [1, 0]})

    def test_recent_follows_and_failures_are_excluded(self):
        rows = [row("@a", "follow", fecha="2026-10-02"), row("@b", "follow", resultado="fallo:x")]
        self.assertEqual(ga.attribute(rows, ["a", "b"], TODAY), {})

    def test_federated_and_local_names_match(self):
        rows = [row("@ana", "follow")]
        self.assertEqual(ga.attribute(rows, ["ana@x.social"], TODAY), {"solo_follow": [1, 1]})
        self.assertEqual(ga.attribute([row("@ana@x.social", "follow")], ["ana"], TODAY), {"solo_follow": [1, 1]})
        self.assertEqual(ga.attribute([row("@ana@x.social", "follow")], ["ana@y.social"], TODAY), {"solo_follow": [1, 0]})


class CombinedKindTests(unittest.TestCase):
    def test_legacy_combined_tipos_are_split(self):
        rows = [row("@a", "follow"), row("@a", "favourite+reply"), row("@b", "follow+like")]
        table = ga.attribute(rows, ["a"], TODAY)
        self.assertEqual(table, {"like+reply": [1, 1], "like": [1, 0]})


class ReplyStyleTests(unittest.TestCase):
    def test_arm_is_deduced_from_word_count(self):
        self.assertEqual(ga.reply_arm("Qué buena idea, enhorabuena"), "micro")
        self.assertEqual(ga.reply_arm("Una respuesta bastante más larga que ocho palabras seguro"), "elaborada")

    def test_by_reply_style_counts_followbacks_per_arm(self):
        def r(cuenta, tipo, texto="", fecha="2026-09-25"):
            return {"cuenta": cuenta, "tipo": tipo, "fecha": fecha, "resultado": "confirmado", "texto_usado": texto}
        rows = [r("@a", "follow"), r("@a", "reply", "Qué bueno"),
                r("@b", "follow"), r("@b", "reply", "Una respuesta bastante más larga que ocho palabras seguro"),
                r("@c", "follow"), r("@c", "reply", "Me gusta mucho")]
        table = ga.by_reply_style(rows, ["a", "b"], TODAY)
        self.assertEqual(table, {"micro": [2, 1], "elaborada": [1, 1]})

    def test_wilson_interval_is_wide_for_tiny_samples(self):
        low, high = ga.wilson(1, 2)
        self.assertLess(low, 0.15)
        self.assertGreater(high, 0.85)
        self.assertEqual(ga.wilson(0, 0), (0.0, 1.0))


class HoldoutViewTests(unittest.TestCase):
    def test_counts_only_aged_control_candidates_that_follow_us_anyway(self):
        rows = [{"fecha": "2026-09-01", "cuenta": "@a"}, {"fecha": "2026-09-01", "cuenta": "@b@x.social"},
                {"fecha": "2026-09-01", "cuenta": "@c"}, {"fecha": "2026-10-01", "cuenta": "@d"}]
        self.assertEqual(ga.holdout_view(rows, ["a", "b@x.social", "d"], TODAY, min_age=14), (3, 2))


class AgeCurveTests(unittest.TestCase):
    def test_curve_counts_follows_by_minimum_age(self):
        rows = [row('@a', 'follow', '2026-09-30'), row('@b', 'follow', '2026-09-20'), row('@c', 'follow', '2026-10-01')]
        curve = dict((edge, (seen, back)) for edge, seen, back in ga.age_curve(rows, ['b'], TODAY, edges=(1, 3, 7)))
        self.assertEqual(curve[1], (3, 1))
        self.assertEqual(curve[3], (1, 1))
        self.assertEqual(curve[7], (1, 1))


if __name__ == "__main__":
    unittest.main()
