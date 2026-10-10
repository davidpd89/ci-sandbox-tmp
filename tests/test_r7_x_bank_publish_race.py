"""R7: el banco de X debe revalidar cadencia dentro del turno del Edge.

Los dos casos reproducen que la decisión hecha ANTES de esperar 40 minutos
puede quedar obsoleta: otro publicador completa una operación mientras tanto.
No usa navegador, cuenta X, archivos reales ni redes.
"""
import contextlib
import datetime
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import x_bank_publish as bank
import content_publisher as content
import action_ledger


POST = {"id": "P001", "text": "¿Qué libro te hizo volver a leer por gusto?"}
NOW = datetime.datetime.now()


class XBankPublishRaceTests(unittest.TestCase):
    def run_main(self, *, log_before=None, log_after=None, other_before=None,
                 other_after=None, apply=True):
        log_before = log_before or []
        log_after = log_after if log_after is not None else log_before
        records = []

        @contextlib.contextmanager
        def edge_turn(*args, **kwargs):
            records.append("edge_acquired")
            try:
                yield
            finally:
                records.append("edge_released")

        def read_log(*, strict=False):
            return log_after if "edge_acquired" in records else log_before

        def last_other(_network, *, strict=False, not_after=None, notify=None):
            return other_after if "edge_acquired" in records else other_before

        with mock.patch.object(bank, "load_bank", return_value=[POST]), \
             mock.patch.object(bank, "read_log", side_effect=read_log), \
             mock.patch.object(content, "last_auto_publication", side_effect=last_other), \
             mock.patch.object(action_ledger, "browser_session", side_effect=edge_turn), \
             mock.patch.dict(sys.modules, {"x_interact": mock.Mock()}), \
             mock.patch.object(bank, "record", side_effect=lambda *args: records.append("record")):
            x = sys.modules["x_interact"]
            x.post.return_value = "https://x.com/DavidPorto/status/11"
            result = bank.main(["--apply"] if apply else [])
            posted = x.post.call_count
        return result, posted, records

    def test_another_bank_post_during_edge_wait_blocks_stale_publication(self):
        other = [{"id": "P999", "when": NOW, "text": "Un post que entró mientras esperaba"}]
        result, posted, steps = self.run_main(log_after=other)
        self.assertEqual(result, 0)
        self.assertEqual(posted, 0)
        self.assertNotIn("record", steps)

    def test_other_automatic_post_during_edge_wait_blocks_stale_publication(self):
        result, posted, steps = self.run_main(other_after=NOW)
        self.assertEqual(result, 0)
        self.assertEqual(posted, 0)
        self.assertNotIn("record", steps)

    def test_still_valid_post_is_published_and_recorded_before_releasing_edge(self):
        result, posted, steps = self.run_main()
        self.assertEqual(result, 0)
        self.assertEqual(posted, 1)
        self.assertEqual(steps, ["edge_acquired", "record", "edge_released"])

    def test_readonly_preview_never_waits_for_edge_or_publishes(self):
        result, posted, steps = self.run_main(apply=False)
        self.assertEqual(result, 0)
        self.assertEqual(posted, 0)
        self.assertEqual(steps, [])


if __name__ == "__main__":
    unittest.main()
