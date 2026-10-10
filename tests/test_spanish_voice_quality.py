"""Casos offline de español social y revisión ciega."""
import pathlib
import sys
import unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from spanish_voice_quality import NETWORKS, QUEUES, audit, _mask
from spanish_voice_blind import pack, score
from spanish_voice_eval import compare


class TestSpanishVoice(unittest.TestCase):
    def check(self, text, network="x", **kwargs):
        return audit(text, network=network, check_accents=False, **kwargs)

    def test_all_networks_and_queues(self):
        self.assertEqual((len(NETWORKS), len(QUEUES)), (9, 3))
        for net in NETWORKS:
            for queue in QUEUES:
                result = self.check("Cuantos libros?", network=net, queue=queue)
                self.assertEqual(result["counts"]["warning"], 1)
                self.assertFalse(result["changed"])

    def test_protected_quotes_links_names_and_offsets(self):
        txt = '«checar?» [carro](https://example.org/?foo) @celular #chambear "checar?" checar?'
        self.assertEqual(len(txt), len(_mask(txt)))
        findings = self.check(txt)["findings"]
        self.assertEqual([(f["code"], txt[f["start"]:f["end"]]) for f in findings],
                         [("locale_variant", "checar"), ("question_opening", "?")])

    def test_correct_native_punctuation(self):
        for txt in ("¿Has leído el libro?", "¡Qué portada!", "¿Uno? ¿Dos?",
                    "En «libro?» aparece Ñuño.", "¿Y el móvil?"):
            self.assertEqual(self.check(txt)["findings"], [], txt)

    def test_calque_and_locale_are_hints(self):
        txt = "Eso hace sentido, voy a checar el carro."
        self.assertEqual(self.check(txt)["counts"]["hint"], 3)
        self.assertEqual(self.check(txt, locale="es")["counts"]["hint"], 1)

    def test_corrupt_utf8_and_spacing(self):
        self.assertIn("encoding_corrupt",
                      {f["code"] for f in self.check("El capÃ­tulo")["findings"]})
        self.assertIn("space_before_punctuation",
                      {f["code"] for f in self.check("Hola , ¿qué tal?")["findings"]})

    def test_emoji_and_nfc_codepoint_offsets(self):
        txt = "🙂 Una computadora?"
        f = self.check(txt)["findings"][0]
        self.assertEqual(txt[f["start"]:f["end"]], "computadora")
        self.assertIn("unicode_normalization",
                      {v["code"] for v in self.check("cafe\u0301")["findings"]})

    def test_reuse_existing_accent_checker(self):
        with mock.patch("spanish_voice_quality._accent_checker",
                        return_value=lambda text: [("capitulo", "capítulo")]):
            txt = "El capitulo. «capitulo»"
            findings = audit(txt, network="bluesky")["findings"]
        self.assertEqual(sum(v["code"] == "possible_missing_accent" for v in findings), 1)

    def test_reject_unknown_network_queue(self):
        with self.assertRaises(ValueError):
            self.check("texto", network="discord")
        with self.assertRaises(ValueError):
            self.check("texto", queue="WRONG")
        with self.assertRaises(TypeError):
            audit(None, network="x")


class TestBlind(unittest.TestCase):
    def setUp(self):
        self.pairs = [
            {"id": net, "network": net, "context": "Saga ficticia.",
             "before": "Cuantos libros?", "after": "¿Cuántos libros?"}
            for net in sorted(NETWORKS)
        ]

    def test_determinism_and_no_faked_humans(self):
        a, key = pack(self.pairs, seed="review")
        self.assertEqual((a, key), pack(list(reversed(self.pairs)), seed="review"))
        with self.assertRaises(ValueError):
            score(a, key)
        for item in a["items"]:
            item["preference"] = key["after_side"][item["id"]]
        self.assertEqual(score(a, key)["preferences"]["after"], 9)

    def test_duplicate_pair_or_missing_key_is_error(self):
        with self.assertRaises(ValueError):
            pack(self.pairs + self.pairs[:1], seed="x")
        a, key = pack(self.pairs, seed="x")
        del key["after_side"]["x"]
        with self.assertRaises(ValueError):
            score(a, key)

    def test_synthetic_before_after(self):
        outcome = compare(self.pairs)
        self.assertEqual(outcome["rule_findings"], {"before": 9, "after": 0})
        self.assertIn("NO demuestra", outcome["warning"])


if __name__ == "__main__":
    unittest.main()
