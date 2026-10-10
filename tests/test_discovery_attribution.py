"""PR #49: deterministic, hermetic tests of candidate discovery attribution."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import discovery_attribution as d

KEY = b"synthetic-key-for-tests-32bytes!!!"


class DiscoveryAttributionTests(unittest.TestCase):
    def test_network_allowlist(self):
        with self.assertRaises(ValueError):
            d.observation(network="instagram", source_type="hashtag")
        with self.assertRaises(ValueError):
            d.state_summary("instagram", {})

    def test_full_observation_keeps_edges_separate(self):
        row = d.observation(
            network="mastodon", source_type="hashtag", source_key="#Fantasía",
            seed="cuenta-de-prueba", query="Novela fantástica",
            candidate_id="inst.example/123", observation_time="2026-10-09T10:01:02+02:00",
            selection_reason="niche_match", hmac_key=KEY)
        self.assertEqual(row["network"], "mastodon")
        self.assertEqual(row["source_type"], "hashtag")
        self.assertFalse(row["provenance_missing"])
        self.assertNotEqual(row["source_key"], row["seed"])
        self.assertNotEqual(row["seed"], row["query"])
        self.assertEqual(row["observation_time"], "2026-10-09T10:01:02+02:00")
        self.assertEqual(row["selection_reason"], "niche_match")
        for raw in ("Fantasía", "cuenta-de-prueba", "Novela"):
            self.assertNotIn(raw, repr(row))

    def test_source_key_differs_across_queries_without_leaking_raw(self):
        sample = {"shortlist": [{"handle": "one",
                                  "sources": ["search:uno", "search:dos"]}]}
        rows = d.state_summary("bluesky", sample, hmac_key=KEY)["sources"]
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]["source_key"], rows[1]["source_key"])
        self.assertNotIn("uno", repr(rows))
        self.assertNotIn("dos", repr(rows))

    def test_first_touch_account_not_invented_or_multicounted(self):
        sample = {"shortlist": [
            {"instance": "example.invalid", "account_id": "11", "acct": "one",
             "sources": ["pool"], "first_source": "hashtag:Libros"},
            {"instance": "example.invalid", "account_id": "11", "acct": "renamed",
             "sources": ["pool"], "first_source": "hashtag:Libros"},
        ]}
        row = d.state_summary("mastodon", sample)
        self.assertEqual(row["first_touch_recorded"], 1)
        self.assertEqual(row["first_touch_by_type"][0]["candidate_count_unique"], 1)
        self.assertNotIn("Libros", repr(row))

    def test_bad_observation_date_not_represented_as_real(self):
        row = d.state_summary("tiktok", {"date": "2026-99-99", "shortlist": []})
        self.assertIsNone(row["observed_on"])

    def test_key_scopes_networks(self):
        x = d.observation(network="x", source_type="seed", candidate_id="123", hmac_key=KEY)
        b = d.observation(network="bluesky", source_type="seed", candidate_id="123", hmac_key=KEY)
        self.assertNotEqual(x["candidate_id"], b["candidate_id"])

    def test_revisit_reuses_stable_token_across_unicode_forms(self):
        args = {"network": "bluesky", "source_type": "tag", "hmac_key": KEY}
        a = d.observation(**args, source_key="  FANTASÍA\nJUVENIL  ", candidate_id="did:plc:abc")
        b = d.observation(**args, source_key="fantasi\u0301a juvenil", candidate_id="DID:PLC:ABC")
        self.assertEqual(a["source_key"], b["source_key"])
        self.assertEqual(a["candidate_id"], b["candidate_id"])

    def test_absent_or_short_key_never_leaks_identity(self):
        for key in (None, b"short"):
            row = d.observation(network="threads", source_type="search",
                                source_key="privada", seed="persona",
                                candidate_id="@persona", hmac_key=key)
            self.assertIsNone(row["source_key"])
            self.assertIsNone(row["candidate_id"])
            self.assertTrue(row["provenance_missing"])

    def test_no_fabricated_timestamps_reasons_or_values(self):
        row = d.observation(network="reddit", source_type="post", source_key=42,
                            candidate_id=None, observation_time="2026-10-09",
                            selection_reason="secret-name", hmac_key=KEY)
        self.assertTrue(row["provenance_missing"])
        self.assertIsNone(row["observation_time"])
        self.assertIsNone(row["source_key"])
        self.assertEqual(row["selection_reason"], "unknown")

    def test_multi_source_same_candidate_counted_once_per_source(self):
        state = {"date": "2026-10-09", "shortlist": [
            {"handle": "Persona", "sources": ["hashtag:Libros", "search:fantasía", "hashtag:Libros"]},
            {"handle": "persona", "sources": ["search:otra"]},
            {"handle": "Otra", "sources": ["hashtag:Libros"]},
        ], "source_metrics": {"hashtag:Libros": {"fetched": 3, "accepted": 2, "new_handles": 1}}}
        report = d.state_summary("bluesky", state, hmac_key=KEY)
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual([(s["source_type"], s["candidate_count_unique"]) for s in report["sources"] if s["source_type"] == "hashtag"], [("hashtag", 2)])
        self.assertEqual(sorted(s["candidate_count_unique"] for s in report["sources"] if s["source_type"] == "search"), [1, 1])
        self.assertEqual(report["queries"][0]["new_reported"], 1)
        self.assertTrue(report["provenance_missing"])
        self.assertIsNone(report["queries"][0]["query_cost"])
        self.assertNotIn("Persona", repr(report))
        self.assertNotIn("Libros", repr(report))

    def test_identity_dedupe_scoped_to_mastodon_instance(self):
        state = {"shortlist": [
            {"instance": "alpha.invalid", "account_id": "100", "acct": "same", "sources": ["pool"]},
            {"instance": "beta.invalid", "account_id": "100", "acct": "same", "sources": ["pool"]},
            {"instance": "alpha.invalid", "account_id": "100", "acct": "renamed", "sources": ["pool"]},
        ]}
        report = d.state_summary("mastodon", state)
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual(report["candidate_id_unstable"], 0)
        self.assertEqual(report["sources"][0]["candidate_count_unique"], 2)

    def test_handle_only_has_unstable_identity(self):
        row = d.state_summary("tiktok", {"shortlist": [
            {"handle": "one", "sources": ["feed"]}]})
        self.assertEqual(row["candidate_id_unstable"], 1)

    def test_missing_unknown_and_bad_legacy_are_not_zero_results(self):
        for state in (None, {}, {"shortlist": "invalid"}, []):
            self.assertEqual(d.state_summary("mastodon", state)["capability"], "missing")
        state = {"shortlist": [None, {}, {"handle": "abc", "sources": []}],
                 "source_metrics": {"search:bar": {"fetched": "garbage", "accepted": None}}}
        summary = d.state_summary("bluesky", state)
        self.assertEqual(summary["candidate_id_missing"], 2)
        self.assertEqual(summary["candidate_source_missing"], 1)
        self.assertEqual(summary["queries"][0]["fetched"], None)

    def test_unsupported_are_explicit_and_never_invent_counts(self):
        for network in ("x", "threads", "facebook", "pinterest", "reddit"):
            summary = d.state_summary(network, {"shortlist": [{"handle": "test"}]})
            self.assertEqual(summary["capability"], "unsupported")
            self.assertIsNone(summary["candidate_count"])

    def test_no_post_ref_used_as_actor_id(self):
        row = d.state_summary("tiktok", {"shortlist": [
            {"posts": [{"post_ref": "fake-video-id"}], "sources": ["feed"]}]})
        self.assertEqual(row["candidate_count"], 0)
        self.assertEqual(row["candidate_id_missing"], 1)

    def test_mixed_empty_metrics_and_cost_do_not_create_false_rate(self):
        state = {"shortlist": [{"handle": "h", "sources": ["feed"]}],
                 "budget": {"used": 9},
                 "source_metrics": {"feed:q": {"fetched": 0, "accepted": 0,
                                               "new_handles": 0},
                                    "ignored": {"fetched": 100}}}
        row = d.state_summary("tiktok", state)
        self.assertEqual(row["read_cost_total"], 9)
        self.assertFalse(row["query_cost_available"])
        self.assertEqual(len(row["queries"]), 1)
        self.assertEqual(row["queries"][0]["fetched"], 0)

    def test_real_prepare_report_adapters_are_passive(self):
        # Exercise the three actual report() integration points, never prepare/run.
        import bluesky_growth_flow as bluesky
        import mastodon_growth_flow as mastodon
        import tiktok_growth_flow as tiktok

        b = bluesky._report({
            "run_id": "synthetic", "date": "2026-10-09",
            "budget": {"used": 2, "remaining": 1},
            "coverage": {"missing": []}, "totals": {"shortlist": 1},
            "readiness": {}, "source_metrics": {},
            "shortlist": [{"handle": "example.invalid", "sources": ["hashtag"]}],
        })
        self.assertEqual(b["discovery_attribution"]["network"], "bluesky")
        self.assertEqual(b["discovery_attribution"]["candidate_count"], 1)

        m = mastodon._report({
            "run_id": "synthetic", "date": "2026-10-09",
            "budget": {"used": 3}, "coverage": {}, "totals": {},
            "shortlist": [{"instance": "example.invalid", "account_id": "1",
                            "sources": ["hashtag"], "actions": []}],
        })
        self.assertEqual(m["discovery_attribution"]["network"], "mastodon")
        self.assertEqual(m["discovery_attribution"]["candidate_count"], 1)

        t = tiktok.report({
            "fetched_posts": 1, "date": "2026-10-09",
            "discovery": None, "auto_plan": [], "issues": [],
            "shortlist": [{"handle": "example", "sources": ["feed"], "lane": "acquisition"}],
        })
        self.assertEqual(t["discovery_attribution"]["network"], "tiktok")
        self.assertEqual(t["discovery_attribution"]["candidate_count"], 1)

    def test_no_legacy_backfill_or_io(self):
        # Function creates a summary only. No file path, database or writes.
        legacy = {"shortlist": [{"acct": "old", "sources": ["search"]}]}
        before = repr(legacy)
        row = d.state_summary("mastodon", legacy)
        self.assertEqual(repr(legacy), before)
        self.assertIsNone(row["observed_on"])
        self.assertIsNone(row["observation_time"])


if __name__ == "__main__":
    unittest.main()
