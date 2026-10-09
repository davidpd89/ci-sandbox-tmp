"""spellcheck_es.py: falsos positivos conocidos (02/10)."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from spellcheck_es import check_missing_accents


class SpellcheckTests(unittest.TestCase):
    def test_londres_is_not_a_missing_accent(self):
        self.assertEqual(check_missing_accents("Londres victoriano"), [])

    def test_real_missing_accent_still_detected(self):
        self.assertTrue(check_missing_accents("la musica del bosque"))


if __name__ == "__main__":
    unittest.main()
