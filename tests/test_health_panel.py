"""health_panel.py (03/10): señales de salud de la automatizacion."""
import datetime
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import health_panel as hp

TODAY = datetime.date(2026, 10, 10)


def row(cuenta, tipo, fecha, resultado="confirmado"):
    return {"cuenta": cuenta, "tipo": tipo, "fecha": fecha, "resultado": resultado}


class WindowStatsTests(unittest.TestCase):
    def test_counts_window_unique_ratio_and_previously_touched_share(self):
        rows = [row("@a", "like", "2026-10-09"), row("@a", "reply", "2026-10-09"), row("@b", "follow", "2026-10-08"),
                row("@c", "like", "2026-10-01"),                      # fuera de la ventana: cuenta como "ya tocada"
                row("@c", "like", "2026-10-09"), row("@d", "like", "2026-10-09", resultado="fallo:x")]
        stats = hp.window_stats(rows, TODAY, 7)
        self.assertEqual(stats["actions"], 4)
        self.assertEqual(stats["unique_targets"], 3)
        self.assertEqual(stats["unique_ratio"], 0.75)
        self.assertEqual(stats["touched_before_pct"], 25)             # solo @c ya se habia tocado
        self.assertEqual(stats["kinds"], {"like": 2, "reply": 1, "follow": 1})

    def test_empty_window_is_safe(self):
        self.assertEqual(hp.window_stats([], TODAY)["unique_ratio"], None)


class LogErrorsTests(unittest.TestCase):
    def test_counts_rate_limits_and_failures_only_in_recent_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "mech_2026-10-09_1005.log"), "w", encoding="utf-8").write(
                "PARADA RATE LIMIT: 429\nFALLO: algo\nFALLO DE PREFLIGHT: x\n")
            open(os.path.join(tmp, "mech_2026-09-01_1005.log"), "w", encoding="utf-8").write("429 429 FALLO\n")
            hits = hp.log_errors(tmp, TODAY, 7)
            self.assertEqual((hits["429"], hits["fallos"], hits["preflight"], hits["rondas"]), (1, 1, 1, 1))

    def test_plain_numbers_containing_429_are_not_rate_limits(self):
        lines = ['"posts_seen": 1429,', '"reply": 429', 'HTTP 429 Too Many Requests']
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'mech_2026-10-09_1005.log'), 'w', encoding='utf-8') as stream:
                stream.write(chr(10).join(lines))
            self.assertEqual(hp.log_errors(tmp, TODAY, 7)['429'], 1)


if __name__ == "__main__":
    unittest.main()
