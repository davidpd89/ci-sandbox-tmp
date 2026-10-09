"""follow_pool de Mastodon (02/10): seleccion por probabilidad de follow-back."""
import datetime as dt
import pathlib
import sys
import types
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

requests_stub = types.ModuleType("requests")
requests_stub.get = lambda *a, **k: None
requests_stub.post = lambda *a, **k: None
requests_stub.delete = lambda *a, **k: None
x_stub = types.ModuleType("x_interact")
x_stub._check_spanish_orthography = lambda text: None
sys.modules.setdefault("requests", requests_stub)
sys.modules.setdefault("x_interact", x_stub)

import mastodon_growth_scan as gs
import mastodon_build_plan as bp

TODAY = dt.date(2026, 10, 2)


def item(acct, **over):
    base = {
        "acct": acct, "account_id": "1", "display_name": acct,
        "bio": "Lectora de fantasía y novelas", "followers": 200,
        "following_count": 300, "statuses_count": 100,
        "last_status_at": "2026-10-01", "locked": False, "bot": False,
        "posts": set(), "known_date": None, "followed_by": False,
        "following": False, "blocked": False, "muting": False,
    }
    base.update(over)
    return base


def collector(*items):
    config = {"niche_terms": ["fantasía", "novelas"], "follow_pool": {}}
    return types.SimpleNamespace(
        config=config, today=TODAY,
        candidates={i["acct"]: i for i in items},
    )


def pool(*items):
    return [row["acct"] for row in gs._follow_pool(collector(*items))]


class FollowPoolTests(unittest.TestCase):
    def test_keeps_active_niche_account_with_follow_back_ratio(self):
        self.assertEqual(pool(item("a")), ["a"])

    def test_rejects_accounts_whose_bio_is_clearly_in_another_language(self):
        """06/10: se seguia a cuentas solo en aleman y una pregunto en Bluesky si nuestra cuenta era falsa."""
        german = "Schreibt Fantasy und Science Fiction. Hat Ahnung von Büchern und schreibt auch über Fantasy und Romane."
        self.assertEqual(pool(item("de", bio=german)), [])
        self.assertEqual(pool(item("ok", bio="Escribo fantasía y novelas, lectora de libros")), ["ok"])

    def test_english_and_german_accounts_are_not_followed_back_either(self):
        german = "Schreibt Fantasy und Science Fiction. Hat Ahnung von Büchern und schreibt auch über novelas und Romane."
        english = "I write fantasy novels and I love reading books about novelas and dragons every single day"
        self.assertEqual(pool(item("de", bio=german, followed_by=True)), [])
        self.assertEqual(pool(item("en", bio=english, followed_by=True)), [])

    def test_rejects_ratio_size_and_activity_misses(self):
        self.assertEqual(pool(item("a", following_count=50)), [])
        self.assertEqual(pool(item("b", followers=5000, following_count=6000)), [])
        self.assertEqual(pool(item("c", followers=1000, following_count=300)), [])
        self.assertEqual(pool(item("d", last_status_at="2026-06-01")), [])
        self.assertEqual(pool(item("e", statuses_count=3)), [])

    def test_rejects_bots_locked_and_relationships(self):
        for field in ("bot", "locked", "following", "blocked", "muting"):
            self.assertEqual(pool(item("x", **{field: True})), [], field)

    def test_known_account_only_if_it_already_follows_us(self):
        self.assertEqual(pool(item("a", known_date="2026-09-20")), [])
        self.assertEqual(pool(item("b", known_date="2026-09-20", followed_by=True)), ["b"])

    def test_rejects_activist_bio_and_no_niche_signal(self):
        self.assertEqual(pool(item("a", bio="Fantasía y #FreePalestine gaza")), [])
        self.assertEqual(pool(item("b", bio="Fotografía de coches")), [])
        self.assertEqual(pool(item("c", bio="Fotografía de coches y de paisajes de mi tierra", posts={"1"})), ["c"])

    def test_orders_followers_of_ours_first(self):
        rows = pool(item("a"), item("b", known_date="2026-09-20", followed_by=True))
        self.assertEqual(rows[0], "b")


class BuildPlanPoolFollowTests(unittest.TestCase):
    def test_account_follow_resolves_from_pool(self):
        scan = {"shortlist": [], "follow_pool": [
            {"acct": "buena@x.social", "followers": 10, "following_count": 200},
        ]}
        plan = bp.build(scan, {"actions": [{"account": "buena@x.social", "kind": "follow"}]})
        self.assertEqual(plan[0]["handle"], "buena@x.social")
        self.assertEqual(plan[0]["kind"], "follow")

    def test_account_outside_pool_is_rejected(self):
        with self.assertRaises(ValueError):
            bp.build({"shortlist": [], "follow_pool": []},
                     {"actions": [{"account": "intruso", "kind": "follow"}]})


if __name__ == "__main__":
    unittest.main()
