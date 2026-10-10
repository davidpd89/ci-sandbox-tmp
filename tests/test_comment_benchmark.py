"""Pruebas únicamente sintéticas y offline; no se abre ninguna red social."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import comment_benchmark as b


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = ROOT / "tests" / "fixtures" / "comment_benchmark_synthetic.json"
        cls.cases, cls.candidates = b.load_dataset(cls.fixture)

    def _temp_data(self, mutate):
        data = json.loads(self.fixture.read_text(encoding="utf-8"))
        mutate(data)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "fixture.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def test_nine_networks_four_scenarios_two_strategies(self):
        self.assertEqual(len(self.cases), 36)
        self.assertEqual(len(self.candidates), 72)
        self.assertEqual({c["network"] for c in self.cases}, set(b.NETWORKS))
        for network in b.NETWORKS:
            self.assertEqual({c["kind"] for c in self.cases if c["network"] == network}, set(b.KINDS))
        self.assertEqual({x["strategy"] for x in self.candidates}, {"baseline_generic", "contextual"})

    def test_auto_report_is_diagnostic_not_subjective_judge(self):
        result = b.evaluate(self.cases, self.candidates)
        self.assertEqual(result["human"]["status"], "pending")
        self.assertEqual(result["human"]["winners"], [])
        summary = result["summary"]
        self.assertEqual(len(summary), 18)
        baseline = [r for r in summary if r["strategy"] == "baseline_generic"]
        contextual = [r for r in summary if r["strategy"] == "contextual"]
        self.assertEqual(sum(x["total"] for x in baseline), 36)
        self.assertGreater(sum(x["anchor_hits"] for x in contextual), sum(x["anchor_hits"] for x in baseline))
        self.assertTrue(all("formats" in r and "details" in r for r in summary))

    def test_blind_export_no_strategy_or_id_or_label_leak(self):
        blind, key = b.prepare_blind(self.cases, self.candidates, "controlled-salt")
        self.assertEqual(len(blind), 72)
        self.assertEqual(len({r["token"] for r in blind}), 72)
        self.assertEqual(blind, b.prepare_blind(self.cases, self.candidates, "controlled-salt")[0])
        self.assertNotEqual(blind[0]["token"], b.prepare_blind(self.cases, self.candidates, "another-salt")[0][0]["token"])
        self.assertTrue(all(not r["judge"] and not r["naturalidad"] for r in blind))
        self.assertTrue(all("strategy" not in r and "case_id" not in r for r in blind))
        self.assertEqual(set(key[0]), set(b.KEY_COLUMNS))

    def test_two_independent_evaluators_enable_paired_results(self):
        invalid = [(x['case_id'], b._valid(x['reply'], next(c['network'] for c in self.cases if c['id'] == x['case_id']))[1]) for x in self.candidates if x['strategy'] == 'contextual' and not b._valid(x['reply'], next(c['network'] for c in self.cases if c['id'] == x['case_id']))[0]]
        self.assertEqual(invalid, [], invalid)
        blind, key = b.prepare_blind(self.cases, self.candidates, "review")
        lookup = {r["token"]: r for r in key}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ratings.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=b.COLUMNS)
                writer.writeheader()
                for row in blind:
                    score = 4 if lookup[row["token"]]["strategy"] == "contextual" else 1
                    for judge in ("a", "b"):
                        writer.writerow({**row, "judge": judge, **{axis: score for axis in b.AXES}})
            result = b.evaluate(self.cases, self.candidates, str(path), salt="review")
            self.assertEqual(result["human"]["fully_paired_cases"], 36)
            self.assertEqual(len(result["human"]["winners"]), 9)
            self.assertEqual({r["strategy"] for r in result["human"]["winners"]}, {"contextual"})
            self.assertTrue(all(r["reviewers_min"] == 2 for r in result["human"]["winners"]))

    def test_partial_one_judge_or_unpaired_cannot_pick_winner(self):
        blind, key = b.prepare_blind(self.cases, self.candidates, "review")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ratings.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=b.COLUMNS)
                writer.writeheader()
                for row in blind:
                    writer.writerow({**row, "judge": "only-one", **{axis: 4 for axis in b.AXES}})
            result = b.evaluate(self.cases, self.candidates, str(path), salt="review")
            self.assertEqual(result["human"]["winners"], [])

    def test_duplicate_judge_and_out_of_range_are_rejected(self):
        blind, _ = b.prepare_blind(self.cases, self.candidates, "review")
        base = {**blind[0], "judge": "a", **{axis: 2 for axis in b.AXES}}
        for rows in ([base, base], [{**base, "aporte": "5"}], [{**base, "aporte": "2.1"}],
                     [{**base, "token": "invalid"}], [{**base, "judge": ""}]):
            with self.subTest(rows=rows):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "ratings.csv"
                    with path.open("w", encoding="utf-8", newline="") as handle:
                        writer = csv.DictWriter(handle, fieldnames=b.COLUMNS)
                        writer.writeheader()
                        writer.writerows(rows)
                    with self.assertRaises(ValueError):
                        b.evaluate(self.cases, self.candidates, str(path), salt="review")

    def test_adversarial_unbalanced_cohorts_and_invalid_winner_cannot_win(self):
        for condition in ("missing_variant", "invalid_best"):
            with self.subTest(condition=condition):
                candidates = [dict(x) for x in self.candidates]
                if condition == "missing_variant":
                    candidates = [x for x in candidates if not
                                  (x["case_id"] == "x_conversacion" and x["strategy"] == "contextual")]
                else:
                    for candidate in candidates:
                        if candidate["case_id"] == "x_conversacion" and candidate["strategy"] == "contextual":
                            candidate["reply"] = "¡Qué gran reflexión!"
                blind, key = b.prepare_blind(self.cases, candidates, "adversarial")
                lookup = {row["token"]: row["strategy"] for row in key}
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "ratings.csv"
                    with path.open("w", encoding="utf-8", newline="") as handle:
                        writer = csv.DictWriter(handle, fieldnames=b.COLUMNS)
                        writer.writeheader()
                        for row in blind:
                            score = 4 if lookup[row["token"]] == "contextual" else 1
                            for judge in ("r1", "r2"):
                                writer.writerow({**row, "judge": judge, **{axis: score for axis in b.AXES}})
                    winners = b.evaluate(self.cases, candidates, str(path), salt="adversarial")["human"]["winners"]
                    self.assertNotIn("x", {winner["network"] for winner in winners})
                    self.assertEqual(len(winners), 8)

    def test_validation_rejects_stale_future_naive_and_duplicates(self):
        alterations = [
            lambda d: d["cases"][0].update(published_at="2026-09-01T00:00:00+02:00"),
            lambda d: d["cases"][0].update(published_at="2026-10-11T00:00:00+02:00"),
            lambda d: d["cases"][0].update(as_of="2026-10-10T04:00:00"),
            lambda d: d["cases"].append(d["cases"][0].copy()),
            lambda d: d["candidates"].append(d["candidates"][0].copy()),
            lambda d: d["cases"][0].update(network="linkedin"),
            lambda d: d["cases"][0].update(anchors=[]),
            lambda d: d["candidates"][0].update(reply=123),
            lambda d: d["candidates"][0].update(case_id="nonexistent"),
        ]
        for change in alterations:
            with self.subTest(change=str(change)):
                with self.assertRaises(ValueError):
                    b.load_dataset(self._temp_data(change))

    def test_validation_abstention_bad_text_and_instagram_limit(self):
        self.assertEqual(b._valid(None, "x"), (False, "abstencion"))
        self.assertFalse(b._valid("Un texto " * 40, "instagram")[0])
        self.assertFalse(b._valid("Sígueme en mi perfil", "threads")[0])
        self.assertFalse(b._valid("¡Qué gran reflexión!", "x")[0])
        self.assertTrue(b._valid("¿El farero escribió las cartas?", "tiktok")[0])

    def test_prompt_uses_network_and_untrusted_post_without_social_action(self):
        for case in self.cases:
            p = b.prompt_context(case)
            self.assertIn(case["network"], p)
            self.assertIn(case["post"], p)
            self.assertIn("null", p)
            self.assertNotIn("publica este comentario", p)

    def test_cli_prepare_evaluate_and_overwrite_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            blind, key = Path(directory) / "blind.csv", Path(directory) / "key.csv"
            cmd = [sys.executable, str(ROOT / "tools" / "comment_benchmark.py")]
            env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
            base = [*cmd, "prepare", "--input", str(self.fixture), "--blind", str(blind), "--key", str(key)]
            first = subprocess.run(base, capture_output=True, text=True, env=env)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(len(list(csv.DictReader(blind.open(encoding="utf-8")))), 72)
            self.assertEqual(subprocess.run(base, capture_output=True, text=True, env=env).returncode, 2)
            result = subprocess.run([*cmd, "evaluate", "--input", str(self.fixture)], capture_output=True, text=True, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["human"]["winners"], [])

    def test_coincident_paths_rejected_without_touching_input(self):
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory) / "key.csv"
            result = b.main(["prepare", "--input", str(self.fixture), "--blind", str(self.fixture), "--key", str(key)])
            self.assertEqual(result, 2)
            self.assertFalse(key.exists())


if __name__ == "__main__":
    unittest.main()
