import pathlib
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import tiktok_mobile_nav as nav


def at(text, x, y, w=200, h=50, kind="TextView"):
    return {"text": text, "type": kind, "rect": {"x": x, "y": y, "width": w, "height": h}}


def tree(*elements):
    return {"elements": list(elements)}


class CountTests(unittest.TestCase):
    def test_parse_count_spanish_suffixes(self):
        self.assertEqual(nav.parse_count("41,7\xa0mil seguidores"), 41700)
        self.assertEqual(nav.parse_count("5,5\xa0mill. me gusta"), 5_500_000)
        self.assertEqual(nav.parse_count("1307 seguidores"), 1307)
        self.assertEqual(nav.parse_count("1,2 M"), 1_200_000)
        self.assertEqual(nav.parse_count("2.5K"), 2500)
        self.assertIsNone(nav.parse_count("sin cifras"))


class UserRowTests(unittest.TestCase):
    def rows(self):
        return nav.parse_user_rows(tree(
            at("‎⁨bookktok⁩", 236, 399, 300, 52),
            at("🌱🌿", 236, 451, 500, 44),
            at("41,7\xa0mil seguidores · 443,1\xa0mil me gusta", 236, 495, 500, 44),
            at("Seguir", 794, 423, 242, 88, "Button"),
            at("‎⁨mariabookss_1⁩", 236, 1406, 278, 52),
            at("Booktoker", 236, 1458, 448, 44),
            at("Es amigo/a de Letras Para Todos", 236, 1513, 382, 44),
            at("Seguir también", 717, 1438, 319, 88, "Button"),
            at("‎⁨ya_seguida⁩", 236, 1700, 278, 52),
            at("Siguiendo", 794, 1724, 242, 88, "Button"),
        ))

    def test_rows_extract_handle_stats_and_relation(self):
        rows = {r["handle"]: r for r in self.rows()}
        self.assertEqual(rows["bookktok"]["followers"], 41700)
        self.assertEqual(rows["bookktok"]["likes"], 443100)
        self.assertEqual(rows["bookktok"]["relation"], "not_following")
        self.assertEqual(rows["mariabookss_1"]["relation"], "follows_me")
        self.assertIn("Letras Para Todos", rows["mariabookss_1"]["proof"])
        self.assertEqual(rows["ya_seguida"]["relation"], "following")

    def test_display_name_is_not_mistaken_for_handle(self):
        handles = [r["handle"] for r in self.rows()]
        self.assertNotIn("Booktoker", handles)


class ProfileTests(unittest.TestCase):
    def test_profile_reads_badge_handle_counts_and_relation_by_width(self):
        t = tree(
            at("Editorial Planeta", 44, 251, 639, 99, "Button"),
            at("@editorialplaneta￼", 44, 356, 294, 41, "Button"),
            at("56", 44, 429, 147, 61), at("Siguiendo", 44, 487, 147, 41),
            at("81,5\xa0mil", 257, 429, 160, 58), at("Seguidores", 257, 487, 167, 41),
            at("967,5\xa0mil", 490, 429, 186, 61), at("Me gusta", 490, 487, 186, 41),
            at("Siguiendo", 640, 572, 220, 110),
        )

        class FakeAdapter:
            def __init__(self):
                self.client = self.device = None

            def _tree(self, validate_shape=False):
                return t

        info = nav.TikTokNavigator.__new__(nav.TikTokNavigator)
        info.a = FakeAdapter()
        info.c = info.device = None
        profile = info.read_profile()
        self.assertEqual(profile["handle"], "editorialplaneta")
        self.assertEqual(profile["followers"], 81500)
        self.assertEqual(profile["following"], 56)
        self.assertEqual(profile["relation"], "following")  # no el contador


class SafetyTests(unittest.TestCase):
    def test_denylist_blocks_money_and_permission_controls(self):
        for label in ("Promocionar", "Regalo", "Monedas", "Sincronizar contactos", "Tienda"):
            self.assertTrue(nav._is_denied([label]), label)
        self.assertFalse(nav._is_denied(["Seguir"]))



class KeyboardSafetyTests(unittest.TestCase):
    def test_return_to_feed_never_taps_home_while_keyboard_is_shown(self):
        class Dev:
            id = "x"

        class Client:
            def __init__(self):
                self.calls = []

            def press(self, button, device_id=None):
                self.calls.append(("press", button))

            def tap(self, x, y, device_id=None):
                self.calls.append(("tap", x, y))

            def _rpc(self, method, params):
                self.calls.append((method,))

            def _device(self, device_id):
                return "x"

        keyboard_open = tree(at("Añadir comentario...", 199, 1259, 809, 142, "EditText"),
                             at("Inicio", 0, 2135, 216, 135, "FrameLayout"))
        feed = tree(at("Para ti", 768, 93, 158, 160), at("Siguiendo", 377, 93, 226, 159))
        state = {"open": True}

        class Adapter:
            client = Client()
            device = Dev()

            def _tree(self, validate_shape=False):
                return keyboard_open if state["open"] else feed

            def _discard_draft(self):
                state["open"] = False
                self.client.calls.append(("discard",))

        navigator = nav.TikTokNavigator.__new__(nav.TikTokNavigator)
        navigator.a, navigator.c, navigator.device = Adapter(), Adapter.client, Dev()
        from unittest import mock
        with mock.patch.object(nav.android_shell, "keyboard_shown", lambda *a, **k: state["open"]):
            navigator.return_to_feed()
        self.assertIn(("discard",), Adapter.client.calls)
        self.assertFalse(any(c[0] == "tap" for c in Adapter.client.calls))


if __name__ == "__main__":
    unittest.main()
