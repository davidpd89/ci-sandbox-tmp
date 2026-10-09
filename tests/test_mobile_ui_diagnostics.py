"""Offline synthetic-only tests of mobile UI diagnostics."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mobile_ui_diagnostics as diag


def node(label, role="TextView", y=100, h=35):
    return {"type": role, "text": label,
            "rect": {"x": 10, "y": y, "width": 110, "height": h}}


def ui(username="cuenta_ejemplo", action="Seguir"):
    return {"elements": [
        node("Usuarios", "Button", 100),
        node(username, "TextView", 320),
        node(action, "Button", 450),
        node("Comentarios", "TextView", 1700),
    ]}


class DiagnosticsTests(unittest.TestCase):
    def test_navigator_exposes_read_only_snapshot(self):
        import tiktok_mobile_nav as nav
        navigator = object.__new__(nav.TikTokNavigator)
        calls = []
        navigator.tree = lambda **kwargs: calls.append("read") or ui()
        reference = diag.diagnose(ui())
        result = navigator.diagnose_current_ui(reference=reference)
        self.assertEqual(calls, ["read"])
        self.assertTrue(result["comparison"]["same_fingerprint"])
        self.assertEqual(result["snapshot"], reference)

    def test_private_text_changes_do_not_affect_fingerprint(self):
        original = diag.diagnose(ui("nombre_privado_A"))
        changed = diag.diagnose(ui("otro_nombre_privado_B"))
        self.assertEqual(original, changed)
        self.assertNotIn("nombre_privado_A", json.dumps(original))

    def test_structural_ui_drift_detected(self):
        before = diag.diagnose(ui())
        after = diag.diagnose(ui(action="Siguiendo"))
        self.assertNotEqual(before["fingerprint"], after["fingerprint"])
        comparison = diag.compare(before, after)
        self.assertLess(comparison["similarity"], 1.0)
        self.assertFalse(comparison["same_fingerprint"])

    def test_stable_under_dict_key_order_and_nested_root(self):
        a = diag.diagnose(ui())
        b = diag.diagnose({"root": {"children": ui()["elements"]}})
        self.assertEqual(a, b)

    def test_no_raw_identifier_or_coordinates_in_output(self):
        sample = ui("private_user_99")
        sample["elements"][1]["resourceId"] = "private_identifier"
        output = json.dumps(diag.diagnose(sample))
        self.assertNotIn("private_", output)
        self.assertNotIn("1700", output)

    def test_limit_deep_tree(self):
        root = node("x")
        for _ in range(40):
            root = {"children": [root]}
        with self.assertRaisesRegex(ValueError, "depth"):
            diag.diagnose(root)

    def test_limit_large_tree(self):
        with self.assertRaisesRegex(ValueError, "node limit"):
            diag.diagnose({"elements": [node("x") for _ in range(3100)]})

    def test_reject_invalid_rectangles(self):
        sample = {"elements": [node("X")]}
        sample["elements"][0]["rect"]["height"] = float("nan")
        with self.assertRaises(ValueError):
            diag.diagnose(sample)

    def test_rejects_tampered_result(self):
        first = diag.diagnose(ui())
        first["features"]["button:0:usuarios"] = 100
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            diag.compare(first, diag.diagnose(ui()))

    def test_rejects_bool_as_integer(self):
        a = diag.diagnose(ui())
        a["schema"] = True
        with self.assertRaises(ValueError):
            diag.compare(a, diag.diagnose(ui()))

    def test_rejects_injected_feature_key(self):
        a = diag.diagnose(ui())
        a["features"]["@private_user:0:none"] = 1
        with self.assertRaises(ValueError):
            diag.compare(a, diag.diagnose(ui()))

    def test_reports_similarity_for_identical(self):
        snapshot = diag.diagnose(ui())
        self.assertEqual(diag.compare(snapshot, snapshot)["similarity"], 1)
        self.assertTrue(diag.compare(snapshot, snapshot)["same_fingerprint"])

    def test_cli_offline_with_synthetic_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.json", Path(tmp) / "b.json"
            a.write_text(json.dumps(ui()), encoding="utf-8")
            b.write_text(json.dumps(ui(action="Siguiendo")), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(Path(diag.__file__)), str(b), "--reference", str(a)],
                check=True, capture_output=True, text=True, timeout=15,
            )
            output = json.loads(proc.stdout)
            self.assertFalse(output["comparison"]["same_fingerprint"])

    def test_cli_rejects_large_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "too_large.json"
            path.write_bytes(b" " * (diag.MAX_INPUT_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "size limit"):
                diag._read_json(path)


if __name__ == "__main__":
    unittest.main()
