"""Contrato obligatorio con RelationshipLedger de la base sincronizada."""
from pathlib import Path
import tempfile
import unittest
from tools.relationship_event_ledger import RelationshipLedger
from tools.native_relationship_evidence_bridge import Batch, bridge_results, bridge_snapshot
class LedgerContract(unittest.TestCase):
    def test_real_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = RelationshipLedger(Path(folder) / "demo.sqlite")
            b = Batch("x", "WEB", "x_execute.run_plan", "export-1")
            row = {"record_id": "a", "kind": "follow", "handle": "@lectora",
                   "resultado": "confirmado", "occurred_at": "2026-10-10T09:00:00Z",
                   "ack": {"id": "ack-1", "kind": "follow",
                           "target": "@lectora", "basis": "ui_state"}}
            self.assertEqual(bridge_results(ledger, b, [row])["inserted"], 1)
            self.assertEqual(bridge_results(ledger, b, [row])["replayed"], 1)
            self.assertEqual(ledger.count(), 1)
            self.assertEqual(ledger.conversion("x",
                as_of="2026-10-14T09:00:00Z")["unknown"], 1)

    def test_snapshot_conversion_partial_then_complete(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = RelationshipLedger(Path(folder) / "demo.sqlite")
            batch = Batch("x", "WEB", "x_execute.run_plan", "export-1")
            follow = {"record_id": "f1", "kind": "follow", "handle": "@lectora",
                      "resultado": "confirmado", "occurred_at": "2026-10-10T09:00:00Z",
                      "ack": {"id": "ack-1", "kind": "follow", "target": "@lectora",
                              "basis": "ui_state"}}
            bridge_results(ledger, batch, [follow])
            snap = {"snapshot_id": "s1", "observed_at": "2026-10-13T09:00:00Z",
                    "tracked": ["lectora"], "followers": [],
                    "coverage": {"identity_stable": True, "complete": True,
                                 "all_pages": False, "account_scope": "self"}}
            self.assertEqual(bridge_snapshot(ledger, batch, snap)["unknown"], 1)
            self.assertEqual(ledger.conversion("x", as_of="2026-10-14T09:00:00Z")
                             ["unknown"], 1)
            snap["snapshot_id"] = "s2"
            snap["coverage"]["all_pages"] = True
            self.assertEqual(bridge_snapshot(ledger, batch, {
                **snap, "snapshot_id": "solo-flags"})["unknown"], 1)
            snap["account_id"] = "cuenta-propia"
            snap["coverage"].update({
                "account_id": "cuenta-propia", "snapshot_id": "s2",
                "producer": batch.producer,
                "pages": [{"account_id": "cuenta-propia", "snapshot_id": "s2",
                           "identity_stable": True, "cursor_in": None,
                           "cursor_out": None, "followers": []}],
            })
            self.assertEqual(bridge_snapshot(ledger, batch, snap)["inserted"], 1)
            stats = ledger.conversion("x", as_of="2026-10-14T09:00:00Z")
            self.assertEqual((stats["negative"], stats["unknown"]), (1, 0))

if __name__ == "__main__":
    unittest.main()
