import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import threads_build_plan as tb


def cand(handle, text, known=None):
    return {"handle": handle, "text": text, "kind": "like", "known_date": known}


class FragmentTests(unittest.TestCase):
    def test_strips_author_and_age_prefix(self):
        frag = tb.fragment("auro_1998 Book Threads 3 h Noches blancas. Fiódor Dostoyevski. Me ha sorprendido, no ha sido para nada")
        self.assertTrue(frag.startswith("Noches blancas"))
        self.assertLessEqual(len(frag), 40)

    def test_short_text_is_kept(self):
        self.assertEqual(tb.fragment("ana 2 días Hola mundo"), "Hola mundo")


class BuildTests(unittest.TestCase):
    def test_one_like_per_account_and_follows_only_new_niche_accounts_up_to_the_cap(self):
        items = [cand("ana", "ana 1 h Terminé mi novela de fantasía por fin"),
                 cand("ana", "ana 2 h Otro post de ana sobre libros"),
                 cand("luis", "luis 3 h Hoy hace sol y fútbol por la tarde"),
                 cand("eva", "eva 4 h Leer un libro antes de dormir", known="2026-09-01"),
                 cand("pau", "pau 5 h Escribir cada mañana cambia el día")]
        plan = tb.build(items, max_follows=1)
        kinds = [(a["handle"], a["kind"]) for a in plan]
        self.assertEqual(kinds, [("ana", "like"), ("ana", "follow"), ("eva", "like"), ("pau", "like")])   # luis (fútbol) ya no recibe like: solo lo que habla de libros

    def test_fragment_strips_community_header_dates_and_trailing_counters(self):
        cases = {
            "escribelaia Author Threads 23/09/2026 Hoy empiezo un capítulo nuevo con mucha calma": "Hoy empiezo un capítulo nuevo con mucha",
            "antoniocastromusic Music Threads 3 h Nuevo disco ya disponible en todas partes": "Nuevo disco ya disponible en todas",
            "elsyolanda ThreshingDay 12 h Una pausa a “Ciudad Medialuna” para empezar": "Una pausa a “Ciudad Medialuna” para",
            "¿Qué rima con lluvia? Libro y manta. 24": "¿Qué rima con lluvia? Libro y manta.",
        }
        for raw, expected in cases.items():
            self.assertEqual(tb.fragment(raw), expected)

    def test_only_book_posts_get_a_like_and_dating_chatter_never_does(self):
        cands = [
            {"handle": "a", "text": "a 3 min Hola hablemos por ig estoy aburrida", "kind": "like"},
            {"handle": "b", "text": "b 2 min Quien me califica el titan", "kind": "like"},
            {"handle": "c", "text": "c 1 h Hola alguien despierto....", "kind": "like"},
            {"handle": "d", "text": "d 1 h Recomienden libros de fantasía con magia original", "kind": "like"},
            {"handle": "e", "text": "e 2 h Recomienden libros de poesía erótica", "kind": "like"},
            {"handle": "f", "text": "f 2 h Carpeta de 250 libros pdf drive para su ayuda drive.google.com/x", "kind": "like"},
        ]
        plan = tb.build(cands)
        self.assertEqual({p["handle"] for p in plan}, {"d"})


if __name__ == "__main__":
    unittest.main()
