"""Prueba real opcional del contrato del ledger #84 (checkout inmutable)."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from tools.native_relationship_evidence_bridge import Batch, bridge_results

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

if __name__ == "__main__":
    unittest.main()
