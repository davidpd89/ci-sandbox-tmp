"""Barrera de paradas TikTok: pruebas sin red, cuentas ni dispositivo."""
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import tiktok_safety as safety
import tiktok_bulk_follow as bulk


class TikTokSafetyTests(unittest.TestCase):
    def test_manual_review_survives_cooldown(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "bulk_cooldown.json"
            now = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)
            self.assertEqual(safety.restrict("rate", str(path), now=now), 60)
            with self.assertRaises(safety.SafetyBlocked):
                safety.require_writable(str(path), now=now + dt.timedelta(days=2))
            self.assertTrue(json.loads(path.read_text())["manual_review"])

    def test_corrupt_state_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "pause.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(safety.SafetyStateError):
                safety.require_writable(str(path))
            with self.assertRaises(safety.SafetyStateError):
                safety.restrict("rate", str(path))
            self.assertEqual(path.read_text(), "{")

    def test_failed_atomic_replace_preserves_old_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "pause.json"
            path.write_text('{"until":"2026-10-09T09:00:00+00:00"}', encoding="utf-8")
            old = path.read_bytes()
            with mock.patch.object(safety.os, "replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    safety.restrict("challenge", str(path), now=dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc))
            self.assertEqual(path.read_bytes(), old)
            self.assertEqual(list(pathlib.Path(folder).glob("*.tmp")), [])

    def test_legacy_local_datetime_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "pause.json"
            value = (dt.datetime.now() + dt.timedelta(minutes=30)).isoformat()
            path.write_text(json.dumps({"until": value}), encoding="utf-8")
            with self.assertRaises(safety.SafetyBlocked):
                safety.require_writable(str(path))

    def test_pending_follow_is_not_reattempted(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(pathlib.Path(folder) / "registro.csv")
            with mock.patch.object(bulk, "REGISTRO_CSV", path):
                bulk.record_follow("lectora", "test", "pendiente_verificacion")
                bulk.record_follow("lectora", "test", "confirmado")
                already, total = bulk.followed_before()
            self.assertIn("lectora", already)
            self.assertIn(total, (0, 1))

    def test_no_progress_alert_does_not_change_deadline(self):
        class Rng:
            def randint(self, a, b):
                return a
        with mock.patch.object(bulk.time, "monotonic", side_effect=[0, 901, 902]):
            session = bulk.Session(None, None, Rng(), max_follows=20, deadline=bulk.time.time() + 3000, done=set())
            with mock.patch("builtins.print") as logged:
                self.assertFalse(session.over)
                self.assertFalse(session.over)
            logged.assert_called_once()


    def test_unique_daily_usage_and_pending_counted_across_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "registro.csv"
            lines = [
                "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas",
                "2026-10-09,@lectora,follow,,,pendiente_verificacion,x",
                "2026-10-09,@lectora,follow,,,confirmado,x",
                "2026-10-09,@lectora,like,https://www.tiktok.com/v/1,,confirmado,x",
                "2026-10-08,@otra,follow,,,confirmado,x",
            ]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
            used, pending = safety.recorded_actions(str(path), today=dt.date(2026, 10, 9))
            self.assertEqual(used, {"follow": 1, "like": 1, "comment": 0})
            self.assertIn(("follow", "lectora"), pending)

    def test_csv_bad_header_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "registro.csv"
            path.write_text("fecha,tipo\n2026-10-09,follow\n", encoding="utf-8")
            with self.assertRaises(safety.SafetyStateError):
                safety.recorded_actions(str(path))

    def test_cooldown_does_not_run_on_zero_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "pause.json"
            self.assertEqual(safety.remaining_minutes(str(path)), 0)
            self.assertEqual(safety.step_status.__name__, "step_status")


if __name__ == "__main__":
    unittest.main()
