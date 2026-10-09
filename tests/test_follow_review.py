"""follow_review.py (03/10): follows sin devolver tras N dias, solo lectura."""
import datetime
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import follow_review as fr

TODAY = datetime.date(2026, 11, 5)


def row(cuenta, tipo, fecha, resultado="confirmado"):
    return {"cuenta": cuenta, "tipo": tipo, "fecha": fecha, "resultado": resultado}


class ReviewTests(unittest.TestCase):
    def test_lists_only_old_unreciprocated_follows_ordered_by_coldness(self):
        rows = [row("@fria", "follow", "2026-09-20"),
                row("@charlada", "follow", "2026-09-21"), row("@charlada", "reply", "2026-09-21"),
                row("@devuelve", "follow", "2026-09-20"),
                row("@reciente", "follow", "2026-10-25")]
        result = fr.review(rows, ["devuelve"], TODAY, days=30)
        self.assertEqual([r["account"] for r in result], ["fria", "charlada"])
        self.assertEqual(result[1]["actions"], "reply")

    def test_unfollowed_and_failed_follows_are_ignored(self):
        rows = [row("@a", "follow", "2026-09-01"), row("@a", "unfollow", "2026-10-01"),
                row("@b", "follow", "2026-09-01", resultado="fallo:x")]
        self.assertEqual(fr.review(rows, [], TODAY), [])


if __name__ == "__main__":
    unittest.main()
