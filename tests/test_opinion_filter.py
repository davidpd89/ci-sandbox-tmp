"""scan_common.asks_for_opinion / opinion_guard (03/10): peticiones de opinion sobre trabajo ajeno."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import scan_common as sc
import growth_reply_view as grv
import bluesky_build_plan as bbp

ASKS = [
    "Lee mi relato y dime qué te parece", "¿Me echáis un ojo a mi novela? Busco feedback",
    "Necesito lectores beta para mi manuscrito", "Os dejo mi primer capítulo, ¿qué os parece mi historia?",
    "Opiniones sobre mi texto, por favor", "Read my short story and tell me what you think",
    "Comparto mi microrrelato, valoradlo", "¿Podéis leer mi novela?",
    "Os dejo el primer capítulo de mi novela, ¿qué os parece?", "¿Os gusta la portada de mi novela?",
    "Leed mi segunda novela", "¿Qué tal mi primer relato?", "He escrito este relato, ¿opiniones?",
    "Por favor, lee mi texto", "Echadle un ojo a mi relato", "Busco opiniones.",
]
NOT_ASKS = [
    "¿Qué os ha parecido la película?", "Opiniones sobre El nombre del viento",
    "Hoy termino de leer mi libro favorito", "Lee más cada día", "Mi novela favorita es Dune, comentad la vuestra",
    "Recomendadme un libro de fantasía", "Acabo de terminar mi novela, estoy feliz",
    # falsos positivos medidos por el revisor independiente (03/10)
    "Busco opiniones sobre el último libro de Sanderson", "Dime qué opinas del final de Juego de Tronos",
    "Quiero leer críticas de La sombra del viento", "Mira, mi libro del año es Piranesi",
    "Mi editor revisa mi manuscrito esta semana", "Mi libro tiene una valoración de 4,5",
    "Gracias por los comentarios sobre mi novela", "Mira mi micrófono nuevo", "Mi historial de lecturas",
]


class DetectionTests(unittest.TestCase):
    def test_detects_requests_for_opinion_on_own_work(self):
        for text in ASKS:
            self.assertTrue(sc.asks_for_opinion(text), text)

    def test_does_not_flag_normal_conversation(self):
        for text in NOT_ASKS:
            self.assertFalse(sc.asks_for_opinion(text), text)


class ReplyCheckTests(unittest.TestCase):
    def test_short_positive_neutral_reply_is_valid(self):
        for ok in ("Tiene buena pinta, deseando leer más.", "Qué entretenido, enhorabuena y ánimo."):
            self.assertEqual(sc.check_opinion_reply(ok), [], ok)

    def test_critical_long_or_questioning_replies_rejected(self):
        self.assertTrue(sc.check_opinion_reply("Está bien, pero podrías mejorar el inicio."))
        self.assertTrue(sc.check_opinion_reply("Tiene buena pinta, ¿de qué va exactamente?"))
        self.assertTrue(sc.check_opinion_reply("Me gusta " + "mucho " * 30))
        self.assertTrue(sc.check_opinion_reply("Hoy hace sol."))  # sin tono positivo

    def test_guard_only_applies_to_opinion_posts(self):
        sc.opinion_guard("Mi novela favorita es Dune", "Qué buena elección, ¿la releíste?")
        with self.assertRaises(ValueError):
            sc.opinion_guard("Lee mi relato y dime qué te parece", "Mucho potencial, pero falta ritmo.")
        sc.opinion_guard("Lee mi relato y dime qué te parece", "Tiene buena pinta, deseando leer más.")


class IntegrationTests(unittest.TestCase):
    def test_reply_view_skips_opinion_requests_unless_included(self):
        text = "Os dejo mi primer capítulo, ¿qué os parece mi historia? Es una fantasía de la que estoy muy orgulloso en español"
        state = {"shortlist": [{"handle": "a", "lane": "acquisition", "score": 1,
                                "posts": [{"id": "G1-P1", "text": text, "actions": ["reply"]}]}]}
        self.assertEqual(grv.view(state), [])
        self.assertEqual(len(grv.view(state, include_opinion=True)), 1)

    def test_builder_blocks_long_reply_to_opinion_request(self):
<<<<<<< HEAD
        state = {"shortlist": [{"id": "G1", "handle": "a", "lane": "acquisition", "actions": [],
=======
        state = {"shortlist": [{"id": "G1", "handle": "lectora.bsky.social", "lane": "acquisition", "actions": [],
>>>>>>> origin/research/public-reuse-parent
                                "posts": [{"id": "G1-P1", "url": "u", "text": "Lee mi relato y dime qué te parece",
                                           "actions": ["reply"], "sources": []}]}]}
        with self.assertRaises(ValueError):
            bbp.build(state, {"actions": [{"post": "G1-P1", "kind": "reply", "text": "Podrías mejorar el inicio."}]})
        plan = bbp.build(state, {"actions": [{"post": "G1-P1", "kind": "reply", "text": "Tiene buena pinta, deseando leer más."}]})
        self.assertEqual(plan[-1]["kind"], "reply")


if __name__ == "__main__":
    unittest.main()


class GlobalApplicationTests(unittest.TestCase):
    ASK = "Lee mi relato y dime qué te parece, es una fantasía corta"
    NORMAL = "¿Qué libro de fantasía recomendáis para empezar este otoño?"

    def test_downgrade_for_opinion_keeps_normal_posts(self):
        self.assertEqual(sc.downgrade_for_opinion("reply", self.ASK), "like")
        self.assertEqual(sc.downgrade_for_opinion("reply", self.ASK, cheap="favourite"), "favourite")
        self.assertEqual(sc.downgrade_for_opinion("comment_external", self.ASK), "like_external")
        self.assertEqual(sc.downgrade_for_opinion("reply", self.NORMAL), "reply")
        self.assertEqual(sc.downgrade_for_opinion("follow", self.ASK), "follow")

    def _run_clean(self, code):
        """Los scanners/ejecutores se importan en un proceso limpio: otros tests
        sustituyen modulos (x_interact...) en sys.modules."""
        import subprocess
        tools = str(pathlib.Path(__file__).resolve().parents[1] / "tools")
        header = "import sys\nsys.path.insert(0, " + repr(tools) + ")\n"
        proc = subprocess.run([sys.executable, "-c", header + code],
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return proc.stdout

    def test_every_scanner_never_suggests_a_reply_for_an_opinion_request(self):
        code = (
            "import threads_scan, mastodon_scan, bluesky_scan, x_scan, facebook_scan, tiktok_scan\n"
            "ask = " + repr(self.ASK + "?") + "\n"
            "normal = " + repr(self.NORMAL) + "\n"
            "assert threads_scan._suggest_kind(ask) == 'like'\n"
            "assert mastodon_scan._suggest_kind(ask) == 'favourite'\n"
            "assert tiktok_scan._suggest_kind(ask) == 'like'\n"
            "assert facebook_scan._suggest_kind_own(ask) == 'like'\n"
            "assert facebook_scan._suggest_kind_external(ask) == 'like_external'\n"
            "assert x_scan._suggest_kind('search:x', ask, frozenset(), None) != 'reply'\n"
            "assert bluesky_scan._suggest_kind('search:x', ask, None, frozenset()) != 'reply'\n"
            "assert threads_scan._suggest_kind(normal) == 'reply'\n"
            "print('ok')\n"
        )
        self.assertIn("ok", self._run_clean(code))

    def test_guard_plan_item_uses_any_context_field(self):
        for field in ("post_text", "text_fragment", "resumen", "title"):
            item = {"kind": "reply", "text": "Mucho potencial, pero falta ritmo.", field: self.ASK}
            with self.assertRaises(ValueError):
                sc.guard_plan_item(item, 3)
        sc.guard_plan_item({"kind": "reply", "text": "Tiene buena pinta, deseando leer más.", "resumen": self.ASK})
        sc.guard_plan_item({"kind": "like", "resumen": self.ASK})
        sc.guard_plan_item({"kind": "reply", "text": "Cualquier cosa larga y con preguntas, ¿no?", "resumen": self.NORMAL})

    def test_executor_preflight_blocks_x_reply_to_opinion_request(self):
        code = (
            "import x_execute\n"
            "plan = [{'kind': 'reply', 'url': 'https://x.com/ana/status/123456789', 'handle': '@ana',\n"
            "         'resumen': " + repr(self.ASK) + ", 'text': 'Podrías mejorar el inicio, ¿lo has revisado?'}]\n"
            "try:\n"
            "    x_execute._preflight_plan(plan)\n"
            "except ValueError as exc:\n"
            "    print('BLOQUEADO', exc)\n"
        )
        out = self._run_clean(code)
        self.assertIn("BLOQUEADO", out)
        self.assertIn("opinion", out)


if __name__ == "__main__":
    unittest.main()
