"""Contrato offline del workflow del mirror público, sin cuentas ni secretos."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "validate-social-tools.yml"


class MirrorWindowsCiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.yaml = WORKFLOW.read_text(encoding="utf-8")

    def test_every_pr_is_validated_without_privileged_pr_target(self):
        self.assertRegex(self.yaml, r"(?m)^  pull_request:\s*$")
        self.assertNotIn("pull_request_target", self.yaml)

    def test_mirror_pr_includes_windows_and_ubuntu(self):
        self.assertIn("github.repository == 'davidpd89/ci-sandbox-tmp'", self.yaml)
        self.assertIn('["ubuntu-latest","windows-latest"]', self.yaml)
        self.assertIn("github.base_ref != 'main'", self.yaml)

    def test_checkout_is_read_only_shallow_and_pinned(self):
        self.assertIn("permissions:\n  contents: read", self.yaml)
        self.assertNotRegex(self.yaml, r"(?m)^\s+[a-z-]+:\s*write\s*$")
        self.assertIn("persist-credentials: false", self.yaml)
        self.assertIn("fetch-depth: 2", self.yaml)
        self.assertNotIn("secrets.", self.yaml)

        uses = re.findall(r"(?m)^\s*- uses:\s*([^\s#]+)", self.yaml)
        self.assertTrue(uses)
        for action in uses:
            self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$")

    def test_hygiene_runs_before_dependency_install(self):
        hygiene = 'python tools/repo_hygiene.py --base "HEAD^1"'
        install = "python -m pip install --disable-pip-version-check -r requirements-ci.txt"
        self.assertIn(hygiene, self.yaml)
        self.assertIn(install, self.yaml)
        self.assertLess(self.yaml.index(hygiene), self.yaml.index(install))

    def test_offline_regressions_run_without_network_entrypoint(self):
        self.assertIn("python -m compileall -q tools tests", self.yaml)
        self.assertIn("python -m pytest tests -q -p no:cacheprovider", self.yaml)
        self.assertNotRegex(self.yaml, r"(?m)^\s*run:\s*(?:curl|wget|Invoke-WebRequest)\b")


if __name__ == "__main__":
    unittest.main()
