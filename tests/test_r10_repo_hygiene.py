"""R10 / F8: nunca admitir archivos de ejecución añadidos por una PR.

Los casos se reproducen con RUTAS ficticias; nunca creamos ni tocamos
registros de cuentas ni secretos para probarlo.
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import repo_hygiene as rh


class FileHygieneTests(unittest.TestCase):
    def test_real_incident_reply_queue_files_rejected(self):
        paths = [
            "00_OPERATIVO/_cola_respuestas/answers.json",
            "00_OPERATIVO/_cola_respuestas/pending.json",
            "00_OPERATIVO/_cola_respuestas/gpt_texts.json",
        ]
        self.assertEqual(rh.violations_for_paths(paths), paths)

    def test_logs_registers_metrics_secrets_and_browser_profiles_blocked(self):
        paths = [
            "SISTEMA_DIARIO_X/registro_interacciones.csv",
            "SISTEMA_DIARIO_MASTODON/metricas.csv",
            "00_OPERATIVO/inbound_interacciones.csv",
            "SISTEMA_DIARIO_BLUESKY/cache/mech_20261008.log",
            "00_OPERATIVO/cola_rondas_web.log",
            ".env",
            ".env.local",
            "secrets/tiktok_tokens.json",
            "browser_profile/Default/Cookies",
            "mobile/cache/state.json",
            "keys/client.pem",
            "keys/client.key",
        ]
        self.assertEqual(rh.violations_for_paths(paths), paths)

    def test_safe_docs_source_and_env_examples_remain_allowed(self):
        paths = [
            "tools/cache_utils.py",
            "tools/repo_hygiene.py",
            "tools/token_resolver.py",
            "tests/test_secret_scanning.py",
            "00_OPERATIVO/PLAN_ROBUSTEZ.md",
            "SISTEMA_DIARIO_MASTODON/ESTADO.md",
            "tests/fixtures/anonymous_state.json",
            ".env.example",
            ".env.template",
            "requirements-ci.txt",
            ".github/workflows/validate-social-tools.yml",
        ]
        self.assertEqual(rh.violations_for_paths(paths), [])

    def test_windows_slashes_casefold_and_rename_target(self):
        paths = [
            "00_OPERATIVO\\_COLA_RESPUESTAS\\answers.json",
            "SISTEMA_DIARIO_X\\METRICAS.CSV",
            "00_OPERATIVO/2026.10.08.LOG",
        ]
        self.assertEqual(rh.violations_for_paths(paths), paths)

    def test_only_changed_paths_are_considered_not_old_repository_history(self):
        from pathlib import Path
        workflow = (ROOT / ".github/workflows/validate-social-tools.yml").read_text("utf-8")
        self.assertIn("repo_hygiene.py", workflow)
        self.assertIn("fetch-depth: 2", workflow)


if __name__ == "__main__":
    unittest.main()
