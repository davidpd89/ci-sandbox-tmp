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


    def test_markdown_images_and_fenced_code_are_not_exclamations(self):
        source = "![portada](https://example.org/book.png) " + chr(96)*3 + "python\\nchecar?\\n" + chr(96)*3 + "\\nchecar?"
        source = source.replace("\\n", "\n")
        output = self.check(source)["findings"]
        self.assertEqual([(f["code"], source[f["start"]:f["end"]]) for f in output],
                         [("locale_variant", "checar"), ("question_opening", "?")])

    def test_multiline_fence_tilde(self):
        text = "~~~text\nChecar?\n~~~\n¡Buen título!"
        self.assertEqual(self.check(text)["findings"], [])

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


    def test_blind_pair_content_integrity_is_checked(self):
        from copy import deepcopy
        doc, key = pack(self.pairs, seed="review")
        for candidate in ("network", "context", "left", "right"):
            changed = deepcopy(doc)
            changed["items"][0][candidate] = "alterado"
            changed["items"][0]["preference"] = "tie"
            with self.assertRaises(ValueError):
                score(changed, key)

    def test_invalid_unhashable_network_is_validation_error(self):
        pairs = [dict(self.pairs[0], network=["x"])]
        with self.assertRaises(ValueError):
            pack(pairs, seed="review")

    def test_two_samples_same_network_are_aggregated(self):
        twice = [dict(self.pairs[0]), dict(self.pairs[0], id="second")]
        measured = compare(twice)
        self.assertEqual(measured["synthetic_pairs"], 2)
        self.assertEqual(measured["rule_findings"], {"before": 2, "after": 0})
        self.assertEqual(measured["by_network"][self.pairs[0]["network"]],
                         {"before": 2, "after": 0, "cases": 2})

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


class TestIntegration(unittest.TestCase):
    def test_shared_writer_reports_without_blocking_or_writing(self):
        import reply_writer as writer
        import spanish_voice_quality as quality
        events = []
        fake_answer = lambda prompt, attachments, wait: (
            '[{"id": "synthetic-id", "reply": "Voy a checar el carro."}]', "offline")
        with (mock.patch.object(writer, "new_authors_only", side_effect=lambda items, net, log: items),
              mock.patch.object(writer, "valid_reply", return_value=(True, "")),
              mock.patch.object(writer, "mark_gpt"),
              mock.patch.object(quality, "audit", return_value={"findings": [
                  {"code": "locale_variant", "severity": "hint"}]})):
            actual = writer.write_replies(
                [{"id": "synthetic-id", "author": "lectora-ficticia",
                  "text": "Una publicación inventada para una prueba.",
                  "network": "tiktok"}],
                "tiktok", recent=[], consult=fake_answer, log=events.append)
        self.assertEqual(actual, {"synthetic-id": "Voy a checar el carro."})
        self.assertIn("locale_variant", " ".join(events))

    def test_auditor_failure_does_not_discard_reply(self):
        import reply_writer as writer
        import spanish_voice_quality as quality
        events = []
        fake_answer = lambda prompt, attachments, wait: (
            '[{"id": "synthetic-id", "reply": "Muy buen hallazgo."}]', "offline")
        with (mock.patch.object(writer, "new_authors_only", side_effect=lambda items, net, log: items),
              mock.patch.object(writer, "valid_reply", return_value=(True, "")),
              mock.patch.object(writer, "mark_gpt"),
              mock.patch.object(quality, "audit", side_effect=RuntimeError("fallo simulado"))):
            actual = writer.write_replies(
                [{"id": "synthetic-id", "author": "lectora-ficticia",
                  "text": "Un libro imaginario sobre dragones.",
                  "network": "reddit_micro"}],
                "reddit_micro", recent=[], consult=fake_answer, log=events.append)
        self.assertEqual(actual, {"synthetic-id": "Muy buen hallazgo."})
        self.assertIn("auditor_es_no_disponible", " ".join(events))

    def test_common_publication_preflight_is_advisory(self):
        import content_publisher as publisher
        messages = []
        issues = publisher._voice_diagnostics(
            "instagram", "Me gusta este carro?", messages.append)
        self.assertTrue(issues)
        self.assertTrue(any("revision_es:" in item for item in messages))
        self.assertEqual(publisher._voice_diagnostics("other", "sin red", messages.append), [])


if __name__ == "__main__":
    unittest.main()
