"""La revisión anti-bloqueo de TikTok detecta retos sin texto en body."""
import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "tiktok_interact.py"


class BotWarningDetected(RuntimeError):
    pass


class FakePage:
    def __init__(self, challenge=0, text=""):
        self.challenge, self.text = challenge, text

    def evaluate(self, js):
        return False   # ningun captcha VISIBLE en la pagina de prueba (el JS real se prueba en test_tiktok_captcha_stop)

    def locator(self, selector):
        return type("Locator", (), {"count": lambda _: self.challenge})()

    def inner_text(self, selector):
        return self.text


class TikTokChallengeTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_check_bot_warning", "captcha_visible")]
        nodes += [n for n in tree.body if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "_CAPTCHA_VISIBLE_JS" for t in n.targets)]
        namespace = {"BotWarningDetected": BotWarningDetected,
                     "BOT_WARNING_SIGNALS": ["verify you are human"]}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), namespace)
        self.check = namespace["_check_bot_warning"]

    def test_iframe_challenge_blocks_without_body_text(self):
        with self.assertRaisesRegex(BotWarningDetected, "CAPTCHA"):
            self.check(FakePage(challenge=1))

    def test_body_warning_blocks(self):
        with self.assertRaises(BotWarningDetected):
            self.check(FakePage(text="Please verify you are human"))

    def test_clean_page_does_not_block(self):
        self.assertIsNone(self.check(FakePage()))


if __name__ == "__main__":
    unittest.main()
