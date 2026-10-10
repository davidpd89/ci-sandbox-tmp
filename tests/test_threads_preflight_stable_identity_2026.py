"""Identidad común de acciones: una respuesta Threads API usa su ID de destino.

Pruebas sin red, tokens, navegador ni publicaciones. La guardia de estilo
permanece en el preflight real; solo se neutraliza el historial local de frases.
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import scan_common as sc
import threads_execute as te


class StableTargetIdentityTests(unittest.TestCase):
    def reply(self, target, answer, *, handle="lectora", fragment="¿Cuál de estos libros recomiendas?"):
        return {
            "handle": handle,
            "kind": "reply",
            "reply_to_id": target,
            "post_text": fragment,
            "text_fragment": fragment,
            "text": answer,
            "post_created_at": "2026-10-10T09:00:00+00:00",
        }

    def preflight(self, items):
        with patch.object(te.dup, "check", return_value=[]):
            return te._preflight_plan(items)

    def test_two_distinct_api_ids_with_identical_excerpt_are_allowed(self):
        a = self.reply("post-100", "El primero tiene un final memorable.")
        b = self.reply("post-200", "El segundo tiene personajes interesantes.")
        validated = self.preflight([a, b])
        self.assertEqual([item["reply_to_id"] for item in validated],
                         ["post-100", "post-200"])

    def test_identical_api_id_is_duplicate_even_with_different_excerpt_and_handle(self):
        a = self.reply("post-100", "El primero tiene un final memorable.")
        b = self.reply("post-100", "También recomiendo la segunda entrega.",
                       handle="otra_lectora", fragment="¿Qué novela eliges?")
        with self.assertRaisesRegex(ValueError, "accion duplicada"):
            self.preflight([a, b])

    def test_browser_fallback_still_blocks_same_excerpt_and_author(self):
        a = self.reply("post-100", "El primero tiene un final memorable.")
        b = self.reply("post-200", "El segundo tiene personajes interesantes.")
        a.pop("reply_to_id")
        b.pop("reply_to_id")
        with self.assertRaisesRegex(ValueError, "accion duplicada"):
            self.preflight([a, b])

    def test_shared_key_preserves_opaque_id_and_fallback(self):
        a = self.reply("AbC-9", "El primero tiene un final memorable.")
        b = self.reply("abc-9", "El segundo tiene personajes interesantes.")
        self.assertNotEqual(
            sc.plan_action_duplicate_key(a, stable_target_fields=("reply_to_id",)),
            sc.plan_action_duplicate_key(b, stable_target_fields=("reply_to_id",)),
        )
        a.pop("reply_to_id")
        b.pop("reply_to_id")
        self.assertEqual(
            sc.plan_action_duplicate_key(a, stable_target_fields=("reply_to_id",)),
            sc.plan_action_duplicate_key(b, stable_target_fields=("reply_to_id",)),
        )


if __name__ == "__main__":
    unittest.main()
