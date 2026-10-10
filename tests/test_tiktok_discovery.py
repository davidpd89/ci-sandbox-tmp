import pathlib
import random
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import tiktok_discovery as d

CONFIG = {
    "niche_terms": ["libro", "libros", "novela", "booktok", "escritora", "editorial"],
    "spam_terms": ["kdp", "ghostwriting", "crypto"],
    "scoring": {},
}


def row(**kw):
    base = d.make_row("ana_libros", source="user_search", name="Ana", bio="")
    base.update(kw)
    return base


class ScoringTests(unittest.TestCase):
    def test_identity_beats_nothing_and_follows_me_needs_base_signal(self):
        strong = row(name="Ana Escritora de novela", relation="follows_me", followers=900)
        weak_bot = row(name="Servicios", bio="", relation="follows_me", followers=900)
        self.assertGreater(d.score_row(strong, CONFIG), 8)
        self.assertLess(d.score_row(weak_bot, CONFIG), 4)

    def test_english_and_huge_accounts_are_penalised(self):
        es = row(name="Lectora de libros", followers=1000)
        en = row(name="The books reader", followers=1000)
        huge = row(name="Lectora de libros", followers=900_000)
        self.assertGreater(d.score_row(es, CONFIG), d.score_row(en, CONFIG))
        self.assertGreater(d.score_row(es, CONFIG), d.score_row(huge, CONFIG))

    def test_spam_politics_self_and_existing_relations_are_rejected(self):
        self.assertFalse(d.validate_row(row(name="Amazon KDP formatting libros"), CONFIG))
<<<<<<< HEAD
        self.assertFalse(d.validate_row(row(handle="autorademoescritor"), CONFIG))
=======
        self.assertFalse(d.validate_row(row(handle="davidportoescritor"), CONFIG))
>>>>>>> origin/research/public-reuse-parent
        self.assertFalse(d.validate_row(row(name="libros", relation="following"), CONFIG))
        self.assertTrue(d.validate_row(row(name="Lectora de libros"), CONFIG))


<<<<<<< HEAD
=======

class CandidateQualityTests(unittest.TestCase):
    def test_plural_of_configured_niche_counts_but_not_substrings(self):
        self.assertEqual(d.term_hits("Me interesan las novelas", ["novela"]), 1)
        self.assertEqual(d.term_hits("Escriben novelas y escritoras",
                                     ["novela", "escritora"]), 2)
        self.assertEqual(d.term_hits("Esto es un novelazo", ["novela"]), 0)

    def test_niche_in_handle_only_never_qualifies_for_automatic_follow(self):
        result = d.assess_quality(row(handle="ana_libros", name="Ana"), CONFIG)
        self.assertEqual(result["decision"], "review")
        self.assertEqual(result["reason"], "sin_nicho_fuera_del_nombre")

    def test_profile_bio_alone_does_not_prove_recent_activity(self):
        result = d.assess_quality(row(bio="Soy lectora de libros de fantasía"), CONFIG)
        self.assertEqual(result["reason"], "actividad_no_observada")

    def test_recent_observed_own_post_can_qualify_without_claiming_humanity(self):
        result = d.assess_quality(row(
            source="for_you", name="Ana", caption="Estoy leyendo un libro de fantasía"
        ), CONFIG)
        self.assertEqual(result["decision"], "eligible")
        self.assertEqual(result["activity"], "observed_undated")

    def test_commenter_does_not_inherit_another_author_caption(self):
        result = d.assess_quality(row(
            source="video_search:comment", name="Cuentas falsas",
            caption="Novelas fantásticas para lectores",
            comment_text="Qué buena idea, me apunto"
        ), CONFIG)
        self.assertEqual(result["decision"], "review")
        self.assertEqual(result["reason"], "sin_nicho_fuera_del_nombre")
        real = d.assess_quality(row(
            source="video_search:comment", caption="Novelas para lectores",
            comment_text="Estoy leyendo una novela increíble"
        ), CONFIG)
        self.assertEqual(real["decision"], "eligible")

    def test_old_post_explicitly_observed_is_review_not_inactive_guess(self):
        old = d.assess_quality(row(
            source="for_you", caption="Leyendo libros de fantasía",
            last_post_date="2026-07-01"
        ), CONFIG, today="2026-10-08")
        self.assertEqual(old["reason"], "ultima_publicacion_antigua")
        unknown = d.assess_quality(row(
            source="for_you", caption="Leyendo libros de fantasía"
        ), CONFIG, today="2026-10-08")
        self.assertEqual(unknown["decision"], "eligible")
        self.assertEqual(unknown["activity"], "observed_undated")

    def test_inbound_follower_with_book_bio_is_eligible_without_public_video(self):
        result = d.assess_quality(row(
            source="inbox:new_follower", relation="follows_me",
            bio="Lectora de fantasía y novelas", caption="",
        ), CONFIG)
        self.assertEqual(result["decision"], "eligible")
        self.assertEqual(result["activity"], "inbound_follow")

    def test_commenter_score_does_not_use_a_video_authored_by_another_user(self):
        own_comment = row(
            source="video_search:comment", bio="",
            comment_text="Me encanta esta idea", caption="",
        )
        another_author_caption = row(
            source="video_search:comment", bio="",
            comment_text="Me encanta esta idea",
            caption="Libro novela libros booktok editorial",
        )
        self.assertEqual(d.score_row(own_comment, CONFIG),
                         d.score_row(another_author_caption, CONFIG))
    def test_organizations_and_explicit_english_remain_for_review(self):
        org = d.assess_quality(row(
            name="Editorial Libros", caption="Presentamos un libro nuevo"
        ), CONFIG)
        self.assertEqual(org["reason"], "cuenta_organizacion")
        english = d.assess_quality(row(
            source="for_you", caption="My books and love of fantasy"
        ), CONFIG)
        self.assertEqual(english["decision"], "review")



