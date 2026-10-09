import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import meta_inbox as mi


def boom(env):
    raise RuntimeError("API 190: token caducado")


class InboxTests(unittest.TestCase):
    def test_one_failing_network_does_not_hide_the_others(self):
        sources = (("a", "KA", lambda env: [{"id": "1", "username": "ana", "text": "¿Dónde?"}]),
                   ("b", "KB", boom),
                   ("c", "KC", lambda env: []))
        report = mi.collect({"KA": "x", "KB": "x"}, sources)
        self.assertEqual(len(report["a"]["pending"]), 1)
        self.assertIn("token caducado", report["b"]["error"])
        self.assertIn("falta KC", report["c"]["error"])

    def test_render_lists_questions_and_warnings(self):
        text = mi.render({"a": {"pending": [{"id": "1", "username": "ana", "text": "¿Dónde?"}], "error": None},
                          "b": {"pending": [], "error": "falta KB en .env"}})
        self.assertIn("[a] 1 pregunta(s) sin contestar", text)
        self.assertIn("@ana", text)
        self.assertIn("[b] AVISO: falta KB", text)


if __name__ == "__main__":
    unittest.main()
