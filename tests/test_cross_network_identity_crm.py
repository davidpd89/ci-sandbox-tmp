"""Offline persistence, CRM projection, and input validation regression tests."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from cross_network_identity import IdentityError, IdentityGraph, Profile

def profile(network, handle, **kwargs):
    return Profile(network, handle, **kwargs)

class PersistenceAndCrmTests(unittest.TestCase):
    def setUp(self):
        self.g = IdentityGraph()
        self.a = self.g.observe(profile("x", "lectora", profile_url="https://x.com/lectora",
                             declared_links=("https://instagram.com/lectora",), links_observed=True))
        self.b = self.g.observe(profile("instagram", "lectora",
                             profile_url="https://instagram.com/lectora",
                             declared_links=("https://x.com/lectora",), links_observed=True))

    def test_json_roundtrip_is_stable(self):
        document = json.loads(json.dumps(self.g.to_document()))
        self.assertEqual(IdentityGraph.from_document(document).to_document(), document)
        self.assertEqual(IdentityGraph.from_document(document).groups(), self.g.groups())

    def test_duplicate_profile_fails_closed(self):
        document = self.g.to_document()
        document["profiles"].append(document["profiles"][0])
        with self.assertRaisesRegex(IdentityError, "duplicate_profile"):
            IdentityGraph.from_document(document)

    def test_duplicate_decisions_fail_closed(self):
        self.g.decide(self.a, self.b, same=True, reason="verificado")
        document = self.g.to_document()
        document["decisions"].append(document["decisions"][0])
        with self.assertRaisesRegex(IdentityError, "duplicate_decision"):
            IdentityGraph.from_document(document)

    def test_decisions_and_observations_are_idempotent(self):
        self.g.decide(self.a, self.b, same=True, reason="verificado")
        document = self.g.to_document()
        self.g.decide(self.a, self.b, same=True, reason="verificado")
        self.assertEqual(self.g.to_document(), document)

    def test_stable_id_change_requires_review(self):
        self.g.observe(profile("bluesky", "reader.bsky.social", stable_id="did:plc:aaaa"))
        with self.assertRaisesRegex(IdentityError, "stable_id_changed"):
            self.g.observe(profile("bluesky", "reader.bsky.social", stable_id="did:plc:bbbb"))

    def test_review_reason_mandatory(self):
        with self.assertRaisesRegex(IdentityError, "reason"):
            self.g.decide(self.a, self.b, same=True, reason=" ")
        with self.assertRaisesRegex(IdentityError, "pair_invalid"):
            self.g.decide(self.a, "reddit|missing", same=True, reason="x")

    def test_crm_deduplicates_observations_without_losing_source(self):
        records = [
            {"account": self.a, "event_id": "x:1", "kind": "comment",
             "direction": "inbound", "conversation_ref": "thread/x/1"},
            {"account": self.a, "event_id": "x:1", "kind": "comment",
             "direction": "inbound", "conversation_ref": "thread/x/1"},
            {"account": self.b, "event_id": "ig:2", "kind": "reply",
             "direction": "outbound", "conversation_ref": "thread/ig/2"},
            {"account": "reddit|other", "event_id": "r:3", "kind": "like", "direction": "inbound"}
        ]
        before = json.dumps(self.g.to_document(), sort_keys=True)
        view = self.g.crm_view(self.a, records)
        self.assertEqual(len(view["accounts"]), 2)
        self.assertEqual(len(view["conversation_refs"]), 2)
        self.assertEqual(sum(e["count"] for e in view["events_by_network"]), 2)
        self.assertEqual(before, json.dumps(self.g.to_document(), sort_keys=True))

    def test_crm_reflects_split_but_not_action_writes(self):
        event = {"account": self.b, "event_id": "ig:1", "kind": "follow", "direction": "inbound"}
        self.assertEqual(len(self.g.crm_view(self.a, [event])["events_by_network"]), 1)
        self.g.decide(self.a, self.b, same=False, reason="falsa coincidencia")
        self.assertEqual(self.g.crm_view(self.a, [event])["events_by_network"], [])

    def test_bad_event_on_matching_account_raises(self):
        with self.assertRaisesRegex(IdentityError, "event_invalid"):
            self.g.crm_view(self.a, [{"account": self.a, "event_id": "", "kind": "like", "direction": "inbound"}])

    def test_candidate_order_and_review_suppression(self):
        c = self.g.observe(profile("threads", "lectora"))
        self.assertTrue(any(c in (m.left, m.right) for m in self.g.candidates()))
        self.g.decide(self.a, c, same=False, reason="different author")
        self.assertFalse(any({m.left, m.right} == {self.a, c} for m in self.g.candidates()))
