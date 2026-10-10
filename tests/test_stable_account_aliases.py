"""Synthetic, offline verification of alias ownership and event attribution."""
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from stable_account_aliases import AliasTimeline, AliasError, NETWORKS, account_key

T1, T2, T3 = ("2026-10-01T09:00:00Z", "2026-10-02T09:00:00Z", "2026-10-03T09:00:00Z")
D1, D2 = ("did:plc:abcdefghijklmnopqrstuvwx", "did:plc:bcdefghijklmnopqrstuvwxy")


def add(g, eid, handle, sid=D1, when=T1, net="bluesky", queue="API"):
    proof = {"bluesky": "did_bidirectional", "mastodon": "actor_uri_confirmed"}.get(net, "provider_account_id")
    return g.observe(evidence_id=eid, network=net, handle=handle, stable_id=sid,
                     observed_at=when, queue=queue, source="synthetic-snapshot",
                     proof="field:confirmed-native-id", verification=proof)


def evt(eid, handle="first.bsky.social", when=T1, proof="a", queue="API", kind="reply"):
    return dict(network="bluesky", kind=kind, event_id=eid, handle=handle,
                observed_at=when, evidence_id=proof, queue=queue)


class StableAliasTests(unittest.TestCase):
    def setUp(self):
        self.g = AliasTimeline()

    def test_nine_networks_are_scoped(self):
        self.assertEqual(len(NETWORKS), 9)
        for net in NETWORKS - {"mastodon"}:
            with self.subTest(net=net):
                self.assertEqual(account_key(net, "@Writer"), net + "|writer")
                add(self.g, net, "Writer", D1 if net == "bluesky" else "42", net=net)
                self.assertEqual(self.g.resolve(net, "writer", T1)["status"], "verified_at_observation")
        add(self.g, "mast", "writer@example.org", "https://example.org/users/writer",
            net="mastodon")
        self.assertEqual(self.g.resolve("mastodon", "@writer@EXAMPLE.org", T1)["status"],
                         "verified_at_observation")
        self.assertNotEqual(self.g.evidence["threads"].stable, self.g.evidence["x"].stable)

    def test_did_must_be_bidirectionally_confirmed(self):
        with self.assertRaisesRegex(AliasError, "bidirectionally"):
            self.g.observe(evidence_id="a", network="bluesky", handle="first.bsky.social",
                           stable_id=D1, observed_at=T1, queue="API", source="fixture",
                           proof="unverified", verification="provider_account_id")
        for sid in ("did:plc:invalid", "did:web:", "entity:deadbeef"):
            with self.subTest(sid=sid), self.assertRaises(AliasError):
                add(self.g, "a", "first.bsky.social", sid)

    def test_mastodon_requires_actor_uri(self):
        with self.assertRaisesRegex(AliasError, "actor_uri_required"):
            self.g.observe(evidence_id="x", network="mastodon", handle="a@example.org",
                           stable_id="42", observed_at=T1, queue="API", source="fixture",
                           proof="field:account_id", verification="provider_account_id")
        add(self.g, "a", "a@example.org", "https://EXAMPLE.org/users/a/",
            net="mastodon")
        self.assertEqual(self.g.evidence["a"].stable,
                         "mastodon|https://example.org/users/a")
        for sid in ("http://example.org/users/a", "https://example.org:443/users/a",
                    "https://example.org", "https://user:pass@example.org/users/a"):
            with self.subTest(sid=sid), self.assertRaises(AliasError):
                add(self.g, "bad", "a@example.org", sid, net="mastodon")

    def test_multiple_renames_recycled_name_and_no_cross_account_mix(self):
        add(self.g, "a", "first.bsky.social")
        add(self.g, "b", "second.bsky.social", when=T2, queue="WEB")
        add(self.g, "c", "third.bsky.social", when=T3, queue="MOBILE")
        self.assertEqual(self.g.link("a", "b"), "bluesky|" + D1)
        self.assertEqual(self.g.link("b", "c"), "bluesky|" + D1)
        self.assertEqual(self.g.resolve("bluesky", "first.bsky.social", T2)["status"],
                         "superseded_alias")
        self.assertEqual(self.g.resolve("bluesky", "third.bsky.social", T3)["stable_key"],
                         "bluesky|" + D1)
        add(self.g, "d", "first.bsky.social", D2, "2026-10-04T09:00:00Z")
        self.assertEqual(self.g.resolve("bluesky", "first.bsky.social",
                                        "2026-10-05T09:00:00Z")["stable_key"], "bluesky|" + D2)
        self.assertEqual(self.g.resolve("bluesky", "third.bsky.social",
                                        "2026-10-05T09:00:00Z")["stable_key"], "bluesky|" + D1)

    def test_same_handle_same_time_conflict_then_revoke_restore(self):
        add(self.g, "a", "first.bsky.social")
        add(self.g, "b", "first.bsky.social", D2)
        self.assertEqual(self.g.resolve("bluesky", "first.bsky.social", T1)["status"],
                         "conflict_handle_recycled_same_time")
        self.g.revoke("b", reason="source mismatch")
        self.assertEqual(self.g.resolve("bluesky", "first.bsky.social", T1)["stable_key"],
                         "bluesky|" + D1)
        self.g.restore("b", reason="review")
        self.assertIsNone(self.g.resolve("bluesky", "first.bsky.social", T1)["stable_key"])

    def test_simultaneous_handles_same_id_are_ambiguous(self):
        add(self.g, "a", "first.bsky.social")
        add(self.g, "b", "second.bsky.social")
        with self.assertRaisesRegex(AliasError, "simultaneous_handles_conflict"):
            self.g.link("a", "b")
        self.assertEqual(self.g.resolve("bluesky", "first.bsky.social", T1)["status"],
                         "conflict_stable_multiple_handles")

    def test_link_rejects_third_party_conflict_at_observation(self):
        add(self.g, "a", "first.bsky.social", when=T1)
        add(self.g, "b", "second.bsky.social", when=T2)
        add(self.g, "c", "third.bsky.social", when=T2)
        with self.assertRaisesRegex(AliasError, "link_evidence_ambiguous"):
            self.g.link("a", "b")
        self.g.revoke("c", reason="false concurrent handle")
        self.assertEqual(self.g.link("a", "b"), "bluesky|" + D1)
        add(self.g, "d", "second.bsky.social", sid=D2, when=T2)
        with self.assertRaisesRegex(AliasError, "link_evidence_ambiguous"):
            self.g.link("a", "b")

    def test_link_requires_same_verified_native_id(self):
        add(self.g, "a", "first.bsky.social")
        add(self.g, "b", "second.bsky.social", D2, T2)
        with self.assertRaisesRegex(AliasError, "stable_identity_conflict"):
            self.g.link("a", "b")
        self.g.revoke("a", reason="correction")
        with self.assertRaisesRegex(AliasError, "link_evidence"):
            self.g.link("a", "b")

    def test_idempotent_evidence_and_collision(self):
        add(self.g, "a", "first.bsky.social")
        add(self.g, "a", "first.bsky.social")
        self.assertEqual(len(self.g.evidence), 1)
        with self.assertRaisesRegex(AliasError, "evidence_id_collision"):
            add(self.g, "a", "other.bsky.social")

    def test_provenance_and_times_required(self):
        for changed in ({"queue": "UNKNOWN"}, {"source": ""}, {"proof": ""},
                        {"observed_at": "2026-10-01"}, {"evidence_id": "../../file"}):
            args = dict(evidence_id="a", network="bluesky", handle="first.bsky.social",
                        stable_id=D1, observed_at=T1, queue="API", source="fixture",
                        proof="field:id", verification="did_bidirectional")
            args.update(changed)
            with self.subTest(changed=changed), self.assertRaises(AliasError):
                self.g.observe(**args)
        self.assertEqual(len(self.g.evidence), 0)

    def test_all_three_queues_dedupe_same_event(self):
        add(self.g, "a", "first.bsky.social")
        result = self.g.project_events([evt("42", queue=q)
                                        for q in ("WEB", "API", "MOBILE")])
        self.assertEqual(len(result["linked"]), 1)
        self.assertFalse(result["unresolved"])

    def test_event_id_is_also_kind_scoped(self):
        add(self.g, "a", "first.bsky.social")
        result = self.g.project_events([evt("42", kind="follow"), evt("42", kind="reply")])
        self.assertEqual(len(result["linked"]), 2)

    def test_duplicate_event_with_different_proof_is_quarantined(self):
        add(self.g, "a", "first.bsky.social")
        result = self.g.project_events([evt("42"), evt("42", proof=None)])
        self.assertFalse(result["linked"])
        self.assertEqual(result["unresolved"][0]["reason"], "event_observation_conflict")

    def test_unknown_and_wrong_account_proof_do_not_attribute(self):
        add(self.g, "a", "first.bsky.social")
        result = self.g.project_events([evt("1", proof=None),
                                        evt("2", handle="other.bsky.social")])
        self.assertFalse(result["linked"])
        self.assertTrue(all(x["reason"] == "missing_verified_proof"
                            for x in result["unresolved"]))

    def test_future_proof_cannot_backfill_past(self):
        add(self.g, "a", "first.bsky.social", when=T2)
        result = self.g.project_events([evt("old", when=T1)])
        self.assertEqual(result["unresolved"][0]["reason"], "proof_is_newer_than_event")

    def test_historical_event_not_assigned_after_rename_or_recycle(self):
        add(self.g, "a", "first.bsky.social")
        add(self.g, "b", "second.bsky.social", when=T2)
        add(self.g, "c", "first.bsky.social", sid=D2, when=T3)
        result = self.g.project_events([evt("old"), evt("gap", when=T2),
                                        evt("new", when=T3, proof="c")])
        self.assertEqual({x["event_id"] for x in result["linked"]}, {"old", "new"})
        self.assertEqual(result["unresolved"][0]["event_id"], "gap")
        self.assertNotEqual(result["linked"][0]["stable_key"],
                            result["linked"][1]["stable_key"])

    def test_revoke_split_restore_replay(self):
        add(self.g, "a", "first.bsky.social")
        add(self.g, "b", "second.bsky.social", when=T2)
        self.g.revoke("b", reason="incorrect alias")
        self.g.revoke("b", reason="duplicate retry")
        self.assertEqual(self.g.resolve("bluesky", "second.bsky.social", T3)["status"], "unknown")
        snapshot = json.loads(json.dumps(self.g.to_document()))
        self.assertEqual(AliasTimeline.from_document(snapshot).to_document(), snapshot)
        self.g.restore("b", reason="manual correction")
        self.g.restore("b", reason="duplicate retry")
        self.assertEqual(self.g.resolve("bluesky", "first.bsky.social", T3)["status"],
                         "superseded_alias")
        self.assertEqual(len(self.g.actions), 2)

    def test_replay_rejects_bad_documents(self):
        add(self.g, "a", "first.bsky.social")
        snapshot = self.g.to_document()
        snapshot["actions"] = [{"action": "revoke", "evidence_id": "a", "reason": "x"}] * 2
        with self.assertRaisesRegex(AliasError, "action_replay"):
            AliasTimeline.from_document(snapshot)
        snapshot = self.g.to_document()
        snapshot["evidence"][0]["stable"] = "bluesky|bad"
        with self.assertRaises(AliasError):
            AliasTimeline.from_document(snapshot)

    def test_replay_rejects_non_string_account_or_stable(self):
        add(self.g, "a", "first.bsky.social")
        for field in ("account", "stable"):
            with self.subTest(field=field):
                snapshot = json.loads(json.dumps(self.g.to_document()))
                snapshot["evidence"][0][field] = None
                with self.assertRaisesRegex(AliasError, "evidence_schema_invalid"):
                    AliasTimeline.from_document(snapshot)

    def test_history_keeps_revoked_proof_without_merging_events(self):
        add(self.g, "a", "first.bsky.social")
        self.g.revoke("a", reason="false DID")
        self.assertFalse(self.g.history("bluesky|" + D1)[0]["active"])
        self.assertEqual(self.g.resolve("bluesky", "first.bsky.social", T3)["status"], "unknown")

    def test_unknown_handle_and_bad_account_keys(self):
        self.assertEqual(self.g.resolve("x", "writer", T1)["status"], "unknown")
        for net, handle in (("mastodon", "writer"), ("x", "bad/handle"),
                            ("unknown", "writer"), ("reddit", "")):
            with self.subTest(net=net), self.assertRaises(AliasError):
                account_key(net, handle)

    def test_out_of_order_claims_and_index_invalidation(self):
        add(self.g, "new", "second.bsky.social", when=T3)
        add(self.g, "old", "first.bsky.social", when=T1)
        self.assertEqual(self.g.resolve("bluesky", "first.bsky.social", T1)["stable_key"],
                         "bluesky|" + D1)
        self.assertEqual(self.g.resolve("bluesky", "first.bsky.social", T3)["status"],
                         "superseded_alias")
        cached_revision = self.g._indexed_epoch
        self.g.resolve("bluesky", "second.bsky.social", T3)
        self.assertEqual(self.g._indexed_epoch, cached_revision)
        self.g.revoke("new", reason="synthetic correction")
        self.assertEqual(self.g.resolve("bluesky", "first.bsky.social", T3)["status"],
                         "inferred_interval")
        self.assertGreater(self.g._indexed_epoch, cached_revision)

    def test_compatible_future_85_key_builder(self):
        g = AliasTimeline(key_builder=account_key)
        add(g, "a", "first.bsky.social")
        replay = AliasTimeline.from_document(g.to_document(), key_builder=account_key)
        self.assertEqual(replay.resolve("bluesky", "first.bsky.social", T1)["stable_key"],
                         "bluesky|" + D1)


if __name__ == "__main__":
    unittest.main()
