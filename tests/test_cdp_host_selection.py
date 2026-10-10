"""Ejecuta solo _connect extraído del AST con un CDP simulado, sin navegador/red."""
import ast
import pathlib
import types
import unittest
import urllib.parse

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"

CASES = (
    ("x_interact.py", "https://falso-x.com/x.com/perfil", "https://x.com/perfil"),
    ("threads_interact.py", "https://threads.com.ejemplo.org/", "https://www.threads.com/"),
    ("instagram_interact.py", "https://instagram.com.ejemplo.org/", "https://www.instagram.com/"),
    ("facebook_interact.py", "https://facebook.com.ejemplo.org/", "https://www.facebook.com/"),
    ("tiktok_interact.py", "https://tiktok.com.ejemplo.org/", "https://www.tiktok.com/"),
)


def _x_connect(urls):
    """X (06/10) delega en `browser_common.Browser`: se prueba la conexion real de x_interact con un Playwright simulado."""
    import sys
    sys.path.insert(0, str(TOOLS))
    import browser_common as bc
    import x_interact
    pages = [types.SimpleNamespace(url=u) for u in urls]
    ctx = types.SimpleNamespace(pages=pages, new_page=lambda: types.SimpleNamespace(url="about:blank"))
    driver = types.SimpleNamespace(chromium=types.SimpleNamespace(connect_over_cdp=lambda *args, **kw: types.SimpleNamespace(contexts=[ctx])), stop=lambda: None)
    original = bc.sync_playwright
    bc.sync_playwright = lambda: types.SimpleNamespace(start=lambda: driver)
    try:
        return x_interact._connect()[1]
    finally:
        bc.sync_playwright = original


def isolated_connect(filename, urls):
    if filename == "x_interact.py":
        return _x_connect(urls)
    import sys
    sys.path.insert(0, str(TOOLS))
    code = (TOOLS / filename).read_text(encoding="utf-8")
    fn = next(node for node in ast.parse(code).body
              if isinstance(node, ast.FunctionDef) and node.name == "_connect")
    pages = [types.SimpleNamespace(url=u) for u in urls]
    ctx = types.SimpleNamespace(pages=pages)
    ctx.new_page = lambda: types.SimpleNamespace(url="about:blank")
    browser = types.SimpleNamespace(contexts=[ctx])
    driver = types.SimpleNamespace(
        chromium=types.SimpleNamespace(connect_over_cdp=lambda *args, **kw: browser),
        stop=lambda: None,
    )
    env = {
        "sync_playwright": lambda: types.SimpleNamespace(start=lambda: driver),
        "CDP_URL": "http://127.0.0.1:9223",
        "urlsplit": urllib.parse.urlsplit,
        "urllib": urllib,
        # TikTok está pausado globalmente; este test aísla únicamente la
        # selección de hostname del conector, no la política de pausa.
        "_refuse_if_paused": lambda: None,
        # Threads reutiliza una sesion compartida cuando hay una abierta (`threads_interact.session`): aqui no la hay
        "_SHARED": {"pg": None},
        "_KeepOpen": object,
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), filename, "exec"), env)
    _, selected = env["_connect"]()
    return selected


class ExactCDPHostTests(unittest.TestCase):
    def test_ignores_domain_containing_social_name(self):
        for filename, fake, real in CASES:
            with self.subTest(module=filename):
                # Ningún hostname demuestra ownership, incluso cuando coincide.
                self.assertEqual(isolated_connect(filename, [real, fake]).url, "about:blank")

    def test_never_reuses_only_fake_social_tab(self):
        for filename, fake, _ in CASES:
            with self.subTest(module=filename):
                self.assertEqual(isolated_connect(filename, [fake]).url, "about:blank")


if __name__ == "__main__":
    unittest.main()
