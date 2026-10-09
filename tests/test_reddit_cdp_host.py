"""No reutilizar pestañas ajenas por contener 'reddit.com' en la URL."""
import ast
import pathlib
import types
import unittest
import urllib.parse

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "reddit_interact.py"


class RedditCDPHostTests(unittest.TestCase):
    def test_exact_domain(self):
        fn = next(node for node in ast.parse(SOURCE.read_text(encoding="utf-8")).body
                  if isinstance(node, ast.FunctionDef) and node.name == "_connect")
        good = types.SimpleNamespace(url="https://www.reddit.com/r/libros")
        evil = types.SimpleNamespace(url="https://reddit.com.ejemplo.org/")
        context = types.SimpleNamespace(pages=[good, evil])
        context.new_page = lambda: types.SimpleNamespace(url="about:blank")
        browser = types.SimpleNamespace(contexts=[context])
        driver = types.SimpleNamespace(
            chromium=types.SimpleNamespace(connect_over_cdp=lambda *args: browser)
        )
        ns = {"sync_playwright": lambda: types.SimpleNamespace(start=lambda: driver),
              "CDP_URL": "http://127.0.0.1:9223", "urllib": urllib}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), ns)
        self.assertIs(ns["_connect"]()[1], good)


if __name__ == "__main__":
    unittest.main()
