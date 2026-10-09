import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import scan_common as sc

TEMPLATED = [  # replies reales del 03-04/10: casi todas "afirmacion sentenciosa. ¿Pregunta?"
    "Los librojuegos tenían algo que casi ningún libro consigue: te hacían dueño del camino. ¿Cuál has releído más veces?",
    "Ginzburg parece sencilla y te deja sin aire. ¿Qué frase te quedó más grabada?",
    "The Book Eaters tiene una premisa que no se olvida. ¿Es de las que esperan en la pila por algo concreto?",
    "Un club nuevo y con gusto por la fantasía es un buen comienzo. ¿Qué toca leer el primer mes?",
    "Apilar libros por afinidades es una buena forma de acertar con el siguiente. ¿Ya has montado alguna pila?",
    "Con ese título, Todos los viernes a medianoche ya promete. ¿Va más hacia el terror o la distopía?",
    "Un poema leído en voz alta pesa distinto que en la página.",
]
VARIED = [
    "¡Qué buena pinta!", "¿Cuántos tomos tiene la saga?", "Ese final me dejó tocado, no te cuento más",
    "Lo tengo en la pila desde agosto", "Uf, esa portada", "El segundo es mejor que el primero. ¿Lo has probado?",
    "Gracias por el dato", "jaja, me pasa igual",
]


class FormatTests(unittest.TestCase):
    def test_classification(self):
        self.assertEqual(sc.reply_format("Buen hallazgo, esa pista."), "micro")
        self.assertEqual(sc.reply_format("¡Qué buena pinta esta portada, de verdad!"), "exclamacion")
        self.assertEqual(sc.reply_format("¿Cuántos tomos tiene la saga entera hasta ahora?"), "pregunta")
        self.assertEqual(sc.reply_format("Ginzburg parece sencilla y te deja sin aire. ¿Qué frase te quedó más grabada?"), "observacion_pregunta")
        self.assertEqual(sc.reply_format("Ese final me dejó tocado, no te cuento más"), "afirmacion")

    def test_templated_batch_is_flagged(self):
        notes = " ".join(sc.reply_style_report(TEMPLATED))
        self.assertIn("mismo formato", notes)
        self.assertIn("aforismo", notes)
        self.assertIn("evaluacion generica", notes)

    def test_varied_batch_has_no_format_warning(self):
        notes = " ".join(sc.reply_format_notes(VARIED))
        self.assertEqual(notes, "")

    def test_small_batches_are_not_judged(self):
        self.assertEqual(sc.reply_format_notes(TEMPLATED[:4]), [])


if __name__ == "__main__":
    unittest.main()
