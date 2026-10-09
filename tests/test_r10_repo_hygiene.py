"""R10 / F8: nunca admitir archivos de ejecución añadidos por una PR.

Los casos unitarios de nombres usan RUTAS ficticias. Los casos de Git crean un
repositorio temporal con datos sintéticos; nunca leen ni tocan cuentas reales.
"""
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import repo_hygiene as rh


def _git(root: pathlib.Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _write(root: pathlib.Path, relative: str, content: str = "synthetic\n") -> None:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _synthetic_pr_merge(root: pathlib.Path, changed_path: str) -> None:
    """Crea el mismo shape que checkout recibe en pull_request: merge con base primero."""
    _git(root, "init")
    _git(root, "config", "user.email", "ci@example.invalid")
    _git(root, "config", "user.name", "CI Contract")

    # Deuda histórica deliberada: la comprobación de una PR no debe reabrirla.
    _write(root, "SISTEMA_DIARIO_X/metricas.csv")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    base_branch = _git(root, "branch", "--show-current")

    _git(root, "checkout", "-b", "feature")
    _write(root, changed_path)
    _git(root, "add", ".")
    _git(root, "commit", "-m", "feature")

    _git(root, "checkout", base_branch)
    _git(root, "merge", "--no-ff", "feature", "-m", "merge feature")


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

    def test_pr_merge_diff_ignores_forbidden_file_already_in_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            _synthetic_pr_merge(repo, "tools/safe_change.py")
            self.assertEqual(rh.changed_paths("HEAD^1", root=repo), ["tools/safe_change.py"])
            self.assertEqual(rh.violations_for_paths(rh.changed_paths("HEAD^1", root=repo)), [])

    def test_pr_merge_diff_blocks_new_forbidden_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            _synthetic_pr_merge(repo, "mobile/cache/state.json")
            changed = rh.changed_paths("HEAD^1", root=repo)
            self.assertEqual(changed, ["mobile/cache/state.json"])
            self.assertEqual(rh.violations_for_paths(changed), ["mobile/cache/state.json"])

    def test_type_change_to_symlink_is_not_invisible_to_hygiene(self):
        # Index-only mode switch is Windows-compatible: no OS symlink needed.
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            _git(repo, "init")
            _git(repo, "config", "user.email", "ci@example.invalid")
            _git(repo, "config", "user.name", "CI Contract")
            _write(repo, "credentials.json")
            _git(repo, "add", "credentials.json")
            _git(repo, "commit", "-m", "historical regular file")
            _write(repo, "synthetic-link-target", "synthetic target only\\n")
            blob = _git(repo, "hash-object", "-w", "synthetic-link-target")
            _git(repo, "update-index", "--cacheinfo", f"120000,{blob},credentials.json")
            _git(repo, "commit", "-m", "change file type")
            changed = rh.changed_paths("HEAD^1", root=repo)
            self.assertEqual(changed, ["credentials.json"])
            self.assertEqual(rh.violations_for_paths(changed), ["credentials.json"])

    def test_rename_into_sensitive_name_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            _git(repo, "init")
            _git(repo, "config", "user.email", "ci@example.invalid")
            _git(repo, "config", "user.name", "CI Contract")
            _write(repo, "example.json")
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "base")
            _git(repo, "mv", "example.json", "credentials.json")
            _git(repo, "commit", "-m", "rename to blocked path")
            changed = rh.changed_paths("HEAD^1", root=repo)
            self.assertEqual(changed, ["credentials.json"])
            self.assertEqual(rh.violations_for_paths(changed), ["credentials.json"])

    def test_deleting_historical_forbidden_path_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            _git(repo, "init")
            _git(repo, "config", "user.email", "ci@example.invalid")
            _git(repo, "config", "user.name", "CI Contract")
            _write(repo, "secrets.json")
            _git(repo, "add", ".")
            _git(repo, "commit", "-m", "old history")
            _git(repo, "rm", "secrets.json")
            _git(repo, "commit", "-m", "remove obsolete sensitive path")
            self.assertEqual(rh.changed_paths("HEAD^1", root=repo), [])

    def test_only_changed_paths_are_considered_not_old_repository_history(self):
        workflow = (ROOT / ".github/workflows/validate-social-tools.yml").read_text("utf-8")
        self.assertIn('repo_hygiene.py --base "HEAD^1"', workflow)
        self.assertIn("fetch-depth: 2", workflow)


if __name__ == "__main__":
    unittest.main()
