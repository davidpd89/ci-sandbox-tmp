"""Regresiones R7: ambas rutas X deben validar sus dos registros."""
import contextlib
import datetime as dt
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import content_publisher as cp
import x_bank_publish as bank
import action_ledger


NOW = dt.datetime(2026, 10, 8, 18)
ITEM = {"md_path": "/test/publicacion.md", "carpeta": "/test",
        "fecha_hora": NOW - dt.timedelta(days=1), "texto": "Ficha",
        "estado": "lista", "media": [], "blockers": []}
POST = {"id": "P001", "text": "¿Qué libro releerías?"}


class StrictXHistoryTests(unittest.TestCase):
    def test_ficha_log_bad_timestamp_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "fichas.csv"
            path.write_text("fecha_hora,red,ficha,programada,url\n"
                            "NO_ES_FECHA,x,uno,2026-10-08 12:00,https://x.com/1\n",
                            encoding="utf-8")
            with self.assertRaises(ValueError):
                cp.last_auto_publication("x", str(path), strict=True)

    def test_ficha_log_extra_csv_column_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "fichas.csv"
            path.write_text("fecha_hora,red,ficha,programada,url\n"
                            "2026-10-08T17:00,x,uno,2026-10-08 12:00,https://x.com/1,EXTRA\n",
                            encoding="utf-8")
            with self.assertRaises(ValueError):
                cp.last_auto_publication("x", str(path), strict=True)

    def test_strict_reader_rejects_disappeared_bank_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            missing_path = pathlib.Path(temp) / "deleted_directory" / "posts_banco.csv"
            with self.assertRaises(OSError):
                bank.read_log(missing_path, strict=True)

    def test_first_day_bank_csv_can_be_absent_if_directory_exists(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(bank.read_log(pathlib.Path(temp) / "posts_banco.csv", strict=True), [])

    def test_ficha_blocks_if_bank_reader_returns_invalid_when(self):
        sent, messages = [], []
        with mock.patch.object(cp, "load_config", return_value={
                 "enabled": {"x": True}, "max_overdue_days": 14}), \
             mock.patch.object(cp.cq, "pending_parse_issues", return_value=[]), \
             mock.patch.object(cp, "eligible", return_value=([dict(ITEM)], [])), \
             mock.patch.object(cp, "last_auto_publication", return_value=None), \
             mock.patch.object(bank, "read_log", return_value=[
                 {"id": "broken", "when": "invalid"}]):
            result = cp.run("x", apply=True, now=NOW,
                            out=messages.append,
                            publishers={"x": lambda _: sent.append("published")},
                            verify=lambda *_: None)
        self.assertIsNone(result)
        self.assertFalse(sent)
        self.assertTrue(any("no verificable" in line for line in messages))

    def test_aware_utc_now_is_normalized_for_x_ficha(self):
        sent = []
        with mock.patch.object(cp, "load_config", return_value={
                 "enabled": {"x": True}, "max_overdue_days": 14}), \
             mock.patch.object(cp.cq, "pending_parse_issues", return_value=[]), \
             mock.patch.object(cp, "eligible", return_value=([dict(ITEM)], [])), \
             mock.patch.object(cp, "last_auto_publication", return_value=None), \
             mock.patch.object(bank, "read_log", return_value=[
                 {"id": "b1", "when": NOW - dt.timedelta(hours=1)}]):
            result = cp.run("x", apply=True,
                            now=dt.datetime(2026, 10, 8, 16, tzinfo=dt.timezone.utc),
                            publishers={"x": lambda _: sent.append("published")},
                            verify=lambda *_: None)
        self.assertIsNone(result)
        self.assertFalse(sent)

    def test_bank_does_not_publish_when_its_real_csv_is_corrupt(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "posts_banco.csv"
            path.write_text("fecha_hora,id,texto,url\nBAD,b1,hola,https://x.com/1\n",
                            encoding="utf-8")
            with mock.patch.object(bank, "LOG", str(path)), \
                 mock.patch.object(bank, "load_bank", return_value=[POST]), \
                 mock.patch.object(cp, "last_auto_publication", return_value=None), \
                 mock.patch.object(action_ledger, "browser_session", return_value=contextlib.nullcontext()), \
                 mock.patch.dict(sys.modules, {"x_interact": mock.Mock()}):
                posted = sys.modules["x_interact"].post
                self.assertEqual(bank.main(["--apply"]), 1)
                posted.assert_not_called()

    def test_bank_does_not_publish_if_ficha_history_is_corrupt(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "fichas.csv"
            path.write_text("fecha_hora,red,ficha,programada,url\n"
                            "BAD,x,uno,2026-10-08 12:00,https://x.com/1\n",
                            encoding="utf-8")
            with mock.patch.object(cp, "LOG", str(path)), \
                 mock.patch.object(bank, "read_log", return_value=[]), \
                 mock.patch.object(bank, "load_bank", return_value=[POST]), \
                 mock.patch.object(action_ledger, "browser_session", return_value=contextlib.nullcontext()), \
                 mock.patch.dict(sys.modules, {"x_interact": mock.Mock()}):
                posted = sys.modules["x_interact"].post
                self.assertEqual(bank.main(["--apply"]), 1)
                posted.assert_not_called()

    def test_bank_integrity_error_is_visible_to_orchestrator(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "posts_banco.csv"
            path.write_text("fecha_hora,id,texto,url\nBAD,b1,hola,https://x.com/1\n",
                            encoding="utf-8")
            with mock.patch.object(bank, "LOG", str(path)), \
                 mock.patch.object(bank, "load_bank", return_value=[POST]), \
                 mock.patch("builtins.print") as output:
                result = bank.main(["--apply"])
            self.assertEqual(result, 1)
            self.assertTrue(any("ERROR integridad" in str(c) for c in output.call_args_list))

    def test_elapsed_clock_is_conservative_across_spring_dst(self):
        before = dt.datetime(2026, 3, 29, 0, 30)
        after_five_real_hours = dt.datetime(2026, 3, 29, 6, 30)
        after_six_real_hours = dt.datetime(2026, 3, 29, 7, 30)
        self.assertEqual(bank.conservative_elapsed_seconds(after_five_real_hours, before), 5 * 3600)
        self.assertEqual(bank.conservative_elapsed_seconds(after_six_real_hours, before), 6 * 3600)
        choice, why = bank.choose([POST], [], now=after_five_real_hours,
                                  last_other_post=before)
        self.assertIsNone(choice)
        self.assertIn("minimo", why)
        choice, _ = bank.choose([POST], [], now=after_six_real_hours,
                                last_other_post=before)
        self.assertEqual(choice, POST)

    def test_elapsed_clock_stays_conservative_during_autumn_fold(self):
        previous = dt.datetime(2026, 10, 25, 2, 30)  # repetida en Madrid
        later = dt.datetime(2026, 10, 25, 8, 0)
        self.assertEqual(bank.conservative_elapsed_seconds(later, previous),
                         int(5.5 * 3600))

    def test_bank_future_outlier_does_not_freeze_own_publications(self):
        future = [{"id": "outlier", "when": NOW + dt.timedelta(days=4)}]
        item, reason = bank.choose([POST], future, now=NOW)
        self.assertEqual(item, POST)
        self.assertEqual(reason, "")
        item, _ = bank.choose([POST], [], now=NOW,
                              last_other_post=NOW + dt.timedelta(days=4))
        self.assertEqual(item, POST)

    def test_bank_future_today_is_ignored_but_recent_today_blocks(self):
        item, _ = bank.choose([POST],
                              [{"id": "future", "when": NOW + dt.timedelta(hours=1)}],
                              now=NOW)
        self.assertEqual(item, POST)
        item, reason = bank.choose([POST],
                                   [{"id": "recent", "when": NOW + dt.timedelta(minutes=5)}],
                                   now=NOW)
        self.assertIsNone(item)
        self.assertIn("hoy", reason)

    def test_bank_rechecks_corruption_after_acquiring_edge(self):
        records = []
        @contextlib.contextmanager
        def acquire(**_kwargs):
            records.append("locked")
            yield
        def bank_log(*, strict=False):
            if "locked" in records:
                raise ValueError("CSV corrupto durante espera")
            return []
        with mock.patch.object(bank, "load_bank", return_value=[POST]), \
             mock.patch.object(bank, "read_log", side_effect=bank_log), \
             mock.patch.object(cp, "last_auto_publication", return_value=None), \
             mock.patch.object(action_ledger, "browser_session", side_effect=acquire), \
             mock.patch.dict(sys.modules, {"x_interact": mock.Mock()}):
            posted = sys.modules["x_interact"].post
            self.assertEqual(bank.main(["--apply"]), 1)
            posted.assert_not_called()
        self.assertEqual(records, ["locked"])

    def test_x_history_ignores_future_outlier_but_keeps_recent_row(self):
        notices = []
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "fichas.csv"
            path.write_text("fecha_hora,red,ficha,programada,url\n"
                            "2026-10-08T17:00,x,uno,2026-10-08 12:00,https://x.com/1\n"
                            "2026-10-13T17:00,x,dos,2026-10-08 12:00,https://x.com/2\n",
                            encoding="utf-8")
            recent = cp.last_auto_publication(
                "x", str(path), strict=True,
                not_after=NOW + dt.timedelta(minutes=5), notify=notices.append)
            self.assertEqual(recent, dt.datetime(2026, 10, 8, 17))
            self.assertTrue(any("futuro" in line for line in notices))

    def test_future_only_x_ficha_log_does_not_block_publishing(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "fichas.csv"
            path.write_text("fecha_hora,red,ficha,programada,url\n"
                            "2026-10-13T17:00,x,dos,2026-10-08 12:00,https://x.com/2\n",
                            encoding="utf-8")
            sent, messages = [], []
            with mock.patch.object(cp, "LOG", str(path)), \
                 mock.patch.object(cp, "load_config", return_value={
                     "enabled": {"x": True}, "max_overdue_days": 14}), \
                 mock.patch.object(cp.cq, "pending_parse_issues", return_value=[]), \
                 mock.patch.object(cp, "eligible", return_value=([dict(ITEM)], [])), \
                 mock.patch.object(cp.cq, "mark_done"), \
                 mock.patch.object(cp, "_log"), \
                 mock.patch.object(bank, "read_log", return_value=[]):
                url = cp.run("x", apply=True, now=NOW,
                             out=messages.append,
                             publishers={"x": lambda _: sent.append(1) or "https://x.com/new"},
                             verify=lambda *_: None)
            self.assertEqual(url, "https://x.com/new")
            self.assertEqual(sent, [1])
            self.assertTrue(any("futuro" in line for line in messages))

    def test_recent_ficha_still_blocks_if_future_outlier_is_also_present(self):
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "fichas.csv"
            path.write_text("fecha_hora,red,ficha,programada,url\n"
                            "2026-10-08T17:00,x,uno,2026-10-08 12:00,https://x.com/1\n"
                            "2026-10-13T17:00,x,dos,2026-10-08 12:00,https://x.com/2\n",
                            encoding="utf-8")
            sent = []
            with mock.patch.object(cp, "LOG", str(path)), \
                 mock.patch.object(cp, "load_config", return_value={
                     "enabled": {"x": True}, "max_overdue_days": 14}), \
                 mock.patch.object(cp.cq, "pending_parse_issues", return_value=[]), \
                 mock.patch.object(cp, "eligible", return_value=([dict(ITEM)], [])), \
                 mock.patch.object(bank, "read_log", return_value=[]):
                result = cp.run("x", apply=True, now=NOW,
                                out=lambda *_: None,
                                publishers={"x": lambda _: sent.append(1)},
                                verify=lambda *_: None)
            self.assertIsNone(result)
            self.assertEqual(sent, [])

    def test_x_main_revalidates_both_logs_in_strict_mode(self):
        seen = []
        @contextlib.contextmanager
        def acquired(**_kwargs):
            seen.append("lock")
            yield
        def bank_log(*, strict=False):
            seen.append(("bank", strict))
            return []
        def ficha_log(network, *, strict=False, not_after=None, notify=None):
            seen.append(("ficha", network, strict))
            return None
        with mock.patch.object(bank, "load_bank", return_value=[POST]), \
             mock.patch.object(bank, "read_log", side_effect=bank_log), \
             mock.patch.object(cp, "last_auto_publication", side_effect=ficha_log), \
             mock.patch.object(action_ledger, "browser_session", side_effect=acquired), \
             mock.patch.object(bank, "record"), \
             mock.patch.dict(sys.modules, {"x_interact": mock.Mock()}):
            sys.modules["x_interact"].post.return_value = "https://x.com/1"
            self.assertEqual(bank.main(["--apply"]), 0)
        self.assertEqual(seen.count(("bank", True)), 2)
        self.assertEqual(seen.count(("ficha", "x", True)), 2)
        self.assertIn("lock", seen)


if __name__ == "__main__":
    unittest.main()
