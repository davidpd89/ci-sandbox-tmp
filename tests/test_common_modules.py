"""Modulos comunes a todas las redes (06/10): clasificadores de texto y piezas de los ejecutores; sin red."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import exec_common as ec
import text_common as tc


class TextCommonTests(unittest.TestCase):
    def test_every_network_module_sees_the_same_classifiers(self):
        import bluesky_pool as bp
        for name in ("niche_hits", "looks_spanish", "looks_english", "NICHE_TERMS", "SPAM", "SPANISH_WORDS", "ENGLISH_WORDS"):
            self.assertIs(getattr(bp, name), getattr(tc, name), name)

    def test_basic_behaviour(self):
        self.assertGreaterEqual(tc.niche_hits("Acabo de terminar una novela de fantasía"), 2)
        self.assertTrue(tc.looks_spanish("Hoy he terminado de leer una novela muy buena"))
        self.assertTrue(tc.looks_english("I just finished reading this book and I love it"))
        self.assertFalse(tc.looks_english("Hola, soy escritor"))


class OtherLanguageTests(unittest.TestCase):
    def test_clearly_foreign_bios_are_flagged(self):
        self.assertEqual(tc.other_language("Humanist, Anomalist und Autor. SysAdmin und Datenschützer."), "de")
        self.assertEqual(tc.other_language("Bücher und Fotografie sind meine Steckenpferde. Schreibe selbst und natürlich"), "de")
        self.assertEqual(tc.other_language("Sou uma leitora apaixonada, não vivo sem livros e você também não vive muito sem eles"), "pt")

    def test_spanish_english_galician_and_links_are_not(self):
        for text in ("Correctora, traductora, filóloga y escritora AGENDA ABIERTA misaleg.info@gmail.com https://misaleg.blogspot.com/",
                     "Roberto González A veces panadero. https://panherido.wordpress.com/",
                     "Escritor galego en Madrid. Fantasía e libros que deixan pegada",
                     "I love fantasy books and writing novels every single day",
                     "Escribo fantasía y novelas, lectora de libros para todos"):
            self.assertIsNone(tc.other_language(text), text)


class ResultListTests(unittest.TestCase):
    def test_reports_each_append(self):
        seen = []
        results = ec.ResultList(seen.append)
        results.append({"a": 1})
        results.append({"a": 2})
        self.assertEqual(seen, [{"a": 1}, {"a": 2}])
        self.assertEqual(len(results), 2)

    def test_works_without_callback(self):
        results = ec.ResultList()
        results.append(1)
        self.assertEqual(results, [1])


class RetryTests(unittest.TestCase):
    class Err(Exception):
        def __init__(self, code):
            super().__init__(f"http {code}")
            self.status_code = code

    def test_retries_transient_then_succeeds(self):
        calls, waits = [], []

        def call():
            calls.append(1)
            if len(calls) == 1:
                raise self.Err(503)
            return "ok"

        self.assertEqual(ec.with_retries(call, sleep=waits.append, log=lambda *_: None), "ok")
        self.assertEqual(waits, [6])

    def test_gives_up_after_the_backoff_and_raises_the_last_error(self):
        waits = []
        with self.assertRaises(self.Err):
            ec.with_retries(lambda: (_ for _ in ()).throw(self.Err(502)), sleep=waits.append, log=lambda *_: None)
        self.assertEqual(waits, [6, 20])

    def test_non_transient_errors_are_not_retried(self):
        calls = []

        def call():
            calls.append(1)
            raise self.Err(404)

        with self.assertRaises(self.Err):
            ec.with_retries(call, sleep=lambda s: None, log=lambda *_: None)
        self.assertEqual(len(calls), 1)

    def test_status_code_is_parsed_from_client_messages(self):
        self.assertEqual(ec.status_code_of(RuntimeError('POST com.atproto.repo.createRecord fallo (502): {"error":"UpstreamFailure"}')), 502)
        self.assertEqual(ec.status_code_of(RuntimeError("POST statuses/1/favourite falló (503): ")), 503)
        self.assertIsNone(ec.status_code_of(RuntimeError("otra cosa")))

    def test_status_code_is_found_in_response_attribute_too(self):
        class Resp:
            status_code = 503

        class E(Exception):
            response = Resp()

        self.assertEqual(ec.status_code_of(E()), 503)


if __name__ == "__main__":
    unittest.main()
