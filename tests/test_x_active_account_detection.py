"""Deteccion de cuenta activa en X (02/10): no depender del ancho de ventana."""
import ast
import pathlib
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"


def load_function(name):
    source = TOOLS / "x_interact.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    node = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name
    )
    env = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), env)
    return env[name]


class FakeLocator:
    def __init__(self, count=0, text="", attr=None, children=None, raise_on_text=False):
        self._count = count
        self._text = text
        self._attr = attr
        self._children = children or {}
        self._raise_on_text = raise_on_text

    def count(self):
        return self._count

    @property
    def first(self):
        return self

    def inner_text(self):
        if self._raise_on_text:
            raise RuntimeError("not hydrated yet")
        return self._text

    def get_attribute(self, _name):
        return self._attr

    def locator(self, selector):
        return self._children.get(selector, FakeLocator(count=0))


class ActiveAccountHandleTests(unittest.TestCase):
    def setUp(self):
        self.fn = load_function("_active_account_handle")

    def test_reads_handle_from_expanded_sidebar_text(self):
        pg = FakeLocatorPage(FakeLocator(
            count=1, text="Autora Demo Díaz\n@autorademodiaz",
        ))
        self.assertEqual(self.fn(pg), "autorademodiaz")

    def test_falls_back_to_avatar_testid_when_sidebar_collapsed(self):
        # Bug real visto en vivo el 02/10: con el sidebar colapsado a solo
        # icono (ventana mas estrecha tras reabrir Edge), el boton nunca
        # muestra texto "@handle" aunque la cuenta activa sea correcta -
        # solo el avatar interno, vacio de inner_text().
        btn = FakeLocator(
            count=1, text="",
            children={
                '[data-testid^="UserAvatar-Container-"]': FakeLocator(
                    count=1, attr="UserAvatar-Container-autorademodiaz",
                ),
            },
        )
        pg = FakeLocatorPage(btn)
        self.assertEqual(self.fn(pg), "autorademodiaz")

    def test_returns_none_when_button_missing(self):
        pg = FakeLocatorPage(FakeLocator(count=0))
        self.assertIsNone(self.fn(pg))

    def test_returns_none_when_neither_text_nor_avatar_available(self):
        pg = FakeLocatorPage(FakeLocator(count=1, text=""))
        self.assertIsNone(self.fn(pg))

    def test_tolerates_inner_text_raising(self):
        btn = FakeLocator(
            count=1, text="", raise_on_text=True,
            children={
                '[data-testid^="UserAvatar-Container-"]': FakeLocator(
                    count=1, attr="UserAvatar-Container-autorademodiaz",
                ),
            },
        )
        pg = FakeLocatorPage(btn)
        self.assertEqual(self.fn(pg), "autorademodiaz")


class FakeLocatorPage:
    """Fake minimo de `pg` - solo necesita exponer .locator(selector)."""

    def __init__(self, account_switcher_btn):
        self._btn = account_switcher_btn

    def locator(self, selector):
        if selector == '[data-testid="SideNav_AccountSwitcher_Button"]':
            return self._btn
        return FakeLocator(count=0)


if __name__ == "__main__":
    unittest.main()
