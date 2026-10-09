"""R3/F4: reproducer real de decisiones obsoletas entre rondas Mastodon.

Integra selector real + merge de comentarios GPT + builder real con datos
sintéticos anonimizados. No hay token, navegador, API ni fichero operativo.
La primera prueba fallaba antes del cambio: el plan intentaba publicar
un post de una shortlist anterior que ya no existe.
"""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import api_comment_writer as writer
import mastodon_build_plan as builder


def fresh_scan():
    return {"shortlist": [{
        "id": "M002", "acct": "lectora@mastodon.ejemplo", "score": 3,
        "actions": ["follow"],
        "posts": [{
            "id": "M002-P1", "text": "He terminado el segundo tomo de esta saga y me ha sorprendido muchísimo el desenlace",
            "status_id": "222", "url": "https://mastodon.ejemplo/@lectora/222",
            "actions": ["reply", "favourite"], "sources": ["nicho"], "es": True
        }]
    }]}


class MastodonStaleDecisionPipelineTests(unittest.TestCase):
    def test_old_reply_missing_from_fresh_scan_does_not_abort_plan(self):
        scan = fresh_scan()
        items = writer.pick_posts(scan, 12)
        self.assertEqual([x["id"] for x in items], ["M002-P1"])
        # GPT trabajador no ha producido una respuesta nueva en esta ronda.
        previous = {"actions": [
            {"post": "M001-P1", "kind": "reply", "text": "Texto antiguo generado para otro hilo"}
        ]}
        decisions = writer.merge(previous, [])
        self.assertEqual(builder.build(scan, decisions), [])
        self.assertEqual(decisions, {"actions": []})

    def test_new_reply_replaces_previous_reply_even_with_same_post_id(self):
        scan = fresh_scan()
        previous = {"actions": [
            {"post": "M002-P1", "kind": "reply", "text": "Texto anterior que no debe persistir"}
        ]}
        decisions = writer.merge(previous, [
            {"post": "M002-P1", "kind": "reply", "text": "Ese segundo tomo parece dar mucho que hablar"}
        ])
        plan = builder.build(scan, decisions)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["status_id"], "222")
        self.assertEqual(plan[0]["text"], "Ese segundo tomo parece dar mucho que hablar")

    def test_nonreply_decisions_survive_when_worker_has_no_reply(self):
        scan = fresh_scan()
        previous = {"actions": [
            {"post": "M001-P1", "kind": "reply", "text": "Respuesta anterior"},
            {"candidate": "M002", "kind": "follow"},
            {"post": "M002-P1", "kind": "favourite"}
        ]}
        decisions = writer.merge(previous, [])
        plan = builder.build(scan, decisions)
        self.assertEqual([r["kind"] for r in plan], ["follow", "favourite"])
        self.assertFalse(any(r["kind"] == "reply" for r in plan))

    def test_new_reply_replaces_like_only_on_same_post(self):
        scan = fresh_scan()
        previous = {"actions": [
            {"candidate": "M002", "kind": "follow"},
            {"post": "M002-P1", "kind": "favourite"}
        ]}
        decisions = writer.merge(previous, [
            {"post": "M002-P1", "kind": "reply", "text": "Ese final ha dado para mucha conversación"}
        ])
        plan = builder.build(scan, decisions)
        self.assertEqual([r["kind"] for r in plan], ["follow", "reply"])


if __name__ == "__main__":
    unittest.main()
