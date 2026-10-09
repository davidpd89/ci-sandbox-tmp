"""Politica y criterios comunes a todas las redes (06/10): growth_policy, share_worthy y boosts automaticos de Mastodon; sin red."""
import datetime
import pathlib
import sys
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: None
sys.modules.setdefault("requests", requests_stub)
import growth_policy as gp
import scan_common as sc
import mastodon_auto_decide as ad
import mastodon_pool as mp
import bluesky_pool as bp
import threads_execute  # noqa: F401  (comprueba que importa la politica comun)

TODAY = datetime.date(2026, 10, 6)
GOOD = "Terminé la saga de fantasía y me ha dejado un vacío enorme, ¿alguna novela parecida para leer ahora?"


class PolicyTests(unittest.TestCase):
    def test_every_network_uses_the_same_thresholds(self):
        self.assertEqual(bp.HUGE_ACCOUNT, gp.FOLLOW_MAX_FOLLOWERS)
        self.assertEqual(mp.HUGE_ACCOUNT, gp.FOLLOW_MAX_FOLLOWERS)
        self.assertEqual(bp.OFFER_AGAIN_DAYS, mp.OFFER_AGAIN_DAYS)
        self.assertEqual(threads_execute.FOLLOW_MAX_FOLLOWERS, gp.FOLLOW_MAX_FOLLOWERS)
        self.assertEqual(mp.MAX_INACTIVE_DAYS, gp.MAX_INACTIVE_DAYS)

    def test_age_limits_accept_both_historical_key_names_and_defaults(self):
        self.assertEqual(gp.max_post_age_days({}, "acquisition"), 21)
        self.assertEqual(gp.max_post_age_days({}, "community"), 45)
        self.assertEqual(gp.max_post_age_days({"shortlist": {"like_max_age_acquisition_days": 10}}, "acquisition"), 10)
        self.assertEqual(gp.max_post_age_days({"shortlist": {"favourite_max_age_days": 30}}, "community"), 30)
        self.assertEqual(gp.follow_max_followers({"shortlist": {"follow_max_followers": 5000}}), 5000)


class ShareWorthyTests(unittest.TestCase):
    def worthy(self, text=GOOD, **kw):
        base = dict(spanish=True, niche_hits=3, followers=800, age_days=1)
        base.update(kw)
        return sc.share_worthy(text, **base)

    def test_good_post_passes(self):
        self.assertTrue(self.worthy())

    def test_bad_posts_do_not(self):
        self.assertFalse(self.worthy(spanish=None))
        self.assertFalse(self.worthy(niche_hits=1))
        self.assertFalse(self.worthy(age_days=9))
        self.assertFalse(self.worthy(followers=90_000))
        self.assertFalse(self.worthy("Libro"))
        self.assertFalse(self.worthy("@ana " + GOOD))                          # respuesta a otra persona
        self.assertFalse(self.worthy(GOOD + " #a #b #c #d"))                    # demasiadas etiquetas
        self.assertFalse(self.worthy(GOOD + " https://amzn.to/x"))              # enlace
        self.assertFalse(self.worthy("Mi libro ya disponible en Amazon, corre a leer esta novela de fantasía que he escrito"))


def state(posts):
    return {"follow_pool": [], "shortlist": [
        {"id": f"M{i:03d}", "acct": acct, "lane": "acquisition", "score": score, "followers": 500, "actions": [],
         "posts": [{"id": f"M{i:03d}-P1", "url": f"https://x/{i}", "text": text, "language": "es", "created_at": "2026-10-05T10:00:00Z", "actions": ["favourite", "boost", "reply"]}]}
        for i, (acct, text, score) in enumerate(posts, start=1)]}


class AutoBoostTests(unittest.TestCase):
    def test_boost_replaces_the_favourite_and_is_limited_to_one_per_account(self):
        st = state([("ana@x.es", GOOD, 9.0), ("ana@x.es", GOOD + " otra", 8.0), ("bea@x.es", GOOD + " tres", 7.0), ("cris@x.es", "hola " * 12, 6.0)])
        actions, _, _ = ad.build(st, 30, max_boosts=5, today=TODAY)
        boosts = [a for a in actions if a["kind"] == "boost"]
        self.assertEqual(sorted(a["post"] for a in boosts), ["M001-P1", "M003-P1"])    # una por cuenta; la de bajo valor no pasa el criterio
        favourites = {a["post"] for a in actions if a["kind"] == "favourite"}
        self.assertFalse(favourites & {"M001-P1", "M003-P1"})                           # el boost reemplaza al favorito del mismo estado
        self.assertIn("M002-P1", favourites)

    def test_no_boosts_by_default_in_build(self):
        actions, _, _ = ad.build(state([("ana@x.es", GOOD, 9.0)]), 30, today=TODAY)
        self.assertEqual([a["kind"] for a in actions], ["favourite"])


class UsableTests(unittest.TestCase):
    def row(self, **kw):
        base = {"reject": None, "english": 0, "spanish": 1, "bio_hits": 0, "seeds_count": 1, "behav": 0}
        base.update(kw)
        return base

    def test_spanish_reader_of_one_niche_seed_is_usable_only_when_relaxed(self):
        self.assertFalse(mp.usable(self.row()))
        self.assertTrue(mp.usable(self.row(), relaxed=True))

    def test_still_excluded(self):
        self.assertFalse(mp.usable(self.row(spanish=0)))
        self.assertFalse(mp.usable(self.row(seeds_count=0)))
        self.assertFalse(mp.usable(self.row(reject="bot")))
        self.assertFalse(mp.usable(self.row(english=1, seeds_count=1)))


if __name__ == "__main__":
    unittest.main()
