"""La publicación propia automatizada de X permanece desactivada."""
import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "x_schedule_post.py"
BATCH = pathlib.Path(__file__).resolve().parents[1] / "tools" / "x_batch_schedule.py"


def _load_publication_stub(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"OwnPublicationDisabled", "schedule_post", "main"}
    nodes = [
        node for node in tree.body
        if (
            isinstance(node, ast.ClassDef) and node.name in names
        ) or (
            isinstance(node, ast.FunctionDef) and node.name in names
        ) or (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "_MESSAGE" for t in node.targets)
        )
    ]
    env = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), env)
    return env


class XOwnPublicationDisabledTests(unittest.TestCase):
    def test_scheduler_fails_without_browser_code(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn("playwright", source.casefold())
        self.assertNotIn("connect_over_cdp", source)
        env = _load_publication_stub(SOURCE)
        with self.assertRaises(env["OwnPublicationDisabled"]):
            env["schedule_post"]("texto", None, 2026, 10, 1, 12, 0)

    def test_old_batch_fails_before_media_or_scheduler(self):
        source = BATCH.read_text(encoding="utf-8")
        self.assertNotIn("imageio_ffmpeg", source)
        self.assertNotIn("subprocess", source)
        env = _load_publication_stub(BATCH)
        with self.assertRaises(env["OwnPublicationDisabled"]):
            env["main"]()


if __name__ == "__main__":
    unittest.main()
