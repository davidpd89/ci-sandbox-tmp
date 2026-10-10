"""Synthetic identity matches, ambiguity, splitting and transitive conflicts."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from cross_network_identity import IdentityError, IdentityGraph, Profile, NETWORKS, account_key, canonical_url

def p(network, handle, *, url="", links=(), website="", name="", stable="", observed=True):
    return Profile(network, handle, profile_url=url, declared_links=links,
                   website=website, display_name=name, stable_id=stable, links_observed=observed)

class MatchTests(unittest.TestCase):
    def setUp(self):
        self.g = IdentityGraph()
        self.a = p("x", "lectora", url="https://x.com/lectora",
                   links=("https://www.instagram.com/lectora/",))
        self.b = p("instagram", "lectora", url="https://www.instagram.com/lectora",
                   links=("https://x.com/lectora",))
        self.a_key, self.b_key = self.g.observe(self.a), self.g.observe(self.b)

    def test_nine_networks_with_local_scope(self):
        self.assertEqual(len(NETWORKS), 9)
        for net in NETWORKS - {"mastodon"}:
            with self.subTest(network=net):
                self.assertEqual(account_key(net, "@Lectora"), net + "|lectora")
        self.assertEqual(account_key("mastodon", "@Ana@example.com"),
                         "mastodon|ana@example.com")
        self.assertNotEqual(account_key("x", "ana"), account_key("instagram", "ana"))

    def test_invalid_network_and_handles(self):
        for net, handle in [("unknown", "a"), ("mastodon", "a"), ("mastodon", "a@localhost"),
                            ("x", "a/b"), ("x", "a\nb"), ("reddit", "bob@host")]:
            with self.subTest(net=net, handle=handle), self.assertRaises(IdentityError):
                account_key(net, handle)

    def test_reciprocal_links_merges(self):
        m = self.g.match(self.a_key, self.b_key)
        self.assertEqual((m.status, m.score), ("verified", 100))
        self.assertEqual(len(self.g.cluster(self.a_key)), 2)

    def test_links_without_observation_do_not_merge(self):
        self.g.observe(p("x", "lectora", url=self.a.profile_url,
                         links=self.a.declared_links, observed=False))
        self.assertEqual(self.g.match(self.a_key, self.b_key).status, "review")
        self.assertEqual(len(self.g.groups()), 2)

    def test_one_way_link_does_not_merge(self):
        self.g.observe(p("instagram", "lectora", url=self.b.profile_url))
        m = self.g.match(self.a_key, self.b_key)
        self.assertEqual((m.status, m.score), ("review", 65))
        self.assertEqual(len(self.g.groups()), 2)

    def test_weak_signals_are_candidate_only(self):
        g = IdentityGraph()
        a = g.observe(p("x", "lectora", name="María Pérez", website="https://example.org"))
        b = g.observe(p("threads", "lectora", name="María Pérez", website="https://example.org"))
        self.assertEqual((g.match(a, b).score, len(g.groups())), (30, 2))

    def test_url_must_be_same_actor_as_handle(self):
        g = IdentityGraph()
        a = g.observe(p("x", "alice", url="https://x.com/impostor", links=("https://instagram.com/bob",)))
        b = g.observe(p("instagram", "bob", url="https://instagram.com/bob", links=("https://x.com/impostor",)))
        self.assertEqual(g.match(a, b).status, "review")
        self.assertEqual(len(g.groups()), 2)

    def test_same_network_not_auto_merged(self):
        g = IdentityGraph()
        a = g.observe(p("x", "alice", url="https://x.com/alice", links=("https://x.com/bob",)))
        b = g.observe(p("x", "bob", url="https://x.com/bob", links=("https://x.com/alice",)))
        self.assertEqual(len(g.groups()), 2)

    def test_explicit_reject_overrides_then_can_be_reversed(self):
        self.g.decide(self.a_key, self.b_key, same=False, reason="personas distintas")
        self.assertEqual(len(self.g.groups()), 2)
        self.g.decide(self.a_key, self.b_key, same=True, reason="revisión humana")
        self.assertEqual(len(self.g.groups()), 1)
        self.g.revoke(self.a_key, self.b_key)
        self.assertEqual(len(self.g.groups()), 1)
        self.g.decide(self.a_key, self.b_key, same=False, reason="revisión corregida")
        self.assertEqual(len(self.g.groups()), 2)

    def test_negative_edge_blocks_transitive_fusion(self):
        g = IdentityGraph()
        a, b, c = (g.observe(p(net, handle)) for net, handle in
                   (("x", "alice"), ("reddit", "bob"), ("threads", "carla")))
        g.decide(a, c, same=False, reason="diferentes")
        g.decide(a, b, same=True, reason="revisado")
        g.decide(b, c, same=True, reason="revisado")
        self.assertEqual(len(g.groups()), 2)
        self.assertNotIn(c, g.cluster(a))
        self.assertEqual(len(g.conflicts()), 1)

    def test_url_canonicalization_is_conservative(self):
        self.assertEqual(canonical_url("https://EXAMPLE.com/a/"), "https://example.com/a")
        self.assertNotEqual(canonical_url("https://example.com/A"), canonical_url("https://example.com/a"))
        for url in ("http://example.com", "https://example.com/?a=1",
                    "https://user:pass@example.com/a", "https://example.com:443/a",
                    "https://example.com/a#b", "https://example.com/a\n"):
            with self.subTest(url=url), self.assertRaises(IdentityError):
                canonical_url(url)
