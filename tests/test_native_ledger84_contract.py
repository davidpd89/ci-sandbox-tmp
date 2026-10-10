"""Prueba real opcional del contrato del ledger #84 (checkout inmutable)."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from tools.native_relationship_evidence_bridge import Batch, bridge_results, bridge_snapshot

LEDGER = Path(os.environ.get("LEDGER84_PY", "/nonexistent/ledger.py"))

@unittest.skipUnless(LEDGER.is_file(), "falta checkout de #84")
class LedgerContract(unittest.TestCase):
    def test_real_ledger(self):
        spec = importlib.util.spec_from_file_location("ledger84", LEDGER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            ledger = module.RelationshipLedger(Path(folder) / "demo.sqlite")
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
        spec = importlib.util.spec_from_file_location("ledger84_snapshot", LEDGER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            ledger = module.RelationshipLedger(Path(folder) / "demo.sqlite")
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
            self.assertEqual(bridge_snapshot(ledger, batch, snap)["inserted"], 1)
            stats = ledger.conversion("x", as_of="2026-10-14T09:00:00Z")
            self.assertEqual((stats["negative"], stats["unknown"]), (1, 0))

if __name__ == "__main__":
    unittest.main()
