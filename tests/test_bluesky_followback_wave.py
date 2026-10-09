"""bluesky_followback_wave.py (02/10): seleccion por probabilidad de follow-back."""
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import bluesky_followback_wave as wave


def cand(handle, *, followers=300, following=400, signals=("bio afín al nicho",),
         bio="Escritora de fantasía", actions=("follow",)):
    return {
        "handle": handle, "lane": "acquisition", "actions": list(actions),
        "signals": list(signals),
        "profile": {"bio": bio, "followers": followers, "following": following},
    }


class SelectTests(unittest.TestCase):
    def pick(self, *cands, already=frozenset()):
        return [r["handle"] for r in wave.select({"shortlist": list(cands)}, already)]

    def test_keeps_niche_account_that_follows_back_prone_ratio(self):
        self.assertEqual(self.pick(cand("a")), ["a"])

    def test_requires_niche_signal(self):
        self.assertEqual(self.pick(cand("a", signals=())), [])

    def test_rejects_low_following_and_huge_accounts(self):
        self.assertEqual(self.pick(cand("a", following=20)), [])
        self.assertEqual(self.pick(cand("b", followers=50000, following=60000)), [])

    def test_rejects_accounts_that_barely_follow_anyone_back(self):
        self.assertEqual(self.pick(cand("a", followers=1000, following=200)), [])

    def test_rejects_political_bio_and_already_planned(self):
        self.assertEqual(self.pick(cand("a", bio="Libros y #FreePalestine gaza")), [])
        self.assertEqual(self.pick(cand("b"), already={"b"}), [])

    def test_ignores_candidates_without_follow_action(self):
        self.assertEqual(self.pick(cand("a", actions=("like",))), [])



class ActivistHintsTests(unittest.TestCase):
    def test_niche_words_are_not_activism(self):
        import scan_common as sc
        for text in ("Hoy podemos ver una serie", "Maga de fuego en mi novela",
                     "Resistencia del pueblo élfico", "Lectora feminista de fantasía"):
            self.assertFalse(sc.looks_activist(text), text)

    def test_real_activism_markers_still_flagged(self):
        import scan_common as sc
        for text in ("#FreePalestine gaza", "🍉 Boicot a todo", "stop trump"):
            self.assertTrue(sc.looks_activist(text), text)




class DailyCapTests(unittest.TestCase):
    def run_main(self, room):
        with tempfile.TemporaryDirectory() as tmp:
            state, out = os.path.join(tmp, "state.json"), os.path.join(tmp, "wave.json")
            with open(state, "w", encoding="utf-8") as stream:
                json.dump({"shortlist": [cand(f"c{i}") for i in range(5)], "auto_plan": []}, stream)
            with patch.object(wave, "follows_allowed_today", return_value=room), patch.object(wave, "_follow_ratio", return_value=1.0):
                wave.main([state, out])
            with open(out, encoding="utf-8") as stream:
                return json.load(stream)

    def test_exhausted_daily_quota_writes_an_empty_wave(self):
        """05/10: con `if limit:` un cupo de 0 no recortaba y la oleada saco 105 follows con el cupo diario agotado."""
        self.assertEqual(self.run_main(0), [])

    def test_quota_truncates_the_wave(self):
        self.assertEqual(len(self.run_main(2)), 2)

if __name__ == "__main__":
    unittest.main()
