import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import x_interact as x


class OrthographyIgnoresUrlSlugsTest(unittest.TestCase):
    def test_slug_sin_ene_en_enlace_no_bloquea(self):
        x._check_spanish_orthography("Una guía para elegir portal fantasy.\nhttps://autorademodiaz.com/recomendaciones/portal-fantasy-espanol/")
        x._check_spanish_orthography("Fantasía juvenil: https://autorademodiaz.com/cuaderno/libros-fantasia-juvenil-espanola-2025-2026/")

    def test_ene_perdida_en_el_texto_sigue_bloqueando(self):
        with self.assertRaises(ValueError):
            x._check_spanish_orthography("Fantasia espanol para este otono https://autorademodiaz.com/x")


if __name__ == "__main__":
    unittest.main()
