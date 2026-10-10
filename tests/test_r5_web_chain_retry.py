"""Regresiones solicitadas por Claude en la revisión de #110.
Nunca lanza red, Edge ni tareas reales. El reloj simulado avanza con nap().
"""
import datetime as dt
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import round_queue as rq


class Clock:
    def __init__(self):
        self.at = dt.datetime(2026, 10, 8, 13)

    def tick(self, seconds):
        self.at += dt.timedelta(seconds=seconds)


class WebRetryTests(unittest.TestCase):
    def run_scenario(self, targets, outcomes, hours=4):
        clock = Clock()
        done = {}
        events = []
        counts = {}

        class DateTimeProxy:
            @staticmethod
            def now():
                return clock.at

            @staticmethod
            def timedelta(**kw):
                return dt.timedelta(**kw)

        def execute(network):
            counts[network] = counts.get(network, 0) + 1
            result = outcomes[network].pop(0)
            events.append((network, result, clock.at))
            return result

        def pause(seconds, **kwargs):
            clock.tick(seconds)

        with mock.patch.object(rq.datetime, "datetime", DateTimeProxy), \
             mock.patch.object(rq, "control_signal", return_value=None), \
             mock.patch.object(rq, "run_round", side_effect=execute), \
             mock.patch.object(rq, "retry_snapshot_today", return_value={}), \
             mock.patch.object(rq, "nap", side_effect=pause), \
             mock.patch("edge_trim.trim", return_value=None), \
             mock.patch.object(rq.random, "uniform", side_effect=lambda low, high: (low + high) / 2):
            rq.web_chain(clock.at + dt.timedelta(hours=hours), targets, done)
        return done, events, clock.at

    def test_error_does_not_increment_done_and_retries_after_15_minutes(self):
        done, events, _ = self.run_scenario(
            {"x": 1}, {"x": ["error", "ok"]})
        self.assertEqual(done, {"x": 1})
        self.assertEqual([e[1] for e in events], ["error", "ok"])
        self.assertGreaterEqual((events[1][2] - events[0][2]).total_seconds(), 15 * 60)

    def test_saltada_does_not_increment_done(self):
        done, events, _ = self.run_scenario(
            {"x": 1}, {"x": ["saltada", "ok"]})
        self.assertEqual(done["x"], 1)
        self.assertEqual(len(events), 2)

    def test_failed_network_does_not_starve_another_network(self):
        done, events, _ = self.run_scenario(
            {"x": 1, "threads": 1},
            {"x": ["error", "ok"], "threads": ["ok"]})
        self.assertEqual(done, {"threads": 1, "x": 1})
        self.assertEqual([e[0] for e in events], ["x", "threads", "x"])

    def test_three_failures_have_15_30_60_minute_backoff(self):
        done, events, _ = self.run_scenario(
            {"x": 1}, {"x": ["error", "error", "error", "ok"]})
        self.assertEqual(done["x"], 1)
        gaps = [(b[2] - a[2]).total_seconds() / 60 for a, b in zip(events, events[1:])]
        self.assertGreaterEqual(gaps[0], 15)
        self.assertGreaterEqual(gaps[1], 30)
        self.assertGreaterEqual(gaps[2], 60)

    def test_deadline_expires_with_failed_round_not_counted(self):
        done, events, _ = self.run_scenario(
            {"x": 1}, {"x": ["error", "error"]}, hours=0.1)
        self.assertEqual(done, {})
        self.assertEqual(len(events), 1)

    def test_partial_counts_and_does_not_retry(self):
        done, events, _ = self.run_scenario(
            {"x": 1}, {"x": ["parcial"]})
        self.assertEqual(done, {"x": 1})
        self.assertEqual(len(events), 1)

    def test_ocupada_is_not_counted_as_error_and_does_not_penalize_an_hour(self):
        done, events, _ = self.run_scenario(
            {"x": 1}, {"x": ["ocupada", "ocupada", "ocupada", "ok"]})
        self.assertEqual(done, {"x": 1})
        gaps = [(b[2] - a[2]).total_seconds() for a, b in zip(events, events[1:])]
        self.assertTrue(all(120 <= s < 600 for s in gaps), gaps)

    def test_unknown_state_fails_closed_and_partial_does_not_retry(self):
        self.assertEqual(rq.classify_round_state("parcial", 0), (True, 0.0, False))
        done, events, _ = self.run_scenario(
            {"x": 1}, {"x": ["desconocido", "parcial"]})
        self.assertEqual(done, {"x": 1})
        self.assertEqual(len(events), 2)

    def test_classifier_shared_between_three_chains(self):
        with mock.patch.object(rq.random, "uniform", side_effect=lambda a, b: (a + b) / 2):
            for state in ("ok", "parcial"):
                self.assertEqual(rq.classify_round_state(state, 0), (True, 0.0, False))
            self.assertEqual(rq.classify_round_state("ocupada", 5), (False, 210, False))
            self.assertEqual(rq.classify_round_state("error", 1), (False, 900, False))
            self.assertEqual(rq.classify_round_state("error", 2), (False, 1800, False))
            self.assertEqual(rq.classify_round_state("error", 3), (False, 3600, True))
            self.assertEqual(rq.classify_round_state("error", 6), (False, 7200, True))

    def test_jitter_is_bounded(self):
        for state, failures, low, high in [
            ("ocupada", 5, 120, 300),
            ("error", 1, 720, 1080),
            ("error", 3, 2880, 4320),
        ]:
            with self.subTest(state=state, failures=failures):
                with mock.patch.object(rq.random, "uniform", side_effect=lambda a, b: a):
                    self.assertEqual(rq.classify_round_state(state, failures)[1], low)
                with mock.patch.object(rq.random, "uniform", side_effect=lambda a, b: b):
                    self.assertEqual(rq.classify_round_state(state, failures)[1], high)

    def test_saltada_waits_for_breaker_reopen(self):
        when = dt.datetime(2026, 10, 8, 13)
        opened = (when + dt.timedelta(hours=3)).isoformat()
        with mock.patch("circuit_breaker.load", return_value={"open_until": opened}), \
             mock.patch.object(rq.random, "uniform", side_effect=lambda a, b: (a + b) / 2):
            counts, seconds, alert = rq.classify_round_state(
                "saltada", 0, network="x", now=when)
        self.assertFalse(counts)
        self.assertFalse(alert)
        self.assertEqual(seconds, 3 * 60 * 60)

    def test_api_does_not_abort_after_six_errors(self):
        clock = Clock()
        calls = []
        statuses = iter(["error"] * 6 + ["ok"])
        class Proxy:
            @staticmethod
            def now():
                return clock.at
            @staticmethod
            def timedelta(**kw):
                return dt.timedelta(**kw)
        def round_(network):
            calls.append((network, clock.at))
            return next(statuses)
        with mock.patch.object(rq.datetime, "datetime", Proxy), \
             mock.patch.object(rq, "control_signal", return_value=None), \
             mock.patch.object(rq, "run_round", side_effect=round_), \
             mock.patch.object(rq, "budget_left", return_value=0), \
             mock.patch.object(rq, "retry_snapshot_today", return_value={}), \
             mock.patch.object(rq, "nap", side_effect=lambda seconds, **kw: clock.tick(seconds)), \
             mock.patch.object(rq.random, "uniform", side_effect=lambda a, b: (a + b) / 2):
            rq.spaced_chain("bluesky", clock.at + dt.timedelta(hours=12), 1, 0, "bluesky")
        self.assertEqual(len(calls), 7)
        self.assertGreaterEqual((calls[6][1] - calls[5][1]).total_seconds(), 7200)

    def test_phone_recovers_from_busy_without_fake_success(self):
        import types
        clock = Clock()
        calls = []
        outcomes = iter(["ocupada", "ok"])
        class Proxy:
            @staticmethod
            def now():
                return clock.at
            @staticmethod
            def timedelta(**kw):
                return dt.timedelta(**kw)
        def round_(network):
            calls.append((network, clock.at))
            return next(outcomes)
        with mock.patch.dict(sys.modules, {"tiktok_bulk_follow": types.SimpleNamespace(cooldown_left=lambda: 600)}), \
             mock.patch.object(rq.datetime, "datetime", Proxy), \
             mock.patch.object(rq, "control_signal", return_value=None), \
             mock.patch.object(rq, "run_round", side_effect=round_), \
             mock.patch.object(rq, "retry_snapshot_today", return_value={}), \
             mock.patch.object(rq, "nap", side_effect=lambda seconds, **kw: clock.tick(seconds)), \
             mock.patch.object(rq.random, "uniform", side_effect=lambda a, b: (a + b) / 2):
            rq.phone_chain(clock.at + dt.timedelta(minutes=20), 1, 0)
        self.assertEqual([n for n, _ in calls], ["tiktok", "tiktok"])
        self.assertLess((calls[1][1] - calls[0][1]).total_seconds(), 600)

    def test_csv_schema_fixture_all_states_and_resume(self):
        import csv
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = os.path.join(tmp, "tiempos_rondas.csv")
            states = ["saltada", "ocupada", "error", "ok", "parcial"]
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["fecha", "red", "inicio", "fin", "minutos",
                                 "estado", "confirmadas", "saltadas", "fallos", "codigo"])
                for state in states:
                    writer.writerow(["2026-10-08", "x", "12:00:00", "12:00:02", 0.1,
                                     state, "{'like': 1}" if state in ("ok", "parcial") else "",
                                     0, 0, 0])
            with mock.patch.object(rq, "LOG", csv_path):
                self.assertEqual(rq.done_today(dt.date(2026, 10, 8)), {"x": 2})
            with mock.patch.object(rq.random, "uniform", side_effect=lambda a,b: (a+b)/2):
                counted = [rq.classify_round_state(s, 1)[0] for s in states]
            self.assertEqual(counted, [False, False, False, True, True])

    def test_canary_reports_consecutive_errors_without_private_text(self):
        import csv
        import tempfile
        import os
        import round_canaries
        with tempfile.TemporaryDirectory() as tmp:
            os.mkdir(os.path.join(tmp, "00_OPERATIVO"))
            path = os.path.join(tmp, "00_OPERATIVO", "tiempos_rondas.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["fecha", "red", "inicio", "fin", "minutos",
                            "estado", "confirmadas", "saltadas", "fallos", "codigo"])
                for i, state in enumerate(("error", "ocupada", "error", "error")):
                    w.writerow(["2026-10-08", "x", "12:00:00", f"13:{i:02d}:00",
                                0.1, state, "", 0, 5, 1])
            report = round_canaries.collect(
                tmp, now=dt.datetime(2026, 10, 8, 13, 10), pid_alive=lambda _: False)
            alerts = [a for a in report["alerts"] if a["code"] == "ERRORES_SEGUIDOS"]
            self.assertEqual(len(alerts), 1)
            self.assertEqual(alerts[0]["consecutive"], 3)
            self.assertEqual(alerts[0]["last_return_code"], 1)
            self.assertEqual(alerts[0]["last_failed_actions"], 5)

    def test_long_breaker_wait_does_not_outlive_api_deadline(self):
        clock = Clock()
        calls = []
        class Proxy:
            fromisoformat = staticmethod(dt.datetime.fromisoformat)
            @staticmethod
            def now():
                return clock.at
            @staticmethod
            def timedelta(**kw):
                return dt.timedelta(**kw)
        with mock.patch.object(rq.datetime, "datetime", Proxy), \
             mock.patch.object(rq, "control_signal", return_value=None), \
             mock.patch.object(rq, "run_round", side_effect=lambda n: calls.append(n) or "saltada"), \
             mock.patch.object(rq, "retry_snapshot_today", return_value={}), \
             mock.patch("circuit_breaker.load", return_value={"open_until": "2026-10-09T02:00:00"}), \
             mock.patch.object(rq, "nap", side_effect=lambda secs, **kw: clock.tick(secs)), \
             mock.patch.object(rq.random, "uniform", side_effect=lambda a, b: (a+b)/2):
            rq.spaced_chain("mastodon", clock.at + dt.timedelta(minutes=10), 1, 0, "mastodon")
        self.assertEqual(calls, ["mastodon"])
        self.assertEqual(clock.at, dt.datetime(2026, 10, 8, 13, 10))

    def test_resume_from_csv_restores_streak_and_worst_case_cooldown(self):
        import csv
        import tempfile
        import os
        at = dt.datetime(2026, 10, 8, 13, 5)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tiempos_rondas.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["fecha", "red", "inicio", "fin", "minutos",
                            "estado", "confirmadas", "saltadas", "fallos", "codigo"])
                for i, state in enumerate(("error", "ocupada", "error", "saltada", "error")):
                    w.writerow(["2026-10-08", "x", "13:00:00", f"13:0{i}:00",
                                0.1, state, "", 0, 0, 1])
                w.writerow(["2026-10-08", "mastodon", "12:00:00", "12:00:01",
                            0.1, "parcial", "{'like': 1}", 0, 1, 1])
            with mock.patch.object(rq, "LOG", path), \
                 mock.patch("circuit_breaker.load", return_value={}), \
                 mock.patch.object(rq.random, "uniform", side_effect=lambda a, b: (a+b)/2):
                recovered = rq.retry_snapshot_today(at)
            self.assertEqual(recovered["x"][0], 3)
            self.assertEqual(recovered["x"][1], dt.datetime(2026, 10, 8, 14, 16))
            self.assertEqual(recovered["mastodon"], (0, None))

    def test_phone_error_wait_capped_by_deadline(self):
        import types
        clock = Clock()
        outcomes = []
        class Proxy:
            @staticmethod
            def now():
                return clock.at
            @staticmethod
            def timedelta(**kw):
                return dt.timedelta(**kw)
        with mock.patch.dict(sys.modules, {"tiktok_bulk_follow": types.SimpleNamespace(cooldown_left=lambda: 500)}), \
             mock.patch.object(rq.datetime, "datetime", Proxy), \
             mock.patch.object(rq, "control_signal", return_value=None), \
             mock.patch.object(rq, "run_round", side_effect=lambda n: outcomes.append(n) or "error"), \
             mock.patch.object(rq, "retry_snapshot_today", return_value={}), \
             mock.patch.object(rq, "nap", side_effect=lambda secs, **kw: clock.tick(secs)), \
             mock.patch.object(rq.random, "uniform", side_effect=lambda a, b: (a+b)/2):
            rq.phone_chain(clock.at + dt.timedelta(minutes=5), 1, 0)
        self.assertEqual(outcomes, ["tiktok"])
        self.assertEqual(clock.at, dt.datetime(2026, 10, 8, 13, 5))

    def test_phone_bulk_cooldown_never_starves_next_normal_round(self):
        import types
        clock = Clock()
        calls = []
        class Proxy:
            @staticmethod
            def now():
                return clock.at
            @staticmethod
            def timedelta(**kw):
                return dt.timedelta(**kw)
        def round_(network):
            calls.append((network, clock.at))
            return "ok"
        snapshot = {"tiktok_bulk": (0, clock.at + dt.timedelta(hours=3))}
        with mock.patch.dict(sys.modules, {"tiktok_bulk_follow": types.SimpleNamespace(cooldown_left=lambda: 0)}), \
             mock.patch.object(rq.datetime, "datetime", Proxy), \
             mock.patch.object(rq, "control_signal", return_value=None), \
             mock.patch.object(rq, "run_round", side_effect=round_), \
             mock.patch.object(rq, "run_bulk", side_effect=AssertionError("bulk no disponible")), \
             mock.patch.object(rq, "retry_snapshot_today", return_value=snapshot), \
             mock.patch.object(rq, "nap", side_effect=lambda secs, **kw: clock.tick(secs)), \
             mock.patch.object(rq.random, "uniform", side_effect=lambda a, b: (a+b)/2):
            rq.phone_chain(clock.at + dt.timedelta(minutes=150), 2, 0)
        self.assertEqual([n for n, _ in calls], ["tiktok", "tiktok"])
        self.assertGreaterEqual((calls[1][1] - calls[0][1]).total_seconds(), 100 * 60)

    def test_run_round_confirmed_actions_win_over_busy_and_skip_messages(self):
        import tempfile
        from types import SimpleNamespace
        from pathlib import Path
        summary = "[x] 3 confirmadas {'like': 3}, 0 saltadas, 0 fallos"
        for message in ("otra ronda esta en curso", "no se lanza",
                        "cortacircuitos ABIERTO", "MobileSessionBusy"):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as folder:
                output = SimpleNamespace(stdout=summary + "\n" + message,
                                         stderr="", returncode=0)
                with mock.patch.object(rq, "LOG", str(Path(folder) / "tiempos.csv")), \
                     mock.patch.object(rq.subprocess, "run", return_value=output):
                    self.assertEqual(rq.run_round("x"), "parcial")

    def test_bulk_round_needs_confirmed_follow_and_preserves_partial(self):
        import tempfile
        from types import SimpleNamespace
        from pathlib import Path
        cases = [
            ("sin seguimientos", 0, "saltada"),
            ("sin seguimientos", 1, "error"),
            ("confirmado follow", 0, "ok"),
            ("confirmado follow", 1, "parcial"),
            ("confirmado follow\nen descanso", 0, "parcial"),
            ("en descanso", 0, "saltada"),
        ]
        for output_text, code, expected_state in cases:
            with self.subTest(text=output_text, code=code), tempfile.TemporaryDirectory() as folder:
                output = SimpleNamespace(stdout=output_text, stderr="", returncode=code)
                with mock.patch.object(rq, "LOG", str(Path(folder) / "tiempos.csv")), \
                     mock.patch.object(rq.subprocess, "run", return_value=output):
                    result, _ = rq.run_bulk()
                self.assertEqual(result, expected_state)

    def test_resume_skips_future_or_invalid_csv_clocks(self):
        import tempfile
        import csv
        from pathlib import Path
        now = dt.datetime(2026, 10, 8, 13, 0)
        with tempfile.TemporaryDirectory() as folder:
            log = Path(folder) / "tiempos.csv"
            with log.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["fecha", "red", "inicio", "fin", "minutos",
                                 "estado", "confirmadas", "saltadas", "fallos", "codigo"])
                writer.writerow(["2026-10-08", "x", "12:00:00", "12:00:01",
                                 0.1, "error", "", 0, 1, 1])
                writer.writerow(["2026-10-08", "x", "21:00:00", "21:00:01",
                                 0.1, "error", "", 0, 1, 1])
                writer.writerow(["2026-10-08", "x", "25:00:00", "25:00:01",
                                 0.1, "error", "", 0, 1, 1])
            with mock.patch.object(rq, "LOG", str(log)):
                recovered = rq.retry_snapshot_today(now)
            self.assertEqual(recovered["x"][0], 1)

    def test_saltada_with_invalid_breaker_shape_still_backs_off(self):
        with mock.patch("circuit_breaker.load", return_value=["not", "a", "dict"]), \
             mock.patch.object(rq.random, "uniform", side_effect=lambda low, high: (low + high) / 2):
            counts, delay, alert = rq.classify_round_state("saltada", 0, network="x")
        self.assertEqual((counts, delay, alert), (False, 720, False))

    def test_run_round_rejects_summary_from_another_network(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        other = "[mastodon] 9 confirmadas {'like': 9}, 0 saltadas, 0 fallos"
        valid = "[x] 2 confirmadas {'like': 2}, 0 saltadas, 0 fallos"
        for stdout, expected in [(other, "saltada"),
                                 (valid + "\n" + other, "ok")]:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as folder:
                result = SimpleNamespace(stdout=stdout, stderr="", returncode=0)
                with mock.patch.object(rq, "LOG", str(Path(folder) / "log.csv")), \
                     mock.patch.object(rq.subprocess, "run", return_value=result):
                    self.assertEqual(rq.run_round("x"), expected)

    def test_bulk_failure_markers_override_successful_exit(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        cases = [("confirmado follow\nFALLO respuesta", 0, "parcial"),
                 ("FALLO respuesta", 0, "error"),
                 ("confirmado follow\nPARADA solicitada", 0, "parcial"),
                 ("PARADA solicitada", 0, "saltada")]
        for output, exit_code, expected in cases:
            with self.subTest(expected=expected, output=output), tempfile.TemporaryDirectory() as folder:
                process = SimpleNamespace(stdout=output, stderr="", returncode=exit_code)
                with mock.patch.object(rq, "LOG", str(Path(folder) / "log.csv")), \
                     mock.patch.object(rq.subprocess, "run", return_value=process):
                    state, _ = rq.run_bulk()
                self.assertEqual(state, expected)


if __name__ == "__main__":
    unittest.main()
