"""PR #58: inspección AST del preflight CDP, sin importar websocket ni abrir red."""
import ast
import contextlib
import io
import pathlib
import types
import unittest
from unittest import mock

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "cdp_resume_workers.py"


def isolated_main(browser_type):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    ns = {"sys": types.SimpleNamespace(argv=["script"]), "Browser": browser_type,
          "print": print}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns["main"]


class FakeBrowser:
    created = []
    targets = [
        {"targetId": "automatio-123", "type": "worker", "url": "https://privado.example/token-secreto", "attached": False},
        {"targetId": "personal-5678", "type": "shared_worker", "url": "https://privado.example/auth?token=123", "attached": True},
        {"targetId": "pagina-real-123", "type": "page", "url": "https://example.com/cuenta"},
    ]

    def __init__(self):
        self.calls = []
        self.closed = False
        self.created.append(self)

    def call(self, method, params=None, session=None):
        self.calls.append(method)
        if method != "Target.getTargets":
            raise AssertionError("Se intentó mutar estado CDP")
        return {"result": {"targetInfos": self.targets}}

    def close(self):
        self.closed = True


class ReadOnlyWorkerTests(unittest.TestCase):
    def setUp(self):
        FakeBrowser.created.clear()

    def test_default_is_readonly_even_for_attached_personal_worker(self):
        lines = io.StringIO()
        with contextlib.redirect_stdout(lines):
            self.assertEqual(isolated_main(FakeBrowser)([]), 0)
        self.assertEqual(len(FakeBrowser.created), 1)
        self.assertEqual(FakeBrowser.created[0].calls, ["Target.getTargets"])
        self.assertTrue(FakeBrowser.created[0].closed)
        self.assertIn("diagnóstico_solo_lectura=1", lines.getvalue())
        self.assertNotIn("token-secreto", lines.getvalue())
        self.assertNotIn("auth?token=", lines.getvalue())

    def test_explicit_list_is_identical(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(isolated_main(FakeBrowser)(["--list"]), 0)
        self.assertEqual(FakeBrowser.created[0].calls, ["Target.getTargets"])

    def test_old_resume_flag_fails_before_connecting(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(isolated_main(FakeBrowser)(["--resume"]), 2)
        self.assertEqual(FakeBrowser.created, [])

    def test_invalid_targets_fail_closed_and_disconnect(self):
        original = FakeBrowser.targets
        try:
            FakeBrowser.targets = "no es lista"
            with self.assertRaisesRegex(RuntimeError, "inválida"):
                with contextlib.redirect_stdout(io.StringIO()):
                    isolated_main(FakeBrowser)([])
            self.assertTrue(FakeBrowser.created[0].closed)
        finally:
            FakeBrowser.targets = original


if __name__ == "__main__":
    unittest.main()
