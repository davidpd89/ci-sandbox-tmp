import pathlib
import sys
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import mobile_client as mc
import tiktok_mobile_interact as tm


def el(text=None, *, y=10, checked=None, selected=None, identifier=None):
    item = {
        "rect": {"x": 10, "y": y, "width": 40, "height": 20},
    }
    if text is not None:
        item["text"] = text
    if identifier is not None:
        item["identifier"] = identifier
    if checked is not None:
        item["checked"] = checked
    if selected is not None:
        item["selected"] = selected
    return item


def tree(*elements):
    return {"elements": list(elements)}


class FakeClient:
    def __init__(self, trees=None):
        self.calls = []
        self.trees = list(trees or [tree(el("Para ti"))])
        self.last_tree = self.trees[-1]
        self.device = mc.MobileDevice(
            id="xiaomi", name="Xiaomi", model="Test", platform="android",
            state="online", device_type="real", version="13",
        )
        self.clipboard = ""

    def select_device(self, _device_id=None):
        self.calls.append(("select_device",))
        return self.device

    def apps(self, _device_id=None):
        self.calls.append(("apps",))
        return [{"packageName": "com.zhiliaoapp.musically", "appName": "TikTok"}]

    def launch_app(self, package, _device_id=None):
        self.calls.append(("launch_app", package))
        return {"launched": True}

    def foreground_app(self, _device_id=None):
        self.calls.append(("foreground_app",))
        return {"packageName": "com.zhiliaoapp.musically"}

    def device_info(self, _device_id=None):
        self.calls.append(("device_info",))
        return {"screenSize": {"width": 100, "height": 200, "scale": 1}}

    def dump_ui(self, _device_id=None):
        self.calls.append(("dump_ui",))
        if self.trees:
            self.last_tree = self.trees.pop(0)
        return self.last_tree

    def screenshot_bytes(self, _device_id=None, *, max_size=1200):
        self.calls.append(("screenshot_bytes", max_size))
        return b"png"

    def tap(self, x, y, _device_id=None):
        self.calls.append(("tap", x, y))
        return {"success": True}

    def swipe(self, x1, y1, x2, y2, *, duration_ms=None, device_id=None):
        self.calls.append(("swipe", x1, y1, x2, y2, duration_ms))
        return {"success": True}

    def press(self, button, _device_id=None):
        self.calls.append(("press", button))
        return {"success": True}

    def type_text(self, text_value, _device_id=None):
        self.calls.append(("type_text", text_value))
        return {"success": True}

    def open_url(self, url, _device_id=None):
        self.calls.append(("open_url", url))
        return {"success": True}

    def clipboard_set(self, value, _device_id=None):
        self.calls.append(("clipboard_set", value))
        self.clipboard = value
        return {"success": True}

    def clipboard_get(self, _device_id=None):
        self.calls.append(("clipboard_get",))
        return self.clipboard


class TikTokMobileTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("time.sleep")
        patcher.start()
        self.addCleanup(patcher.stop)
        # return_to_feed consulta adb/IME reales: en los tests el feed se da por alcanzado.
        nav_patch = mock.patch("tiktok_mobile_nav.TikTokNavigator.return_to_feed", lambda self: None)
        nav_patch.start()
        self.addCleanup(nav_patch.stop)

    def test_probe_discovers_package_and_reads_ui(self):
        client = FakeClient([tree(el("Para ti"))])
        adapter = tm.TikTokMobileAdapter(client)
        result = adapter.readonly_probe(settle_seconds=0)
        self.assertEqual(result["package"], "com.zhiliaoapp.musically")
        self.assertEqual(result["screenshot_bytes"], 3)

    def test_challenge_stops_probe(self):
        client = FakeClient([tree(el("Verifica que eres humano"))])
        adapter = tm.TikTokMobileAdapter(client)
        with self.assertRaises(tm.TikTokMobileChallenge):
            adapter.readonly_probe(settle_seconds=0)

    def test_fullscreen_leaf_tree_is_rejected(self):
        client = FakeClient([
            {"elements": [{
                "text": "overlay",
                "rect": {"x": 0, "y": 0, "width": 100, "height": 200},
            }]}
        ])
        adapter = tm.TikTokMobileAdapter(client)
        with self.assertRaisesRegex(mc.MobileCliError, "colapsado"):
            adapter.readonly_probe(settle_seconds=0)

    def test_default_adapter_refuses_writes_before_navigation(self):
        client = FakeClient()
        adapter = tm.TikTokMobileAdapter(client)
        before = list(client.calls)
        for action, args in (
            (adapter.follow, ("foo",)),
            (adapter.like, ("https://www.tiktok.com/@foo/video/1",)),
            (adapter.comment, ("https://www.tiktok.com/@foo/video/1", "hola")),
        ):
            with self.subTest(action=action.__name__):
                with self.assertRaises(tm.TikTokMobilePaused):
                    action(*args)
        self.assertEqual(client.calls, before)

    def test_open_surface_returns_to_home_after_profile_state(self):
        client = FakeClient([
            tree(el("Inicio", y=170)),
            tree(el("Para ti", y=20)),
            tree(el("Para ti", y=20), el("Siguiendo", y=20), el("@lectora", y=70)),
        ])
        adapter = tm.TikTokMobileAdapter(client)
        adapter.open_surface("for_you")
        taps = [call for call in client.calls if call[0] == "tap"]
        self.assertEqual(len(taps), 2)

    def test_open_surface_stops_if_banner_hijacked_tap(self):
        client = FakeClient([
            tree(el("Inicio", y=170)),
            tree(el("Para ti", y=20)),
            tree(el("Mensajes", y=170)),  # el tap abrió otra pantalla
        ])
        adapter = tm.TikTokMobileAdapter(client)
        with self.assertRaises(tm.TikTokTargetNotFound):
            adapter.open_surface("for_you")

    def test_foreign_package_nodes_are_not_targets_or_content(self):
        nav = el("Inicio", y=170, identifier="com.android.systemui:id/home")
        own = el("Inicio", y=170, identifier="com.zhiliaoapp.musically:id/omq")
        found = tm._semantic_matches(tree(nav, own), tm.ALIASES["home"])
        self.assertEqual(found, [own])
        notif = el("Notificación de LinkedIn: empleos nuevos", identifier="com.android.systemui:id/x")
        self.assertNotIn("LinkedIn", tm._visible_text(tree(notif)))

    def test_snapshot_flags_ads_and_ignores_toasts(self):
        client = FakeClient([tree(
            el("Sugerencia de promoción", y=50), el("@autor", y=60),
            el("Notificación de LinkedIn: nuevos empleos publicados hoy", y=5),
            el("Un caption normal sobre libros", y=80),
        )])
        snap = tm.TikTokMobileAdapter(client).current_post_snapshot(source="for_you")
        self.assertTrue(snap["is_ad"])
        self.assertNotIn("LinkedIn", snap["caption"])

    def test_resolve_author_handle_reads_profile_and_returns_to_feed(self):
        avatar = el("Perfil de Ana", y=100, identifier="com.zhiliaoapp.musically:id/user_avatar")
        feed = tree(avatar, el("Para ti", y=10), el("Siguiendo", y=10))
        profile = tree(el("@ana_libros", y=20), el("Bio con @otra_persona", y=40))
        client = FakeClient([feed, profile, feed])
        self.assertEqual(tm.TikTokMobileAdapter(client).resolve_author_handle(), "ana_libros")
        self.assertIn(("press", "BACK"), [c[:2] for c in client.calls])

    def test_send_button_found_by_geometry_when_icon_has_no_label(self):
        def at(text, x, y, w, h, kind):
            return {"text": text, "type": kind, "rect": {"x": x, "y": y, "width": w, "height": h}}
        t = tree(
            at("a", 199, 1259, 809, 142, "EditText"),
            at("@2131823358", 17, 1459, 121, 99, "Button"),   # menciones
            at("@2131823407", 904, 1459, 143, 88, "Button"),  # enviar (icono)
        )
        # las menciones están a la izquierda (x<800): solo queda el enviar
        self.assertEqual(tm._find_send_button(t)["rect"]["x"], 904)

    def test_send_button_ignores_comment_like_buttons_below(self):
        def at(text, x, y, w, h, kind):
            return {"text": text, "type": kind, "rect": {"x": x, "y": y, "width": w, "height": h}}
        t = tree(
            at("Qué buena pinta", 199, 1259, 809, 142, "EditText"),
            at("@2131823407", 904, 1459, 143, 88, "Button"),   # enviar
            at("@2131823403", 803, 1547, 161, 66, "Button"),   # like de un comentario
            at("@2131823401", 964, 1547, 110, 66, "Button"),   # no me gusta de un comentario
        )
        self.assertEqual(tm._find_send_button(t)["rect"]["y"], 1459)

    def test_comment_box_prefers_topmost_when_two(self):
        def box(y):
            return {"text": "Añadir comentario...", "type": "EditText",
                    "rect": {"x": 199, "y": y, "width": 505, "height": 86}}
        self.assertEqual(tm._find_comment_box(tree(box(2126), box(1259)))["rect"]["y"], 1259)

    def test_comment_box_matches_real_placeholder_with_dots(self):
        box = {"text": "Añadir comentario...", "type": "EditText",
               "rect": {"x": 199, "y": 2126, "width": 505, "height": 86}}
        self.assertIs(tm._find_comment_box(tree(box)), box)
        with self.assertRaises(tm.TikTokTargetNotFound):
            tm._find_comment_box(tree())

    def test_main_video_band_drops_next_video_controls(self):
        main = {"rect": {"x": 904, "y": 1213, "width": 176, "height": 165}}
        nxt = {"rect": {"x": 904, "y": 1981, "width": 176, "height": 154}}
        info = {"screenSize": {"width": 1080, "height": 2400}}
        self.assertEqual(tm._in_main_video_band([main, nxt], info), [main])

    def test_liked_video_label_is_recognised_as_already_liked(self):
        client = FakeClient([
            tree(el("inicio")),
            tree(el("Vídeo con me gusta")),
            tree(el("Vídeo con me gusta")),
        ])
        adapter = tm.TikTokMobileAdapter(client, allow_writes=True)
        self.assertEqual(adapter.like("https://vm.tiktok.com/ZN8kYpVrG/"), "already")
        self.assertFalse(any(c[0] == "tap" for c in client.calls))

    def test_pick_unique_collapses_container_and_child_label(self):
        outer = {"rect": {"x": 0, "y": 150, "width": 50, "height": 40}, "label": "Perfil"}
        inner = {"rect": {"x": 0, "y": 170, "width": 50, "height": 20}, "text": "Perfil"}
        picked = tm._pick_unique(tree(outer, inner), tm.ALIASES["profile"], description="Perfil")
        self.assertIs(picked, outer)
    def test_verify_active_account_uses_profile_and_exact_handle(self):
        client = FakeClient([
            tree(el("Perfil", y=170)),
<<<<<<< HEAD
            tree(el("@autorademoescritor")),
=======
            tree(el("@davidportoescritor")),
>>>>>>> origin/research/public-reuse-parent
        ])
        adapter = tm.TikTokMobileAdapter(client)
        self.assertTrue(adapter.verify_active_account())
        self.assertTrue(any(call[0] == "tap" for call in client.calls))

    def test_wrong_account_is_terminal(self):
        client = FakeClient([
            tree(el("Perfil", y=170)),
            tree(el("@otra_cuenta")),
        ])
        adapter = tm.TikTokMobileAdapter(client)
        with self.assertRaises(tm.TikTokWrongAccount):
            adapter.verify_active_account()

    @staticmethod
    def _profile(relation, handle="autor"):
        def at(text, x, y, w, h, kind="TextView"):
            return {"text": text, "type": kind, "rect": {"x": x, "y": y, "width": w, "height": h}}
        return tree(
            at("@" + handle, 44, 356, 294, 41, "Button"),
            at("12", 44, 429, 147, 61),
            at("Siguiendo", 44, 487, 147, 41),  # contador, no es el control
            at(relation, 44, 572, 419, 110),
        )

    def test_follow_uses_relation_control_not_following_counter(self):
        client = FakeClient([
            tree(el("inicio")),
            self._profile("Seguir"),
            self._profile("Seguir"),   # relectura fresca tras el hojeo
            self._profile("Siguiendo"),
        ])
        adapter = tm.TikTokMobileAdapter(client, allow_writes=True)
        self.assertEqual(adapter.follow("autor"), "followed")
        taps = [c for c in client.calls if c[0] == "tap"]
        self.assertEqual(len(taps), 1)
        self.assertGreater(taps[0][2], 560)  # pulsó el control, no el contador (y=487)

    def test_follow_refuses_when_profile_handle_differs(self):
        client = FakeClient([tree(el("inicio")), self._profile("Seguir", handle="otra")])
        adapter = tm.TikTokMobileAdapter(client, allow_writes=True)
        with self.assertRaises(tm.TikTokTargetNotFound):
            adapter.follow("autor")
        self.assertFalse(any(c[0] == "tap" for c in client.calls))

    def test_follow_already_following_does_not_tap(self):
        client = FakeClient([tree(el("inicio")), self._profile("Siguiendo")])
        adapter = tm.TikTokMobileAdapter(client, allow_writes=True)
        self.assertEqual(adapter.follow("autor"), "already")
        self.assertFalse(any(c[0] == "tap" for c in client.calls))

    def test_follow_unverified_when_state_does_not_change(self):
        client = FakeClient([
            tree(el("inicio")), self._profile("Seguir"), self._profile("Seguir"), self._profile("Seguir"),
        ])
        adapter = tm.TikTokMobileAdapter(client, allow_writes=True)
        with self.assertRaises(tm.TikTokWriteUnverified):
            adapter.follow("autor")

    def test_like_never_toggles_when_already_selected(self):
        client = FakeClient([
            tree(el("Quitar Me gusta", selected=True)),
            tree(el("Quitar Me gusta", selected=True)),
        ])
        adapter = tm.TikTokMobileAdapter(client, allow_writes=True)
        before_taps = sum(call[0] == "tap" for call in client.calls)
        self.assertEqual(
            adapter.like("https://www.tiktok.com/@foo/video/1"), "already"
        )
        after_taps = sum(call[0] == "tap" for call in client.calls)
        self.assertEqual(before_taps, after_taps)

    def test_like_requires_post_write_confirmation(self):
        caption = "Hoy comparto la portada de mi nueva novela de fantasía juvenil"
        client = FakeClient([
            tree(el("Me gusta")),
            tree(el("Me gusta"), el(caption)),
            tree(el("Quitar Me gusta", selected=True)),
        ])
        adapter = tm.TikTokMobileAdapter(client, allow_writes=True)
        self.assertEqual(
            adapter.like("https://www.tiktok.com/@foo/video/1"), "created"
        )

    def test_image_only_video_does_not_receive_like(self):
        client = FakeClient([
            tree(el("Me gusta")),
            tree(el("Me gusta")),
        ])
        adapter = tm.TikTokMobileAdapter(client, allow_writes=True)
        with self.assertRaises(tm.TikTokTargetNotFound):
            adapter.like("https://www.tiktok.com/@foo/video/123")
        self.assertFalse(any(call[0] == "tap" for call in client.calls))

    def test_copy_link_validates_clipboard(self):
        client = FakeClient([
            tree(el("Compartir")),
            tree(el("Copiar enlace")),
        ])
        client.clipboard = "https://www.tiktok.com/@foo/video/1"
        adapter = tm.TikTokMobileAdapter(client)
        # clipboard_set("") ocurre antes de get; simular que TikTok escribió el link al tap.
        original_tap = client.tap
        def tap(x, y, device=None):
            result = original_tap(x, y, device)
            if sum(call[0] == "tap" for call in client.calls) >= 2:
                client.clipboard = "https://www.tiktok.com/@foo/video/1"
            return result
        client.tap = tap
        self.assertIn("tiktok.com", adapter.copy_current_post_url())

    def test_unknown_tiktok_package_fails(self):
        client = FakeClient()
        client.apps = lambda _device_id=None: [{"packageName": "com.example"}]
        with self.assertRaises(mc.MobileCliError):
            tm.TikTokMobileAdapter(client)


if __name__ == "__main__":
    unittest.main()
