"""Guardas offline de objetivo/estado compartidas por varias redes."""
import ast
import pathlib
import re
import types
import unittest
import urllib

ROOT = pathlib.Path(__file__).resolve().parents[1] / "tools"


def load_functions(filename, names, namespace=None):
    source = ROOT / filename
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in set(names)
    ]
    env = dict(namespace or {})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), env)
    return env


class FakeButton:
    def __init__(self, *, y=0, text="", testid=None, pressed=None, in_primary=True):
        self.y = y
        self.text = text
        self.testid = testid
        self.pressed = pressed
        self.in_primary = in_primary

    def bounding_box(self):
        return {"x": 0, "y": self.y, "width": 100, "height": 30}

    def inner_text(self):
        return self.text

    def get_attribute(self, name):
        if name == "data-testid":
            return self.testid
        if name == "aria-pressed":
            return self.pressed
        return None


class FakeCollection:
    def __init__(self, items):
        self.items = list(items)

    def count(self):
        return len(self.items)

    def nth(self, index):
        return self.items[index]

    @property
    def first(self):
        return self.items[0]


class FakeScope:
    """Simula el resultado de acotar a un contenedor (p.ej. primaryColumn)."""
    def __init__(self, items):
        self.items = items

    def locator(self, selector):
        return FakeCollection(self.items)


class XPage:
    """`[data-testid="primaryColumn"]` solo devuelve los controles marcados
    `in_primary=True` - simula que la columna lateral de sugerencias queda
    fuera de ese contenedor, igual que en la página real de X."""
    def __init__(self, controls):
        self.controls = controls

    def locator(self, selector):
        if selector == '[data-testid="primaryColumn"]':
            primary = [c for c in self.controls if getattr(c, "in_primary", True)]
            return FakeCollection([FakeScope(primary)])
        return FakeCollection(self.controls)


class RolePage:
    def __init__(self, controls):
        self.controls = controls

    def get_by_role(self, role):
        self.last_role = role
        return FakeCollection(self.controls)


class TikTokPage:
    def __init__(self, controls):
        self.controls = controls

    def locator(self, selector):
        return FakeCollection(self.controls)


class NavPage:
    def __init__(self):
        self.visits = []

    def goto(self, url, **kwargs):
        self.visits.append(url)

    def wait_for_timeout(self, *args, **kwargs):
        return None


