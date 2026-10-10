"""Sentinelas offline del publicador protegido preservado al actualizar PR #14.

No simulan una publicación válida ni tocan cuentas. Funcionan en Python 3.11.
"""
import datetime as dt
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import threads_api
import post_age_policy


class ThreadsProtectedBaseline(unittest.TestCase):
    def test_proof_required_before_any_post(self):
        with mock.patch.object(threads_api, "_verify_reply_destination",
                               side_effect=PermissionError("synthetic proof missing")), \
             mock.patch.object(threads_api, "api_post") as remote:
            with self.assertRaises(PermissionError):
                threads_api.publish_reply(
                    "synthetic", "test-user", "target-id", "Respuesta sintetica."
                )
            remote.assert_not_called()

    def test_protected_signature_still_accepts_provenance(self):
        import inspect
        params = inspect.signature(threads_api.publish_reply).parameters
        self.assertIn("proof_action", params)
        self.assertIn("proof_path", params)

    def test_common_age_policy_rejects_stale_thread_target(self):
        instant = dt.datetime(2026, 10, 10, 12, tzinfo=dt.timezone.utc)
        case = {
            "kind": "reply", "reply_to_us": True,
            "target_created_at": "2026-09-20T12:00:00Z",
        }
        accepted, reason = post_age_policy.check("threads", case, now=instant)
        self.assertFalse(accepted)
        self.assertEqual(reason, "post_antiguo")


if __name__ == "__main__":
    unittest.main()
