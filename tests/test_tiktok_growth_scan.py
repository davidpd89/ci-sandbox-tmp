import pathlib
import sys
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import tiktok_growth_scan as ts


class TikTokGrowthScanTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "niche_terms": ["libro", "fantasía", "lectura"],
            "spam_terms": ["crypto"],
        }

    def test_candidate_filter_is_mechanical_and_niche_based(self):
        row = ts._candidate_from_snapshot(
            {
                "handle": "lectora",
                "caption": "¿Qué libro de fantasía recomendarías este otoño?",
                "source": "for_you",
            },
            config=self.config,
            known={},
            followed=set(),
            discarded=set(),
        )
        self.assertIsNotNone(row)
        self.assertGreaterEqual(row["niche_hits"], 2)

    def test_spam_and_politics_are_rejected(self):
        self.assertIsNone(ts._candidate_from_snapshot(
            {
                "handle": "spam",
                "caption": "crypto libro fantasía",
                "source": "for_you",
            },
            config=self.config, known={}, followed=set(), discarded=set(),
        ))
        self.assertIsNone(ts._candidate_from_snapshot(
            {
                "handle": "news",
                "caption": "El Gobierno aprueba medidas y este libro analiza el debate",
                "source": "for_you",
            },
            config=self.config, known={}, followed=set(), discarded=set(),
        ))

    def test_known_but_not_followed_profile_can_still_be_follow_candidate(self):
        rows = [{
            "handle": "lectora", "caption": "libro de fantasía",
            "source": "for_you", "niche_hits": 2, "known": True,
            "known_date": "2026-10-01", "followed": False, "url": None,
        }]
        out = ts._compact_shortlist(rows, limit=6)
        self.assertIn("follow", out[0]["actions"])

    def test_shortlist_uses_compact_ids_and_no_auto_writes(self):
        rows = [
            {
                "handle": "lectora",
                "caption": "¿Qué libro de fantasía estás leyendo?",
                "source": "for_you",
                "niche_hits": 2,
                "known": False,
                "known_date": None,
                "followed": False,
                "url": "https://www.tiktok.com/@lectora/video/1",
            },
            {
                "handle": "autora",
                "caption": "Proceso de escritura de mi novela",
                "source": "following",
                "niche_hits": 1,
                "known": True,
                "known_date": "2026-09-01",
                "followed": False,
                "url": None,
            },
        ]
        out = ts._compact_shortlist(rows, limit=6)
        self.assertEqual(out[0]["id"], "T001")
        self.assertEqual(out[0]["posts"][0]["id"], "T001-P1")
        self.assertIn("follow", out[0]["actions"])
        self.assertIn("comment", out[0]["posts"][0]["actions"])
        self.assertNotIn("auto_plan", out[0])


class FakeScanAdapter:
    def __init__(self, snapshots=None, fail=False):
        self.snapshots = list(snapshots or [])
        self.fail = fail
        self.calls = []

    def verify_active_account(self, expected):
        self.calls.append(("account", expected))
        return True

    def open_surface(self, surface):
        self.calls.append(("surface", surface))

    def current_post_snapshot(self, *, source):
        self.calls.append(("snapshot", source))
        if self.fail:
            import mobile_client as mc
            raise mc.MobileCliError("transport lost")
        return self.snapshots.pop(0)

    def copy_current_post_url(self):
        self.calls.append(("copy",))
        return None

    def swipe_next(self):
        self.calls.append(("swipe",))


class TikTokGrowthCollectTests(unittest.TestCase):
    def _config(self):
        return {
            "account": "autorademoescritor",
            "surfaces": {"for_you": True, "following": True, "search": False},
            "budgets": {"max_posts_total": 2, "posts_per_surface": 3, "shortlist": 6},
            "niche_terms": ["libro"],
            "spam_terms": [],
        }

    def test_total_read_budget_counts_attempts_not_only_accepted_candidates(self):
        adapter = FakeScanAdapter([
            {"handle": "a", "caption": "contenido sin nicho", "source": "for_you"},
            {"handle": "b", "caption": "otro contenido", "source": "for_you"},
        ])
        with mock.patch.object(ts.sc, "known_accounts", return_value={}), mock.patch.object(ts, "_followed_handles", return_value=set()), mock.patch.object(ts.sc, "discarded_handles", return_value=set()):
            result = ts.collect(adapter, self._config())
        self.assertEqual(result["fetched_posts"], 2)
        self.assertEqual(result["accepted_posts"], 0)
        self.assertEqual([call for call in adapter.calls if call[0] == "snapshot"], [("snapshot", "for_you"), ("snapshot", "for_you")])
        self.assertNotIn(("surface", "following"), adapter.calls)

    def test_transport_error_is_terminal_during_discovery(self):
        import mobile_client as mc
        adapter = FakeScanAdapter(fail=True)
        with mock.patch.object(ts.sc, "known_accounts", return_value={}), mock.patch.object(ts, "_followed_handles", return_value=set()), mock.patch.object(ts.sc, "discarded_handles", return_value=set()):
            with self.assertRaises(mc.MobileCliError):
                ts.collect(adapter, self._config())

class RecurrenceAndLaneTests(unittest.TestCase):
    def row(self, handle, ctx, source="user_search", **kw):
        base = {"handle": handle, "caption": "", "source": source, "niche_hits": 2, "score": 4.0,
                "known": False, "known_date": None, "followed": False, "ctx": ctx, "name": handle}
        base.update(kw)
        return base

    def test_independent_contexts_beat_repeats_of_the_same_query(self):
        rows = [self.row("a", "user_search:q1"), self.row("a", "user_search:q1"),
                self.row("b", "user_search:q1"), self.row("b", "video_search:q2", "video_search:comment"),
                self.row("b", "seed_comments:s1", "video_search:comment")]
        out = {c["handle"]: c for c in ts._compact_shortlist(rows, limit=10, config={"scoring": {}})}
        self.assertEqual(out["a"]["independent"], 1)
        self.assertEqual(out["b"]["independent"], 3)
        self.assertGreater(out["b"]["score"], out["a"]["score"] + 2)

    def test_creator_and_community_lanes(self):
        rows = [self.row("libreria_x", "c1", name="Librería X"), self.row("amiga", "c2", relation="follows_me"),
                self.row("persona", "c3", name="Persona")]
        lanes = {c["handle"]: c["lane"] for c in ts._compact_shortlist(rows, limit=10, config={"scoring": {}})}
        self.assertEqual(lanes, {"libreria_x": "creator", "amiga": "community", "persona": "acquisition"})


if __name__ == "__main__":
    unittest.main()
