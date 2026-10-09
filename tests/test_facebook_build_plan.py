import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import facebook_build_plan as fp


def c(autor, text, n=1):
    return {"autor": autor, "text": text, "permalink": f"https://www.facebook.com/photo/?fbid={n}", "tag": "t"}


class BuildTests(unittest.TestCase):
    def test_keeps_niche_posts_and_drops_institutions_politics_spam_and_duplicates(self):
        cands = [
            c("Buendía Estudios", "Nueva novela fantástica de nuestra colección", 1),
            c("Dirección General del Libro", "Convocatoria de ayudas a la edición", 2),
            c("Guardia Civil", "Nuestros libros y lectura", 3),
            c("Ediciones Minotauro", "La saga de fantasía vuelve en edición especial", 4),
            c("Ediciones Minotauro", "Otro post de la misma editorial sobre libros", 5),
            c("Club Lector", "Carpeta de 250 libros pdf gratis drive.google.com/x", 6),
            c("Libros Amazon", "Los mejores libros booktok con descuento en Amazon", 8),
            c("Tienda de Muebles", "Oferta de sofás y mesas", 7),
        ]
        plan = fp.build(cands)
        self.assertEqual([p["autor"] for p in plan], ["Buendía Estudios", "Ediciones Minotauro"])
        self.assertTrue(all(p["kind"] == "like_external" for p in plan))

    def test_cap(self):
        cands = [c(f"Autor {i}", "Reseña de una novela", i) for i in range(30)]
        self.assertEqual(len(fp.build(cands, 12)), 12)


if __name__ == "__main__":
    unittest.main()
