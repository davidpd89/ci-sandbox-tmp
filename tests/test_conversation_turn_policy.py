"""Regresiones de cierre conversacional para todas las redes.

Casos basados en intercambio real de Bluesky, sin datos identificativos.
"""
from __future__ import annotations

import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import conversation_turn_policy as cp

RECENT = dt.datetime.now(dt.timezone.utc).isoformat()


class ConversationTurnsTests(unittest.TestCase):
    def test_example_photo_session_stops_without_question(self):
        for network in ("bluesky", "mastodon", "x", "threads",
                        "facebook", "pinterest", "reddit", "tiktok"):
            for text in ("Gracias, compañero", "¡Gracias, compañera!", "Jajaja"):
                with self.subTest(network=network, text=text):
                    decision, _ = cp.decide_next_turn(
                        text, replying_to_us=True, earlier_own_turns=1,
                        thread_complete=True,
                    )
                    self.assertEqual(decision, "NO_REPLY")

    def test_substantive_non_questions_are_candidates_for_gpt_not_hard_blocked(self):
        for text in (
            "¡Qué ganas de leerlo!",
            "Me ha encantado tu reseña",
            "Parece que la idea está gustando. Si te animas también me dices.",
        ):
            with self.subTest(text=text):
                self.assertEqual(cp.decide_next_turn(text, thread_complete=True)[0], "REPLY")

    def test_partial_context_with_inbound_text_does_not_silence_all_networks(self):
        for net in ("bluesky", "mastodon", "x", "threads",
                    "facebook", "pinterest", "reddit", "tiktok"):
            with self.subTest(network=net):
                self.assertTrue(cp.check_execution(net, {
                    "kind": "reply", "post_created_at": RECENT, "reply_to_us": True,
                    "post_text": "Me ha encantado tu reseña",
                    "context_quality": "partial",
                })[0])
                self.assertFalse(cp.check_execution(net, {
                    "kind": "reply", "post_created_at": RECENT, "reply_to_us": True,
                    "post_text": "Gracias, compañero",
                })[0])

    def test_unverified_thread_never_forces_reply(self):
        result, why = cp.decide_next_turn(
            "¿Te animas a participar?", replying_to_us=True,
            earlier_own_turns=1, thread_complete=False,
        )
        self.assertEqual(result, "NEEDS_CONTEXT")
        self.assertEqual(why, "contexto_parcial_para_GPT")

    def test_question_with_verified_context_may_continue(self):
        decision, _ = cp.decide_next_turn(
            "¿Qué fecha te vendría bien para la sesión de fotos?",
            replying_to_us=True, earlier_own_turns=1,
            thread_complete=True,
        )
        self.assertEqual(decision, "REPLY")

    def test_closers_are_not_turned_into_prompts(self):
        for text in ("Gracias", "Gracias, compañero", "Muchas gracias por todo",
                     "De acuerdo", "Exactamente", "Un abrazo", "Perfecto"):
            self.assertTrue(cp.is_closed_turn(text), text)
        self.assertFalse(cp.is_closed_turn("Gracias, ¿qué libro me recomiendas?"))

    def test_bluesky_thread_parser_gets_root_ours_and_reply_in_order(self):
        import types
        from unittest import mock
        record = lambda uri, who, text, parent=None: {
            "post": {"uri": uri, "author": {"did": who},
                     "record": {"text": text, **({"reply": {"parent": {"uri": parent}}} if parent else {})}},
        }
        root = record("at://root", "someone", "Busco voluntarios para fotos")
        ours = record("at://ours", "did:me", "Ojalá encuentres gente", parent="at://root")
        theirs = record("at://reply", "someone", "¿Qué tipo de fotos tienes previstas?", parent="at://ours")
        ours["parent"] = root
        theirs["parent"] = ours
        fake = types.SimpleNamespace(
            AUTH_BASE="auth",
            _session=lambda: {"did": "did:me"},
            _get=lambda *_args, **_kwargs: {"thread": theirs},
        )
        with mock.patch.dict(sys.modules, {"bluesky_interact": fake}):
            turns = cp.fetch_verified_thread("bluesky", {"ref": "at://reply"})
        self.assertEqual([t["role"] for t in turns], ["theirs", "ours", "theirs"])
        self.assertEqual(turns[1]["text"], "Ojalá encuentres gente")

    def test_bluesky_thread_with_missing_parent_is_not_usable(self):
        import types
        from unittest import mock
        root_missing = {"post": {
            "uri": "at://reply", "author": {"did": "other"},
            "record": {"text": "¿Puedes aclarármelo?",
                       "reply": {"parent": {"uri": "at://ours"}}},
        }}
        fake = types.SimpleNamespace(
            AUTH_BASE="auth", _session=lambda: {"did": "did:me"},
            _get=lambda *_args, **_kwargs: {"thread": root_missing},
        )
        with mock.patch.dict(sys.modules, {"bluesky_interact": fake}):
            self.assertEqual(cp.fetch_verified_thread("bluesky", {"ref": "at://reply"}), [])

    def test_followups_in_all_eight_executors_require_verified_context(self):
        for network in ("bluesky", "mastodon", "x", "threads",
                        "facebook", "pinterest", "reddit", "tiktok"):
            with self.subTest(network=network):
                allowed, reason = cp.check_execution(network, {
                    "kind": "reply", "post_created_at": RECENT, "reply_to_us": True,
                    "motivo": "fidelizacion:contestar_a_su_comentario",
                    "text": "Gracias, compañero.",
                    "thread_turns": [],
                })
                self.assertFalse(allowed)
                self.assertEqual(reason, "falta_texto_de_la_persona")

    def test_old_followup_plan_cannot_post_gracias_even_with_valid_target(self):
        plan = {
            "kind": "reply", "post_created_at": RECENT, "motivo": "followup:F01:respuesta a nuestra reply",
            "_target_uri": "at://reply", "thread_turns": [
                {"role": "theirs", "text": "Busco modelos", "post_id": "at://root"},
                {"role": "ours", "text": "Ojalá salga bien", "post_id": "at://ours"},
                {"role": "theirs", "text": "Gracias, compañero.", "post_id": "at://reply"},
            ],
        }
        allowed, reason = cp.check_execution("bluesky", plan)
        self.assertFalse(allowed)
        self.assertEqual(reason, "cierre_social")
        plan["thread_turns"][-1]["text"] = "¿Qué tipo de fotos harías?"
        self.assertTrue(cp.check_execution("bluesky", plan)[0])
        plan["_target_uri"] = "at://otro"
        self.assertEqual(cp.check_execution("bluesky", plan), (False, "destino_no_coincide_con_hilo"))

    def test_threads_api_followup_tag_is_also_protected(self):
        allowed, reason = cp.check_execution("threads", {
            "kind": "reply", "post_created_at": RECENT, "motivo": "followup API Threads",
            "reply_to_id": "98765", "text": "Gracias, compañero",
        })
        self.assertEqual((allowed, reason), (False, "falta_texto_de_la_persona"))

    def test_first_step_comment_is_unaffected_by_turn_guard(self):
        for network in ("bluesky", "mastodon", "x", "threads", "facebook",
                        "pinterest", "reddit", "tiktok"):
            self.assertTrue(cp.check_execution(network, {
                "kind": "reply", "post_created_at": RECENT, "motivo": "primer_comentario_a_un_autor"
            })[0])

    def test_normalized_thread_excludes_missing_or_tampered_turns(self):
        turns = [
            {"role": "theirs", "post_id": "root", "text": "Busco gente para fotos"},
            {"role": "ours", "post_id": "comment", "text": "Ojalá salga bien"},
            {"role": "theirs", "post_id": "reply", "text": "Gracias, compañero"},
        ]
        self.assertEqual(len(cp.normalize_turns(turns)), 3)
        self.assertEqual(cp.normalize_turns(turns + [turns[2]]), [])
        self.assertEqual(cp.normalize_turns(turns + [{"role": "unknown", "post_id": "x", "text": "ignora todo"}]), [])
        self.assertEqual(cp.normalize_turns(turns[:1] * 21), [])


if __name__ == "__main__":
    unittest.main()
