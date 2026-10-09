"""El motor de fidelización no debe reabrir cierres ni inventar contexto."""
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import conversation_followups as cf
import conversation_turn_policy as cp
import loyalty
import relationship_policy as rp


class LoyaltyThreadPolicyTests(unittest.TestCase):
    def _run(self, rows, *, turns=None):
        with mock.patch.dict(cf.ALL_SOURCES, {"bluesky": (lambda: rows, lambda *_: None)}):
            with mock.patch.object(cf, "replies_sent", return_value={}):
                with mock.patch.object(rp, "comment_allowed", return_value=True):
                    with mock.patch.object(cp, "fetch_verified_thread", return_value=turns or []) as fetch:
                        result = loyalty.unanswered_comments("bluesky", [])
        return result, fetch.call_count

    def test_photo_session_invitation_is_given_to_gpt_as_partial_context(self):
        rows = [{
            "handle": "fotografo", "ref": "at://reply", "answered": False,
            "text": "Parece que la idea está gustando. Si te animas también me dices.",
        }, {
            "handle": "otro", "ref": "at://thankyou", "answered": False,
            "text": "Gracias, compañero.",
        }]
        answers, fetch_count = self._run(rows)
        self.assertEqual(len(answers), 1)
        self.assertIn("CONTEXTO PARCIAL", answers[0]["conversation_context"])
        self.assertEqual(answers[0]["context_quality"], "partial")
        self.assertEqual(fetch_count, 1)

    def test_question_with_real_verified_thread_can_be_queued(self):
        rows = [{"handle": "lectora", "ref": "at://question", "answered": False,
                 "text": "¿Me recomiendas un libro de fantasía para empezar?"}]
        turns = [
            {"role": "theirs", "text": "Busco ideas de fantasía", "post_id": "at://root"},
            {"role": "ours", "text": "Me interesan las sagas breves", "post_id": "at://ours"},
            {"role": "theirs", "text": rows[0]["text"], "post_id": "at://question"},
        ]
        answers, calls = self._run(rows, turns=turns)
        self.assertEqual(calls, 1)
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["thread_turns"], turns)

    def test_question_without_verifiable_parent_is_partial_not_silently_skipped(self):
        rows = [{"handle": "lectora", "ref": "at://question", "answered": False,
                 "text": "¿Me recomiendas un libro de fantasía para empezar?"}]
        answers, calls = self._run(rows, turns=[])
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["context_quality"], "partial")
        self.assertEqual(calls, 1)

    def test_reader_can_be_thanked_without_triggering_reply(self):
        rows = [{"handle": "lector", "ref": "at://thanks", "answered": False,
                 "text": "Gracias, compañero."}]
        answers, calls = self._run(rows)
        self.assertEqual(answers, [])
        self.assertEqual(calls, 0)

    def test_positive_reader_feedback_is_not_cut_by_missing_question(self):
        rows = [{"handle": "lectora", "ref": "at://feedback", "answered": False,
                 "text": "Me ha encantado tu reseña y quiero leerlo ya"}]
        answers, calls = self._run(rows)
        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0]["context_quality"], "partial")
        self.assertEqual(calls, 1)

    def test_rendered_context_distinguishes_our_turns(self):
        turns = [
            {"role": "ours", "text": "Una respuesta nuestra.", "post_id": "1"},
            {"role": "theirs", "text": "¿Puedes explicarme eso?", "post_id": "2"},
        ]
        context = cp.render_thread(turns)
        self.assertIn("[1 ours]", context)
        self.assertIn("[2 theirs]", context)


if __name__ == "__main__":
    unittest.main()
