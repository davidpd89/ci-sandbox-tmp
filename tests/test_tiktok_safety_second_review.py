"""Regresiones de la segunda auditoría de #41. Siempre offline y sin móvil."""
import contextlib
import csv
import datetime
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import mechanical_round as mr
import tiktok_mobile_execute as te
import tiktok_safety as safety


class TikTokSecondReviewTests(unittest.TestCase):
    def test_first_native_write_creates_csv_header_and_stays_parseable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "registro_interacciones.csv"
            with mock.patch.object(te, "REGISTRO_CSV", str(path)):
                te._append_registro_one({
                    "resultado": "pendiente_verificacion", "kind": "follow",
                    "handle": "lectora", "motivo": "offline-test",
                })
                te._append_registro_one({
                    "resultado": "confirmado", "kind": "follow",
                    "handle": "lectora", "motivo": "offline-test",
                })
                with path.open(encoding="utf-8", newline="") as stream:
                    rows = list(csv.DictReader(stream))
                counts, pending = safety.recorded_actions(str(path), today=datetime.date.today())
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[-1]["resultado"], "confirmado")
            self.assertEqual(counts["follow"], 1)
            self.assertIn(("follow", "lectora"), pending)

    def test_wrong_account_during_startup_persists_pause_before_lock_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            plan = root / "plan.json"
            plan.write_text('[{"kind":"follow","handle":"lectora"}]', encoding="utf-8")
            flag = root / "paused.json"
            released = []

            @contextlib.contextmanager
            def fake_lock():
                try:
                    yield
                finally:
                    released.append(flag.exists())

            adapter = mock.Mock()
            adapter.verify_active_account.side_effect = te.TikTokWrongAccount("mismatched")
            config = {
                "action_ceiling": {"follow": 2, "like": 1, "comment": 1},
                "session": {"min_days_between_write_sessions": 0},
                "human": {},
            }
            with mock.patch.object(te, "REGISTRO_CSV", str(root / "registro.csv")), \
                 mock.patch.object(safety, "COOLDOWN_PATH", str(flag)), \
                 mock.patch.object(te, "_load_config", return_value=config), \
                 mock.patch.object(te, "mobile_session_lock", fake_lock), \
                 mock.patch.object(te, "ensure_server", return_value=object()), \
                 mock.patch.object(te, "HumanClient", return_value=object()), \
                 mock.patch.object(te, "TikTokMobileAdapter", return_value=adapter), \
                 mock.patch.object(te, "Pace", return_value=mock.Mock()), \
                 mock.patch.object(te, "Behavior", return_value=mock.Mock()):
                code = te.main([str(plan), "--apply"])
            self.assertEqual(code, 5)
            self.assertEqual(released, [True], "la pausa debe estar durable antes de liberar el lock")
            self.assertEqual(json.loads(flag.read_text(encoding="utf-8"))["reason"], "wrong_account")

    def test_bulk_cleanup_challenge_is_persisted_not_swallowed(self):
        import tiktok_bulk_follow as bulk
        import mobile_runtime
        import tiktok_human
        import tiktok_mobile_interact
        import tiktok_mobile_nav
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            pause = root / "bulk_cooldown.json"
            navigator = mock.Mock()
            navigator.return_to_feed.side_effect = te.TikTokMobileChallenge("challenge")
            cfg = {"action_ceiling": {"follow": 1}, "human": {}}
            with mock.patch.object(bulk, "COOLDOWN_PATH", str(pause)), \
                 mock.patch.object(bulk, "SEEDS_PATH", str(root / "seeds.json")), \
                 mock.patch.object(bulk, "REGISTRO_CSV", str(root / "log.csv")), \
                 mock.patch.object(bulk, "load_config", return_value=cfg), \
                 mock.patch.object(bulk, "followed_before", return_value=(set(), 0)), \
                 mock.patch.object(mobile_runtime, "mobile_session_lock", return_value=contextlib.nullcontext()), \
                 mock.patch.object(mobile_runtime, "ensure_server", return_value=object()), \
                 mock.patch.object(tiktok_human, "HumanClient", return_value=object()), \
                 mock.patch.object(tiktok_human, "Pace", return_value=mock.Mock()), \
                 mock.patch.object(tiktok_mobile_interact, "TikTokMobileAdapter", return_value=mock.Mock()), \
                 mock.patch.object(tiktok_mobile_nav, "TikTokNavigator", return_value=navigator):
                result = bulk.main(["--max-follows", "1", "--modes", ""])
            self.assertEqual(result, 4)
            self.assertTrue(pause.exists())
            self.assertEqual(json.loads(pause.read_text())["reason"], "challenge")

    def test_challenge_during_inter_action_browsing_stops_before_next_write(self):
        with tempfile.TemporaryDirectory() as directory:
            pause = pathlib.Path(directory) / "stop.json"
            seen = []
            class Adapter:
                def follow(self, handle):
                    seen.append(handle)
                    return "followed"
            behavior = mock.Mock()
            behavior.browse.side_effect = te.TikTokMobileChallenge("security UI")
            plan = [{"kind": "follow", "handle": "lectora"},
                    {"kind": "follow", "handle": "escritora"}]
            with mock.patch.object(safety, "COOLDOWN_PATH", str(pause)):
                with self.assertRaises(safety.SafetyBlocked):
                    te.run_plan(plan, Adapter(), pause=True, behavior=behavior,
                                sleep=lambda _: None)
            self.assertEqual(seen, ["lectora"])
            self.assertTrue(pause.exists())
            self.assertEqual(json.loads(pause.read_text())["reason"], "challenge")

    def test_only_ordinary_navigation_failures_are_ignorable(self):
        te._optional_navigation(mock.Mock(side_effect=RuntimeError("decorativo")))
        with self.assertRaises(safety.SafetyBlocked):
            te._optional_navigation(mock.Mock(side_effect=safety.SafetyBlocked("ya pausado")))
        with tempfile.TemporaryDirectory() as directory:
            pause = pathlib.Path(directory) / "pause.json"
            with mock.patch.object(safety, "COOLDOWN_PATH", str(pause)):
                with self.assertRaises(safety.SafetyBlocked):
                    te._optional_navigation(mock.Mock(side_effect=te.TikTokWrongAccount("otra cuenta")))
            self.assertEqual(json.loads(pause.read_text())["reason"], "wrong_account")

    def test_empty_plan_apply_never_opens_mobile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            plan = root / "plan.json"
            plan.write_text("[]", encoding="utf-8")
            config = {"action_ceiling": {"follow": 2, "like": 1, "comment": 1},
                      "session": {"min_days_between_write_sessions": 0}}
            with mock.patch.object(te, "REGISTRO_CSV", str(root / "registro.csv")), \
                 mock.patch.object(te, "_load_config", return_value=config), \
                 mock.patch.object(te, "preflight_plan", return_value=[]), \
                 mock.patch.object(te, "_assert_session_spacing"), \
                 mock.patch.object(te, "ensure_server", side_effect=AssertionError("nunca conectar")):
                code = te.main([str(plan), "--apply"])
            self.assertEqual(code, 0)

    def test_mobile_quota_rechecked_under_lock_before_server(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            plan = root / "plan.json"
            plan.write_text('[{"kind":"follow","handle":"lectora"}]', encoding="utf-8")
            action = {"kind": "follow", "handle": "lectora"}
            config = {"action_ceiling": {"follow": 1, "like": 1, "comment": 1},
                      "session": {"min_days_between_write_sessions": 0}}
            first = ({"follow": 0, "like": 0, "comment": 0}, set())
            occupied = ({"follow": 1, "like": 0, "comment": 0}, set())
            with mock.patch.object(te, "REGISTRO_CSV", str(root / "registro.csv")), \
                 mock.patch.object(te, "_load_config", return_value=config), \
                 mock.patch.object(te, "preflight_plan", return_value=[action]), \
                 mock.patch.object(te, "_assert_session_spacing"), \
                 mock.patch.object(te, "mobile_session_lock", return_value=contextlib.nullcontext()), \
                 mock.patch.object(te.safety, "recorded_actions", side_effect=[first, occupied]), \
                 mock.patch.object(te, "ensure_server", side_effect=AssertionError("no abrir")) as server:
                result = te.main([str(plan), "--apply"])
            self.assertEqual(result, 0)
            server.assert_not_called()

    def _native_result(self, status, code):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / "SISTEMA_DIARIO_TIKTOK").mkdir()
            (root / "plan.json").write_text("[]", encoding="utf-8")
            cfg = {
                "dir": "SISTEMA_DIARIO_TIKTOK",
                "pre": [], "build": None, "decisions": None,
                "decisions_default": None, "write_decisions": None,
                "execute": [sys.executable, "tools/tiktok_growth_flow.py", "run"],
                "plan": "plan.json",
                "post": [[sys.executable, "tools/tiktok_reciprocity_audit.py"]],
                "shape": False,
            }
            calls = []
            signals = []
            def runner(argv):
                calls.append(pathlib.Path(argv[1]).name)
                if argv[1].endswith("tiktok_growth_flow.py"):
                    return code, status
                return 0, ""
            with mock.patch.object(mr, "ROOT", str(root)), \
                 mock.patch.dict(mr.PIPELINES, {"tiktok": cfg}):
                result = mr._run("tiktok", runner=runner, shape=False,
                                 today=datetime.date(2026, 10, 9),
                                 out=lambda _: None, signals=signals)
            return result, calls, signals

    def test_native_busy_local_uncertain_never_enter_post(self):
        cases = (
            ("TIKTOK_STEP_STATUS=busy", 3, "busy"),
            ("TIKTOK_STEP_STATUS=local_error", 5, "plan"),
            ("TIKTOK_STEP_STATUS=uncertain", 5, "plan"),
            ("TIKTOK_STEP_STATUS=restricted", 4, "execute"),
        )
        for message, exit_code, expected in cases:
            with self.subTest(expected=expected):
                result, calls, _ = self._native_result(message, exit_code)
                if expected == "busy":
                    self.assertTrue(result.get("skipped"))
                else:
                    self.assertFalse(result["ok"])
                    self.assertEqual(result["failure_kind"], expected)
                self.assertNotIn("tiktok_reciprocity_audit.py", calls)

    def test_native_missing_or_duplicate_marker_blocks_post(self):
        for raw in ("", "TIKTOK_STEP_STATUS=completed\nTIKTOK_STEP_STATUS=busy"):
            with self.subTest(raw=raw):
                result, calls, _ = self._native_result(raw, 0)
                self.assertFalse(result["ok"])
                self.assertEqual(result["failure_kind"], "plan")
                self.assertNotIn("tiktok_reciprocity_audit.py", calls)

    def test_native_no_budget_is_safe_and_cannot_fail_round(self):
        result, _, _ = self._native_result("TIKTOK_STEP_STATUS=no_budget", 0)
        self.assertTrue(result["ok"])

    def test_native_completed_with_zero_exit_can_reach_post(self):
        result, calls, _ = self._native_result("TIKTOK_STEP_STATUS=completed", 0)
        self.assertTrue(result["ok"])
        self.assertIn("tiktok_reciprocity_audit.py", calls)

    def test_native_completed_with_nonzero_exit_blocks(self):
        result, calls, _ = self._native_result("TIKTOK_STEP_STATUS=completed", 5)
        self.assertFalse(result["ok"])
        self.assertNotIn("tiktok_reciprocity_audit.py", calls)


if __name__ == "__main__":
    unittest.main()
