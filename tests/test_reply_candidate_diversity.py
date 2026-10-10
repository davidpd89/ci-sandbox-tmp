"""Offline regression tests for #114; no remote access or social effects."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import reply_candidate_diversity as quality
from vendor.distinct_n_compat import (distinct_n_corpus_level,
                                      distinct_n_pooled, ngrams)


class DiversityTests(unittest.TestCase):
    def test_upstream_semantics_and_short_sequence_fix(self):
        self.assertEqual(list(ngrams(["a", "b", "c"], 2)), [("a", "b"), ("b", "c")])
        self.assertEqual(list(ngrams(["a"], 3)), [])
        self.assertEqual(distinct_n_corpus_level([], 2), 0.0)
        self.assertEqual(distinct_n_pooled([["a", "b"], ["a", "b"]], 2), .5)
        self.assertEqual(distinct_n_pooled([["a"], ["b"]], 2), 0.0)
        self.assertAlmostEqual(distinct_n_corpus_level([["a", "b", "a"]], 1), 2/3)
        for n in (0, -1, 1.2, True):
            with self.subTest(n=n), self.assertRaises(ValueError):
                list(ngrams(["x"], n))

    def test_nine_networks_and_reddit_micro(self):
        for network in quality.NETWORK_LIMITS:
            with self.subTest(network=network):
                out = quality.select_approved(network, [{"text": "Qué giro tan raro", "context_approved": True}])
                self.assertEqual(out["selected_index"], 0)
                self.assertTrue(out["requires_external_preflight"])

    def test_explicit_abstention_when_no_context_approval(self):
        out = quality.select_approved("x", [
            {"text": "Qué giro tan raro"}, {"text": "Qué final tan raro", "context_approved": False}])
        self.assertIsNone(out["selected_index"])
        self.assertEqual(out["rejected"]["contexto_no_aprobado"], 2)

    def test_duplicate_normalization_diacritics_and_recent(self):
        c = [{"text": "Qué sorpresa tan grande", "context_approved": True},
             {"text": "Que sorpresa tan grande", "context_approved": True},
             {"text": "Qué desenlace tan raro", "context_approved": True}]
        res = quality.select_approved("bluesky", c, ["QUÉ sorpresa tan grande"])
        self.assertEqual(res["selected_index"], 2)
        self.assertEqual(res["rejected"]["repeticion"], 2)

    def test_most_novel_approved_wins(self):
        c = [{"text": "Qué portada tan curiosa", "context_approved": True},
             {"text": "Me intriga ese desenlace", "context_approved": True}]
        out = quality.select_approved("threads", c, ["Qué portada tan bonita"])
        self.assertEqual(out["selected_index"], 1)
        self.assertGreater(out["max_novelty"], 0.8)

    def test_preflight_callback_is_enforced(self):
        calls = []
        def validator(text, network, recent):
            calls.append((text, network, recent))
            return (text.startswith("Me"), "blocked")
        c = [{"text": "Qué final tan raro", "context_approved": True},
             {"text": "Me intriga ese desenlace", "context_approved": True}]
        out = quality.select_approved("facebook", c, validator=validator)
        self.assertEqual(out["selected_index"], 1)
        self.assertEqual(out["rejected"]["preflight"], 1)
        self.assertEqual(len(calls), 2)
        self.assertIsNone(quality.select_approved("x", c, validator=lambda *args: None)["selected_index"])

    def test_format_and_unknown_network_are_rejected(self):
        for s in ["Hola", "a" * 240, "Visita https://x.com", "#libros para hoy", "Hola\nqué tal"]:
            with self.subTest(s=s):
                x = quality.select_approved("tiktok", [{"text": s, "context_approved": True}])
                self.assertIsNone(x["selected_index"])
        with self.assertRaises(ValueError):
            quality.select_approved("twitch", [])
        with self.assertRaises(ValueError):
            quality.select_approved("x", [{}] * 17)
        with self.assertRaises(ValueError):
            quality.select_approved("x", [], recent=[None])

    def test_same_batch_duplicate_has_single_winner(self):
        inp = [{"text": "Menuda saga tan larga", "context_approved": True}] * 2
        out = quality.select_approved("reddit", inp)
        self.assertEqual(out["eligible"], 1)
        self.assertEqual(out["rejected"]["repeticion"], 1)

    def test_reject_malformed_cases_and_never_emit_text(self):
        with self.assertRaises(ValueError):
            quality.evaluate_cases({"oops": 1})
        res = quality.evaluate_cases([{"network": "instagram", "candidates": [
            {"text": "Qué edición tan bonita", "context_approved": True}]}])
        self.assertNotIn("edición", json.dumps(res, ensure_ascii=False))
        self.assertEqual(res[0]["selected_index"], 0)

    def test_cli_offline_windows_portable(self):
        payload = [{"network": "pinterest", "candidates": [
            {"text": "La portada tiene fuerza", "context_approved": True}]}]
        with tempfile.TemporaryDirectory() as td:
            file = pathlib.Path(td) / "casos.json"
            file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            cp = subprocess.run([sys.executable, str(ROOT / "tools" / "reply_candidate_diversity.py"),
                                 str(file)], capture_output=True, text=True, check=True)
            obj = json.loads(cp.stdout)
            self.assertEqual(obj["cases"][0]["selected_index"], 0)
            self.assertNotIn("portada", cp.stdout)


if __name__ == "__main__":
    unittest.main()
