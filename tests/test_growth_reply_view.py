"""growth_reply_view.py (02/10): candidatos a reply compactos."""
import datetime
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import growth_reply_view as grv

SPANISH = "Acabo de terminar la novela y me ha dejado con muchas ganas de seguir leyendo la saga"


def cand(handle, text=SPANISH, lane="acquisition", score=1.0, actions=("reply",)):
    return {"handle": handle, "lane": lane, "score": score,
            "posts": [{"id": f"{handle}-P1", "text": text, "actions": list(actions)}]}


def handles(*cands, skip=frozenset()):
    return [r["handle"] for r in grv.view({"shortlist": list(cands)}, skip)]


class ViewTests(unittest.TestCase):
    def test_keeps_spanish_posts_with_enough_own_text(self):
        self.assertEqual(handles(cand("a")), ["a"])

    def test_drops_english_short_and_link_only_posts(self):
        self.assertEqual(handles(cand("a", text="Currently reading a great book about dragons and magic")), [])
        self.assertEqual(handles(cand("b", text="Buen libro")), [])
        self.assertEqual(handles(cand("c", text="https://x.y/z #libros #booksky @alguien " * 4)), [])

    def test_drops_bridge_accounts_and_recent_targets(self):
        self.assertEqual(handles(cand("bot.mastodon.social.ap.brid.gy")), [])
        self.assertEqual(handles(cand("a"), skip={"a"}), [])

    def test_federated_handle_matches_local_registro_name(self):
        self.assertEqual(handles(cand("severianx@mastodon.la"), skip={"severianx"}), [])

    def test_posts_without_reply_action_are_ignored(self):
        self.assertEqual(handles(cand("a", actions=("like",))), [])

    def test_community_first_then_score(self):
        rows = grv.view({"shortlist": [
            cand("fria", score=9.0), cand("amiga", lane="community", score=1.0),
        ]})
        self.assertEqual([r["handle"] for r in rows], ["amiga", "fria"])


class FreshnessTests(unittest.TestCase):
    NOW = datetime.datetime(2026, 10, 3, 12, 0, tzinfo=datetime.timezone.utc)

    def cand_at(self, handle, created, likes, lane="acquisition"):
        c = cand(handle, lane=lane)
        c["posts"][0]["created_at"] = created
        c["posts"][0]["stats"] = {"likes": likes, "replies": 0}
        return c

    def test_recent_posts_beat_more_liked_old_ones(self):
        rows = grv.view({"shortlist": [
            self.cand_at("vieja_famosa", "2026-10-01T10:00:00Z", 300),
            self.cand_at("reciente", "2026-10-03T10:30:00Z", 2),
            self.cand_at("de_hoy", "2026-10-03T03:00:00Z", 40),
        ]}, now=self.NOW)
        self.assertEqual([r["handle"] for r in rows], ["reciente", "de_hoy", "vieja_famosa"])
        self.assertAlmostEqual(rows[0]["age_h"], 1.5, places=1)

    def test_community_still_first_and_missing_dates_go_last(self):
        rows = grv.view({"shortlist": [
            self.cand_at("fresca", "2026-10-03T11:00:00Z", 1),
            self.cand_at("amiga_vieja", "2026-09-01T10:00:00Z", 1, lane="community"),
            cand("sin_fecha"),
        ]}, now=self.NOW)
        self.assertEqual([r["handle"] for r in rows], ["amiga_vieja", "fresca", "sin_fecha"])
        self.assertIsNone(rows[2]["age_h"])


class ActionTests(unittest.TestCase):
    def test_action_selects_repost_candidates(self):
        c = cand("a", actions=("like", "repost"))
        self.assertEqual([r["handle"] for r in grv.view({"shortlist": [c]}, action="repost")], ["a"])
        self.assertEqual(grv.view({"shortlist": [c]}), [])


class VisibilityTests(unittest.TestCase):
    def test_acquisition_sorted_by_likes_before_score(self):
        def stat(handle, likes, score):
            c = cand(handle, score=score)
            c["posts"][0]["stats"] = {"likes": likes, "replies": 2}
            return c
        rows = grv.view({"shortlist": [stat("poca", 3, 9.0), stat("mucha", 120, 1.0)]})
        self.assertEqual([r["handle"] for r in rows], ["mucha", "poca"])
        self.assertEqual(rows[0]["likes"], 120)


if __name__ == "__main__":
    unittest.main()
