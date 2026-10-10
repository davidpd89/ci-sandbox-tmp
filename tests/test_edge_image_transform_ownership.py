"""PR #58: transformador de imágenes — tests AST offline sin Edge, archivos o red."""
import ast
import contextlib
import pathlib
import sys
import types
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
SOURCE = TOOLS / "chatgpt_image_transform.py"


def isolated(*functions, **globals_):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in functions]
    namespace = dict(globals_)
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace


class Page:
    def __init__(self, url="about:blank"):
        self.url = url
        self.closed = False
        self.messages = []
        self.waits = []

    def close(self):
        self.closed = True

    def wait_for_timeout(self, ms):
        self.waits.append(ms)

    def locator(self, selector):
        if 'send-button' in selector:
            return types.SimpleNamespace(count=lambda: 1, click=lambda: self.messages.append("sent"))
        return types.SimpleNamespace(first=types.SimpleNamespace(fill=self.messages.append))


class Context:
    def __init__(self, stranger):
        self.pages = [stranger]
        self.created = []

    def new_page(self):
        pg = Page()
        self.created.append(pg)
        return pg

    def grant_permissions(self, permissions):
        raise AssertionError("Context grant_permissions no debe usarse")


class SyntheticPath:
    written = []
    def __init__(self, text):
        self.text = str(text)
        self.name = self.text.rsplit("/", 1)[-1]
        self.stem = self.name.rsplit(".", 1)[0]
        self.parent = self

    def __truediv__(self, other):
        return SyntheticPath(other)

    def exists(self):
        return not self.text.endswith("_v3.png")

    def write_bytes(self, data):
        self.written.append(data)


class TestImageTransformOwnership(unittest.TestCase):
    def test_existing_chat_page_never_reused(self):
        stranger = Page("https://chatgpt.com/c/private")
        ctx = Context(stranger)
        functions = isolated("find_chatgpt_page")
        own = functions["find_chatgpt_page"](types.SimpleNamespace(contexts=[ctx]))
        self.assertIs(own, ctx.created[0])
        self.assertIsNot(own, stranger)
        self.assertFalse(stranger.closed)

    def test_navigation_out_of_expected_project_refuses_upload(self):
        import chatgpt_consult
        page = Page("https://chatgpt.com/g/otro-proyecto/project")
        page.goto = lambda url: None
        funcs = isolated(
            "navigate_to_new_project_chat",
            PROJECT_URL=chatgpt_consult.PROJECT_URL,
            PROJECT_ID=chatgpt_consult.PROJECT_ID,
            print=lambda *a, **k: None,
        )
        with self.assertRaisesRegex(RuntimeError, "proyecto ChatGPT no verificable"):
            funcs["navigate_to_new_project_chat"](page)
        self.assertFalse(page.closed)  # Esta función no posee ni cierra tabs.

    def test_composer_uses_fill_without_context_permissions(self):
        own, ctx = Page(), Context(Page("https://chatgpt.com/c/private"))
        funcs = isolated("send_text")
        funcs["send_text"](own, ctx, "¿Qué tal?")
        self.assertEqual(own.messages, ["¿Qué tal?", "sent"])

    def test_main_closes_only_own_page_even_after_success(self):
        ctx = Context(Page("https://chatgpt.com/c/private"))
        browser = types.SimpleNamespace(contexts=[ctx])
        class Playwright:
            chromium = types.SimpleNamespace(connect_over_cdp=lambda *_args, **_kwargs: browser)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        state = {"processes": 0}
        def process(pg, c, path):
            state["processes"] += 1
            return b"synthetic-image"

        SyntheticPath.written = []
        functions = isolated(
            "main", "find_chatgpt_page",
            sys=types.SimpleNamespace(argv=["script", "photo_sintética.png"]),
            Path=SyntheticPath, IMAGES_DIR=SyntheticPath("fixture"),
            ORIGINALS=[], sync_playwright=lambda: Playwright(),
            contextlib=contextlib, CDP_URL="http://127.0.0.1:9223",
            process_image=process, print=lambda *args, **kwargs: None,
        )
        functions["main"]()
        self.assertEqual(state["processes"], 1)
        self.assertEqual(SyntheticPath.written, [b"synthetic-image"])
        self.assertTrue(ctx.created[0].closed)
        self.assertFalse(ctx.pages[0].closed)

    def test_main_cleanup_after_fatal_write_error(self):
        ctx = Context(Page("https://chatgpt.com/c/private"))
        browser = types.SimpleNamespace(contexts=[ctx])
        class Pw:
            chromium = types.SimpleNamespace(connect_over_cdp=lambda *_args, **_kwargs: browser)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        def broken_write(self, data):
            raise PermissionError("WinError 5")

        functions = isolated(
            "main", "find_chatgpt_page",
            sys=types.SimpleNamespace(argv=["script", "photo.png"]),
            Path=SyntheticPath, IMAGES_DIR=SyntheticPath("fixture"),
            ORIGINALS=[], sync_playwright=lambda: Pw(),
            contextlib=contextlib, CDP_URL="http://127.0.0.1:9223",
            process_image=lambda *_: b"synthetic-image",
            print=lambda *args, **kwargs: None,
        )
        with mock.patch.object(SyntheticPath, "write_bytes", broken_write):
            with self.assertRaises(PermissionError):
                functions["main"]()
        self.assertTrue(ctx.created[0].closed)
        self.assertFalse(ctx.pages[0].closed)


if __name__ == "__main__":
    unittest.main()
