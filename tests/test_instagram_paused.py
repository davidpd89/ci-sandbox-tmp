"""Mecanismo de pausa de Instagram (03/10 pausada; 04/10 reactivada con 10 follows/dia): con la constante en True no se interactua."""
import pathlib
import subprocess
import sys
import unittest

TOOLS = str(pathlib.Path(__file__).resolve().parents[1] / "tools")


def run_clean(code):
    proc = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {TOOLS!r})\n" + code],
                          capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, proc.stdout + proc.stderr


class InstagramPausedTests(unittest.TestCase):
    def test_connect_refuses_before_touching_the_browser(self):
        code = ("import instagram_interact as ig\nig.INTERACTIONS_PAUSED = True\n"
                "try:\n    ig._connect()\nexcept ig.InteractionsPaused:\n    print('PAUSADO')\n")
        rc, out = run_clean(code)
        self.assertEqual(rc, 0, out)
        self.assertIn("PAUSADO", out)

    def test_run_plan_refuses_after_offline_preflight(self):
        code = ("import instagram_execute as ex, instagram_interact as ig\nig.INTERACTIONS_PAUSED = True\n"
                "plan = [{'kind': 'like', 'handle': '@a', 'permalink': 'https://www.instagram.com/p/ABC123/'}]\n"
                "try:\n    ex.run_plan(plan)\nexcept ig.InteractionsPaused:\n    print('PAUSADO')\n")
        rc, out = run_clean(code)
        self.assertEqual(rc, 0, out)
        self.assertIn("PAUSADO", out)


if __name__ == "__main__":
    unittest.main()