class ProvenanceTests(unittest.TestCase):
    def test_seed_comment_keeps_original_author_role_and_seed_query(self):
        from unittest import mock
        candidate = row(handle="lectora", name="Lectora de libros",
                        source="video_search:comment", comment_text="Leo fantasía")
        config = {"niche_terms": ["libros", "fantasía"], "spam_terms": []}
        ctx = {"today": "2026-10-08", "discarded": set(),
               "seen": {}, "metrics": [], "issues": []}
        navigator = mock.Mock()
        with mock.patch.object(d, "_surface_fn", return_value=lambda *args: [candidate]):
            valid, stats = d.run_surface(navigator, "seed_comments", "editorial_x", config, ctx)
        self.assertEqual(stats["valid"], 1)
        self.assertEqual(valid[0]["ctx"], "seed_comments:editorial_x")
        self.assertEqual(valid[0]["source"], "video_search:comment")
        self.assertEqual(valid[0]["provenance"], {
            "surface": "seed_comments", "query": "editorial_x",
            "source": "video_search:comment", "phase": "direct",
        })


    def test_foreign_video_spam_does_not_reject_an_ordinary_commenter(self):
        candidate = row(
            handle="lectora", name="Ana",
            source="video_search:comment",
            caption="crypto servicios que ofrece el creador del vídeo",
            comment_text="Estoy leyendo una novela",
        )
        self.assertTrue(d.validate_row(candidate, CONFIG))
        # La misma palabra, ahora escrita por el candidato, sí es atribuible.
        candidate["comment_text"] = "crypto de libros"
        self.assertFalse(d.validate_row(candidate, CONFIG))


    def test_foreign_caption_does_not_boost_or_penalize_commenter_score(self):
        base = row(source="video_search:comment", name="Ana", bio="",
                   comment_text="Me interesa conocer más", caption="")
        literary = {**base, "caption": "Libros novela booktok editorial"}
        foreign_english = {**base, "caption": "The fantasy books are great"}
        self.assertEqual(d.score_row(base, CONFIG),
                         d.score_row(literary, CONFIG))
        self.assertEqual(d.score_row(base, CONFIG),
                         d.score_row(foreign_english, CONFIG))
        genuine = {**base, "comment_text": "Estoy leyendo una novela"}
        self.assertGreater(d.score_row(genuine, CONFIG),
                           d.score_row(base, CONFIG))


>>>>>>> origin/research/public-reuse-parent
class MemoryTests(unittest.TestCase):
    def test_seen_roundtrip_and_new_flag(self):
        seen = {}
        self.assertTrue(d.touch_seen(seen, "Ana", "user_search", "2026-10-05"))
        self.assertFalse(d.touch_seen(seen, "ana", "video_search:comment", "2026-10-06"))
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "seen.csv"
            d.save_seen(seen, str(path))
            loaded = d.load_seen(str(path))
        self.assertEqual(loaded["ana"]["times_seen"], "2")
        self.assertTrue(d.recently_seen(loaded, "ANA", "2026-10-07", 3))
        self.assertFalse(d.recently_seen(loaded, "ANA", "2026-10-20", 3))

    def test_rotation_uses_common_ranking_unused_first_and_metrics_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp, "m.csv"))
            d.append_metrics([
                {"fecha": "2026-10-01", "surface": "user_search", "query": "b", "rows": 20, "valid": 18, "new": 15},
                {"fecha": "2026-10-01", "surface": "user_search", "query": "c", "rows": 20, "valid": 1, "new": 0},
            ], path, run_id="r1")
            stats = d.load_stats(path)
        picked = d.pick_queries(["a", "b", "c"], "user_search", stats, 3)
        self.assertEqual(picked[0], "a")           # nunca usada
        self.assertEqual(picked[1], "b")           # más rentable que "c"


class SeedPoolTests(unittest.TestCase):
    def test_pool_learns_only_strong_niche_accounts_with_audience(self):
        cfg = {"scoring": {"seed_min_score": 6, "seed_min_followers": 1500}}
        rows = [
            {"handle": "libreria_x", "name": "Librería X", "score": 8, "followers": 5000},
            {"handle": "tiny_libros", "name": "Libros", "score": 9, "followers": 40},
            {"handle": "random", "name": "Cocina", "score": 9, "followers": 90000},
            {"handle": "low", "name": "Editorial Baja", "score": 2, "followers": 9000},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = str(pathlib.Path(tmp, "pool.csv"))
            d.update_seed_pool(rows, cfg, path)
            self.assertEqual(d.load_seed_pool(path), ["libreria_x"])


if __name__ == "__main__":
    unittest.main()
