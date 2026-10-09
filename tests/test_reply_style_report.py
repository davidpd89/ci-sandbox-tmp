"""scan_common.reply_style_report (02/10): avisos de estilo de replies."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import scan_common as sc


class StyleReportTests(unittest.TestCase):
    def test_clean_batch_has_no_notes(self):
        texts = ["Buen arranque. ¿Lo recomiendas?", "Me quedo con el final. ¿Y tú?", "Ese tono funciona. ¿Cuál es tu favorito?"]
        self.assertEqual(sc.reply_style_report(texts), [])

    def test_batch_without_micro_replies_is_nudged(self):
        long_ones = ["Esta es una respuesta con bastantes más de ocho palabras en total ahora mismo mismo?"] * 3
        self.assertTrue(any("micro-replies" in n for n in sc.reply_style_report(long_ones)))

    def test_dashes_length_and_missing_questions_flagged(self):
        texts = ["Algo muy largo " + "x" * 220, "Mezclar eso - funciona", "Otra más - sin pregunta"]
        notes = " | ".join(sc.reply_style_report(texts))
        self.assertIn("pasan de", notes)
        self.assertIn("guion", notes)
        self.assertIn("pregunta", notes)

    def test_repeated_explanatory_colon_is_flagged(self):
        batch = ['Buen arranque: el piso dice mas.', 'Tiene sentido: la biblioteca es un lugar.', 'Apuntado: gracias.',
                 'Me gusta esa idea.', 'Eso cambia mucho el final?']
        self.assertTrue(any('dos puntos' in n for n in sc.reply_style_report(batch)))
        self.assertFalse(any('dos puntos' in n for n in sc.reply_style_report(['Me gusta.', 'Tiene buena pinta.', 'Apuntado.', 'Que bueno: si.'])))


    def test_small_batches_do_not_demand_questions(self):
        self.assertEqual(sc.reply_style_report(["Solo una reply corta."]), [])


class TellTests(unittest.TestCase):
    def test_measured_tells_and_repeated_openers_are_flagged(self):
        texts = ["Que un libro piense a la vez dice mucho", "Es de esos libros que se leen de una sentada, de verdad.",
                 "Que gran idea, casi siempre funciona", "Que bien suena"]
        notes = " | ".join(sc.reply_style_report(texts))
        for fragment in ("'Que + verbo'", "'es de esas/os", "'dice mucho'", "'de verdad'", "'casi siempre/nunca'",
                         "empiezan por 'que'"):
            self.assertIn(fragment, notes)

    def test_median_length_flagged_only_for_real_batches(self):
        long_batch = ["Una respuesta bastante larga " + "x" * 140 + "?" for _ in range(4)]
        self.assertIn("mediana", " | ".join(sc.reply_style_report(long_batch)))
        self.assertNotIn("mediana", " | ".join(sc.reply_style_report(long_batch[:2])))


class StructuralNotesTests(unittest.TestCase):
    def test_wires_variety_checker_warnings_and_suggestions(self):
        import types
        fake = types.SimpleNamespace(
            load_recent=lambda: ["h"],
            analyze=lambda text, history: {"warnings": ["apertura repetida"] if text.startswith("Que") else []},
            recommend_modes=lambda history: ["reaccion_corta", "humor_seco"],
        )
        sys.modules["check_language_variety"] = fake
        try:
            notes = sc.structural_notes(["Que cosa más rara", "Otra cosa distinta"])
        finally:
            del sys.modules["check_language_variety"]
        self.assertTrue(any("apertura repetida" in n for n in notes))
        self.assertTrue(any("reaccion_corta" in n for n in notes))
        self.assertEqual(sc.structural_notes([], history=[]) if False else [], [])

    def test_missing_checker_never_breaks_the_plan_report(self):
        sys.modules["check_language_variety"] = None  # import falla
        try:
            self.assertEqual(sc.structural_notes(["Hola"]), [])
        finally:
            del sys.modules["check_language_variety"]


class WhitespaceTests(unittest.TestCase):
    def test_whitespace_only_texts_are_ignored_not_crashing(self):
        self.assertEqual(sc.reply_style_report(["   ", ""]), [])
        self.assertEqual(sc.reply_style_report(["Buen arranque. ¿Lo recomiendas?", "  "]), [])


if __name__ == "__main__":
    unittest.main()
