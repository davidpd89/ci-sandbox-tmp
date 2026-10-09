"""Regresión offline: proporción visible de JPEG con EXIF, sin upload ni red."""
import pathlib
import sys
import tempfile
import unittest
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from pinterest_media_guard import validate_web_pin_image


class PinterestOrientationTests(unittest.TestCase):
    def test_exif_orientation_is_informational_and_visual_ratio_correct(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = pathlib.Path(tmp) / "photo.jpg"
            for orientation, swapped in ((1, False), (3, False), (5, True),
                                         (6, True), (7, True), (8, True)):
                with self.subTest(orientation=orientation):
                    im = Image.new("RGB", (150, 100))
                    exif = Image.Exif()
                    exif[274] = orientation
                    im.save(image_path, "JPEG", exif=exif)
                    result = validate_web_pin_image(image_path)
                    self.assertEqual((result["pixel_width"], result["pixel_height"]),
                                     (150, 100))
                    self.assertEqual(result["exif_orientation"], orientation)
                    self.assertEqual((result["width"], result["height"]),
                                     (100, 150) if swapped else (150, 100))
                    self.assertEqual(result["aspect_2_3"], swapped)

    def test_image_without_exif_remains_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = pathlib.Path(tmp) / "ordinary.png"
            Image.new("RGB", (100, 150)).save(image_path)
            result = validate_web_pin_image(image_path)
            self.assertEqual((result["width"], result["height"]), (100, 150))
            self.assertEqual((result["pixel_width"], result["pixel_height"]), (100, 150))
            self.assertTrue(result["aspect_2_3"])



class PinterestMetadataTypeTests(unittest.TestCase):
    """Los inputs de una ficha malformada nunca pueden lanzar TypeError ni abrir CDP."""

    def test_invalid_types_are_rejected_by_publisher_before_browser(self):
        from unittest.mock import patch
        import pinterest_publish as publisher
        with tempfile.TemporaryDirectory() as tmp:
            image_path = pathlib.Path(tmp) / "good.png"
            Image.new("RGB", (100, 150)).save(image_path)
            good = [str(image_path), "Título", "Descripción",
                    "https://example.org/recursos", "Alt de imagen",
                    publisher.KNOWN_BOARDS[0]]
            for position, value in ((1, None), (2, None), (4, None),
                                    (1, 123), (2, 123), (5, 456),
                                    (1, "x" * 101), (2, "x" * 801)):
                with self.subTest(position=position, invalid_type=type(value).__name__):
                    args = good.copy()
                    args[position] = value
                    with patch.object(publisher, "sync_playwright",
                                      side_effect=AssertionError("nunca abrir navegador")):
                        with self.assertRaises(publisher.PinterestPublishError):
                            publisher.publish_pin(*args, apply=True)

if __name__ == "__main__":
    unittest.main()
