"""R4/F4/F9: un comentario duplicado en Mastodon no tumba acciones sanas.

Fixtures sintéticos y comprobadores falsos: ni API ni datos de ejecución.
El preflight sigue rechazando destino inseguro, identidad ausente y tipos inválidos.
"""
import contextlib
<<<<<<< HEAD
=======
import datetime as dt
>>>>>>> origin/research/public-reuse-parent
import io
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import mastodon_execute as ex


class MastodonPreflightIsolationTests(unittest.TestCase):
    def test_published_reply_is_omitted_and_rest_of_plan_survives(self):
        actions = [
            {"kind": "reply", "status_id": "1001", "text": "Ya respondimos a este mensaje"},
            {"kind": "favourite", "status_id": "1002"},
            {"kind": "follow", "handle": "lectora@ejemplo.social"},
        ]
        output = io.StringIO()
        with mock.patch.object(ex.dup, "check", return_value=[("mastodon", "ayer")]):
            with mock.patch.object(ex.m, "_check_length"):
                with mock.patch.object(ex.m, "_check_spanish_orthography"):
                    with mock.patch.object(ex.sc, "guard_plan_item"):
                        with contextlib.redirect_stdout(output):
                            kept = ex._preflight_plan(actions)
        self.assertEqual([r["kind"] for r in kept], ["favourite", "follow"])
        self.assertIn("OMITIDO_PREFLIGHT_DUPLICADO", output.getvalue())
        self.assertNotIn("Ya respondimos", output.getvalue())

    def test_skipped_reply_does_not_reserve_target_of_valid_action(self):
        actions = [
            {"kind": "reply", "status_id": "1001", "text": "Texto publicado ayer"},
            {"kind": "favourite", "status_id": "1001"},
        ]
        with mock.patch.object(ex.dup, "check", return_value=[("mastodon", "ayer")]):
            with mock.patch.object(ex.m, "_check_length"):
                with mock.patch.object(ex.m, "_check_spanish_orthography"):
                    with mock.patch.object(ex.sc, "guard_plan_item"):
                        with contextlib.redirect_stdout(io.StringIO()):
                            kept = ex._preflight_plan(actions)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["kind"], "favourite")

    def test_two_conflicting_nontext_actions_still_fail_closed(self):
        actions = [
            {"kind": "favourite", "status_id": "1001"},
            {"kind": "boost", "status_id": "1001"},
        ]
        with self.assertRaisesRegex(ValueError, "varias acciones"):
            ex._preflight_plan(actions)

    def test_invalid_status_and_missing_author_still_block_plan(self):
        with self.assertRaisesRegex(ValueError, "status_id inválido"):
            ex._preflight_plan([{"kind": "favourite", "status_id": "not-a-number"}])
        with self.assertRaisesRegex(ValueError, "follow exige handle"):
            ex._preflight_plan([{"kind": "follow", "handle": None}])

    def test_distinct_replies_without_history_duplicate_are_preserved(self):
<<<<<<< HEAD
        actions = [
            {"kind": "reply", "status_id": "1001", "text": "Una respuesta que sí aporta algo"},
            {"kind": "reply", "status_id": "1002", "text": "Otra respuesta sobre el segundo tomo"},
=======
        fresh = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat()
        actions = [
            {"kind": "reply", "status_id": "1001", "post_created_at": fresh, "text": "Una respuesta que sí aporta algo"},
            {"kind": "reply", "status_id": "1002", "post_created_at": fresh, "text": "Otra respuesta sobre el segundo tomo"},
>>>>>>> origin/research/public-reuse-parent
        ]
        with mock.patch.object(ex.dup, "check", return_value=[]):
            with mock.patch.object(ex.m, "_check_length"):
                with mock.patch.object(ex.m, "_check_spanish_orthography"):
                    with mock.patch.object(ex.sc, "guard_plan_item"):
                        kept = ex._preflight_plan(actions)
        self.assertEqual(kept, actions)


if __name__ == "__main__":
    unittest.main()
