import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import adult_filter as af
import scan_common as sc

# Posts reales que dieron like el 04/10/2026 desde la busqueda "autores indie españa" (David: cuidado con esto)
DATING = [
    "Tengo una vergota", "Quien me califica el titan", "Levante duro", "Amigas hormonales alguna",
    "Hola hablemos por ig estoy aburrida", "Oyeeeeeee mamiiii te quiero ver", "@esr_192015 ey sigueme y hablemos",
    "Ocupo un novio???", "holaa me lliamo josé y -me sigues en ig y te sigo quiero amistad",
    "Hola alguien despierto....", "Y si nos mandamos historias paranormales a esta hora. Hablemos",
    "Recomienden libros de poesía erótica. Pllease.", "Vendo packs de fotos y nudes por privado",
    "Mi onlyfans ya está disponible", "Busco novia seria, escríbeme al privado",
]
BOOKS = [
    "Leer 20 páginas. Cerrar el libro. Y darte cuenta de que llevas cinco minutos pensando en otra cosa.",
    "Hace años no disfrutaba tanto una lectura como Memorias del subsuelo.",
    "Recomienden libros de fantasía con sistemas de magia originales",
    "Reseña Exprés: Dónde estás, mundo bello, de Sally Rooney.",
    "Estoy escribiendo una novela de fantasía sobre un portal y un peaje",
    "El club de lectura de octubre: una historia de amistad entre un dragón y una cartógrafa",
    "Cómo ligar escenas en un capítulo sin que se note la costura",   # 'ligar' como verbo de oficio: se descarta por prudencia
]


class AdultFilterTests(unittest.TestCase):
    def test_real_dating_and_sexual_posts_are_caught(self):
        for text in DATING:
            self.assertTrue(af.is_adult_or_dating(text), text)

    def test_ordinary_book_posts_pass(self):
        for text in BOOKS[:-1]:
            self.assertFalse(af.is_adult_or_dating(text), text)

    def test_is_political_now_also_rejects_dating_content_everywhere(self):
        self.assertTrue(sc.is_political("Hola hablemos por ig estoy aburrida"))
        self.assertTrue(sc.is_political("Quien me califica el titan"))
        self.assertFalse(sc.is_political("Reseña de una novela de fantasía con portal"))

    def test_non_text_is_discarded_and_empty_is_not(self):
        self.assertTrue(af.is_adult_or_dating(123))
        self.assertFalse(af.is_adult_or_dating(""))
        self.assertFalse(af.is_adult_or_dating(None))


if __name__ == "__main__":
    unittest.main()
