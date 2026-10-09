"""Guards puros del descubrimiento de Threads."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "threads_scan.py"


class ThreadsScanCandidateKeyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        node = next(
            item for item in tree.body
            if isinstance(item, ast.FunctionDef) and item.name == "_candidate_key"
        )
        namespace = {}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), namespace)
        cls.candidate_key = staticmethod(namespace["_candidate_key"])

    def test_distinct_posts_by_same_author_are_not_collapsed(self):
        first = self.candidate_key(
            "autora", "https://www.threads.com/@autora/post/uno", "Post uno"
        )
        second = self.candidate_key(
            "autora", "https://www.threads.com/@autora/post/dos", "Post dos"
        )
        self.assertNotEqual(first, second)

    def test_same_post_from_feed_and_search_is_collapsed(self):
        first = self.candidate_key(
            "autora", "https://www.threads.com/@autora/post/uno/", "Post uno"
        )
        second = self.candidate_key(
            "autora", "https://www.threads.com/@autora/post/uno", "Texto distinto por re-render"
        )
        self.assertEqual(first, second)

    def test_missing_permalink_uses_normalized_text(self):
        first = self.candidate_key("autora", None, "  Una   idea útil. ")
        second = self.candidate_key("AUTORA", None, "una idea útil.")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
