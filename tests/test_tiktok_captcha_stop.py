import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import tiktok_interact as tt


class FakePage:
    def __init__(self, visible_captcha=False, body="", broken=False):
        self.visible_captcha, self.body, self.broken = visible_captcha, body, broken

    def evaluate(self, js):
        if self.broken:
            raise RuntimeError("pagina cerrada")
        return self.visible_captcha

    def locator(self, selector):
        class Empty:
            def count(self_inner):
                return 0
        return Empty()

    def inner_text(self, selector):
        return self.body


class CaptchaStopTests(unittest.TestCase):
    def test_visible_captcha_stops_before_anything_else(self):
        with self.assertRaises(tt.BotWarningDetected):
            tt._check_bot_warning(FakePage(visible_captcha=True))

    def test_new_rotate_image_wording_is_caught_even_without_a_visible_container(self):
        with self.assertRaises(tt.BotWarningDetected):
            tt._check_bot_warning(FakePage(body="Verificación de seguridad. Gira la imagen hasta que encaje"))

    def test_unreadable_page_is_treated_as_captcha(self):
        self.assertTrue(tt.captcha_visible(FakePage(broken=True)))

    def test_normal_page_passes(self):
        tt._check_bot_warning(FakePage(body="Siguiendo 1214 Seguidores 905"))

    def test_the_js_only_counts_visible_boxes(self):
        # los elementos 'captcha' ocultos existen en paginas normales: el JS exige tamano real y visibilidad
        for needle in ("getBoundingClientRect", "display !== 'none'", "visibility !== 'hidden'", "r.width >= 120"):
            self.assertIn(needle, tt._CAPTCHA_VISIBLE_JS)


if __name__ == "__main__":
    unittest.main()
