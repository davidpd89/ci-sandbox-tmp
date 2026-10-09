"""MY_ACCOUNT_EMAIL nunca debe quedar vacío solo porque falte la variable de
entorno REDDIT_ACCOUNT_EMAIL - eso rompía _health_check() de inmediato en
cualquier máquina donde esa variable no estuviera puesta (bug real
encontrado el 28/09/2026 revisando esta PR: no lo estaba en la máquina real
donde corre este proyecto)."""
import os
import pathlib
import subprocess
import sys
import unittest

TOOLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "tools"


def _account_email_without_env_var():
    env = {k: v for k, v in os.environ.items() if k != "REDDIT_ACCOUNT_EMAIL"}
    result = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, r'%s')\n"
         "import ast\n"
         "src = open(r'%s/reddit_interact.py', encoding='utf-8').read()\n"
         "tree = ast.parse(src)\n"
         "ns = {'os': __import__('os')}\n"
         "for node in tree.body:\n"
         "    if isinstance(node, ast.Assign) and any(\n"
         "        isinstance(t, ast.Name) and t.id == 'MY_ACCOUNT_EMAIL' for t in node.targets\n"
         "    ):\n"
         "        exec(compile(ast.Module(body=[node], type_ignores=[]), 'x', 'exec'), ns)\n"
         "print(ns['MY_ACCOUNT_EMAIL'])"
         % (TOOLS_DIR, TOOLS_DIR)],
        capture_output=True, text=True, env=env, timeout=15,
    )
    return result.stdout.strip()


class AccountEmailFallbackTests(unittest.TestCase):
    def test_non_empty_without_environment_variable(self):
        self.assertTrue(_account_email_without_env_var())


if __name__ == "__main__":
    unittest.main()
