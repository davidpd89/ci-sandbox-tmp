"""Regresión de códigos emitidos por módulos offline y aceptados por panel."""
import ast
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import alert_codes as codes
import estado_rondas as panel
import round_canaries as canaries


def _literal_alerts(path):
    tree = ast.parse((ROOT / "tools" / path).read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_alert":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                found.add(node.args[0].value)
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (isinstance(key, ast.Constant) and key.value == "code"
                        and isinstance(value, ast.Constant) and isinstance(value.value, str)):
                    found.add(value.value)
    return found


class AlertRegistryTests(unittest.TestCase):
    def test_canary_legacy_and_companion_emitters_are_known(self):
        for module in ("round_canaries.py", "round_absence.py", "growth_anomaly.py",
                       "plan_failure_events.py"):
            with self.subTest(module=module):
                self.assertFalse(_literal_alerts(module) - codes.PROVIDER_ALERT_CODES)

    def test_both_panel_and_canary_share_one_registry(self):
        self.assertIs(panel.ALERT_CODES, codes.ALERT_CODES)
        self.assertIs(panel.BLOCKING_CODES, codes.BLOCKING_CODES)
        self.assertIn("QUEJA_EXTERNA_REVISAR", panel.ALERT_CODES)
        self.assertIn("CAIDA_RENDIMIENTO_SOSTENIDA", panel.ALERT_CODES)
        self.assertIn("QUEJA_EXTERNA_REVISAR", panel.BLOCKING_CODES)
        self.assertEqual(canaries._alert("QUEJA_EXTERNA_REVISAR", "alta")["code"],
                         "QUEJA_EXTERNA_REVISAR")
        with self.assertRaises(ValueError):
            canaries._alert("NUEVO_CODIGO_NO_REGISTRADO", "alta")

    def test_all_blockers_are_known_to_panel(self):
        self.assertFalse(codes.BLOCKING_CODES - codes.ALERT_CODES)


if __name__ == "__main__":
    unittest.main()