class TargetGuardTests(unittest.TestCase):
    def test_x_follow_uses_top_profile_control_not_lower_recommendation(self):
        env = load_functions(
            "x_interact.py",
            ["_top_profile_follow_control", "_profile_follow_state"],
        )
        target = FakeButton(y=100, text="Follow", testid="123-follow")
        recommendation = FakeButton(
            y=500, text="Following", testid="999-unfollow"
        )
        chosen = env["_top_profile_follow_control"](
            XPage([recommendation, target])
        )
        self.assertIs(chosen, target)
        self.assertEqual(env["_profile_follow_state"](chosen), "follow")

    def test_x_follow_ignores_sidebar_suggestion_above_profile_button(self):
        """Regresión (revisión externa 28/09): en vivo, el widget "A quién
        seguir" de la columna derecha renderiza a un y MENOR que el propio
        botón del perfil (confirmado en 3 perfiles reales) - la heurística
        de "menor y de toda la página" elegía sistemáticamente una cuenta
        ajena de esa columna en vez del perfil objetivo. Acotar a
        primaryColumn debe ignorar esa columna aunque tenga menor y."""
        env = load_functions(
            "x_interact.py",
            ["_top_profile_follow_control", "_profile_follow_state"],
        )
        sidebar_suggestion = FakeButton(
            y=10, text="Follow", testid="999-follow", in_primary=False
        )
        profile_button = FakeButton(
            y=264, text="Follow", testid="123-follow", in_primary=True
        )
        chosen = env["_top_profile_follow_control"](
            XPage([sidebar_suggestion, profile_button])
        )
        self.assertIs(chosen, profile_button)

    def test_threads_and_instagram_follow_use_top_profile_button(self):
        for filename in ("threads_interact.py", "instagram_interact.py"):
            with self.subTest(filename=filename):
                env = load_functions(
                    filename,
                    [
                        "_top_profile_follow_button",
                        "_profile_follow_button_state",
                    ],
                )
                target = FakeButton(y=90, text="Seguir")
                recommendation = FakeButton(y=450, text="Siguiendo")
                chosen = env["_top_profile_follow_button"](
                    RolePage([recommendation, target])
                )
                self.assertIs(chosen, target)
                self.assertEqual(
                    env["_profile_follow_button_state"](chosen),
                    "follow",
                )

    def test_pending_follow_state_is_explicit(self):
        for filename, helper in (
            ("x_interact.py", "_profile_follow_state"),
            ("threads_interact.py", "_profile_follow_button_state"),
            ("instagram_interact.py", "_profile_follow_button_state"),
        ):
            with self.subTest(filename=filename):
                names = [helper]
                env = load_functions(filename, names)
                button = FakeButton(text="Pending", testid="123-follow")
                self.assertEqual(env[helper](button), "pending")

    def test_tiktok_like_state_requires_aria_pressed(self):
        env = load_functions("tiktok_interact.py", ["_video_like_control"])
        for value in ("true", "false"):
            with self.subTest(value=value):
                button = FakeButton(pressed=value)
                got, state = env["_video_like_control"](
                    TikTokPage([button])
                )
                self.assertIs(got, button)
                self.assertEqual(state, value)

        with self.assertRaisesRegex(RuntimeError, "aria-pressed"):
            env["_video_like_control"](
                TikTokPage([FakeButton(pressed=None)])
            )

        with self.assertRaisesRegex(RuntimeError, "ausente o ambiguo"):
            env["_video_like_control"](TikTokPage([]))

    def test_facebook_external_permalink_is_exact_https_host(self):
        env = load_functions(
            "facebook_interact.py",
            ["_validated_facebook_permalink"],
            {"urlsplit": urllib.parse.urlsplit, "re": re},
        )
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
        valid = "https://www.facebook.com/editorialpage/posts/123"
        self.assertEqual(
            env["_validated_facebook_permalink"](valid),
            valid,
        )
        # PR55: photo/story pueden venir de grupos y no se aceptan como destino de accion.
        with self.assertRaises(ValueError):
            env["_validated_facebook_permalink"]("https://www.facebook.com/photo/?fbid=123")
        pfbid = "https://www.facebook.com/editorialpage/posts/pfbidABC123"
        self.assertEqual(env["_validated_facebook_permalink"](pfbid), pfbid)
        for bad in (
            "http://www.facebook.com/photo/?fbid=123",
            "https://facebook.com.evil.example/photo/?fbid=123",
            "https://evil.example/facebook.com/photo/?fbid=123",
            "https://user:pass@www.facebook.com/photo/?fbid=123",
            "https://www.facebook.com/",
            "https://www.facebook.com/editorialpage",
            "https://www.facebook.com/editorialpage/posts/",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                env["_validated_facebook_permalink"](bad)

    def test_instagram_permalink_is_validated_before_navigation(self):
        env = load_functions(
            "instagram_interact.py",
            ["_validated_post_permalink", "_goto_post"],
            {
                "urllib": urllib,
                "_check_bot_warning": lambda pg: None,
                "_active_handle": lambda pg: "davidportodiaz",
                "MY_HANDLE": "davidportodiaz",
            },
        )

        page = NavPage()
        env["_goto_post"](
            page,
            "https://instagram.com/p/ABC123/?utm_source=test#frag",
        )
        self.assertEqual(
            page.visits,
            ["https://www.instagram.com/p/ABC123/"],
        )

        bad_page = NavPage()
        with self.assertRaises(ValueError):
            env["_goto_post"](
                bad_page,
                "https://instagram.com.evil.example/p/ABC123/",
            )
        self.assertEqual(bad_page.visits, [])


if __name__ == "__main__":
    unittest.main()
