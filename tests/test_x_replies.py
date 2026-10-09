import datetime
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import x_replies as xr


class ClassifyTests(unittest.TestCase):
    def test_intents(self):
        cases = {
            "¿Me recomendáis una novela de fantasía para este verano?": "recommendation_request",
            "Acabo de terminar la saga y qué final": "finished_book",
            "Estoy leyendo una novela de fantasía preciosa": "reading_now",
            "Bloqueo de escritor total con el capítulo 7 de mi novela": "writing_struggle",
            "Por fin terminé mi novela, primer borrador listo": "wip_milestone",
            "¿Cuál es vuestro libro favorito de fantasía?": "favorite_question",
        }
        for text, intent in cases.items():
            self.assertEqual(xr.classify(text), intent, text)

    def test_no_intent_without_book_topic_or_with_opinion_request(self):
        self.assertIsNone(xr.classify("Acabo de terminar de pintar la cocina"))
        self.assertIsNone(xr.classify("Hoy hace calor"))
        self.assertIsNone(xr.classify("Acabo de terminar mi novela, ¿me decís qué os parece el primer capítulo? Leed mi texto"))

class BuildRepliesTests(unittest.TestCase):
    ROWS = [
        {"handle": "Ana", "permalink": "https://x.com/Ana/status/1", "text": "Acabo de terminar la saga de fantasía, qué final", "source": "s"},
        {"handle": "Ana", "permalink": "https://x.com/Ana/status/2", "text": "Estoy leyendo otra novela de fantasía", "source": "s"},
        {"handle": "Luis", "permalink": "https://x.com/Luis/status/3", "text": "¿Me recomendáis una novela para el verano?", "source": "s"},
        {"handle": "Eva", "permalink": "https://x.com/Eva/status/4", "text": "Buenos días a todos", "source": "s"},
        {"handle": "Marta", "permalink": "https://x.com/Marta/status/5", "text": "Bloqueo de escritor con mi novela, no consigo avanzar", "source": "s"},
    ]

    def test_one_reply_per_account_and_cap(self):
        plan = xr.build_replies(self.ROWS, max_replies=2, used=set(), rng=random.Random(1))
        self.assertEqual(len(plan), 2)
        self.assertEqual(len({p["handle"] for p in plan}), 2)
        self.assertTrue(all(p["kind"] == "reply" and p["text"] for p in plan))

    def test_skips_done_urls_recent_handles_and_no_intent(self):
        plan = xr.build_replies(self.ROWS, max_replies=10, used=set(), done_urls={"https://x.com/Luis/status/3"}, recent_handles={"marta"}, rng=random.Random(1))
        self.assertEqual([p["handle"] for p in plan], ["Ana"])

class RegistryTests(unittest.TestCase):
    def test_recent_phrases_and_replied_handles(self):
        today = datetime.date(2026, 10, 20)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "registro.csv")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n")
                stream.write("2026-10-19,,reply,https://x.com/Ana/status/1,¿Qué tal el final?,publicado,x\n")
                stream.write("2026-09-01,,reply,https://x.com/Luis/status/2,Ánimo,publicado,x\n")
            self.assertEqual(xr.recent_phrases(path, today), {"¿que tal el final?"})
            self.assertEqual(xr.replied_handles(path, today), {"ana"})

    def test_replies_per_round_by_stage(self):
        self.assertEqual(xr.replies_per_round(1), 6)
        self.assertEqual(xr.replies_per_round(5), 10)
        self.assertEqual(xr.replies_per_round(99), 3)


if __name__ == "__main__":
    unittest.main()
