"""Contrato documental/configuración del motor diario Bluesky."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BS = ROOT / "SISTEMA_DIARIO_BLUESKY"


class BlueskyGrowthDocsTests(unittest.TestCase):
    def test_hot_path_points_to_growth_flow_not_legacy_scan(self):
        for name in ("README.md", "ESTADO.md", "PROCESO.md"):
            text = (BS / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertIn("bluesky_growth_flow.py", text)

        estado = (BS / "ESTADO.md").read_text(encoding="utf-8")
        self.assertIn("Legacy", estado)
        self.assertNotIn(
            "python tools/bluesky_scan.py --json",
            estado,
        )

    def test_growth_config_requires_real_external_exploration(self):
        config = json.loads((BS / "growth_config.json").read_text(encoding="utf-8"))
        required = set(config["coverage"]["required_surfaces"])
        self.assertTrue({
            "post_search",
            "actor_search",
            "thread_commenters",
            "engagers",
            "similar_accounts",
            "graph_neighbors",
        }.issubset(required))
        self.assertGreaterEqual(len(config["query_families"]), 6)
        self.assertGreaterEqual(config["budgets"]["max_read_requests"], 100)
        self.assertNotIn("action_ceiling", config)

    def test_daily_docs_use_orchestrated_state_ai_and_report_files(self):
        for name in ("ESTADO.md", "PROCESO.md"):
            text = (BS / name).read_text(encoding="utf-8")
            with self.subTest(name=name):
                self.assertIn("bluesky_growth_flow.py prepare", text)
                self.assertIn("--strict", text)
                self.assertIn("growth_ai.json", text)
                self.assertIn("growth_state.json", text)
                self.assertIn("growth_report.json", text)

    def test_legacy_scanner_warns_it_is_not_daily_entrypoint(self):
        text = (ROOT / "tools" / "bluesky_scan.py").read_text(encoding="utf-8")
        self.assertIn("LEGACY / DIAGNÓSTICO RÁPIDO", text)
        self.assertIn("bluesky_growth_flow.py", text)


if __name__ == "__main__":
    unittest.main()
