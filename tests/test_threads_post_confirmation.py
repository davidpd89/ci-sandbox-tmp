"""Confirmar post Threads por permalink propio nuevo, sin abrir navegador real."""
import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "threads_interact.py"


class FakePage:
    def goto(self, *args, **kwargs):
        return None
    def wait_for_timeout(self, *args, **kwargs):
        return None


class ThreadsPostConfirmationTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == "_matching_own_post_urls")
        self.env = {
            "MY_HANDLE": "autorademodiaz",
            "_check_bot_warning": lambda pg: None,
            "_extract_posts": lambda pg, limit=20: [
                ("autorademodiaz", "https://www.threads.com/@autorademodiaz/post/1",
                 "Autora Demo Hace 1 min Mi texto exacto para publicar"),
                ("otra", "https://www.threads.com/@otra/post/2",
                 "Mi texto exacto para publicar"),
                ("autorademodiaz", None, "Mi texto exacto para publicar"),
            ],
        }
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), self.env)

    def test_only_own_matching_permalink_counts(self):
        urls = self.env["_matching_own_post_urls"](
            FakePage(), "Mi texto exacto para publicar"
        )
        self.assertEqual(
            urls, {"https://www.threads.com/@autorademodiaz/post/1"}
        )

    def test_unrelated_text_does_not_confirm(self):
        self.assertEqual(
            self.env["_matching_own_post_urls"](FakePage(), "Otro contenido"),
            set(),
        )


if __name__ == "__main__":
    unittest.main()
