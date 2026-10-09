import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
import reply_corpus_lint as rl


class CorpusLintTests(unittest.TestCase):
    def test_varied_corpus_has_no_warnings(self):
        texts = ['Qué buen final.', 'Me apunto el título, gracias por la pista.', 'Jajaja, justo me pasó con ese.',
                 'Esa portada engancha más que la sinopsis, y mira que la sinopsis es buena.', 'Ni idea, pero suena bien.',
                 'Lo leí de niño y todavía me acuerdo del olor del libro.', 'Apuntado.', 'Con ese ritmo me quedo hasta tarde.',
                 'Gran elección para empezar.', 'Tu lista me ha hecho ir a la estantería a buscar uno.', 'Qué ganas de verlo terminado.',
                 'Una portada así vende sola, otra cosa es el interior, que nunca se sabe.']
        metrics, warnings = rl.lint(texts)
        self.assertEqual(warnings, [])
        self.assertGreater(metrics['micro_share'], 0)

    def test_template_corpus_is_flagged(self):
        texts = ['Sí, tiene sentido: la trama aguanta. Al final.' for _ in range(12)]
        _, warnings = rl.lint(texts)
        joined = ' '.join(warnings)
        self.assertIn('dos puntos', joined)
        self.assertIn('empiezan por', joined)
        self.assertIn('cierres', joined)
        self.assertIn('uniforme', joined)

    def test_too_few_texts_never_warn(self):
        metrics, warnings = rl.lint(['Sí: claro. Al final.'] * 5)
        self.assertEqual(warnings, [])
        self.assertEqual(rl.lint([]), ({}, []))


if __name__ == '__main__':
    unittest.main()
