"""Contrato offline: Windows solo en el mirror saneado, sin cuentas."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "validate-social-tools.yml"


class MirrorWindowsCiContract(unittest.TestCase):
    def test_mirror_pr_includes_windows_runner_without_enabling_private_actions(self):
        yaml = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.repository == 'davidpd89/ci-sandbox-tmp'", yaml)
        self.assertIn('["ubuntu-latest","windows-latest"]', yaml)
        self.assertIn("github.base_ref != 'main'", yaml)
        self.assertIn("python -m pytest tests -q -p no:cacheprovider", yaml)
        self.assertIn("python tools/repo_hygiene.py", yaml)
        self.assertIn("permissions:\n  contents: read", yaml)


if __name__ == "__main__":
    unittest.main()
