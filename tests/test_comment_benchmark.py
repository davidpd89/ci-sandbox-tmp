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

    def _temp_key(self, key):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "key.csv"
        b._write_csv(path, key, b.KEY_COLUMNS)
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
        blind, key = b.prepare_blind(self.cases, self.candidates)
        self.assertEqual(len(blind), 72)
        self.assertEqual(len({r["token"] for r in blind}), 72)
        self.assertNotEqual(blind, b.prepare_blind(self.cases, self.candidates)[0])
        self.assertTrue(all(not r["judge"] and not r["naturalidad"] for r in blind))
        self.assertTrue(all("strategy" not in r and "case_id" not in r for r in blind))
        self.assertEqual(set(key[0]), set(b.KEY_COLUMNS))

    def test_two_independent_evaluators_enable_paired_results(self):
        invalid = [(x['case_id'], b._valid(x['reply'], next(c['network'] for c in self.cases if c['id'] == x['case_id']))[1]) for x in self.candidates if x['strategy'] == 'contextual' and not b._valid(x['reply'], next(c['network'] for c in self.cases if c['id'] == x['case_id']))[0]]
        self.assertEqual(invalid, [], invalid)
        blind, key = b.prepare_blind(self.cases, self.candidates)
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
            result = b.evaluate(self.cases, self.candidates, str(path), key_path=self._temp_key(key))
            self.assertEqual(result["human"]["fully_paired_cases"], 36)
            self.assertEqual(len(result["human"]["winners"]), 9)
            self.assertEqual({r["strategy"] for r in result["human"]["winners"]}, {"contextual"})
            self.assertTrue(all(r["reviewers_min"] == 2 for r in result["human"]["winners"]))

    def test_partial_one_judge_or_unpaired_cannot_pick_winner(self):
        blind, key = b.prepare_blind(self.cases, self.candidates)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ratings.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=b.COLUMNS)
                writer.writeheader()
                for row in blind:
                    writer.writerow({**row, "judge": "only-one", **{axis: 4 for axis in b.AXES}})
            result = b.evaluate(self.cases, self.candidates, str(path), key_path=self._temp_key(key))
            self.assertEqual(result["human"]["winners"], [])

    def test_duplicate_judge_and_out_of_range_are_rejected(self):
        blind, key = b.prepare_blind(self.cases, self.candidates)
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
                        b.evaluate(self.cases, self.candidates, str(path), key_path=self._temp_key(key))

    def test_ratings_reject_altered_text_or_context(self):
        blind, key = b.prepare_blind(self.cases, self.candidates)
        original = {**blind[0], "judge": "reviewer",
                    **{axis: 2 for axis in b.AXES}}
        for field in ("network", "kind", "post", "thread", "reply"):
            with self.subTest(field=field):
                tampered = {**original, field: original[field] + " alterado"}
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / "ratings.csv"
                    with path.open("w", encoding="utf-8", newline="") as handle:
                        writer = csv.DictWriter(handle, fieldnames=b.COLUMNS)
                        writer.writeheader()
                        writer.writerow(tampered)
                    with self.assertRaisesRegex(ValueError, "difieren"):
                        b.evaluate(self.cases, self.candidates, str(path), key_path=self._temp_key(key))

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
                blind, key = b.prepare_blind(self.cases, candidates)
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
                    winners = b.evaluate(self.cases, candidates, str(path), key_path=self._temp_key(key))["human"]["winners"]
                    self.assertNotIn("x", {winner["network"] for winner in winners})
                    self.assertEqual(len(winners), 8)

    def test_four_posts_without_four_editorial_kinds_cannot_win(self):
        # Un cuarto post de literatura no sustituye la categoría conversación.
        cases = [dict(case) for case in self.cases]
        for case in cases:
            if case["id"] == "x_conversacion":
                case["kind"] = "literatura"
        blind, key = b.prepare_blind(cases, self.candidates)
        strategies = {row["token"]: row["strategy"] for row in key}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ratings.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=b.COLUMNS)
                writer.writeheader()
                for row in blind:
                    grade = 4 if strategies[row["token"]] == "contextual" else 1
                    for judge in ("r1", "r2"):
                        writer.writerow({**row, "judge": judge, **{axis: grade for axis in b.AXES}})
            winners = b.evaluate(cases, self.candidates, str(path), key_path=self._temp_key(key))["human"]["winners"]
        self.assertEqual(len(winners), 8)
        self.assertNotIn("x", {row["network"] for row in winners})

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
            blind_dir, key_dir = Path(directory) / "review", Path(directory) / "private"
            blind_dir.mkdir()
            key_dir.mkdir()
            blind, key = blind_dir / "blind.csv", key_dir / "key.csv"
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

    def test_blind_key_is_unpredictable_required_and_dataset_bound(self):
        first, key = b.prepare_blind(self.cases, self.candidates)
        second, _ = b.prepare_blind(self.cases, self.candidates)
        self.assertTrue(set(x["token"] for x in first).isdisjoint(
            x["token"] for x in second))
        with tempfile.TemporaryDirectory() as directory:
            ratings = Path(directory) / "ratings.csv"
            row = {**first[0], "judge": "anotador", **{axis: 2 for axis in b.AXES}}
            with ratings.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=b.COLUMNS)
                writer.writeheader()
                writer.writerow(row)
            with self.assertRaisesRegex(ValueError, "clave privada"):
                b.evaluate(self.cases, self.candidates, str(ratings))
            with self.assertRaises(ValueError):
                b.evaluate(self.cases, self.candidates, str(ratings),
                           key_path=self._temp_key(b.prepare_blind(self.cases, self.candidates)[1]))
            altered = [dict(x) for x in key]
            altered[0]["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "alterada"):
                b.evaluate(self.cases, self.candidates, str(ratings),
                           key_path=self._temp_key(altered))
            changed_cases = [dict(c) for c in self.cases]
            changed_cases[0]["post"] += " reescrito"
            with self.assertRaisesRegex(ValueError, "alterada"):
                b.evaluate(changed_cases, self.candidates, str(ratings),
                           key_path=self._temp_key(key))
            result = b.evaluate(self.cases, self.candidates, str(ratings),
                                key_path=self._temp_key(key))
            self.assertEqual(result["human"]["winners"], [])

    def test_global_duplicate_across_networks_even_if_local_unique(self):
        cases = [dict(c) for c in self.cases]
        candidates = [dict(c) for c in self.candidates]
        chosen = ("x_literatura", "threads_literatura", "mastodon_literatura")
        for c in candidates:
            if c["case_id"] in chosen and c["strategy"] == "baseline_generic":
                c["reply"] = "¿Qué te ha parecido ese final?"
        result = b.automatic(cases, candidates)
        diversity = result["diversity"]
        self.assertGreaterEqual(diversity["global_duplicate_texts"], 2)
        self.assertGreaterEqual(diversity["cross_network_duplicate_texts"], 2)
        self.assertIn("opening_top_share", diversity["lint_metrics"])
        for network in ("x", "threads", "mastodon"):
            row = next(x for x in result["summary"]
                       if x["network"] == network and x["strategy"] == "baseline_generic")
            self.assertEqual(row["duplicate_texts"], 0)

    def test_ratings_reject_extra_columns_and_truncated_rows(self):
        blind, key = b.prepare_blind(self.cases, self.candidates)
        base = {**blind[0], "judge": "lector1",
                **{axis: 2 for axis in b.AXES}}
        with tempfile.TemporaryDirectory() as directory:
            key_path = self._temp_key(key)
            extra = Path(directory) / "extra.csv"
            with extra.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=(*b.COLUMNS, "strategy"))
                writer.writeheader()
                writer.writerow({**base, "strategy": "contextual"})
            with self.assertRaisesRegex(ValueError, "exactamente"):
                b.evaluate(self.cases, self.candidates, str(extra), key_path=key_path)
            broken = Path(directory) / "broken.csv"
            broken.write_text(",".join(b.COLUMNS) + "\n" + "cut-off\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "incompleta"):
                b.evaluate(self.cases, self.candidates, str(broken), key_path=key_path)

    def test_network_specific_fixture_has_distinct_contexts_and_full_parity(self):
        dataset = ROOT / "tests" / "fixtures" / "comment_benchmark_network_specific.json"
        cases, candidates = b.load_dataset(dataset)
        self.assertEqual(len(cases), 36)
        self.assertEqual(len(candidates), 72)
        self.assertEqual({c["network"] for c in cases}, set(b.NETWORKS))
        self.assertEqual(len({c["post"] for c in cases}), 36)
        for network in b.NETWORKS:
            subset = [c for c in cases if c["network"] == network]
            self.assertEqual({c["kind"] for c in subset}, set(b.KINDS))
            self.assertTrue(any(c["thread"] for c in subset if c["kind"] == "conversacion"))
            for case in subset:
                self.assertEqual({x["strategy"] for x in candidates
                                  if x["case_id"] == case["id"]},
                                 {"baseline_generic", "contextual"})
        report = b.evaluate(cases, candidates)
        self.assertEqual(report["human"]["winners"], [])
        self.assertEqual(len(report["summary"]), 18)

    def test_prepare_cli_separates_private_key_from_review(self):
        with tempfile.TemporaryDirectory() as directory:
            same_dir = Path(directory) / "same.csv"
            other = Path(directory) / "key.csv"
            code = b.main(["prepare", "--input", str(self.fixture),
                           "--blind", str(same_dir), "--key", str(other)])
            self.assertEqual(code, 2)
            self.assertFalse(same_dir.exists())
            self.assertFalse(other.exists())


if __name__ == "__main__":
    unittest.main()
