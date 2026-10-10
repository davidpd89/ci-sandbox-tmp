"""#157: un follow `requested` cierra su intencion como pendiente_aprobacion; el estado de seguridad no puede romperse ni perder la cuota."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import tiktok_mobile_execute as te
import tiktok_safety as safety


class RequestedFollowStateTests(unittest.TestCase):
    def test_requested_follow_keeps_safety_state_readable_and_counts_quota(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = Path(tmp) / "registro.csv"
            adapter = SimpleNamespace(follow=lambda handle: "requested")
            with mock.patch.object(te, "REGISTRO_CSV", str(path)), \
                 mock.patch.object(safety, "COOLDOWN_PATH", str(Path(tmp) / "cooldown.json")), \
                 mock.patch("reply_writer.require_gpt", side_effect=lambda plan, network: plan), \
                 mock.patch("conversation_turn_policy.check_execution", return_value=(True, "ok")), \
                 mock.patch.object(safety, "require_writable"), \
                 mock.patch.object(safety, "follow_paused", return_value=False):
                results = te.run_plan([{"kind": "follow", "handle": "alguien"}], adapter, pause=False,
                                      on_result=te._append_registro_one)
            self.assertEqual([r["resultado"] for r in results], ["pendiente_aprobacion"])
            counts, pending = safety.recorded_actions(str(path))
            self.assertEqual(counts["follow"], 1)      # el tap ocurrio: consume cuota
            self.assertEqual(pending, set())           # no es un ACK incierto


if __name__ == "__main__":
    unittest.main()
