"""Backend movil de Instagram (09/10/2026): lectura pura sobre capturas REALES recortadas de la app (es-ES, 450.0.0.50.77) y adaptador con cliente falso."""
import json
import os
import pathlib
import sys
import tempfile
import types
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
os.environ.setdefault("RRSS_INSTAGRAM_COOLDOWN_PATH", os.path.join(tempfile.mkdtemp(prefix="rrss_test_ig_cd_"), "mobile_cooldown.json"))
import instagram_mobile_interact as im

FIX = pathlib.Path(__file__).parent / "fixtures_instagram_mobile"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def el(ident="", text="", label=None, x=0, y=0, w=100, h=50):
    d = {"type": "android.widget.TextView", "text": text, "identifier": f"com.instagram.android:id/{ident}" if ident else "",
         "rect": {"x": x, "y": y, "width": w, "height": h}}
    if label is not None:
        d["label"] = label
    return d


class ReadProfileTests(unittest.TestCase):
    def test_not_followed_profile(self):
        p = im.read_profile(load("profile_not_followed.json"))
        self.assertEqual(p["handle"], "cuenta_no_seguida")
        self.assertEqual(p["relation"], "not_following")
        self.assertEqual(p["counts"]["followers"], "2.270")
        self.assertFalse(p["is_own"])

    def test_followed_profile(self):
        p = im.read_profile(load("profile_followed.json"))
        self.assertEqual((p["handle"], p["relation"]), ("cuenta_seguida", "following"))

    def test_own_profile_is_recognised_and_has_no_follow_button(self):
        p = im.read_profile(load("profile_own.json"))
        self.assertTrue(p["is_own"])
        self.assertIsNone(p["relation"])
        self.assertEqual(p["counts"]["following"], "86")

    def test_requested_and_follow_back_states(self):
        for text, relation in (("Solicitado", "requested"), ("Seguir también", "follows_me"), ("Following", "following")):
            tree = {"children": [el("action_bar_title", "x", "x"), el("profile_header_follow_button", text, "etiqueta")]}
            self.assertEqual(im.read_profile(tree)["relation"], relation, text)

    def test_unknown_button_text_fails_closed(self):
        tree = {"children": [el("action_bar_title", "x", "x"), el("profile_header_follow_button", "Mensaje")]}
        self.assertIsNone(im.read_profile(tree)["relation"])

    def test_real_private_account_states_from_the_app(self):
        # Capturado en vivo el 09/10: tras seguir a una cuenta privada, texto «Pendiente» / etiqueta «Has solicitado seguir a X»;
        # en otros estados el texto llega vacio y solo la etiqueta identifica la relacion.
        cases = (("Pendiente", "Has solicitado seguir a Nombre", "requested"),
                 ("", "Has solicitado seguir a Nombre", "requested"),
                 ("", "Sigues a @Nombre", "following"),
                 ("", "Seguir a Nombre", "not_following"),
                 ("", "Mensaje", None))
        for text, label, relation in cases:
            tree = {"children": [el("action_bar_title", "x", "x"), el("profile_header_follow_button", text, label)]}
            self.assertEqual(im.read_profile(tree)["relation"], relation, (text, label))


class WarningTests(unittest.TestCase):
    def test_action_blocked_dialog_stops(self):
        tree = {"children": [el("dialog_title", "Acción bloqueada"), el("dialog_body", "Intenta de nuevo más tarde")]}
        with self.assertRaises(im.BotWarningDetected):
            im.check_warning(tree)

    def test_normal_profile_has_no_warning(self):
        im.check_warning(load("profile_not_followed.json"))

    def test_system_notifications_are_ignored(self):
        # Una notificacion del sistema con la palabra "checkpoint" no es un aviso de Instagram (y no debe leerse jamas).
        tree = {"children": [el("", "Notificación de Cualquier app: checkpoint", None)]}
        self.assertEqual(im.visible_text(tree), "")
        im.check_warning(tree)

    def test_status_bar_and_system_ui_are_excluded(self):
        tree = {"children": [el("", "11:35", None), {**el("clock", "11:35"), "identifier": "com.android.systemui:id/clock"}]}
        self.assertNotIn("systemui", str(im.app_elements(tree)))


class FakeClient:
    """Cliente falso: sirve una secuencia de arboles y registra los taps."""

    def __init__(self, trees, package="com.instagram.android"):
        self.trees, self.package, self.taps, self.urls, self.i = list(trees), package, [], [], 0
        self.device = types.SimpleNamespace(id="dev")

    def select_device(self, _):
        return self.device

    def open_url(self, url, device_id=None):
        self.urls.append(url)

    def foreground_app(self, device_id=None):
        return {"packageName": self.package}

    def dump_ui(self, device_id=None):
        tree = self.trees[min(self.i, len(self.trees) - 1)]
        self.i += 1
        return tree

    def tap(self, x, y, device_id=None):
        self.taps.append((x, y))


def adapter(trees, **kw):
    return im.InstagramMobile(FakeClient(trees, **kw), allow_writes=True, sleep=lambda s: None)


def profile_tree(handle, button_text):
    return {"children": [el("action_bar_title", handle, handle), el("profile_header_follow_button", button_text, "x", x=33, y=815, w=292, h=88)]}


class FollowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        im.COOLDOWN_PATH = os.path.join(self.tmp, "cd.json")

    def test_follow_taps_once_and_verifies(self):
        a = adapter([profile_tree("abc", "Seguir"), profile_tree("abc", "Siguiendo")])
        self.assertEqual(a.follow("@ABC"), "followed")
        self.assertEqual(len(a.client.taps), 1)
        self.assertEqual(a.client.urls, ["https://www.instagram.com/abc/"])

    def test_private_account_becomes_pending(self):
        a = adapter([profile_tree("abc", "Seguir"), profile_tree("abc", "Solicitado")])
        self.assertEqual(a.follow("abc"), "pending")

    def test_private_account_after_tap_shows_pendiente(self):
        before = profile_tree("abc", "Seguir")
        after = {"children": [el("action_bar_title", "abc", "abc"),
                              el("profile_header_follow_button", "Pendiente", "Has solicitado seguir a Abc", x=33, y=732, w=1014, h=88)]}
        a = adapter([before, after])
        self.assertEqual(a.follow("abc"), "pending")
        self.assertEqual(len(a.client.taps), 1)

    def test_already_following_never_taps(self):
        a = adapter([profile_tree("abc", "Siguiendo")])
        self.assertEqual(a.follow("abc"), "already")
        self.assertEqual(a.client.taps, [])

    def test_requested_never_taps(self):
        a = adapter([profile_tree("abc", "Solicitado")])
        self.assertEqual(a.follow("abc"), "pending")
        self.assertEqual(a.client.taps, [])

    def test_wrong_profile_is_target_not_found(self):
        a = adapter([profile_tree("otra", "Seguir")])
        with self.assertRaises(im.InstagramTargetNotFound):
            a.follow("abc")
        self.assertEqual(a.client.taps, [])

    def test_unverified_follow_raises_and_does_not_retap(self):
        a = adapter([profile_tree("abc", "Seguir")])      # el boton nunca cambia
        with self.assertRaises(im.InstagramWriteUnverified):
            a.follow("abc")
        self.assertEqual(len(a.client.taps), 1)

    def test_warning_after_tap_stops_everything(self):
        a = adapter([profile_tree("abc", "Seguir"), {"children": [el("dialog_title", "Acción bloqueada")]}])
        with self.assertRaises(im.BotWarningDetected):
            a.follow("abc")

    def test_instagram_not_in_foreground_fails_closed(self):
        a = adapter([profile_tree("abc", "Seguir")], package="com.android.intentresolver")
        with self.assertRaises(im.InstagramMobileError):
            a.follow("abc")
        self.assertEqual(a.client.taps, [])

    def test_read_only_adapter_cannot_write(self):
        a = im.InstagramMobile(FakeClient([profile_tree("abc", "Seguir")]), allow_writes=False, sleep=lambda s: None)
        with self.assertRaises(im.InteractionsPaused):
            a.follow("abc")

    def test_active_cooldown_blocks_before_opening_anything(self):
        import tiktok_safety as safety
        safety.restrict("warning", im.COOLDOWN_PATH)
        a = adapter([profile_tree("abc", "Seguir")])
        with self.assertRaises(im.BotWarningDetected):
            a.follow("abc")
        self.assertEqual(a.client.urls, [])

    def test_cooldown_is_independent_from_tiktok(self):
        import tiktok_safety as safety
        self.assertNotEqual(os.path.abspath(im.COOLDOWN_PATH), os.path.abspath(safety.COOLDOWN_PATH))


class VerifyAccountTests(unittest.TestCase):
    def test_own_account_ok(self):
        a = adapter([load("profile_own.json")])
        self.assertTrue(a.verify_active_account("davidportodiaz"))

    def test_other_account_logged_in_is_wrong_account(self):
        tree = {"children": [el("action_bar_title", "davidportodiaz", "davidportodiaz")]}   # sin "Editar perfil"
        a = adapter([tree])
        with self.assertRaises(im.InstagramWrongAccount):
            a.verify_active_account("davidportodiaz")


class LikeTests(unittest.TestCase):
    def setUp(self):
        im.COOLDOWN_PATH = os.path.join(tempfile.mkdtemp(), "cd.json")

    def post(self, label):
        return {"children": [el("row_feed_button_like", "", label, x=40, y=1500, w=90, h=90)]}

    def test_like_creates_and_verifies(self):
        a = adapter([self.post("Me gusta"), self.post("Ya no me gusta")])
        self.assertEqual(a.like("https://www.instagram.com/p/ABC/"), "created")
        self.assertEqual(len(a.client.taps), 1)

    def test_already_liked_never_taps(self):
        a = adapter([self.post("Ya no me gusta")])
        self.assertEqual(a.like("https://www.instagram.com/p/ABC/"), "already")
        self.assertEqual(a.client.taps, [])

    def test_missing_button_fails_closed(self):
        a = adapter([{"children": []}])
        with self.assertRaises(im.InstagramTargetNotFound):
            a.like("https://www.instagram.com/p/ABC/")

    def test_comment_is_not_available_yet(self):
        a = adapter([{"children": []}])
        with self.assertRaises(im.InstagramMobileError):
            a.comment("https://www.instagram.com/p/ABC/", "hola")


class BackendSelectionTests(unittest.TestCase):
    def test_invalid_backend_is_refused_before_anything_runs(self):
        import subprocess
        root = pathlib.Path(__file__).resolve().parents[1]
        env = {**os.environ, "RRSS_INSTAGRAM_BACKEND": "bogus"}
        out = subprocess.run([sys.executable, str(root / "tools" / "instagram_execute.py"), "no_existe.json"],
                             capture_output=True, text=True, env=env, timeout=60)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("RRSS_INSTAGRAM_BACKEND invalido", out.stdout + out.stderr)

    def test_mobile_backend_exposes_the_executor_api(self):
        for name in ("follow", "like", "comment", "ensure_browser", "release", "fetch_my_metrics", "record_warning",
                     "BotWarningDetected", "AlreadyCommented", "_validated_post_permalink", "_check_length",
                     "_check_spanish_orthography", "_refuse_if_paused", "MY_HANDLE"):
            self.assertTrue(hasattr(im, name), name)


if __name__ == "__main__":
    unittest.main()
