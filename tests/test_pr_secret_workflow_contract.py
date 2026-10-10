"""Make the secret scan an actual PR gate on both supported runners."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/validate-social-tools.yml"


class PrSecretWorkflowContract(unittest.TestCase):
    def test_pr_enabled_and_read_only_with_pinned_actions(self):
        y = WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(y, r"(?m)^  pull_request:\s*$")
        self.assertNotIn("pull_request_target", y)
        self.assertIn("permissions:\n  contents: read", y)
        self.assertNotRegex(y, r"(?m)^\s+\S+:\s*write\s*$")
        self.assertIn("persist-credentials: false", y)
        self.assertIn("fetch-depth: 2", y)
        self.assertIn("ubuntu-latest", y)
        self.assertIn("windows-latest", y)
        self.assertIn("fromJSON(", y)
        self.assertIn("branches: [main]", y)
        self.assertIn("paths:", y)
        self.assertNotIn("secrets.", y)
        actions = re.findall(r"(?m)^\s*- uses: ([^\s#]+)", y)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$")

    def test_pr_scan_before_pip_and_only_under_pr_event(self):
        y = WORKFLOW.read_text(encoding="utf-8")
        hygiene = 'python tools/repo_hygiene.py --base "HEAD^1"'
        installer = "python tools/install_gitleaks_ci.py"
        scan = "python tools/pr_secret_content_scan.py"
        pip = "python -m pip install --disable-pip-version-check -r requirements-ci.txt"
        for command in (hygiene, installer, scan):
            self.assertIn(command, y)
        self.assertLess(y.index(hygiene), y.index(installer))
        self.assertLess(y.index(installer), y.index(scan))
        self.assertLess(y.index(scan), y.index(pip))
        for command in (hygiene, installer, scan):
            step = y[:y.index(command)].rsplit("      - name:", 1)[-1]
            self.assertIn("if: github.event_name == 'pull_request'", step)

    def test_engine_uses_first_parent_diff_not_whole_history(self):
        script = (ROOT / "tools/pr_secret_content_scan.py").read_text(encoding="utf-8")
        self.assertIn("--diff-merges=first-parent", script)
        self.assertIn("--first-parent", script)
        self.assertIn("--no-renames", script)
        self.assertIn("--text", script)
        self.assertIn("--ignore-gitleaks-allow", script)
        self.assertIn("--redact=100", script)
        self.assertIn("HEAD^1..HEAD", script)
        self.assertNotIn("--all", script)


if __name__ == "__main__":
    unittest.main()
