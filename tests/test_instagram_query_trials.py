"""Pruebas offline del banco experimental de consultas de Instagram."""
import ast
import csv
import datetime
import os
import pathlib
import tempfile
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "instagram_scan.py"


def load_helpers():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    wanted_functions = {
        "_rotate_queries",
        "_record_trial_result",
        "_trial_summary",
        "_eligible_candidate",
        "_process_query_results",
    }
    wanted_constants = {"QUERY_POOL", "TRIAL_QUERY_POOL", "AI_CONTENT_SIGNALS"}

    nodes = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = {
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if names & wanted_constants:
                nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted_functions:
            nodes.append(node)

    env = {
        "csv": csv,
        "datetime": datetime,
        "os": os,
        "sc": type(
            "SC",
            (),
            {
                "is_valid_candidate": staticmethod(
                    lambda handle, text, my_handle, discarded:
                    handle != my_handle and handle not in discarded
                )
            },
        ),
    }
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"),
        env,
    )
    return env


class InstagramTrialTests(unittest.TestCase):
    def test_rotation_keeps_all_verified_before_one_trial(self):
        env = load_helpers()
        rotated = env["_rotate_queries"](99)
        verified = [q for q, status in rotated if status == "validada"]
        trials = [q for q, status in rotated if status == "prueba_no_validada"]

        self.assertEqual(len(verified), len(env["QUERY_POOL"]))
        self.assertEqual(len(set(verified)), len(env["QUERY_POOL"]))
        self.assertEqual(len(trials), 1)
        self.assertIn(trials[0], env["TRIAL_QUERY_POOL"])

    def test_summary_uses_latest_run_per_day(self):
        env = load_helpers()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "trials.csv")
            rec = env["_record_trial_result"]
            rec(path, "fantasía", 10, 2, date="2026-09-25")
            rec(path, "fantasía", 8, 4, date="2026-09-25")
            rec(path, "fantasía", 6, 3, date="2026-09-26")
            self.assertEqual(
                env["_trial_summary"](path, "fantasía"),
                {"days": 2, "discovered": 14, "eligible": 7},
            )

    def test_summary_accepts_legacy_aceptadas_header(self):
        env = load_helpers()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "trials.csv")
            with open(path, "w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["fecha", "query", "descubiertas", "aceptadas"])
                writer.writerow(["2026-09-25", "fantasía", "5", "3"])
            self.assertEqual(
                env["_trial_summary"](path, "fantasía"),
                {"days": 1, "discovered": 5, "eligible": 3},
            )

    def test_summary_skips_invalid_dates_and_clamps_corrupt_counts(self):
        env = load_helpers()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "trials.csv")
            with open(path, "w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(["fecha", "query", "descubiertas", "elegibles"])
                writer.writerow(["fecha-mala", "fantasía", "99", "99"])
                writer.writerow(["2026-09-25", "fantasía", "2", "99"])
                writer.writerow(["2026-09-26", "fantasía", "-5", "-3"])
            self.assertEqual(
                env["_trial_summary"](path, "fantasía"),
                {"days": 2, "discovered": 2, "eligible": 2},
            )

    def test_record_rejects_invalid_identity_and_clamps_eligible(self):
        env = load_helpers()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "trials.csv")
            rec = env["_record_trial_result"]
            with self.assertRaises(ValueError):
                rec(path, "", 1, 1, date="2026-09-25")
            with self.assertRaises(ValueError):
                rec(path, "fantasía", 1, 1, date="25/09/2026")

            rec(path, "fantasía", 2, 99, date="2026-09-25")
            self.assertEqual(
                env["_trial_summary"](path, "fantasía")["eligible"],
                2,
            )

    def test_quality_filter_rejects_empty_self_discarded_and_ai(self):
        env = load_helpers()
        eligible = env["_eligible_candidate"]
        self.assertFalse(
<<<<<<< HEAD
            eligible("lectora", "", my_handle="autorademodiaz", discarded=set())
        )
        self.assertFalse(
            eligible(
                "autorademodiaz",
                "bio",
                my_handle="autorademodiaz",
=======
            eligible("lectora", "", my_handle="davidportodiaz", discarded=set())
        )
        self.assertFalse(
            eligible(
                "davidportodiaz",
                "bio",
                my_handle="davidportodiaz",
>>>>>>> origin/research/public-reuse-parent
                discarded=set(),
            )
        )
        self.assertFalse(
            eligible(
                "descartada",
                "Club de lectura",
<<<<<<< HEAD
                my_handle="autorademodiaz",
=======
                my_handle="davidportodiaz",
>>>>>>> origin/research/public-reuse-parent
                discarded={"descartada"},
            )
        )
        self.assertFalse(
            eligible(
                "lectora",
                "Perfil con contenido generado con IA",
<<<<<<< HEAD
                my_handle="autorademodiaz",
=======
                my_handle="davidportodiaz",
>>>>>>> origin/research/public-reuse-parent
                discarded=set(),
            )
        )
        self.assertTrue(
            eligible(
                "lectora",
                "Club de lectura de fantasía",
<<<<<<< HEAD
                my_handle="autorademodiaz",
=======
                my_handle="davidportodiaz",
>>>>>>> origin/research/public-reuse-parent
                discarded=set(),
            )
        )

    def test_trial_measurement_never_calls_emit_or_creates_novel_candidates(self):
        env = load_helpers()
        calls = []

        def forbidden_emit(*args):
            calls.append(args)
            raise AssertionError("Una trial no debe emitir candidatos")

        discovered = (
            row
            for row in [
                ("Lectora", "Club de lectura de fantasía"),
<<<<<<< HEAD
                ("autorademodiaz", "Mi perfil"),
=======
                ("davidportodiaz", "Mi perfil"),
>>>>>>> origin/research/public-reuse-parent
                ("robot", "Perfil con contenido generado con IA"),
            ]
        )
        result = env["_process_query_results"](
            discovered,
<<<<<<< HEAD
            my_handle="autorademodiaz",
=======
            my_handle="davidportodiaz",
>>>>>>> origin/research/public-reuse-parent
            discarded=set(),
            operational=False,
            emit=forbidden_emit,
            source="no-debe-usarse",
        )

        self.assertEqual(result["discovered"], 3)
        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["novel"], 0)
        self.assertEqual(calls, [])
        self.assertEqual(result["eligible_rows"][0][0], "Lectora")

    def test_operational_query_emits_only_eligible_rows(self):
        env = load_helpers()
        emitted = []

        def emit(source, handle, text):
            emitted.append((source, handle, text))
            return handle.casefold() != "repetida"

        result = env["_process_query_results"](
            [
                ("Nueva", "Autora de fantasía"),
                ("Repetida", "Club de lectura"),
                ("robot", "Contenido de IA"),
<<<<<<< HEAD
                ("autorademodiaz", "Mi cuenta"),
            ],
            my_handle="autorademodiaz",
=======
                ("davidportodiaz", "Mi cuenta"),
            ],
            my_handle="davidportodiaz",
>>>>>>> origin/research/public-reuse-parent
            discarded=set(),
            operational=True,
            emit=emit,
            source="busqueda:validada",
        )

        self.assertEqual(result["discovered"], 4)
        self.assertEqual(result["eligible"], 2)
        self.assertEqual(result["novel"], 1)
        self.assertEqual(
            [h for _, h, _ in emitted],
            ["Nueva", "Repetida"],
        )

    def test_operational_query_requires_emitter_and_source(self):
        env = load_helpers()
        with self.assertRaises(ValueError):
            env["_process_query_results"](
                [("lectora", "Fantasía")],
<<<<<<< HEAD
                my_handle="autorademodiaz",
=======
                my_handle="davidportodiaz",
>>>>>>> origin/research/public-reuse-parent
                discarded=set(),
                operational=True,
            )


if __name__ == "__main__":
    unittest.main()
