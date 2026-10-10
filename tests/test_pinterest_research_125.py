"""Pinterest #125: pruebas puras de descubrimiento y métricas; ninguna red."""
import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import pinterest_niche as niche
import pinterest_organic_insights as insights


class QueryAndMediaTests(unittest.TestCase):
    def test_existing_growth_import_and_romantasy_filter(self):
        import pinterest_growth as growth
        self.assertIn(("romantasy libros recomendados", None), growth.QUERY_POOL)
        self.assertTrue(growth.pin_ok("Mis lecturas de romantasy favoritas",
                                      "Son novelas románticas con magia en español"))
        self.assertFalse(growth.pin_ok("Shop romantasy merch",
                                       "Compra con descuento en tienda"))

    def test_query_intentions_es_and_uniqueness(self):
        result = niche.merge_queries([("Libros de fantasía", None),
                                      ("ROMANTASY libros recomendados", "existing")])
        names = [r[0] for r in result]
        self.assertEqual(len(names), len({t.casefold() for t in names}))
        self.assertIn("enemigos a amantes fantasía juvenil", names)
        self.assertEqual(result[1][1], "existing")
        self.assertGreaterEqual(len(names), 18)

    def test_unicode_alias_deduplicated(self):
        self.assertEqual(niche.merge_queries([("romantasy libros recomendados", None)],
                                            [" ROMANTASY  libros recomendados "]),
                         [("romantasy libros recomendados", None)])

    def test_largest_image_area_not_max_side(self):
        pin = {"media": {"images": {
            "very_wide": {"width": 1600, "height": 100, "url": "https://i.pinimg.com/x.jpg"},
            "poster": {"width": 1000, "height": 1500, "url": "https://i.pinimg.com/y.jpg"},
            "malicious": {"width": 4000, "height": 4000, "url": "https://i.pinimg.com.evil/x"},
        }}}
        self.assertEqual(niche.largest_image(pin), ("https://i.pinimg.com/y.jpg", 1000, 1500))

    def test_media_invalid_is_unknown(self):
        self.assertIsNone(niche.largest_image({"media": {"images": {
            "a": {"width": True, "height": 1000, "url": "https://i.pinimg.com/a"}
        }}}))
        self.assertIsNone(niche.largest_image({}))


class OrganicInsightsTests(unittest.TestCase):
    def sample(self):
        return [
            {"id": "2", "title": "Más visitas", "pin_metrics": {"90d": {
                "impression": 1000, "pin_click": 400, "clickthrough": 20, "save": 11}}},
            {"id": "1", "title": "Pocas impresiones", "pin_metrics": {"90d": {
                "impression": 5, "clickthrough": 4}}},
            {"id": "3", "title": "Falta métrica", "pin_metrics": {"90d": {
                "impression": 200}}},
        ]

    def test_only_comparable_pins_ranked(self):
        result = insights.summarize(self.sample())
        self.assertEqual((result["total_pins"], result["comparable_pins"]), (3, 1))
        self.assertEqual(result["ranked"][0]["pin_id"], "2")
        self.assertEqual(result["ranked"][0]["clickthrough_per_impression"], .02)
        self.assertEqual(result["unranked"][1]["metrics"]["clickthrough"], None)

    def test_visual_observation_has_three_states(self):
        sample = self.sample()[:1]
        sample[0]["media"] = {"images": {
            "vertical": {"width": 1000, "height": 1500,
                         "url": "https://i.pinimg.com/1000x1500/pin.jpg"}
        }}
        row = insights.summarize(sample)["ranked"][0]
        self.assertTrue(row["vertical_2_3"])
        self.assertEqual(row["image_dimensions"], [1000, 1500])
        missing = insights.summarize([{"id": "x"}])["unranked"][0]
        self.assertIsNone(missing["vertical_2_3"])

    def test_lifetime_is_not_substituted_for_90d(self):
        pins = [{"id": "10", "pin_metrics": {"lifetime_metrics": {
            "impression": 1000, "clickthrough": 50}}}]
        self.assertEqual(insights.summarize(pins)["comparable_pins"], 0)
        self.assertEqual(insights.summarize(pins, window="lifetime_metrics")["comparable_pins"], 1)

    def test_duplicates_fail_closed_and_missing_not_zero(self):
        pin = {"id": 10, "pin_metrics": {"90d": {"impression": 300}}}
        with self.assertRaisesRegex(ValueError, "duplicado"):
            insights.summarize([pin, dict(pin, id="10")])
        row = insights.summarize([pin])["unranked"][0]
        self.assertEqual(row["source"], "offline_unverified_json")
        self.assertIsNone(row["metrics"]["clickthrough"])
        self.assertIsNone(row["clickthrough_per_impression"])

    def test_negative_bool_and_nonnumeric_metrics_rejected(self):
        for value in (-2, True, "20", 2.5):
            with self.subTest(value=value):
                data = [{"id": "1", "pin_metrics": {"90d": {
                    "impression": 500, "clickthrough": value}}}]
                self.assertFalse(insights.summarize(data)["ranked"])
        with self.assertRaises(ValueError):
            insights.summarize([{"id": True}])

    def test_invalid_threshold_and_window(self):
        with self.assertRaisesRegex(ValueError, "procedencia"):
            insights.summarize([], provenance="confirmed")
        with self.assertRaises(ValueError):
            insights.summarize([], min_impressions=0)
        with self.assertRaises(ValueError):
            insights.summarize([], window="all")
        with self.assertRaises(ValueError):
            insights.summarize([None])

    def test_reject_incomplete_pagination_offline(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "pins.json"
            path.write_text(json.dumps({"items": [], "bookmark": "next"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "incompleta"):
                insights._from_json(path)
            path.write_text(json.dumps({"items": self.sample(), "bookmark": None}), encoding="utf-8")
            self.assertEqual(len(insights._from_json(path)), 3)

    def test_demo_never_touches_api(self):
        with patch.dict(sys.modules, {"pinterest_api_audit": None}):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(insights.main(["--demo"]), 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["comparable_pins"], 1)
        self.assertEqual(data["ranked"][0]["source"], "synthetic_demo")


if __name__ == "__main__":
    unittest.main()
