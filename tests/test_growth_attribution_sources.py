import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import growth_attribution as ga

TODAY = datetime.date(2026, 10, 10)


def row(account, notes, date="2026-10-05", kind="follow", result="confirmado"):
    return {"fecha": date, "cuenta": "@" + account, "tipo": kind, "resultado": result, "notas": notes}


class SourceTests(unittest.TestCase):
    def test_source_of(self):
        self.assertEqual(ga.source_of("growth:auto_follow:score=14.2:umbral_mecanico:src=thread_commenter"), "thread_commenter")
        self.assertEqual(ga.source_of("growth:auto_like:score=11.9:umbral_mecanico:src=search/fantasia"), "search/fantasia")
        self.assertEqual(ga.source_of("seed_wave:commenter:editorial:akane.bsky.social"), "seed_wave/comentarista/editorial")
        self.assertEqual(ga.source_of("seed_wave:seed:libreria"), "seed_wave/semilla")
        self.assertEqual(ga.source_of("growth:followback_wave:bio_nicho"), "followback_wave")
        self.assertEqual(ga.source_of("comunidad"), "otras")
        self.assertEqual(ga.source_of(None), "otras")

    def test_follow_back_by_source_ignores_young_follows_duplicates_and_unfollows(self):
        rows = [row("a.bsky.social", "x:src=s1"), row("b.bsky.social", "x:src=s1"), row("c.bsky.social", "x:src=s2"), row("a.bsky.social", "x:src=s2"),
                row("d.bsky.social", "x:src=s2", date="2026-10-09"), row("e.bsky.social", "x:src=s2", kind="unfollow"), row("f.bsky.social", "x:src=s2", result="fallo")]
        table = ga.by_source(rows, ["a.bsky.social", "c.bsky.social"], TODAY, 2)
        self.assertEqual(table, {"s1": [2, 1], "s2": [1, 1]})


if __name__ == "__main__":
    unittest.main()
