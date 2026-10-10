"""R2 / F1+F9: el guard común nunca deja una reply vacía al preflight.

Una respuesta sin texto antes se dejaba pasar porque `if item.get("text")`
era falso: el ejecutor rechazaba el lote entero por un solo elemento inválido.
"""
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reply_writer as rw


class GuardBeforePreflightTests(unittest.TestCase):
    def test_empty_missing_or_wrong_type_reply_skipped_but_like_survives(self):
        plan = [
            {"kind": "reply", "url": "https://example.invalid/p1", "text": ""},
            {"kind": "comment", "url": "https://example.invalid/p2"},
            {"kind": "comment_external", "url": "https://example.invalid/p3", "text": None},
            {"kind": "quote", "url": "https://example.invalid/p4", "text": 42},
            {"kind": "like", "url": "https://example.invalid/p5"},
            {"kind": "reply", "url": "https://example.invalid/p6", "text": "Una respuesta válida"},
        ]
        logs = []
        with mock.patch.dict(os.environ, {"RRSS_ALLOW_UNMARKED_TEXT": ""}):
            with mock.patch.object(rw, "is_gpt", return_value=True):
                kept = rw.require_gpt(plan, "bluesky", log=logs.append)
        self.assertEqual([r["url"] for r in kept],
                         ["https://example.invalid/p5", "https://example.invalid/p6"])
        self.assertTrue(any("texto_vacio" in line for line in logs))

    def test_manual_exception_does_not_override_empty_text(self):
        plan = [{"kind": "reply", "text": "  ", "authored": "manual"},
                {"kind": "reply", "text": "Respuesta manual revisada", "authored": "manual"}]
        with mock.patch.dict(os.environ, {"RRSS_ALLOW_UNMARKED_TEXT": ""}):
            kept = rw.require_gpt(plan, "reddit", log=lambda _: None)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["text"], "Respuesta manual revisada")

    def test_unmarked_nonempty_keeps_existing_provenance_block(self):
        plan = [{"kind": "reply", "text": "Inventado sin ChatGPT"},
                {"kind": "follow", "handle": "lectora"}]
        with mock.patch.dict(os.environ, {"RRSS_ALLOW_UNMARKED_TEXT": ""}):
            with mock.patch.object(rw, "is_gpt", return_value=False):
                kept = rw.require_gpt(plan, "x", log=lambda _: None)
        self.assertEqual(kept, [plan[1]])

    def test_non_text_action_is_not_flagged(self):
        plan = [{"kind": "follow", "handle": "lectora"},
                {"kind": "like", "url": "https://example.invalid"}]
        with mock.patch.dict(os.environ, {"RRSS_ALLOW_UNMARKED_TEXT": ""}):
            self.assertEqual(rw.require_gpt(plan, "threads"), plan)


if __name__ == "__main__":
    unittest.main()
