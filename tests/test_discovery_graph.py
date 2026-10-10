"""Pure synthetic tests; no API, .env, pools or real social handles."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import discovery_graph as graph

KEY = b"synthetic-only-hmac-key-for-unit-tests"
DID = "did:plc:" + "a" * 24
DID_2 = "did:plc:" + "b" * 24
DID_3 = "did:plc:" + "c" * 24
DID_4 = "did:plc:" + "d" * 24


def observation(seed=DID, candidate=DID_4, network="bluesky",
                relation="followers", source="graph:test", api_origin=None,
                observed_at="2026-10-09T10:00:00+02:00", key=KEY):
    return graph.capture_relation(network=network, relation=relation,
        seed_actor_id=seed, candidate_actor_id=candidate, source=source,
        observed_at=observed_at, hmac_key=key, api_origin=api_origin)


class GraphContractTests(unittest.TestCase):
    def test_three_seeds_one_candidate_two_sources_and_no_double_count(self):
        records = [observation(seed=s) for s in (DID, DID_2, DID_3)]
        records += [observation(), observation(seed=DID_2, source="graph:another")]
        report = graph.summarize_graph(records, hmac_key=KEY)
        self.assertEqual((report["unique_candidates"], report["unique_edges"]), (1, 3))
        self.assertEqual(len(report["candidates"][0]["seeds"]), 3)
        self.assertEqual(len(report["candidates"][0]["sources"]), 2)

    def test_promoted_candidate_has_same_graph_token_when_later_seed(self):
        first = observation(seed=DID, candidate=DID_2)
        second = observation(seed=DID_2, candidate=DID_3)
        self.assertEqual(first["candidate_actor"], second["seed_actor"])
        report = graph.summarize_graph([first, second], hmac_key=KEY)
        self.assertEqual(report["unique_edges"], 2)
        self.assertEqual(report["unique_candidates"], 2)

    def test_invalid_actors_self_loop_and_unapproved_surface(self):
        invalid = [(DID, DID, "bluesky", "followers", None),
                   ("@handle", DID_2, "bluesky", "followers", None),
                   ("did:plc:" + "0" * 24, DID_2, "bluesky", "followers", None),
                   ("did:web:example.org/path", DID_2, "bluesky", "followers", None),
                   (DID, DID_2, "bluesky", "liked", None),
                   (DID, DID_2, "threads", "followers", None),
                   ("123", "123", "mastodon", "followers", "https://example.org"),
                   ("@abc", "345", "mastodon", "followers", "https://example.org")]
        for seed, candidate, net, rel, origin in invalid:
            with self.subTest(net=net, seed=seed, relation=rel):
                with self.assertRaises(ValueError):
                    observation(seed=seed, candidate=candidate, network=net,
                                relation=rel, api_origin=origin)

    def test_api_origin_is_required_and_scopes_mastodon_actor(self):
        with self.assertRaises(ValueError):
            observation(seed="101", candidate="202", network="mastodon", relation="following")
        a = observation(seed="101", candidate="202", network="mastodon",
                        relation="following", api_origin="https://one.example")
        b = observation(seed="101", candidate="202", network="mastodon",
                        relation="following", api_origin="https://two.example")
        self.assertNotEqual(a["candidate_actor"], b["candidate_actor"])
        self.assertEqual(graph.summarize_graph([a, b], hmac_key=KEY)["unique_candidates"], 2)
        canonical = observation(seed="101", candidate="202", network="mastodon",
                                relation="following", api_origin="https://one.example:443")
        self.assertEqual(a["candidate_actor"], canonical["candidate_actor"])
        for origin in ("http://example.org", "https://user:secret@example.org",
                       "https://example.org/actor", "https://example.org?x=1",
                       "https://evil host"):
            with self.assertRaises(ValueError):
                observation(seed="101", candidate="202", network="mastodon",
                            relation="followers", api_origin=origin)

    def test_signature_rejects_tampered_fields_and_wrong_key(self):
        good = observation()
        tampered = []
        for name, value in (("candidate_actor", "0" * 24),
                            ("seed_actor", "0" * 24),
                            ("source", "0" * 24),
                            ("observed_at", "2026-10-01T10:00:00+00:00"),
                            ("relation", "follows"), ("network", "mastodon"),
                            ("proof", "0" * 64), ("version", 2)):
            row = dict(good)
            row[name] = value
            tampered.append(row)
        report = graph.summarize_graph([good, *tampered, {"legacy": True}, None], hmac_key=KEY)
        self.assertEqual(report["unique_edges"], 1)
        self.assertEqual(report["observations_rejected"], len(tampered) + 2)
        wrong = graph.summarize_graph([good], hmac_key=b"another synthetic key not the same")
        self.assertEqual(wrong["unique_edges"], 0)
        self.assertEqual(wrong["observations_rejected"], 1)

    def test_key_absence_is_unknown_not_fake_zero(self):
        report = graph.summarize_graph([observation()], hmac_key=None)
        self.assertIsNone(report["unique_edges"])
        self.assertEqual(report["status"], "key_unavailable")
        with self.assertRaises(ValueError):
            observation(key=b"short")

    def test_date_aware_provenance_and_dedup(self):
        old = observation(observed_at="2026-10-09T11:00:00+02:00")
        new = observation(observed_at="2026-10-09T09:30:00Z")
        r = graph.summarize_graph([old, new], hmac_key=KEY)
        self.assertEqual(r["unique_edges"], 1)
        self.assertEqual(r["status"], "historical_only")
        for bad in ("2026-10-09", "2026-10-09T10:00", "invalid"):
            with self.assertRaises(ValueError):
                observation(observed_at=bad)

    def test_no_raw_handle_in_output_and_input_unchanged(self):
        row = observation(source="confidential-person-123")
        source_before = dict(row)
        report = graph.summarize_graph([row], hmac_key=KEY)
        self.assertEqual(row, source_before)
        self.assertNotIn("confidential-person-123", repr(report))
        self.assertNotIn(DID, repr(row))
        self.assertNotIn(DID_4, repr(row))

    def test_invalid_type_and_excessive_batch(self):
        with self.assertRaises(TypeError):
            graph.summarize_graph(None, hmac_key=KEY)
        with self.assertRaises(ValueError):
            graph.summarize_graph([None] * 100001, hmac_key=KEY)
        r = graph.summarize_graph([], hmac_key=KEY)
        self.assertEqual(r["unique_edges"], 0)
        self.assertEqual(r["capability"]["pinterest"], "unsupported")

    def test_all_unsupported_networks_fail_closed(self):
        for network in ("x", "threads", "facebook", "pinterest", "reddit", "tiktok"):
            with self.subTest(network=network):
                with self.assertRaises(ValueError):
                    observation(network=network)
        for invalid in ([], {}, None, 7):
            with self.subTest(bad_network=repr(invalid)):
                with self.assertRaises(ValueError):
                    observation(network=invalid)

    def test_untrusted_row_types_do_not_raise_or_become_edges(self):
        good = observation()
        bad = []
        for field in ("version", "network", "relation", "seed_actor",
                      "candidate_actor", "source", "observed_at", "proof"):
            for value in ([], {}, None, True, 7):
                tampered = dict(good)
                tampered[field] = value
                bad.append(tampered)
        for malformed in ([], {}, "post-url", 23, None):
            bad.append(malformed)
        report = graph.summarize_graph([good, *bad], hmac_key=KEY)
        self.assertEqual(report["unique_edges"], 1)
        self.assertEqual(report["observations_rejected"], len(bad))

    def test_source_limits_and_instance_id_canonicalisation(self):
        with self.assertRaises(ValueError):
            observation(source=" " * 3)
        with self.assertRaises(ValueError):
            observation(source="a" * 1025)
        a = observation(seed="000101", candidate="00202", network="mastodon",
                        relation="followers", api_origin="https://EXAMPLE.ORG")
        b = observation(seed="101", candidate="202", network="mastodon",
                        relation="followers", api_origin="https://example.org:443")
        self.assertEqual(a["seed_actor"], b["seed_actor"])
        self.assertEqual(a["candidate_actor"], b["candidate_actor"])

    def test_source_token_interoperates_with_discovery_attribution_49(self):
        a = observation(source="  Graph:Á   Semilla ")
        b = observation(source="graph:a\u0301 semilla")
        self.assertEqual(a["source"], b["source"])
        # The source contract is available only after the older PR branch
        # has been reconciled with integration where #49 was merged.
        try:
            import discovery_attribution as provenance
        except ModuleNotFoundError:
            return
        linked = provenance.observation(network="bluesky", source_type="followers",
            source_key="  Graph:Á   Semilla ", seed=DID, candidate_id=DID_4,
            observation_time="2026-10-09T10:00:00+02:00", hmac_key=KEY)
        self.assertEqual(a["source"], linked["source_key"])
        self.assertNotEqual(a["candidate_actor"], linked["candidate_id"])

    def test_network_registries_match_after_rebase(self):
        # These merged dependencies do not exist in the old PR branch.
        # The check becomes active in the integration preview checkout.
        for module_name in ("network_capabilities", "discovery_attribution"):
            with self.subTest(module=module_name):
                try:
                    module = __import__(module_name)
                except ModuleNotFoundError:
                    continue
                self.assertEqual(set(graph.NETWORKS), set(module.NETWORKS))

    def test_same_actor_tokens_are_network_scoped(self):
        a = observation()
        b = observation(seed="101", candidate="202", network="mastodon",
                        relation="following", api_origin="https://example.org")
        self.assertNotEqual(a["candidate_actor"], b["candidate_actor"])


if __name__ == "__main__":
    unittest.main()
