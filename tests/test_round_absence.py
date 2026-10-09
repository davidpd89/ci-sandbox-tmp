"""Canario de ausencia: no toca redes, Task Scheduler ni ficheros reales."""
import csv
import datetime as dt
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import round_absence as a
import round_canaries as canaries

NOW = dt.datetime(2026, 10, 9, 16, 0)
HEADER = ["fecha", "red", "inicio", "fin", "minutos", "estado",
          "confirmadas", "saltadas", "fallos", "codigo"]
TARGETS = {"x": 3, "threads": 3, "facebook": 3, "pinterest": 3,
           "bluesky": 4, "mastodon": 3, "tiktok": 3}


class RoundAbsenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = pathlib.Path(self.folder.name)
        self.op = self.root / "00_OPERATIVO"
        self.op.mkdir()

    def deployed(self):
        (self.op / "cola_rondas_web.log").write_text("", encoding="utf-8")

    def rounds(self, *rows):
        with (self.op / "tiempos_rondas.csv").open("w", encoding="utf-8", newline="") as handle:
            out = csv.writer(handle)
            out.writerow(HEADER)
            for network, when, state in rows:
                out.writerow([NOW.date().isoformat(), network, when, when, 1,
                              state, "{'like': 1}", 0, 0, 0])

    def alerts(self, at=NOW):
        try:
            recent = canaries._read_recent(self.op / "tiempos_rondas.csv", at)
        except ValueError:
            recent = []  # El colector principal detecta REGISTRO_INVALIDO.
        return a.collect(self.root, at, recent, targets=TARGETS,
                         owner_is_live=lambda token: token == "777:888")

    def test_silent_deployed_chains_alert_all_pending_networks(self):
        self.deployed()
        got = self.alerts()
        self.assertEqual({x["network"] for x in got}, set(TARGETS))
        self.assertTrue(all(x["severity"] == "alta" for x in got))
        self.assertTrue(all(x["code"] == "SIN_RONDAS_ESPERADAS" for x in got))

    def test_live_chain_lock_does_not_alert_while_long_round_running(self):
        self.deployed()
        (self.op / "cola_rondas_api.lock").write_text("777:888", encoding="ascii")
        got = self.alerts()
        self.assertFalse({"bluesky", "mastodon"} & {x["network"] for x in got})
        self.assertIn("tiktok", {x["network"] for x in got})

    def test_recent_finished_round_is_not_missing(self):
        self.deployed()
        self.rounds(("mastodon", "14:45:00", "ok"))
        self.assertNotIn("mastodon", {x["network"] for x in self.alerts()})

    def test_daily_target_reached_even_if_old(self):
        self.deployed()
        self.rounds(*[("bluesky", "08:00:00", "parcial") for _ in range(4)])
        self.assertNotIn("bluesky", {x["network"] for x in self.alerts()})

    def test_old_failure_does_not_count_as_completed(self):
        self.deployed()
        self.rounds(("x", "09:00:00", "error"))
        self.assertIn("x", {x["network"] for x in self.alerts()})

    def test_stop_and_outside_service_window_are_quiet(self):
        self.deployed()
        self.assertEqual(self.alerts(at=NOW.replace(hour=8)), [])
        self.assertEqual(self.alerts(at=NOW.replace(hour=23)), [])
        (self.op / "cola_parar.flag").write_text("stop", encoding="ascii")
        self.assertEqual(self.alerts(), [])

    def test_not_deployed_or_malformed_csv_no_fabricated_alerts(self):
        self.assertEqual(self.alerts(), [])
        self.deployed()
        (self.op / "tiempos_rondas.csv").write_text("incorrect header", encoding="ascii")
        self.assertEqual(self.alerts(), [])

    def test_readonly_preserves_file_bytes_and_mtime(self):
        self.deployed()
        self.rounds(("x", "09:00:00", "ok"))
        csvfile = self.op / "tiempos_rondas.csv"
        before = (csvfile.read_bytes(), csvfile.stat().st_mtime_ns)
        self.alerts()
        self.assertEqual((csvfile.read_bytes(), csvfile.stat().st_mtime_ns), before)

    def test_canaries_export_same_alert_and_no_reddit_false_alarm(self):
        self.deployed()
        self.rounds(("x", "09:00:00", "ok"))
        with mock.patch.object(a, "collect", wraps=a.collect) as wrapper, \
             mock.patch("round_queue.rounds_target", side_effect=lambda n: TARGETS[n]), \
             mock.patch("round_queue._owner_is_live", return_value=False):
            report = canaries.collect(self.root, now=NOW, pid_alive=lambda p: False)
        self.assertTrue(wrapper.called)
        alerts = [x for x in report["alerts"] if x["code"] == "SIN_RONDAS_ESPERADAS"]
        self.assertIn("tiktok", {x["network"] for x in alerts})
        self.assertNotIn("reddit", {x["network"] for x in alerts})


if __name__ == "__main__":
    unittest.main()
