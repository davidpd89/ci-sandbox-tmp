"""Contrato offline de la subida web: bytes reales, sin Pinterest ni credenciales."""
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import pinterest_media_guard as guard


class PinterestImageContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / "pin.png"

    def image(self, width=100, height=150, fmt="PNG"):
        Image.new("RGB", (width, height)).save(self.path, format=fmt)
        return self.path

    def test_real_valid_png_reports_measured_bytes_and_ratio(self):
        path = self.image()
        info = guard.validate_web_pin_image(path)
        self.assertEqual((info["width"], info["height"], info["format"]),
                         (100, 150, "PNG"))
        self.assertEqual(info["bytes"], path.stat().st_size)
        self.assertTrue(info["aspect_2_3"])

    def test_landscape_is_allowed_not_misrepresented_as_2_3(self):
        self.assertFalse(guard.validate_web_pin_image(self.image(150, 100))["aspect_2_3"])

    def test_content_signature_not_filename_controls_format(self):
        self.path.write_bytes(b"a" * 100)
        with self.assertRaisesRegex(guard.PinPreflightError, "ilegible"):
            guard.validate_web_pin_image(self.path)
        self.image(fmt="PNG")
        self.path.write_bytes(self.path.read_bytes()[:20])
        with self.assertRaises(guard.PinPreflightError):
            guard.validate_web_pin_image(self.path)

    def test_jpeg_truncation_cannot_pass_structural_verify(self):
        # Contrato real: Image.verify() deja pasar este JPEG sin marcador
        # terminal, pero Image.load() lo rechaza.
        self.image(fmt="JPEG")
        original = self.path.read_bytes()
        self.path.write_bytes(original[:-2])
        with Image.open(self.path) as structure:
            structure.verify()  # reproducimos el falso positivo anterior
        with self.assertRaisesRegex(guard.PinPreflightError, "ilegible"):
            guard.validate_web_pin_image(self.path)

    def test_gif_not_in_static_web_contract(self):
        with self.assertRaisesRegex(guard.PinPreflightError, "tipo no admitido"):
            guard.validate_web_pin_image(self.image(fmt="GIF"))

    def test_max_file_size_checked_before_image_decoder(self):
        with self.path.open("wb") as f:
            f.truncate(guard.MAX_WEB_IMAGE_BYTES + 1)
        with patch.object(guard.Image, "open") as opened:
            with self.assertRaisesRegex(guard.PinPreflightError, "20 MB"):
                guard.validate_web_pin_image(self.path)
            opened.assert_not_called()

    def test_missing_empty_and_invalid_paths(self):
        for path in (None, "", self.path):
            with self.subTest(path=str(path)), self.assertRaises(guard.PinPreflightError):
                guard.validate_web_pin_image(path)
        self.path.touch()
        with self.assertRaises(guard.PinPreflightError):
            guard.validate_web_pin_image(self.path)

    def test_field_contract_and_https_links(self):
        good = ("Una novela", "Una descripción útil", "https://example.org/guia/?utm_source=pinterest", "Libro sobre mesa")
        guard.validate_web_pin_fields(*good)
        for idx, bad in [(0, ""), (0, "x" * 101), (1, ""), (1, "x" * 801),
                         (2, "http://example.org/guia"), (2, "https://user:pass@example.org/"),
                         (2, "https://example.org:444/"), (2, "https://[host/"),
                         (2, "https://example.org/\nsecret"), (3, "")]:
            with self.subTest(index=idx, bad=bad[:35]):
                args = list(good)
                args[idx] = bad
                with self.assertRaises(guard.PinPreflightError):
                    guard.validate_web_pin_fields(*args)


class PinterestPublisherWiringTests(unittest.TestCase):
    """Integra con el publicador real: nunca crea navegador en dry-run."""

    def setUp(self):
        import pinterest_publish as publisher
        self.publisher = publisher
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = pathlib.Path(self.tmp.name) / "pin.png"
        Image.new("RGB", (100, 150)).save(self.path)
        self.valid = (str(self.path), "Título de prueba", "Descripción de prueba",
                      "https://example.org/cuaderno/articulo/", "Libro sobre mesa",
                      self.publisher.KNOWN_BOARDS[0])

    def test_valid_dry_run_does_not_connect_to_browser(self):
        events = []
        with patch.object(self.publisher, "sync_playwright", side_effect=AssertionError("browser opened")):
            out = self.publisher.publish_pin(*self.valid, apply=False, log=events.append)
        self.assertEqual(out, "ensayo")
        self.assertTrue(any("100x150" in e and "PNG" in e for e in events))

    def test_bad_image_or_link_fails_before_browser_even_with_apply(self):
        self.path.write_text("not an image", encoding="utf-8")
        with patch.object(self.publisher, "sync_playwright", side_effect=AssertionError("browser opened")):
            with self.assertRaisesRegex(self.publisher.PinterestPublishError, "imagen"):
                self.publisher.publish_pin(*self.valid, apply=True)
        Image.new("RGB", (100, 150)).save(self.path)
        args = list(self.valid)
        args[3] = "http://example.org/pin"
        with patch.object(self.publisher, "sync_playwright", side_effect=AssertionError("browser opened")):
            with self.assertRaisesRegex(self.publisher.PinterestPublishError, "enlace"):
                self.publisher.publish_pin(*args, apply=True)

    def test_oversize_image_is_rejected_without_decoding_or_browser(self):
        with self.path.open("wb") as stream:
            stream.truncate(guard.MAX_WEB_IMAGE_BYTES + 1)
        with patch.object(self.publisher, "sync_playwright", side_effect=AssertionError("browser opened")):
            with self.assertRaisesRegex(self.publisher.PinterestPublishError, "20 MB"):
                self.publisher.publish_pin(*self.valid, apply=True)


if __name__ == "__main__":
    unittest.main()
