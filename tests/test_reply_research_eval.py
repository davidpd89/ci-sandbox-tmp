"""Regresiones de la PR #90: evaluación local, sin cuentas ni consultas al modelo."""
import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reply_research_eval as reval


def sample(case_id, post, reply, *, network="bluesky", variant="baseline"):
    return {"case_id": case_id, "network": network, "post": post,
            "reply": reply, "variant": variant}


class OfflineEvaluationTests(unittest.TestCase):
    def test_abstention_and_micro_replies_are_both_visible(self):
        result = reval.summarize([
            sample("1", "Gracias, compañero", None),
            sample("2", "Una pila de libros enorme", "Uf, menudo montón"),
            sample("3", "¿Qué libro de fantasía leo?", "Un mago de Terramar"),
        ])
        self.assertEqual(result["all"]["cases"], 3)
        self.assertEqual(result["all"]["answers"], 2)
        self.assertEqual(result["all"]["null"], 1)
        self.assertEqual(result["all"]["answer_share"], 0.667)

    def test_keeps_networks_separate(self):
        result = reval.summarize([
            sample("1", "Post de Reddit", None, network="reddit"),
            sample("2", "Post Bluesky", "Me lo apunto", network="bluesky"),
        ])
        self.assertEqual(result["by_variant_network"]["baseline/reddit"]["null"], 1)
        self.assertEqual(result["by_variant_network"]["baseline/bluesky"]["answers"], 1)

    def test_variants_can_compare_same_case_without_collision(self):
        result = reval.summarize([
            sample("id1", "Una reseña literaria", "Qué bien", variant="baseline"),
            sample("id1", "Una reseña literaria", "Me gusta esa comparación", variant="A"),
        ])
        self.assertEqual(set(result["variants"]), {"A", "baseline"})
        self.assertEqual(result["variants"]["A"]["cases"], 1)

    def test_repeated_short_sentence_is_detected_without_raw_text_leak(self):
        cases = [
            sample("1", "Terminé una novela", "Jaja, totalmente"),
            sample("2", "Estoy escribiendo", "jaja, totalmente"),
        ]
        result = reval.summarize(cases)
        self.assertEqual(result["all"]["exact_repeated_extra"], 1)
        self.assertEqual(result["all"]["opening_2word_top_share"], 1.0)
        self.assertNotIn("Jaja, totalmente", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("Terminé una novela", json.dumps(result, ensure_ascii=False))

    def test_null_is_not_replaced_by_placeholder_answer(self):
        out = reval.summarize([sample("empty", "Texto", None)])
        self.assertIsNone(out["all"]["questions_share"])
        self.assertIsNone(out["all"]["median_words"])
        self.assertEqual(out["all"]["null"], 1)

    def test_invalid_or_ambiguous_inputs_fail_closed(self):
        invalid = [
            [sample("1", "Texto", "")],
            [sample("1", "Texto", 12)],
            [sample("1", "", None)],
            [sample("1", "Texto", None, network="twitch")],
            [sample("1", "Texto", None), sample("1", "Otro", None)],
            "no soy lista",
        ]
        for rows in invalid:
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):
                    reval.summarize(rows)

    def test_ab_comparison_requires_identical_case_coverage(self):
        report = reval.summarize([
            sample("c1", "Terminé el segundo tomo", "Me alegro", variant="baseline"),
            sample("c2", "Hoy no he leído nada", None, variant="baseline"),
            sample("c1", "Terminé el segundo tomo", "¿Y qué tal el segundo?", variant="A"),
        ])
        pair = report["pairing"]
        self.assertFalse(pair["all_variants_fully_matched"])
        self.assertEqual(pair["matched_case_samples"], 1)
        self.assertEqual(pair["unpaired_case_samples_by_variant"]["baseline"], 1)
        self.assertEqual(pair["unpaired_case_samples_by_variant"]["A"], 0)

    def test_ab_complete_pairing_allows_comparison_not_quality_claim(self):
        report = reval.summarize([
            sample("c1", "Terminé el segundo tomo", "Qué bien", variant="baseline"),
            sample("c1", "Terminé el segundo tomo", "¿Qué tal el segundo?", variant="A"),
        ])
        self.assertTrue(report["pairing"]["all_variants_fully_matched"])
        self.assertEqual(report["schema_version"], 2)
        self.assertIn("NO miden pertinencia", report["warning"])

    def test_case_reused_with_different_post_or_network_fails(self):
        with self.assertRaisesRegex(ValueError, "entradas diferentes"):
            reval.summarize([
                sample("c1", "He leído el primer tomo", "Vaya", variant="baseline"),
                sample("c1", "He leído el segundo tomo", "Qué bien", variant="A"),
            ])
        with self.assertRaisesRegex(ValueError, "entradas diferentes"):
            reval.summarize([
                sample("c1", "He leído el primer tomo", "Vaya", variant="baseline"),
                sample("c1", "He leído el primer tomo", "Qué bien", variant="A", network="x"),
            ])
        # Una clave futura/inesperada de contexto tampoco puede cambiar
        # silenciosamente entre variantes: el emparejamiento es estricto.
        with self.assertRaisesRegex(ValueError, "entradas diferentes"):
            reval.summarize([
                {**sample("c1", "Texto", "Vale", variant="baseline"), "author_id": "A"},
                {**sample("c1", "Texto", "Bien", variant="A"), "author_id": "B"},
            ])

    def test_repeated_generations_need_explicit_sample_id(self):
        first = sample("c1", "Empiezo la saga", "Jaja, bien", variant="baseline")
        second = {**sample("c1", "Empiezo la saga", "Qué emoción", variant="baseline"),
                  "sample_id": "2"}
        report = reval.summarize([first, second])
        self.assertEqual(report["variants"]["baseline"]["cases"], 2)
        self.assertFalse(report["pairing"]["all_variants_fully_matched"])
        with self.assertRaisesRegex(ValueError, "repetidos"):
            reval.summarize([first, sample("c1", "Empiezo la saga", "Otra", variant="baseline")])

    def test_missing_reply_is_not_an_abstention(self):
        row = sample("c1", "Texto válido", None)
        del row["reply"]
        with self.assertRaisesRegex(ValueError, "reply"):
            reval.summarize([row])
        accepted = reval.summarize([sample("c1", "Texto válido", None)])
        self.assertEqual(accepted["all"]["null"], 1)

    def test_empty_dataset_does_not_invent_percentage(self):
        out = reval.summarize([])
        self.assertEqual(out["all"]["cases"], 0)
        self.assertIsNone(out["all"]["answer_share"])
        self.assertEqual(out["variants"], {})

    def test_cli_accepts_windows_utf8_bom_without_leaking_corpus(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "cases.json"
            path.write_text("\ufeff" + json.dumps({"cases": [
                sample("caso", "Piñones y fantasía", None)
            ]}, ensure_ascii=False), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = reval.main([str(path)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["all"]["null"], 1)
            self.assertNotIn("Piñones", stdout.getvalue())

    def test_cli_returns_aggregate_json_only(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "casos.json"
            path.write_text(json.dumps({"cases": [
                sample("1", "Novedad literaria", "Uf, qué ganas", network="x"),
            ]}, ensure_ascii=False), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = reval.main([str(path)])
            self.assertEqual(code, 0)
            output = json.loads(stdout.getvalue())
            self.assertEqual(output["by_variant_network"]["baseline/x"]["answers"], 1)
            self.assertNotIn("Novedad literaria", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
