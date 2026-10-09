"""Filtros offline para no resugerir posts ya respondidos."""
import ast
import pathlib
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_helper(filename, function_name, urls):
    source = ROOT / "tools" / filename
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == function_name
    )
    namespace = {"sc": types.SimpleNamespace(already_interacted_urls=lambda _path: urls)}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[function_name]


def load_candidate_key(filename):
    source = ROOT / "tools" / filename
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == "_candidate_key"
    )
    namespace = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return staticmethod(namespace["_candidate_key"])


class ScanHistoryFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.instagram_key = load_candidate_key("instagram_scan.py")

    def test_instagram_keeps_distinct_posts_by_same_author(self):
        first = self.instagram_key(
            "autora", "https://www.instagram.com/p/UNO/", "Post uno"
        )
        second = self.instagram_key(
            "autora", "https://www.instagram.com/p/DOS/", "Post dos"
        )
        self.assertNotEqual(first, second)

    def test_instagram_dedupes_account_search_without_permalink(self):
        first = self.instagram_key("@AUTORA", None, "Bio uno")
        second = self.instagram_key("autora", None, "Bio dos")
        self.assertEqual(first, second)

    def test_threads_normalizes_trailing_slash(self):
        helper = load_helper(
            "threads_scan.py",
            "_previously_replied_urls",
            {"https://www.threads.com/@autora/post/1/"},
        )
        self.assertEqual(helper("unused.csv"), {"https://www.threads.com/@autora/post/1"})

    def test_instagram_normalizes_trailing_slash(self):
        helper = load_helper(
            "instagram_scan.py",
            "_previously_commented_urls",
            {"https://www.instagram.com/p/ABC/"},
        )
        self.assertEqual(helper("unused.csv"), {"https://www.instagram.com/p/ABC"})


if __name__ == "__main__":
    unittest.main()
