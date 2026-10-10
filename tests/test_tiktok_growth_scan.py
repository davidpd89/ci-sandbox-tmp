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


<<<<<<< HEAD
=======
class QualityGateTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "niche_terms": ["libro", "fantasía", "lectura", "novela"],
            "spam_terms": [],
            "scoring": {"min_follow_score": 2, "auto_follow_score_min": 2},
        }

    def _row(self, **kwargs):
        row = {
            "handle": "ana_libros", "name": "Ana", "bio": "",
            "caption": "", "source": "user_search", "niche_hits": 2,
            "score": 12, "known": False, "known_date": None,
            "followed": False, "url": None, "ctx": "user_search:libros",
        }
        row.update(kwargs)
        return row

    def test_name_only_is_visible_for_review_but_not_auto_followed(self):
        rows = [self._row(name="Ana Libros")]
        shortlist = ts._compact_shortlist(rows, limit=3, config=self.config)
        self.assertEqual(shortlist[0]["quality"], "review")
        self.assertNotIn("follow", shortlist[0]["actions"])
        self.assertFalse(any(a["kind"] == "follow" for a in ts.build_auto_plan(shortlist, self.config)))

    def test_own_book_post_keeps_relevant_candidate(self):
        rows = [self._row(
            source="for_you", caption="Estoy leyendo una novela de fantasía",
            url="https://www.tiktok.com/@ana_libros/video/123",
        )]
        shortlist = ts._compact_shortlist(rows, limit=3, config=self.config)
        self.assertEqual(shortlist[0]["quality"], "eligible")
        self.assertIn("follow", shortlist[0]["actions"])
        self.assertEqual([a["kind"] for a in ts.build_auto_plan(shortlist, self.config)
                          if a["kind"] == "follow"], ["follow"])

    def test_multiple_rows_gather_evidence_without_false_exclusion(self):
        rows = [
            self._row(name="Ana Libros"),
            self._row(source="for_you", caption="Leyendo una novela de fantasía",
                      url="https://www.tiktok.com/@ana_libros/video/321", ctx="for_you:1"),
        ]
        result = ts._compact_shortlist(rows, limit=4, config=self.config)[0]
        self.assertEqual(result["quality"], "eligible")
        self.assertEqual(result["independent"], 2)

    def test_previous_cached_shortlist_lacking_quality_cannot_auto_follow(self):
        legacy = [{
            "id": "T001", "handle": "ana_libros", "score": 100,
            "actions": ["follow"], "sources": ["user_search"],
            "posts": [],
        }]
        self.assertFalse(any(x["kind"] == "follow" for x in ts.build_auto_plan(legacy, self.config)))



>>>>>>> origin/research/public-reuse-parent
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
<<<<<<< HEAD
            "account": "autorademoescritor",
=======
            "account": "davidportoescritor",
>>>>>>> origin/research/public-reuse-parent
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

