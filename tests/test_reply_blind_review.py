"""PR #90: revisión ciega de respuestas sintéticas; nunca abre cuentas ni usa red."""
import csv
import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reply_blind_review as blind


def make(case_id="c1", *, net="bluesky", post="He terminado el tomo dos",
         context="complete", category="new_post", reply_a="Uf, ese segundo tomo",
         reply_b="¿Qué te ha parecido el final?"):
    base = {"case_id": case_id, "network": net, "post": post,
            "source_permission": "synthetic", "context_status": context,
            "interaction_type": category, "thread": [], "reply_to_us": False,
            "media_context": None}
    return [dict(base, variant="baseline", reply=reply_a),
            dict(base, variant="H1", reply=reply_b)]


def fill(sheet, *, should_reply="yes", preference="left"):
    for row in sheet:
        row["should_reply"] = should_reply
        row["preference"] = preference
        for side in ("left", "right"):
            for category in blind.CATEGORIES:
                row[f"{category}_{side}"] = "" if row[f"{side}_abstained"] == "yes" else "2"
    return sheet


class BlindReviewTests(unittest.TestCase):
    def test_blind_pairing_balances_order_without_exposing_variant(self):
        data = sum((make(str(n), net=("x" if n % 2 else "reddit")) for n in range(8)), [])
        sheet, key = blind.prepare(data, seed=90)
        self.assertEqual(len(sheet), 8)
        self.assertEqual(sum(x["left"] == "baseline" for x in key["rows"].values()), 4)
        self.assertEqual({x["review_id"] for x in sheet}, set(key["rows"]))
        self.assertTrue(all("variant" not in x and "case_id" not in x for x in sheet))
        self.assertEqual((sheet, key), blind.prepare(data, seed=90))

    def test_pairing_permissions_context_and_categories(self):
        with self.assertRaisesRegex(ValueError, "variantes"):
            blind.prepare(make()[:1])
        with self.assertRaisesRegex(ValueError, "permission"):
            blind.prepare([{**x, "source_permission": ""} for x in make()])
        with self.assertRaisesRegex(ValueError, "interaction_type"):
            blind.prepare([{**x, "interaction_type": "texto privado"} for x in make()])
        with self.assertRaisesRegex(ValueError, "variantes"):
            blind.prepare([])
        with self.assertRaisesRegex(ValueError, "entradas diferentes"):
            pair = make()
            pair[1]["thread"] = ["Otro hilo"]
            blind.prepare(pair)
        with self.assertRaisesRegex(ValueError, "contradicción"):
            blind.prepare([{**x, "context_status": "visual_unverified",
                            "visual_verified": True} for x in make()])

    def test_length_strata_are_reported_and_visual_not_verified_is_ineligible(self):
        long_post = " ".join(["historia"] * 45)
        medium_post = " ".join(["cuento"] * 21)
        rows = make("short") + make("medium", post=medium_post) + make("long", post=long_post)
        sheet, key = blind.prepare(rows)
        report = blind.grade(fill(sheet), key)
        self.assertEqual(report["coverage"]["by_length_bucket"],
                         {"long": 1, "medium": 1, "short": 1})
        with self.assertRaisesRegex(ValueError, "visual no verificado"):
            blind.prepare(make(category="visual", context="complete"))

    def test_null_is_an_explicit_decision_not_a_pseudo_reply(self):
        sheet, key = blind.prepare(make(reply_a=None))
        report = blind.grade(fill(sheet, should_reply="no"), key)
        self.assertEqual(report["coverage"]["complete_context"], 1)
        self.assertEqual(report["decision"]["baseline"]["correct"], 1)
        self.assertEqual(report["rubric"]["baseline"]["pertinencia"]["count"], 0)

    def test_visual_or_partial_context_excluded_from_quality(self):
        for state in ("visual_unverified", "partial"):
            with self.subTest(state=state):
                sheet, key = blind.prepare(make(context=state))
                report = blind.grade(fill(sheet), key)
                self.assertEqual(report["coverage"]["excluded_incomplete_context"], 1)
                self.assertEqual(sum(report["preference"]["wins"].values()), 0)

    def test_rejects_tampered_content_missing_scores_and_duplicates(self):
        sheet, key = blind.prepare(make())
        fill(sheet)
        sheet[0]["reply_left"] = "publicidad"
        with self.assertRaisesRegex(ValueError, "alterado"):
            blind.grade(sheet, key)
        sheet, key = blind.prepare(make())
        with self.assertRaisesRegex(ValueError, "obligatorio"):
            blind.grade(sheet, key)
        with self.assertRaisesRegex(ValueError, "faltan filas"):
            blind.grade([], key)
        with self.assertRaisesRegex(ValueError, "duplicado"):
            blind.grade(fill(sheet) * 2, key)

    def test_csv_bom_unicode_crlf_and_spreadsheet_formula_safety(self):
        pair = make(post='=HYPERLINK("https://example.invalid")',
                    reply_a="+1 bonito", reply_b="@contacto")
        sheet, key = blind.prepare(pair)
        self.assertTrue(sheet[0]["post"].startswith("'="))
        self.assertTrue(sheet[0]["reply_left"].startswith("'"))
        raw = blind._csv(sheet)
        self.assertTrue(raw.startswith("\ufeff"))
        self.assertIn("\r\n", raw)
        parsed = list(csv.DictReader(io.StringIO(raw.lstrip("\ufeff"), newline="")))
        self.assertEqual(parsed[0]["post"], sheet[0]["post"])
        self.assertEqual(blind.grade(fill(parsed), key)["coverage"]["reviewed"], 1)

    def test_cli_round_trip_aggregate_only_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            inp, sheet_path, key_path = (root / name for name in
                                         ("input.json", "review.csv", "key.json"))
            inp.write_text(json.dumps({"cases": make(post="Texto privado de prueba ñ")},
                                      ensure_ascii=False), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(blind.main(["prepare", str(inp), "--sheet", str(sheet_path),
                                             "--key", str(key_path)]), 0)
            self.assertNotIn("Texto privado", output.getvalue())
            with sheet_path.open(encoding="utf-8-sig", newline="") as f:
                sheet = list(csv.DictReader(f))
            fill(sheet)
            with sheet_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=blind.COLUMNS)
                writer.writeheader()
                writer.writerows(sheet)
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(blind.main(["score", str(sheet_path),
                                             "--key", str(key_path)]), 0)
            self.assertIn("complete_context", output.getvalue())
            self.assertNotIn("Texto privado", output.getvalue())
            with self.assertRaises(SystemExit):
                blind.main(["prepare", str(inp), "--sheet", str(sheet_path),
                            "--key", str(key_path)])

    def test_identical_replies_or_two_nulls_cannot_manufacture_a_win(self):
        for identical in (None, "La misma respuesta"):
            with self.subTest(identical=identical):
                sheet, key = blind.prepare(make(reply_a=identical, reply_b=identical))
                with self.assertRaisesRegex(ValueError, "idénticas"):
                    blind.grade(fill(sheet, preference="left"), key)
                report = blind.grade(fill(sheet, preference="tie"), key)
                self.assertEqual(report["preference"]["tie"], 1)
                self.assertEqual(sum(report["preference"]["wins"].values()), 0)

    def test_csv_extra_columns_and_duplicate_header_rejected(self):
        sheet, key = blind.prepare(make())
        fill(sheet)
        with self.assertRaisesRegex(ValueError, "extra"):
            blind.grade([{**sheet[0], None: ["dato inesperado"]}], key)
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            key_path, sheet_path = root / "key.json", root / "review.csv"
            key_path.write_text(json.dumps(key), encoding="utf-8")
            # Duplicamos la cabecera y el valor al final: DictReader anterior
            # silenciaba la duplicación y aun así puntuaba la hoja.
            source = list(csv.reader(io.StringIO(blind._csv(sheet).lstrip("\ufeff"))))
            source[0].append("review_id")
            source[1].append(source[1][0])
            with sheet_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerows(source)
            with self.assertRaises(SystemExit) as error:
                blind.main(["score", str(sheet_path), "--key", str(key_path)])
            self.assertEqual(error.exception.code, 2)

    def test_fullwidth_formula_and_leading_control_are_escaped(self):
        for text in ("＝1+2", "＋SUM(1;2)", "－42", "＠usuario",
                     "\ttexto", "\rtexto", "\ntexto", "  ＝1+2"):
            with self.subTest(text=text):
                self.assertTrue(blind._excel_safe(text).startswith("'"))
        self.assertEqual(blind._excel_safe("¿Qué estás leyendo, ñ?"),
                         "¿Qué estás leyendo, ñ?")

    def test_multiple_samples_same_post_and_unicode(self):
        pairs = make(post="¿Mañana?\n¡Sí!", reply_a="Qué alegría", reply_b="Me lo apunto")
        for row in pairs:
            row["sample_id"] = "b"
        other = make(post="¿Mañana?\n¡Sí!", reply_a="¡Qué bien!", reply_b="Ostras, genial")
        for row in other:
            row["sample_id"] = "a"
        sheet, key = blind.prepare(pairs + other)
        self.assertEqual(len(sheet), 2)
        self.assertEqual(blind.grade(fill(sheet), key)["coverage"]["reviewed"], 2)


if __name__ == "__main__":
    unittest.main()
