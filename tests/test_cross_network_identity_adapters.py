"""Adapting the existing three CRM-related schemas without writing account files."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from cross_network_identity import IdentityGraph, Profile
from identity_crm_adapters import (adapt_inbound_rows, adapt_outbound_rows,
                                   adapt_conversation_rows, project_legacy)

class LegacyProjectionTests(unittest.TestCase):
    def setUp(self):
        self.graph = IdentityGraph()
        self.x = self.graph.observe(Profile("x", "reader"))
        self.reddit = self.graph.observe(Profile("reddit", "reader2"))
        self.graph.decide(self.x, self.reddit, same=True, reason="revisión sintética")

    def test_confirmed_outbound_and_no_network_writes(self):
        rows = [{"cuenta": "reader", "tipo": "reply", "resultado": "confirmado",
                 "event_id": "remote:1", "url": "https://x.com/reader/status/123"},
                {"cuenta": "reader", "tipo": "reply", "resultado": "fallido",
                 "event_id": "remote:2"}]
        events, warnings = adapt_outbound_rows("x", rows)
        self.assertEqual(warnings, [])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["conversation_ref"], "https://x.com/reader/status/123")

    def test_inbound_dedupes_multi_lane_observation(self):
        row = {"fecha": "2026-10-10", "red": "x", "handle": "reader", "tipo": "comment"}
        events, warnings = adapt_inbound_rows([row, row.copy()])
        self.assertEqual(warnings, [])
        view = self.graph.crm_view(self.x, events)
        self.assertEqual(sum(e["count"] for e in view["events_by_network"]), 1)

    def test_inbound_identity_uses_canonical_network_and_kind(self):
        rows = [
            {"fecha": "2026-10-10", "red": " X ", "handle": "@Reader", "tipo": " Comment "},
            {"fecha": "2026-10-10", "red": "x", "handle": "reader", "tipo": "comment"},
        ]
        events, warnings = adapt_inbound_rows(rows)
        self.assertEqual(warnings, [])
        self.assertEqual(events[0]["event_id"], events[1]["event_id"])
        self.assertEqual(events[0]["kind"], "comment")
        view = self.graph.crm_view(self.x, events)
        self.assertEqual(view["events_by_network"], [
            {"network": "x", "direction": "inbound", "kind": "comment", "count": 1}
        ])

    def test_mastodon_unscoped_acct_reports_without_guessing(self):
        events, warnings = adapt_inbound_rows([
            {"fecha": "2026-10-10", "red": "mastodon", "handle": "reader", "tipo": "follow"}
        ])
        self.assertEqual(events, [])
        self.assertEqual(warnings[0]["row"], 0)

    def test_conversation_reference_and_global_group(self):
        report = project_legacy(self.graph, self.x,
            inbound=[{"fecha": "2026-10-10", "red": "x", "handle": "reader", "tipo": "comment"}],
            outbound_by_network={"reddit": [{"cuenta": "reader2", "tipo": "follow",
                                             "resultado": "publicado"}]},
            conversations_by_network={"reddit": [{"handle": "reader2", "ref": "comment-ref-42"}]})
        self.assertEqual(report["warnings"], [])
        self.assertEqual(len(report["crm"]["accounts"]), 2)
        self.assertEqual(sum(e["count"] for e in report["crm"]["events_by_network"]), 3)
        self.assertEqual(report["crm"]["conversation_refs"][0]["ref"], "comment-ref-42")

    def test_invalid_conversation_rows_reported(self):
        events, warnings = adapt_conversation_rows("reddit", [{"handle": "reader2"}])
        self.assertEqual(events, [])
        self.assertEqual(warnings[0]["row"], 0)

    def test_all_network_adapters_same_contract(self):
        networks = ["x", "threads", "facebook", "pinterest", "reddit",
                    "bluesky", "tiktok", "instagram", "mastodon"]
        for net in networks:
            handle = "reader@example.com" if net == "mastodon" else "reader"
            with self.subTest(net=net):
                rows, warnings = adapt_outbound_rows(net, [
                    {"cuenta": handle, "tipo": "follow", "resultado": "confirmado"}])
                self.assertEqual(warnings, [])
                self.assertEqual(rows[0]["account"], net + "|" + handle)