<<<<<<< HEAD
=======
class ProvenanceTests(unittest.TestCase):
    def _item(self, source, origin):
        return {
            "handle": "lectora", "name": "Lectora", "caption": "Un vídeo ajeno",
            "source": source, "ctx": origin["surface"] + ":" + origin["query"],
            "niche_hits": 2, "score": 9.0, "known": False,
            "known_date": None, "followed": False, "provenance": origin,
        }

    def test_shortlist_keeps_distinct_origins_without_duplicate_rows(self):
        first = {"surface": "seed_comments", "query": "editorial_a",
                 "source": "video_search:comment", "phase": "direct"}
        second = {"surface": "seed_comments", "query": "escritora_b",
                  "source": "video_search:comment", "phase": "frontier"}
        out = ts._compact_shortlist([
            self._item("video_search:comment", first),
            self._item("video_search:comment", first),
            self._item("video_search:comment", second),
        ], limit=3)[0]
        self.assertEqual(out["provenance"], [first, second])
        self.assertEqual(out["independent"], 2)
        self.assertEqual(out["posts"], [])  # comentarios no son vídeos propios

    def test_frontier_does_not_relabel_comment_as_video_author(self):
        import tiktok_discovery as disc
        seed = {"handle": "editorial_a", "name": "Editorial A", "source": "user_search",
                "score": 9.0, "followers": 2000}
        comment = self._item("video_search:comment", {
            "surface": "seed_comments", "query": "editorial_a",
            "source": "video_search:comment", "phase": "direct",
        })
        comment["comment_text"] = "Me gusta leer fantasía"
        rows = [seed]
        cfg = {"budgets": {"frontier_seeds": 1},
               "surfaces": {"seed_comments": True},
               "scoring": {"frontier_min_score": 7, "frontier_min_followers": 300}}
        with mock.patch.object(disc, "run_surface",
                               return_value=([comment], {"rows": 1, "valid": 1, "new": 1})):
            ts._run_frontier(object(), cfg, {}, rows, {}, set(), {})
        self.assertEqual(rows[1]["source"], "video_search:comment")
        self.assertEqual(rows[1]["provenance"]["phase"], "frontier")
        self.assertEqual(rows[1]["provenance"]["query"], "editorial_a")
        out = ts._compact_shortlist([rows[1]], limit=1)[0]
        self.assertEqual(out["posts"], [])


    def test_second_frontier_seed_retains_origin_without_a_second_action(self):
        import tiktok_discovery as disc
        seeds = [
            {"handle": "creator_a", "source": "user_search", "score": 9.0,
             "followers": 2000},
            {"handle": "creator_b", "source": "user_search", "score": 9.0,
             "followers": 2000},
        ]
        first = {"surface": "seed_comments", "query": "creator_a",
                 "source": "video_search:comment", "phase": "direct"}
        second = {"surface": "seed_comments", "query": "creator_b",
                  "source": "video_search:comment", "phase": "direct"}
        def observed(origin, handle):
            row = self._item("video_search:comment", origin)
            row["handle"] = handle
            return row
        by_seed = {
            "creator_a": [observed(first, "lectora"), observed(first, "otra")],
            "creator_b": [observed(second, "lectora")],
        }
        def scan(_nav, _surface, query, _config, _ctx):
            found = by_seed[query]
            return found, {"rows": len(found), "valid": len(found), "new": len(found)}
        cfg = {
            "budgets": {"frontier_seeds": 2},
            "surfaces": {"seed_comments": True},
            "scoring": {"frontier_min_score": 7, "frontier_min_followers": 300},
        }
        rows = list(seeds)
        with mock.patch.object(disc, "run_surface", side_effect=scan):
            ts._run_frontier(object(), cfg, {}, rows, {}, set(), {})
        # Sólo dos candidatos nuevos: la segunda semilla no crea otra
        # fila, plan ni puntuación para la misma persona.
        self.assertEqual(len(rows), 4)
        person = next(row for row in rows if row["handle"] == "lectora")
        out = ts._compact_shortlist([person], limit=1)[0]
        self.assertEqual(out["provenance"], [
            {**first, "phase": "frontier"},
            {**second, "phase": "frontier"},
        ])
        self.assertEqual(out["independent"], 1)  # metadatos no inflan score

    def test_contradictory_primary_origin_is_not_accepted_as_authorship(self):
        inconsistent = {
            "surface": "seed_comments", "query": "editorial_a",
            "source": "video_search:author", "phase": "frontier",
        }
        comment = self._item("video_search:comment", inconsistent)
        candidate = ts._compact_shortlist([comment], limit=1)[0]
        self.assertEqual(candidate["provenance"], [])
        self.assertEqual(candidate["posts"], [])


    def test_old_frontier_checkpoint_is_readonly_recovered_as_comment_role(self):
        import json
        import tempfile
        old = self._item("frontier:video_search:comment", {
            "surface": "seed_comments", "query": "old",
            "source": "video_search:comment", "phase": "frontier",
        })
        old.pop("provenance")
        old["url"] = "https://www.tiktok.com/@otro/video/123"  # URL ajena
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "checkpoint.jsonl"
            path.write_text(json.dumps(old, ensure_ascii=False) + "\n", encoding="utf-8")
            original_bytes = path.read_bytes()
            recovered = ts.load_checkpoint(str(path))
            self.assertEqual(path.read_bytes(), original_bytes)
        self.assertEqual(recovered[0]["source"], "video_search:comment")
        self.assertEqual(recovered[0]["provenance"]["phase"], "frontier")
        self.assertEqual(recovered[0]["provenance"]["query"], "")  # semilla no verificable
        self.assertEqual(ts._compact_shortlist(recovered, limit=1)[0]["posts"], [])

    def test_unrecognized_source_is_not_promoted_to_actionable_video(self):
        suspicious = self._item("frontier:other_unknown_role", {
            "surface": "seed_comments", "query": "editorial_a",
            "source": "frontier:other_unknown_role", "phase": "frontier",
        })
        suspicious["url"] = "https://www.tiktok.com/@otro/video/987"
        result = ts._compact_shortlist([suspicious], limit=1)[0]
        self.assertEqual(result["posts"], [])


    def test_unknown_source_is_review_only_even_with_high_score(self):
        unknown = self._item("frontier:unknown", {
            "surface": "seed_comments", "query": "seed",
            "source": "frontier:unknown", "phase": "frontier",
        })
        unknown["score"] = 1000
        unknown["url"] = "https://www.tiktok.com/@otro/video/987"
        config = {"scoring": {"min_follow_score": 0, "auto_follow_score_min": 0,
                              "auto_like_score_min": 0}}
        candidate = ts._compact_shortlist([unknown], limit=1, config=config)[0]
        self.assertEqual(candidate["score"], 0)
        self.assertEqual(candidate["posts"], [])
        self.assertNotIn("follow", candidate["actions"])
        self.assertEqual(ts.build_auto_plan([candidate], config), [])
        self.assertEqual(candidate["sources"], ["frontier:unknown"])

    def test_unknown_source_cannot_raise_recurrence_or_score_of_valid_source(self):
        legitimate = self._item("user_search", {
            "surface": "user_search", "query": "libros",
            "source": "user_search", "phase": "direct",
        })
        legitimate.update(score=1.0, ctx="user_search:libros", caption="")
        unknown = self._item("frontier:unknown", {
            "surface": "seed_comments", "query": "other",
            "source": "frontier:unknown", "phase": "frontier",
        })
        unknown.update(score=1000, ctx="seed_comments:other")
        candidate = ts._compact_shortlist(
            [legitimate, unknown], limit=1, config={"scoring": {"min_follow_score": 2}},
        )[0]
        self.assertEqual(candidate["score"], 1)
        self.assertEqual(candidate["independent"], 1)
        self.assertNotIn("follow", candidate["actions"])


    def test_provenance_cannot_claim_comment_from_wrong_surface(self):
        inconsistent = self._item("video_search:comment", {
            "surface": "user_search", "query": "libros",
            "source": "video_search:comment", "phase": "direct",
        })
        candidate = ts._compact_shortlist([inconsistent], limit=1)[0]
        self.assertEqual(candidate["provenance"], [])
        self.assertEqual(candidate["posts"], [])

    def test_provenance_rejects_unknown_phase_without_losing_comment_role(self):
        inconsistent = self._item("video_search:comment", {
            "surface": "seed_comments", "query": "editorial",
            "source": "video_search:comment", "phase": "promoted_author",
        })
        candidate = ts._compact_shortlist([inconsistent], limit=1)[0]
        self.assertEqual(candidate["provenance"], [])
        self.assertEqual(candidate["posts"], [])


    def test_followed_state_wins_regardless_of_checkpoint_row_order(self):
        origin = {"surface": "seed_comments", "query": "seed",
                  "source": "video_search:comment", "phase": "direct"}
        old = self._item("video_search:comment", origin)
        new = {**old, "followed": True, "ctx": "seed_comments:second"}
        for rows in ([old, new], [new, old]):
            item = ts._compact_shortlist(rows, limit=1)[0]
            self.assertTrue(item["followed"])
            self.assertNotIn("follow", item["actions"])

    def test_pending_follow_request_is_not_reissued_from_old_checkpoint(self):
        origin = {"surface": "seed_comments", "query": "seed",
                  "source": "video_search:comment", "phase": "direct"}
        old = self._item("video_search:comment", origin)
        current = {**old, "relation": "requested", "ctx": "seed_comments:new"}
        for rows in ([old, current], [current, old]):
            item = ts._compact_shortlist(rows, limit=1)[0]
            self.assertTrue(item["followed"])
            self.assertNotIn("follow", item["actions"])


    @unittest.skipUnless(
        hasattr(__import__("tiktok_discovery"), "assess_quality"),
        "contrato de integración #36: assess_quality aún no está en #37",
    )
    def test_quality_gate_must_ignore_unknown_source_even_with_trusted_low_evidence(self):
        trusted = self._item("user_search", {
            "surface": "user_search", "query": "libros",
            "source": "user_search", "phase": "direct",
        })
        trusted.update(caption="", comment_text="", bio="", score=10)
        unknown = self._item("frontier:unknown", {
            "surface": "seed_comments", "query": "legacy",
            "source": "frontier:unknown", "phase": "frontier",
        })
        unknown.update(caption="Leyendo una novela de fantasía", score=1000)
        config = {
            "niche_terms": ["novela", "fantasía"], "spam_terms": [],
            "scoring": {"min_follow_score": 2, "auto_follow_score_min": 2},
        }
        candidate = ts._compact_shortlist([trusted, unknown], limit=1, config=config)[0]
        self.assertEqual(candidate["quality"], "review")
        self.assertNotIn("follow", candidate["actions"])
        self.assertEqual(ts.build_auto_plan([candidate], config), [])


>>>>>>> origin/research/public-reuse-parent
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
