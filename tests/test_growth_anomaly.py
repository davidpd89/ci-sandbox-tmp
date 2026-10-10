"""Regresión hermética de anomalías; no toca red, cuentas ni datos vivos."""
import csv
import datetime as dt
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import growth_anomaly as a
import round_canaries as canaries

NOW = dt.datetime(2026, 10, 9, 16, 0)
HEADER = ["fecha", "red", "inicio", "fin", "minutos", "estado",
          "confirmadas", "saltadas", "fallos", "codigo"]


class AnomalyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        (self.root / "00_OPERATIVO").mkdir()
        self.file = self.root / "00_OPERATIVO" / "tiempos_rondas.csv"
        self.rows = []

    def day(self, age, net="bluesky", amount=9, rounds=3, state="ok"):
        date = (NOW.date() - dt.timedelta(days=age)).isoformat()
        for _ in range(rounds):
            self.rows.append([date, net, "12:00:00", "12:01:00", 1, state,
                              "{'like': %d}" % amount, 0, 0, 0])

    def write(self):
        with self.file.open("w", encoding="utf-8", newline="") as stream:
            out = csv.writer(stream)
            out.writerow(HEADER)
            out.writerows(self.rows)

    def baseline(self, net="bluesky", amount=9, days=7):
        for age in range(3, 3 + days):
            self.day(age, net=net, amount=amount)

    def alerts(self):
        self.write()
        return a.collect(self.root, now=NOW)

    def test_sustained_drop_detected_once(self):
        self.baseline()
        self.day(2, amount=2)
        self.day(1, amount=1)
        found = self.alerts()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["network"], "bluesky")
        self.assertEqual(found[0]["baseline_days"], 7)

    def test_one_low_day_does_not_alert(self):
        self.baseline()
        self.day(2, amount=2)
        self.day(1, amount=9)
        self.assertEqual(self.alerts(), [])

    def test_absence_occupied_and_insufficient_sample_are_not_zero(self):
        self.baseline()
        self.day(2, amount=0, state="saltada")
        self.day(1, amount=0, state="ocupada")
        self.assertEqual(self.alerts(), [])
        self.rows.clear()
        self.baseline()
        self.day(2, amount=1, rounds=2)
        self.day(1, amount=1)
        self.assertEqual(self.alerts(), [])

    def test_four_baseline_days_and_meaningful_baseline_required(self):
        self.baseline(days=3)
        self.day(2, amount=1)
        self.day(1, amount=1)
        self.assertEqual(self.alerts(), [])
        self.rows.clear()
        self.baseline(amount=1)
        self.day(2, amount=0)
        self.day(1, amount=0)
        self.assertEqual(self.alerts(), [])

    def test_untrusted_zero_in_success_row_is_not_evidence(self):
        self.baseline()
        self.day(2, amount=0)
        self.day(1, amount=0)
        self.assertEqual(self.alerts(), [])

    def test_error_not_counted_as_zero_and_partial_is_observed(self):
        self.baseline()
        self.day(2, amount=1, state="parcial")
        self.day(1, amount=1, state="parcial")
        self.day(1, amount=0, state="error", rounds=9)
        self.assertEqual(len(self.alerts()), 1)

    def test_invalid_network_sample_does_not_poison_other_network(self):
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=1)
        self.baseline(net="mastodon")
        self.day(2, net="mastodon", amount=1)
        self.day(1, net="mastodon", amount=1)
        self.rows.append([(NOW.date()-dt.timedelta(days=1)).isoformat(),
                          "bluesky", "12:00", "12:01", 1, "ok", "invalid", 0, 0, 0])
        self.assertEqual([v["network"] for v in self.alerts()], ["mastodon"])

    def test_today_and_stale_history_ignored(self):
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=9)
        self.day(0, amount=0, rounds=50)
        self.day(20, amount=0)
        self.assertEqual(self.alerts(), [])

    def test_no_file_bad_header_and_read_only(self):
        self.assertEqual(a.collect(self.root, now=NOW), [])
        self.file.write_text("incorrect header", encoding="utf-8")
        self.assertEqual(a.collect(self.root, now=NOW), [])
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=1)
        self.write()
        before = (self.file.read_bytes(), self.file.stat().st_mtime_ns)
        a.collect(self.root, now=NOW)
        self.assertEqual((self.file.read_bytes(), self.file.stat().st_mtime_ns), before)

    def test_plus_thirty_days_and_plain_date(self):
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=1)
        self.write()
        self.assertEqual(a.collect(self.root, now=NOW + dt.timedelta(days=30)), [])
        self.assertEqual(a.collect(self.root, now=NOW + dt.timedelta(days=3)), [])
        self.assertEqual(len(a.collect(self.root, now=NOW.date())), 1)

    def test_all_eight_networks_and_paused_instagram_excluded(self):
        for net in a.NETWORKS + ("instagram",):
            self.baseline(net=net)
            self.day(2, net=net, amount=1)
            self.day(1, net=net, amount=1)
        self.assertEqual({item["network"] for item in self.alerts()},
                         set(a.NETWORKS))

    def test_corrupt_success_fields_invalidate_only_affected_network(self):
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=1)
        self.baseline(net="mastodon")
        self.day(2, net="mastodon", amount=1)
        self.day(1, net="mastodon", amount=1)
        day = (NOW.date() - dt.timedelta(days=1)).isoformat()
        for bad in ("", "{}", "9"*5000):
            self.rows.append([day, "bluesky", "12:00:00", "12:01:00",
                              1, "ok", bad, 0, 0, 0])
        self.assertEqual([x["network"] for x in self.alerts()], ["mastodon"])

    def test_unknown_state_or_extra_column_is_not_silently_dropped(self):
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=1)
        day = (NOW.date() - dt.timedelta(days=1)).isoformat()
        self.rows.append([day, "bluesky", "12:00:00", "12:01:00", 1,
                          "unknown", "{'like': 5}", 0, 0, 0])
        self.assertEqual(self.alerts(), [])
        self.rows[-1][-1] = 0
        self.rows[-1][5] = "ok"
        self.rows[-1].append("extra")
        self.assertEqual(self.alerts(), [])

    def test_bad_date_in_known_network_blocks_that_network(self):
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=1)
        self.rows.append(["bad-date", "bluesky", "12:00:00", "12:01:00",
                          1, "ok", "{'like': 1}", 0, 0, 0])
        self.assertEqual(self.alerts(), [])

    def test_aware_utc_clock_uses_madrid_day(self):
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=1)
        self.write()
        utc = dt.datetime(2026, 10, 8, 22, 30, tzinfo=dt.timezone.utc)
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo("Europe/Madrid")
        except ZoneInfoNotFoundError:
            expected = 0  # Windows sin tzdata: sin inferencias arbitrarias
        else:
            expected = 1
        self.assertEqual(len(a.collect(self.root, now=utc)), expected)

    def test_unattributed_recent_row_blocks_false_drop(self):
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=1)
        self.rows.append([(NOW.date()-dt.timedelta(days=1)).isoformat(),
                          "", "12:00:00", "12:01:00", 1, "ok",
                          "{'like': 4}", 0, 0, 0])
        self.assertEqual(self.alerts(), [])

    def test_invalid_calendar_day_and_missing_end_time_block_false_drop(self):
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=1)
        self.rows.append(["2026-13-40", "bluesky", "12:00:00", "12:01:00",
                          1, "ok", "{'like': 8}", 0, 0, 0])
        self.assertEqual(self.alerts(), [])
        self.rows.pop()
        self.rows.append([(NOW.date()-dt.timedelta(days=1)).isoformat(),
                          "bluesky", "12:00:00", "", 1, "ok",
                          "{'like': 8}", 0, 0, 0])
        self.assertEqual(self.alerts(), [])

    def test_duplicate_column_names_cannot_skew_confirmation_counts(self):
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=1)
        self.write()
        text = self.file.read_text(encoding="utf-8")
        self.file.write_text(text.replace("confirmadas", "estado", 1),
                             encoding="utf-8")
        self.assertEqual(a.collect(self.root, now=NOW), [])

    def test_panel_accepts_anomaly_code_when_pr86_is_integrated(self):
        try:
            import estado_rondas as panel
        except ModuleNotFoundError as exc:
            if exc.name == "estado_rondas":
                self.skipTest("Panel #86 no fusionado; revisar en conjunto")
            raise
        self.assertIn("CAIDA_RENDIMIENTO_SOSTENIDA", panel.ALERT_CODES)

    def test_canary_integration_same_alert(self):
        self.baseline()
        self.day(2, amount=1)
        self.day(1, amount=1)
        self.write()
        report = canaries.collect(self.root, now=NOW, pid_alive=lambda pid: False)
        matches = [x["network"] for x in report["alerts"]
                   if x["code"] == "CAIDA_RENDIMIENTO_SOSTENIDA"]
        self.assertEqual(matches, ["bluesky"])


if __name__ == "__main__":
    unittest.main()
