"""Pruebas offline del preflight de variedad de lenguaje."""
import importlib.util
import pathlib
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "check_language_variety.py"
SPEC = importlib.util.spec_from_file_location("language_variety", SOURCE)
lv = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lv)


def history(*texts):
    return [
        {"network": "X", "date": f"2026-09-{20+i:02d}", "text": text}
        for i, text in enumerate(texts)
    ]


class LanguageVarietyTests(unittest.TestCase):
    def test_only_conversation_rows_enter_used_text_history(self):
        self.assertTrue(lv._is_conversation_row({"tipo": "reply"}))
        self.assertTrue(lv._is_conversation_row({"tipo": "comentario"}))
        self.assertTrue(lv._is_conversation_row({"tipo": "quote"}))
        self.assertTrue(lv._is_conversation_row({"tipo": "comment_external"}))
        self.assertTrue(lv._is_conversation_row({"tipo": "favourite+reply"}))
        self.assertFalse(lv._is_conversation_row({"tipo": "like"}))
        self.assertFalse(lv._is_conversation_row({"tipo": "follow"}))
        self.assertFalse(lv._is_conversation_row({"tipo": "pin"}))
        self.assertFalse(lv._is_conversation_row({}))


    def test_paused_non_conversational_networks_are_not_required_histories(self):
        self.assertNotIn("TikTok", lv.REGISTROS)
        self.assertNotIn("Pinterest", lv.REGISTROS)
        self.assertIn("X", lv.REGISTROS)
        self.assertIn("Threads", lv.REGISTROS)

    def test_real_repository_history_is_readable_without_schema_or_status_errors(self):
        rows, issues = lv.load_recent(limit=30, with_issues=True)
        self.assertEqual(issues, [])
        self.assertGreaterEqual(len(rows), 20)
        self.assertTrue(all(row["text"].strip() for row in rows))
        self.assertTrue(all(lv._is_iso_date(row["date"]) for row in rows))

    def test_repeated_contrast_scaffold_is_flagged(self):
        h = history(
            "No es un problema de magia, sino de coste.",
            "No es falta de ritmo, sino de foco.",
            "La puerta está cerrada y nadie pregunta por la llave.",
        )
        result = lv.analyze("No es una cuestión de longitud, sino de tensión.", h)
        self.assertTrue(any("andamio" in w for w in result["warnings"]))

    def test_editorial_warning_is_non_blocking_unless_strict(self):
        h = history(
            "Ese es el problema real.",
            "Ese es el detalle importante.",
            "Ese es el punto que cambia todo.",
        )
        with patch.object(lv, "load_recent", return_value=(h, [])):
            self.assertEqual(lv.main(["Ese es otro detalle."]), 0)
            self.assertEqual(lv.main(["--strict", "Ese es otro detalle."]), 2)

    def test_repeated_opening_and_analytic_mode_are_flagged(self):
        h = history(
            "Ese es el punto que más me interesa de la escena.",
            "Lo interesante es que el personaje no lo sabe todavía.",
            "Ese es el problema cuando la magia resuelve demasiado.",
            "Una biblioteca pequeña puede contar una vida entera.",
        )
        result = lv.analyze("Ese es el detalle que cambia toda la lectura.", h)
        self.assertFalse(result["ok"])
        self.assertTrue(any("apertura repetida" in w for w in result["warnings"]))
        self.assertTrue(any("analítico" in w for w in result["warnings"]))

    def test_symmetric_em_dash_formula_is_always_flagged(self):
        result = lv.analyze(
            "La portada —por bonita que sea— no arregla un final flojo.",
            history("Qué ganas de releerlo.", "Yo empezaría por el primero."),
        )
        self.assertTrue(any("inciso simétrico" in w for w in result["warnings"]))

    def test_failed_or_pending_rows_do_not_enter_used_text_history(self):
        self.assertFalse(lv._was_actually_used({"resultado": "fallo"}))
        self.assertFalse(lv._was_actually_used({"resultado": "pendiente"}))
        self.assertFalse(lv._was_actually_used({"resultado": "pendiente_verificacion"}))
        self.assertFalse(lv._was_actually_used({"resultado": "saltado_duplicado"}))
        self.assertFalse(lv._was_actually_used({"resultado": ""}))
        self.assertFalse(lv._was_actually_used({}))
        self.assertFalse(lv._was_actually_used({"resultado": "estado_nuevo_no_mapeado"}))
        self.assertFalse(lv._was_actually_used({"resultado": "publicado_pendiente_verificacion"}))
        self.assertTrue(lv._was_actually_used({"resultado": "confirmado"}))
        self.assertTrue(lv._was_actually_used({"resultado": "publicado"}))
        self.assertTrue(lv._was_actually_used({"resultado": "publicado y fijado"}))

    def test_iso_date_requires_real_calendar_date(self):
        self.assertTrue(lv._is_iso_date("2026-09-28"))
        self.assertFalse(lv._is_iso_date("2026-99-99"))
        self.assertFalse(lv._is_iso_date("28/09/2026"))

    def test_article_opening_is_not_automatically_analytic(self):
        self.assertNotEqual(
            lv.classify("Un reloj roto encima de la mesa ya cuenta media historia."),
            "analitico",
        )

    def test_que_opening_has_its_own_shape(self):
        self.assertEqual(
            lv.opening_shape("Que un libro siga vivo treinta años después dice algo."),
            "que_subordinada",
        )

    def test_analytic_gesture_beats_topic_keyword(self):
        self.assertEqual(
            lv.classify("La clave está en el personaje, no en el mapa."),
            "analitico",
        )

    def test_legitimate_phrase_is_not_generic_assistant_warning(self):
        result = lv.analyze(
            "Es importante que la magia tenga un coste visible en escena.",
            history("Qué final tan raro.", "Yo empezaría por el primero."),
        )
        self.assertFalse(any("asistente" in w for w in result["warnings"]))

    def test_generic_assistant_phrase_is_flagged(self):
        result = lv.analyze(
            "Totalmente de acuerdo. Qué buena reflexión.",
            history("Me hizo gracia porque me pasa igual."),
        )
        self.assertTrue(any("asistente" in w for w in result["warnings"]))

        result = lv.analyze(
            "Sin duda. Ese libro cambia la conversación.",
            history("Qué final tan raro."),
        )
        self.assertTrue(any("asistente" in w for w in result["warnings"]))

    def test_short_human_reaction_can_pass(self):
        result = lv.analyze(
            "Ese final duele más de lo que debería 😂",
            history(
                "La clave está en el ritmo del capítulo.",
                "Yo empezaría por Nada, de Laforet.",
                "¿Y cuál te hizo cambiar de opinión?",
            ),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "humor_seco")

    def test_question_closing_saturation_is_flagged(self):
        h = history(
            "¿Cuál te gustó más?",
            "Yo no lo veo igual. ¿Tú sí?",
            "Ese giro funciona. ¿Lo esperabas?",
            "La edición es preciosa. ¿La comprarías?",
            "Yo empezaría por el segundo.",
            "La adaptación cambia bastante el tono.",
        )
        result = lv.analyze("El primero envejeció mejor. ¿Con cuál te quedas?", h)
        self.assertTrue(any("pregunta final" in w for w in result["warnings"]))

    def test_mode_saturation_is_aggregate_not_fake_sequence(self):
        h = history(
            "Lo interesante es el ritmo.",
            "Una puerta cerrada cambia la escena.",
            "La clave está en el personaje.",
            "¿Qué elegirías?",
            "Ese es el conflicto real.",
            "Una mesa vacía también cuenta cosas.",
        )
        result = lv.analyze("Lo curioso es que nadie pregunta por el precio.", h)
        self.assertTrue(any("analítico saturado" in w for w in result["warnings"]))

    def test_recent_cutoff_keeps_whole_day(self):
        rows = [
            {"date": "2026-09-25", "network": "X", "text": "a"},
            {"date": "2026-09-26", "network": "X", "text": "b"},
            {"date": "2026-09-26", "network": "Reddit", "text": "c"},
            {"date": "2026-09-26", "network": "Threads", "text": "d"},
        ]
        selected = lv._select_recent_rows(rows, 2)
        self.assertEqual(len(selected), 3)
        self.assertEqual({x["network"] for x in selected}, {"X", "Reddit", "Threads"})

    def test_analyze_does_not_cut_a_same_day_sample_by_network_order(self):
        h = [
            {"date": "2026-09-25", "network": "X", "text": "Una respuesta antigua."},
            {"date": "2026-09-26", "network": "A", "text": "Que un libro llegue tarde cambia la lectura."},
            {"date": "2026-09-26", "network": "B", "text": "Que la portada engañe también forma parte del juego."},
            {"date": "2026-09-26", "network": "C", "text": "Que siga funcionando años después dice bastante."},
            {"date": "2026-09-26", "network": "D", "text": "Que nadie pregunte por el mapa me parece lo raro."},
            {"date": "2026-09-26", "network": "E", "text": "Una portada concreta puede cambiar la expectativa."},
        ]
        result = lv.analyze("Que una escena aguante sola ya es mucho.", h)
        self.assertTrue(any("que_subordinada" in w for w in result["warnings"]))

    def test_repeated_cadence_is_flagged_even_when_words_change(self):
        h = history(
            "La puerta está cerrada. Nadie pregunta por la llave.",
            "El reloj sigue andando. Nadie mira la hora.",
            "Una escena muy distinta, con bastante más recorrido.",
        )
        result = lv.analyze(
            "La mesa sigue vacía. Nadie pregunta por el dueño.", h
        )
        self.assertTrue(any("cadencia" in w for w in result["warnings"]))

    def test_recommendations_prefer_underused_modes(self):
        h = history(
            "Ese es el problema real del capítulo.",
            "Lo interesante es la decisión final.",
            "La clave está en lo que no dice.",
            "El ritmo funciona porque corta pronto.",
        )
        modes = lv.recommend_modes(h, n=3)
        self.assertNotIn("analitico", modes)

    def test_no_personal_experience_is_synthesized(self):
        result = lv.analyze(
            "Yo nunca leo dos libros a la vez.",
            history("La portada me hizo gracia.", "¿Lo releerías?"),
        )
        # El checker analiza estructura: no convierte esa frase en un hecho
        # biográfico validado ni recomienda inventar recuerdos.
        self.assertNotIn("experiencia_personal", result["recommended_modes"])


    def test_ascii_dash_inciso_is_flagged_too(self):
        result = lv.analyze(
            "La escena - por bonita que sea - no arregla el ritmo.",
            history("Qué final tan raro.", "Una puerta cerrada cambia todo."),
        )
        self.assertTrue(any("inciso simétrico" in w for w in result["warnings"]))

    def test_near_duplicate_recent_reply_is_flagged_without_external_library(self):
        previous = (
            "El problema no es que el mapa sea grande, sino que el personaje "
            "nunca parece perderse dentro de él."
        )
        candidate = (
            "El problema no es que el mapa sea enorme, sino que el personaje "
            "nunca parece perderse dentro de él."
        )
        result = lv.analyze(candidate, history(previous, "Qué giro tan raro."))
        self.assertTrue(any("demasiado parecido" in w for w in result["warnings"]))

    def test_variation_plans_are_structures_not_prefabricated_replies(self):
        plans = lv.variation_plans(history(
            "La clave está en el personaje.",
            "Lo interesante es el ritmo.",
        ))
        self.assertEqual(len(plans), 3)
        self.assertTrue(all(len(plan) > 10 for plan in plans))
        self.assertFalse(any("David" in plan for plan in plans))



if __name__ == "__main__":
    unittest.main()
