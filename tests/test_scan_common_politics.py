"""Regresiones del filtro político compartido (24/09/2026)."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from scan_common import is_political, is_valid_candidate


class PoliticalFilterTests(unittest.TestCase):
    def test_politics_in_reposts_and_news(self):
        for text in (
            "Repost: familias afectadas por desahucios en Madrid",
            "La noticia de los DESAHUCIOS",
            "Feijóo responde en el Congreso de los Diputados",
            "Pedro Sánchez y el Partido Popular",
            "Pedro\nSánchez presenta una propuesta",
            "Partido   Popular en una noticia",
            "La ley de vivienda y los alquileres",
            "Última hora: campaña electoral",
            "Una ministra anuncia nuevas medidas",
            "Consejo de Ministros aprueba nuevas medidas",
            "Moción de censura en el Congreso de los Diputados",
            "Debate sobre los Presupuestos Generales del Estado",
            "Referéndum convocado para este domingo",
            "El Gobierno de España anuncia cambios",
            "Las ministras comparecen ante la prensa",
            "Varios ministros comparecen ante la prensa",
            "Opinión sobre la inmigración ilegal",
            "Franco y la política española",
            "Noticias sobre Ukraine",
            "El genocidio en un conflicto armado",
            "Actualidad política española esta mañana",
            "Debate político sobre vivienda",
            "El Gobierno anuncia nuevas medidas",
        ):
            with self.subTest(text=text):
                self.assertTrue(is_political(text))

    def test_accents_boundaries_and_nonpolitical_books(self):
        for text in (
            "La app permite leer sin conexión",
            "Voxels y mapas de fantasía",
            "Mi saga de fantasía juvenil",
            "Mi elección de lecturas para octubre",
            "Un rey dicta una ley de magia",
            "Reseña de novela: el presidente del club de lectura",
            "Un parlamento élfico decide quién hereda la corona",
            "La dictadura de los magos en mi novela",
            "",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_political(text))
        self.assertFalse(is_political("Véase pp. 23-25 de la edición crítica"))
        self.assertFalse(is_political("Véase PP. 23-25 de la edición crítica"))
        self.assertTrue(is_political("El Grupo Mixto interviene en el pleno"))

        self.assertFalse(is_political("Es un narrador nato, con muy buen oído para el diálogo"))
        self.assertTrue(is_political("El PP propone cambios en la ley"))
        self.assertTrue(is_political("PP critica al Gobierno"))
        self.assertTrue(is_political("NATO acuerda nuevas medidas"))
        self.assertTrue(is_political("FEIJOO propone cambios"))
        self.assertTrue(is_political("Polémica por DESAHUCIO"))
        self.assertTrue(is_political("Elecciones generales este domingo"))
        self.assertTrue(is_political("Elección presidencial en el país"))
        self.assertTrue(is_political("Sánchez responde en el Congreso"))
        self.assertTrue(is_political("La Unión Europea debate nuevas medidas"))
        self.assertTrue(is_political("La OTAN celebra una cumbre"))
        self.assertTrue(is_political("Junts negocia en el Congreso"))
        self.assertTrue(is_political("ERC registra una iniciativa"))
        self.assertTrue(is_political("EH Bildu interviene en el pleno"))
        self.assertTrue(is_political("El PNV presenta una propuesta"))
        self.assertTrue(is_political("UPN registra una iniciativa en el Congreso"))
        self.assertTrue(is_political("El Grupo Parlamentario Socialista registra una iniciativa"))
        self.assertTrue(is_political("Sesión parlamentaria de control al Gobierno"))
        self.assertTrue(is_political("El Real Decreto-ley se debate esta semana"))
        self.assertTrue(is_political("SUMAR negocia con el Gobierno"))
        self.assertTrue(is_political("Podemos critica al Gobierno"))
        self.assertFalse(is_political("Podemos sumar páginas sin perder el hilo"))
        self.assertFalse(is_political("Quiero sumar tres lecturas a octubre"))
        self.assertFalse(is_political("El parlamento del reino decide quién hereda la corona"))
        self.assertFalse(is_political("La ministra del imperio aparece en el capítulo tres"))
        self.assertFalse(is_political("Un senador galáctico traiciona al protagonista"))
        self.assertFalse(is_political("María Sánchez publica una novela fantástica"))
        self.assertTrue(is_political({"texto": "formato externo inesperado"}))

        # Encontrado en vivo el 28/09/2026 al revisar esta PR (no venía en sus
        # propios tests): el filtro trataba "parlamento"/"senador" como
        # política real incluso en literatura clásica o ficción histórica sin
        # ninguna marca de fantasía - "El Parlamento de las Aves" (Chaucer) o
        # un senador romano de una novela histórica se descartaban igual que
        # una noticia real. La excepción se amplió sin tocar el resto del
        # filtro (ver comentario junto a `_FICTIONAL_POLITICAL_RE`).
        self.assertFalse(is_political(
            "El rey convoca al Parlamento de las Aves para decidir el destino del reino"
        ))
        self.assertFalse(is_political("Termino leyendo el Parlamento de los Pájaros de Chaucer"))
        self.assertFalse(is_political(
            "El senador romano Cicerón pronuncia un discurso en mi novela histórica"
        ))
        self.assertFalse(is_political("El senado romano debate en el segundo capítulo"))
        # Pero si el mismo texto además trae una señal política real e
        # inequívoca, esta excepción no debe taparla.
        self.assertTrue(is_political(
            "El Parlamento de las Aves y también el Congreso de los Diputados"
        ))

    def test_candidate_handles_are_case_insensitive_and_malformed_fail_closed(self):
        self.assertFalse(is_valid_candidate(
            "DAVIDPORTODIAZ", "fantasía juvenil", "davidportodiaz", set()
        ))
        self.assertFalse(is_valid_candidate(
            "@Lectora", "fantasía juvenil", "davidportodiaz", {"lectora"}
        ))
        self.assertFalse(is_valid_candidate(
            {"handle": "lector"}, "fantasía juvenil", "davidportodiaz", set()
        ))
        self.assertFalse(is_valid_candidate(
            "Lectora", "fantasía juvenil", None, {"otra"}
        ))
        self.assertTrue(is_valid_candidate(
            "Lectora", "fantasía juvenil", "davidportodiaz", {"otra"}
        ))


    def test_candidate_without_evaluable_text_is_not_suggested(self):
        self.assertFalse(is_valid_candidate(
            "@lectora", None, "@davidportodiaz"
        ))
        self.assertFalse(is_valid_candidate(
            "@lectora", "", "@davidportodiaz"
        ))
        self.assertFalse(is_valid_candidate(
            "@lectora", "   ", "@davidportodiaz"
        ))





class FeedBridgeTests(unittest.TestCase):
    def test_bridges_detected(self):
        import scan_common as sc
        for handle in ("blogsdeoscar.wordpress.com@blogsdeoscar.wordpress.com",
                       "bot.mastodon.social.ap.brid.gy", "@laenesima.com@laenesima.com"):
            self.assertTrue(sc.is_feed_bridge(handle), handle)

    def test_people_are_not_bridges(self):
        import scan_common as sc
        for handle in ("argyle13@xarxa.cloud", "donporque", "ana.bsky.social"):
            self.assertFalse(sc.is_feed_bridge(handle), handle)


if __name__ == "__main__":
    unittest.main()
