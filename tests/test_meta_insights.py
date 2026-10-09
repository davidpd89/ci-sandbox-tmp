import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import meta_insights as mi


class InsightsTests(unittest.TestCase):
    def test_engagement_sums_all_interactions_and_ignores_missing(self):
        self.assertEqual(mi.engagement({"likes": 2, "comments": 1, "saved": None, "shares": 3}), 6)
        self.assertEqual(mi.engagement({}), 0)

    def test_rank_orders_by_interactions_then_reach(self):
        rows = [{"id": "a", "likes": 1, "reach": 50}, {"id": "b", "likes": 5},
                {"id": "c", "likes": 1, "reach": 90}]
        self.assertEqual([r["id"] for r in mi.rank(rows)], ["b", "c", "a"])

    def test_metrics_flattens_api_payload(self):
        payload = {"data": [{"name": "reach", "values": [{"value": 7}]}, {"name": "saved", "values": []}]}
        self.assertEqual(mi._metrics(payload), {"reach": 7, "saved": 0})

    def test_render_never_prints_unknown_payload_and_reports_warnings(self):
        rows = [{"red": "facebook", "fecha": "2026-10-02", "tipo": "POST", "texto": "Hola", "likes": 2}]
        text = mi.render(rows, ["instagram: falta IG_ACCESS_TOKEN"])
        self.assertIn("facebook: 1 posts, media 2.0 interacciones", text)
        self.assertIn("AVISO instagram", text)

    def test_render_breaks_down_by_format_when_a_network_has_several(self):
        rows = [{"red": "instagram", "fecha": "2026-10-02", "tipo": "CAROUSEL_ALBUM", "texto": "a", "likes": 4, "reach": 20},
                {"red": "instagram", "fecha": "2026-10-03", "tipo": "VIDEO", "texto": "b", "likes": 1, "reach": 10}]
        text = mi.render(rows, [])
        self.assertIn("instagram CAROUSEL_ALBUM: 1 posts, 4.0 interacciones, alcance medio 20", text)
        self.assertIn("instagram VIDEO: 1 posts, 1.0 interacciones, alcance medio 10", text)


if __name__ == "__main__":
    unittest.main()
