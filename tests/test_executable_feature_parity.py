"""Smoke/contratos de paridad sobre AST: ninguna acción en redes."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import executable_feature_parity as parity


class MatrixContractTests(unittest.TestCase):
    def test_real_networks_full_cells_and_existing_evidence(self):
        matrix = parity.build_matrix()
        self.assertEqual(set(matrix), set(parity.NETWORKS))
        self.assertEqual(len(matrix), 9)
        for network, row in matrix.items():
            with self.subTest(network=network):
                self.assertEqual(set(row), set(parity.FEATURES))
                for feature, cell in row.items():
                    self.assertIn(cell["status"], parity.STATES)
                    if cell["status"] == "wired":
                        self.assertTrue((parity.ROOT / cell["implementation"]).is_file())
                        self.assertIn(cell["pipeline_stage"], {"pre", "build", "execute", "post"})
                    for field in ("tests", "config", "metrics_source"):
                        value = cell[field]
                        for rel in value if isinstance(value, list) else [value]:
                            if rel:
                                self.assertTrue((parity.ROOT / rel).is_file(), (network, feature, field, rel))
        self.assertFalse(parity.problems(matrix))

    def test_real_smokes_are_not_remote_guarantees(self):
        matrix = parity.build_matrix()
        self.assertEqual(matrix["instagram"]["follow"]["status"], "wired")
        self.assertEqual(matrix["bluesky"]["unfollow"]["status"], "wired")
        self.assertEqual(matrix["x"]["unfollow"]["status"], "wired")
        self.assertEqual(matrix["reddit"]["repost"]["status"], "missing")
        self.assertEqual(matrix["pinterest"]["repost"]["status"], "missing")
        self.assertEqual(matrix["reddit"]["like"]["variant"], "vote")
        self.assertEqual(matrix["pinterest"]["like"]["variant"], "react")
        self.assertIsNone(matrix["facebook"]["follow"]["implementation"])
        self.assertNotEqual(matrix["reddit"]["comment"]["status"], "wired")

    def test_missing_unwired_and_wired_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools").mkdir()
            (root / "tools" / "instagram_execute.py").write_text(
                'def run_plan(plan):\n    if kind == "follow": pass\n', encoding="utf-8"
            )
            matrix = parity.build_matrix(root=root, pipelines={})
            self.assertEqual(matrix["instagram"]["follow"]["status"], "present_not_wired")
            self.assertEqual(matrix["instagram"]["like"]["status"], "missing")
            self.assertEqual(matrix["bluesky"]["follow"]["status"], "unverifiable")
            specs = {"instagram": {"execute": [sys.executable, "tools/instagram_execute.py", "plan.json"]}}
            matrix = parity.build_matrix(root=root, pipelines=specs)
            self.assertEqual(matrix["instagram"]["follow"]["status"], "wired")

    def test_invalid_ast_never_fakes_implementation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools").mkdir()
            (root / "tools" / "x_execute.py").write_text("def run_plan(:\n", encoding="utf-8")
            specs = {"x": {"execute": ["python", "tools/x_execute.py"]}}
            matrix = parity.build_matrix(root=root, pipelines=specs)
            self.assertEqual(matrix["x"]["like"]["status"], "unverifiable")
            self.assertEqual(matrix["x"]["comment"]["status"], "unverifiable")

    def test_windows_path_and_network_argument(self):
        spec = {"post": [["python.exe", "tools\\unfollow_cleanup.py", "x"]]}
        self.assertEqual(parity._wiring(spec, "unfollow_cleanup", "x"), "post")
        self.assertIsNone(parity._wiring(spec, "unfollow_cleanup", "threads"))
        self.assertIsNone(parity._wiring(spec, "loyalty"))

    def test_docstring_does_not_count_as_kind_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools").mkdir()
            (root / "tools" / "x_execute.py").write_text(
                '"""kind == "like" """\ndef run_plan(plan):\n    pass\n', encoding="utf-8"
            )
            specs = {"x": {"execute": ["python", "tools/x_execute.py"]}}
            matrix = parity.build_matrix(root=root, pipelines=specs)
            self.assertEqual(matrix["x"]["like"]["status"], "missing")

    def test_negative_kind_guard_is_not_positive_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools").mkdir()
            (root / "tools" / "x_execute.py").write_text(
                'def run_plan(plan):\n    if kind != "like": return\n', encoding="utf-8"
            )
            specs = {"x": {"execute": ["python", "tools/x_execute.py"]}}
            matrix = parity.build_matrix(root=root, pipelines=specs)
            self.assertEqual(matrix["x"]["like"]["status"], "missing")

    def test_cli_json_strict_and_requirement_gate(self):
        script = parity.ROOT / "tools/executable_feature_parity.py"
        result = subprocess.run(
            [sys.executable, str(script), "--json", "--strict"], cwd=parity.ROOT,
            text=True, capture_output=True, check=True,
        )
        self.assertEqual(len(json.loads(result.stdout)["matrix"]), 9)
        result = subprocess.run(
            [sys.executable, str(script), "--require", "reddit:repost"],
            cwd=parity.ROOT, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("not wired", result.stdout)
        result = subprocess.run(
            [sys.executable, str(script), "--require", "instagram:follow"],
            cwd=parity.ROOT, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_markdown_has_nine_rows_and_implementation_links(self):
        markdown = parity.as_markdown(parity.build_matrix())
        self.assertEqual(markdown.count("|\n"), 11)
        self.assertIn("../../tools/instagram_execute.py", markdown)


if __name__ == "__main__":
    unittest.main()
