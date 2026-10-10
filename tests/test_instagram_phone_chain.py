"""Instagram aprovecha el movil mientras TikTok descansa (09/10/2026): solo logica de decision, sin tocar movil ni Edge."""
import csv
import datetime
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
os.environ.setdefault("RRSS_INSTAGRAM_COOLDOWN_PATH", os.path.join(tempfile.mkdtemp(prefix="rrss_test_ig_cd_"), "mobile_cooldown.json"))
import round_queue as rq
import instagram_mobile_interact as igm

NOW = datetime.datetime(2026, 10, 9, 13, 0)
HEADER = ["fecha", "red", "inicio", "fin", "minutos", "estado", "confirmadas", "saltadas", "fallos", "codigo"]


class InstagramDueTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.log = os.path.join(self.dir, "tiempos.csv")
        igm.COOLDOWN_PATH = os.path.join(self.dir, "cd.json")

    def write(self, *rows):
        with open(self.log, "w", newline="", encoding="utf-8") as stream:
            w = csv.writer(stream)
            w.writerow(HEADER)
            for estado, inicio, fin in rows:
                w.writerow(["2026-10-09", "instagram", inicio, fin, 10, estado, "", 0, 0, 0])

    def due(self):
        return rq.instagram_due(now=NOW, log=self.log)

    def test_due_without_history(self):
        self.assertTrue(self.due())

    def test_done_today_is_not_due_again(self):
        self.write(("ok", "09:00:00", "09:20:00"))
        self.assertFalse(self.due())
        self.write(("parcial", "09:00:00", "09:20:00"))
        self.assertFalse(self.due())

    def test_failed_attempt_waits_an_hour_then_retries_once(self):
        self.write(("error", "12:30:00", "12:35:00"))
        self.assertFalse(self.due())                 # hace 25 min
        self.write(("error", "11:00:00", "11:05:00"))
        self.assertTrue(self.due())                  # hace casi 2 h
        self.write(("error", "09:00:00", "09:05:00"), ("saltada", "11:00:00", "11:05:00"))
        self.assertFalse(self.due())                 # 2 intentos: se acabo por hoy

    def test_busy_rounds_do_not_count_as_attempts(self):
        self.write(("ocupada", "12:55:00", "12:55:05"))
        self.assertTrue(self.due())

    def test_instagram_cooldown_blocks(self):
        import tiktok_safety as safety
        safety.restrict("warning", igm.COOLDOWN_PATH)
        self.assertFalse(self.due())

    def test_unreadable_cooldown_fails_closed(self):
        with open(igm.COOLDOWN_PATH, "w", encoding="utf-8") as stream:
            stream.write("{no es json")
        self.assertFalse(self.due())

    def test_other_networks_rows_are_ignored(self):
        with open(self.log, "w", newline="", encoding="utf-8") as stream:
            w = csv.writer(stream)
            w.writerow(HEADER)
            w.writerow(["2026-10-09", "tiktok", "09:00:00", "09:20:00", 20, "ok", "", 0, 0, 0])
        self.assertTrue(self.due())


class TikTokBlockedTests(unittest.TestCase):
    def test_blocked_only_with_active_pause_or_manual_review_or_unreadable_state(self):
        import tiktok_safety as safety
        directory = tempfile.mkdtemp()
        old = safety.COOLDOWN_PATH
        try:
            safety.COOLDOWN_PATH = os.path.join(directory, "bulk_cooldown.json")
            self.assertFalse(rq.tiktok_writes_blocked())              # sin fichero: puede escribir
            safety.restrict("warning", safety.COOLDOWN_PATH)
            self.assertTrue(rq.tiktok_writes_blocked())               # aviso activo
            with open(safety.COOLDOWN_PATH, "w", encoding="utf-8") as stream:
                stream.write("{ilegible")
            self.assertTrue(rq.tiktok_writes_blocked())               # ilegible: falla cerrado
        finally:
            safety.COOLDOWN_PATH = old


class PhoneChainWiringTests(unittest.TestCase):
    def test_run_round_sets_mobile_backend_only_for_instagram(self):
        import inspect
        source = inspect.getsource(rq.run_round)
        self.assertIn('RRSS_INSTAGRAM_BACKEND', source)
        self.assertIn('network == "instagram"', source)

    def test_cooling_branch_runs_instagram_before_napping(self):
        import inspect
        source = inspect.getsource(rq.phone_chain)
        self.assertLess(source.index("if tiktok_writes_blocked():"), source.index("instagram_due()"))
        self.assertLess(source.index('run_round("instagram")'), source.index("nap_before_deadline(10 * 60, until)"))


if __name__ == "__main__":
    unittest.main()
