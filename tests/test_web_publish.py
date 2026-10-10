"""Publicacion por web (06/10): partes puras de Pinterest y de la lectura de fichas; sin navegador."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import content_queue as cq
import content_queue_alert as cqa
import pinterest_publish as pp


class PinterestTests(unittest.TestCase):
    def test_board_slug_matches_pinterest_urls(self):
        self.assertEqual(pp.board_slug("Fantasía juvenil española"), "fantas%C3%ADa-juvenil-espa%C3%B1ola")
        self.assertEqual(pp.board_slug("Lugares literarios, bibliotecas y librerías"), "lugares-literarios-bibliotecas-y-librer%C3%ADas")
        self.assertEqual(pp.board_slug("Lecturas y reseñas de libros"), "lecturas-y-rese%C3%B1as-de-libros")
        self.assertEqual(pp.board_slug("Recursos para escritores"), "recursos-para-escritores")

    def test_limits_are_checked_before_touching_the_browser(self):
        with self.assertRaises(pp.PinterestPublishError):
            pp.publish_pin("no-existe.png", "t" * 101, "d", "https://x", "alt", "Tablero")
        with self.assertRaises(pp.PinterestPublishError):
            pp.publish_pin("no-existe.png", "titulo", "d", "https://x", "alt", "Tablero")


class FichaParsingTests(unittest.TestCase):
    def test_meta_and_title_are_read_from_the_ficha(self):
        text = """# PIN - X

**Estado:** lista.

- **Tablero:** `Recursos para escritores`.
- **Enlace:** https://autorademodiaz.com/x/
- **Etiqueta del enlace de perfil:** `Premios`.

## Título

Cómo comprobar datos

## Descripción

Método para investigar.
"""
        self.assertEqual(cq._parse_meta(text)["tablero"], "Recursos para escritores")
        self.assertEqual(cq._parse_meta(text)["enlace"], "https://autorademodiaz.com/x/")
        self.assertEqual(cq._parse_meta(text)["etiqueta del enlace de perfil"], "Premios")
        self.assertEqual(cq._parse_titulo(text), "Cómo comprobar datos")

    def test_pinterest_is_verified_by_title_and_alt_too(self):
        item = {"red": "pinterest", "texto": "Método para investigar", "titulo": "Cómo comprobar datos", "alt": "Guía visual"}
        self.assertEqual(cqa.verify_values(item), ["Método para investigar", "Cómo comprobar datos", "Guía visual"])
        self.assertEqual(cqa.verify_values({"red": "bluesky", "texto": "hola", "titulo": "x"}), ["hola"])


if __name__ == "__main__":
    unittest.main()
