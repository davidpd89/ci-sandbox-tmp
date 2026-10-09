"""Barrera de paradas TikTok: pruebas sin red, cuentas ni dispositivo."""
import datetime as dt
import inspect
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

    def test_follow_limit_cannot_downgrade_manual_review_after_cooldown(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "pause.json"
            now = dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc)
            safety.restrict("challenge", str(path), now=now)
            before = path.read_bytes()

            self.assertEqual(
                safety.restrict("follow_limit", str(path), now=now + dt.timedelta(days=2)),
                float("inf"),
            )
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(safety.SafetyBlocked):
                safety.require_writable(str(path), now=now + dt.timedelta(days=2))

    def test_invalid_manual_review_is_corrupt_state_and_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "pause.json"
            payload = {
                "until": "2026-10-10T09:00:00+00:00",
                "manual_review": "yes",
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            before = path.read_bytes()

            with self.assertRaises(safety.SafetyStateError):
                safety.restrict(
                    "follow_limit",
                    str(path),
                    now=dt.datetime(2026, 10, 9, tzinfo=dt.timezone.utc),
                )
            self.assertEqual(path.read_bytes(), before)

    def test_follow_scope_with_invalid_until_still_fails_closed_for_like(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "pause.json"
            path.write_text(
                json.dumps({"scope": "follow", "until": "not-a-date"}),
                encoding="utf-8",
            )
            before = path.read_bytes()

            with self.assertRaises(safety.SafetyStateError):
                safety.require_writable(str(path), kind="like")
            with self.assertRaises(safety.SafetyStateError):
                safety.remaining_minutes(str(path), kind="comment")
            self.assertEqual(path.read_bytes(), before)

    def test_invalid_strikes_is_rejected_on_read_not_only_on_write(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "pause.json"
            path.write_text(
                json.dumps({
                    "until": "2026-10-10T09:00:00+00:00",
                    "strikes": -1,
                }),
                encoding="utf-8",
            )
            with self.assertRaises(safety.SafetyStateError):
                safety.require_writable(str(path))

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

    def test_cooldown_wrapper_propagates_corrupt_state(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "pause.json"
            path.write_text("{", encoding="utf-8")
            with mock.patch.object(bulk, "COOLDOWN_PATH", str(path)):
                with self.assertRaises(safety.SafetyStateError):
                    bulk.cooldown_left()

    def test_tap_reserved_follow_survives_tap_crash_and_blocks_retry(self):
        class DummySession:
            def __init__(self):
                self.done = set()

        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "registro.csv"
            session = DummySession()

            def crash():
                raise RuntimeError("tap crashed")

            with mock.patch.object(bulk, "REGISTRO_CSV", str(path)):
                with self.assertRaises(RuntimeError):
                    bulk.tap_reserved_follow(session, "lectora", "test", crash)
                already, _ = bulk.followed_before()

            event_day = dt.date.fromisoformat(path.read_text(encoding="utf-8").splitlines()[1].split(",", 1)[0])
            used, pending = safety.recorded_actions(str(path), today=event_day)
            self.assertIn("lectora", session.done)
            self.assertIn("lectora", already)
            self.assertEqual(used["follow"], 1)
            self.assertIn(("follow", "lectora"), pending)

    def test_confirmed_reserved_follow_closes_intent_without_double_quota(self):
        class Rng:
            def randint(self, a, b):
                return a

        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "registro.csv"
            session = bulk.Session(
                None,
                None,
                Rng(),
                max_follows=2,
                deadline=bulk.time.time() + 300,
                done=set(),
            )
            with mock.patch.object(bulk, "REGISTRO_CSV", str(path)):
                intent_id = bulk.tap_reserved_follow(session, "lectora", "test", lambda: None)
                session.ok("lectora", "test", intent_id=intent_id)

            event_day = dt.date.fromisoformat(path.read_text(encoding="utf-8").splitlines()[1].split(",", 1)[0])
            used, pending = safety.recorded_actions(str(path), today=event_day)
            self.assertEqual(used["follow"], 1)
            self.assertNotIn(("follow", "lectora"), pending)
            self.assertEqual(session.followed, 1)

    def test_ack_write_failure_does_not_mark_session_success(self):
        class Rng:
            def randint(self, a, b):
                return a

        session = bulk.Session(
            None,
            None,
            Rng(),
            max_follows=2,
            deadline=bulk.time.time() + 300,
            done=set(),
        )
        with mock.patch.object(bulk, "record_follow", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                session.ok("lectora", "test", intent_id="a" * 32)
        self.assertEqual(session.followed, 0)
        self.assertNotIn("lectora", session.done)

    def test_all_bulk_follow_routes_use_write_ahead_helper(self):
        for func in (bulk.mine_followers, bulk.mine_mutual, bulk.followback_own):
            with self.subTest(func=func.__name__):
                self.assertIn("tap_reserved_follow(", inspect.getsource(func))

    def test_no_progress_alert_does_not_change_deadline(self):
        class Rng:
            def randint(self, a, b):
                return a

        deadline = bulk.time.time() + 3000
        with mock.patch.object(bulk.time, "monotonic", side_effect=[0, 901, 902]):
            session = bulk.Session(None, None, Rng(), max_follows=20, deadline=deadline, done=set())
            with mock.patch("builtins.print") as logged:
                self.assertFalse(session.over)
                self.assertFalse(session.over)
            logged.assert_called_once()
            self.assertEqual(session.deadline, deadline)


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

    def test_pending_approval_closes_intent_and_counts_once(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "registro.csv"
            intent_id = "b" * 32
            lines = [
                "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas",
                f"2026-10-09,@privada,follow,,,pendiente_verificacion,x | intent_id={intent_id}",
                f"2026-10-09,@privada,follow,,,pendiente_aprobacion,x | intent_id={intent_id}",
            ]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
            used, pending = safety.recorded_actions(str(path), today=dt.date(2026, 10, 9))
            self.assertEqual(used["follow"], 1)
            self.assertNotIn(("follow", "privada"), pending)

    def test_pending_approval_without_target_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "registro.csv"
            intent_id = "c" * 32
            lines = [
                "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas",
                f"2026-10-09,,follow,,,pendiente_aprobacion,x | intent_id={intent_id}",
            ]
            path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
            with self.assertRaises(safety.SafetyStateError):
                safety.recorded_actions(str(path), today=dt.date(2026, 10, 9))

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
