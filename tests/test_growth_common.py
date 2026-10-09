"""Pruebas offline de utilidades de crecimiento compartidas."""
import csv
import datetime
import pathlib
import tempfile
import unittest

import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import growth_common as gc


class GrowthCommonTests(unittest.TestCase):
    def test_read_budget_tracks_surfaces_and_fails_closed(self):
        budget = gc.ReadBudget(3)
        budget.take("search")
        budget.take("search")
        budget.take("thread")
        self.assertEqual(
            budget.snapshot(),
            {
                "used": 3,
                "maximum": 3,
                "remaining": 0,
                "by_surface": {"search": 2, "thread": 1},
            },
        )
        with self.assertRaises(gc.ReadBudgetExceeded):
            budget.take("extra")

    def test_budget_can_preserve_a_reserve(self):
        budget = gc.ReadBudget(10)
        for _ in range(7):
            budget.take("discovery")
        self.assertEqual(budget.remaining, 3)
        self.assertFalse(budget.can_spend(1, reserve=3))
        self.assertTrue(budget.can_spend(1, reserve=2))
        self.assertEqual(budget.snapshot()["remaining"], 3)

    def test_never_used_query_is_explored_before_recent_query(self):
        today = datetime.date(2026, 9, 29)
        stats = {
            ("post_search", "lectura"): {
                "attempts": 5,
                "fetched": 100,
                "accepted": 50,
                "new_handles": 25,
                "last_date": today,
            }
        }
        ranked = gc.rank_keys(
            ["lectura", "leyendo ahora"],
            stats,
            surface="post_search",
            today=today,
        )
        self.assertEqual(ranked[0], "leyendo ahora")

    def test_metrics_are_aggregated(self):
        today = datetime.date(2026, 9, 29)
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "metrics.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow([
                    "fecha", "run_id", "surface", "key",
                    "fetched", "accepted", "new_handles",
                ])
                writer.writerow(["2026-09-28", "a", "post_search", "lectura", 20, 10, 8])
                writer.writerow(["2026-09-29", "b", "post_search", "lectura", 10, 4, 3])
            stats = gc.load_discovery_metrics(str(path), today=today)
        row = stats[("post_search", "lectura")]
        self.assertEqual(row["attempts"], 2)
        self.assertEqual(row["fetched"], 30)
        self.assertEqual(row["accepted"], 14)
        self.assertEqual(row["new_handles"], 11)
        self.assertEqual(row["last_date"], today)


if __name__ == "__main__":
    unittest.main()
