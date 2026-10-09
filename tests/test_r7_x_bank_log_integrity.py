"""R7: un registro corrupto del banco no debe permitir otra ficha de X."""
import datetime as dt
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import x_bank_publish as bank
import content_publisher as cp


class LogIntegrityTests(unittest.TestCase):
    def test_missing_bank_log_is_normal_first_day(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(bank.read_log(pathlib.Path(d) / "missing.csv", strict=True), [])

    def test_bad_header_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "bank.csv"
            path.write_text("bad,columns\nfoo,bar\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cabecera"):
                bank.read_log(path, strict=True)

    def test_bad_date_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "bank.csv"
            path.write_text("fecha_hora,id,texto,url\nINVALID,b1,hola,https://x.com/1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fecha"):
                bank.read_log(path, strict=True)

    def test_duplicate_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "bank.csv"
            path.write_text("fecha_hora,fecha_hora,id,texto,url\n"
                            "2026-10-08T17:00,2026-10-08T17:00,b1,hola,https://x.com/1\n",
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cabecera"):
                bank.read_log(path, strict=True)

    def test_incomplete_or_extra_columns_are_rejected(self):
        for line in ("2026-10-08T17:00,b1,hola\n",
                     "2026-10-08T17:00,b1,hola,https://x.com/1,otra\n"):
            with self.subTest(line=line), tempfile.TemporaryDirectory() as d:
                path = pathlib.Path(d) / "bank.csv"
                path.write_text("fecha_hora,id,texto,url\n" + line, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "fila incompleta"):
                    bank.read_log(path, strict=True)

    def test_offset_date_is_read_as_madrid_wall_time(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "bank.csv"
            path.write_text("fecha_hora,id,texto,url\n"
                            "2026-10-08T15:00:00+00:00,b1,hola,https://x.com/1\n",
                            encoding="utf-8")
            self.assertEqual(bank.read_log(path, strict=True)[0]["when"],
                             dt.datetime(2026, 10, 8, 17))

    def test_record_normalizes_utc_to_madrid(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "bank.csv"
            bank.record({"id": "b1", "text": "hola"}, "https://x.com/1",
                        now=dt.datetime(2026, 10, 8, 15, tzinfo=dt.timezone.utc),
                        path=str(path))
            self.assertEqual(bank.read_log(path, strict=True)[0]["when"],
                             dt.datetime(2026, 10, 8, 17))
            self.assertNotIn("+00:00", path.read_text(encoding="utf-8"))

    def test_strict_reader_rejects_unclosed_quote(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "bank.csv"
            path.write_text('fecha_hora,id,texto,url\n'
                            '2026-10-08T17:00,b1,hola,"https://x.com/1\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CSV"):
                bank.read_log(path, strict=True)

    def test_strict_reader_rejects_invalid_utf8(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "bank.csv"
            path.write_bytes(b"fecha_hora,id,texto,url\n2026-10-08T17:00,b1,\xff,https://x.com/1\n")
            with self.assertRaisesRegex(ValueError, "codificación"):
                bank.read_log(path, strict=True)

    def test_content_log_with_offset_is_madrid_local(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "fichas.csv"
            path.write_text("fecha_hora,red,ficha,programada,url\n"
                            "2026-10-08T15:00:00+00:00,x,uno,2026-10-08 10:00,https://x.com/1\n",
                            encoding="utf-8")
            self.assertEqual(cp.last_auto_publication("x", str(path)),
                             dt.datetime(2026, 10, 8, 17))

    def test_real_utc_offset_log_blocks_x_ficha(self):
        now = dt.datetime(2026, 10, 8, 18)
        item = {"md_path": "/f/post/publicacion.md", "carpeta": "/f/post",
                "fecha_hora": now - dt.timedelta(days=1), "texto": "Ficha",
                "estado": "lista", "media": [], "blockers": []}
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "posts_banco.csv"
            path.write_text("fecha_hora,id,texto,url\n"
                            "2026-10-08T15:00:00+00:00,b1,hola,https://x.com/1\n",
                            encoding="utf-8")
            published = []
            with mock.patch.object(bank, "LOG", str(path)), \
                 mock.patch.object(cp, "load_config", return_value={
                     "enabled": {"x": True}, "max_overdue_days": 14}), \
                 mock.patch.object(cp.cq, "pending_parse_issues", return_value=[]), \
                 mock.patch.object(cp, "eligible", return_value=([item], [])), \
                 mock.patch.object(cp, "last_auto_publication", return_value=None):
                result = cp.run("x", apply=True, now=now,
                                publishers={"x": lambda _: published.append(1) or "https://x.com/2"},
                                verify=lambda *_: None)
            self.assertIsNone(result)
            self.assertEqual(published, [])

    def test_x_ficha_log_writes_madrid_even_on_utc_host(self):
        from zoneinfo import ZoneInfo
        item = {"carpeta": "/f/uno", "fecha_hora": dt.datetime(2026, 10, 8, 10)}
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "fichas.csv"
            with mock.patch.object(cp, "LOG", str(path)):
                cp._log("x", item, "https://x.com/1")
            when = cp.last_auto_publication("x", str(path))
            madrid_now = dt.datetime.now(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
            self.assertLess(abs((when - madrid_now).total_seconds()), 90)

    def test_valid_csv_preserves_date(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "bank.csv"
            bank.record({"id": "a1", "text": "Una pregunta"}, "https://x.com/1",
                        now=dt.datetime(2026, 10, 8, 17), path=str(path))
            rows = bank.read_log(path, strict=True)
            self.assertEqual(rows[0]["when"], dt.datetime(2026, 10, 8, 17))

    def test_content_publisher_does_not_publish_with_corrupt_bank(self):
        now = dt.datetime(2026, 10, 8, 18)
        item = {"md_path": "/f/post/publicacion.md", "carpeta": "/f/post",
                "fecha_hora": now - dt.timedelta(days=1), "texto": "Ficha",
                "estado": "lista", "media": [], "blockers": []}
        published = []
        logs = []
        with mock.patch.object(cp, "load_config", return_value={
                 "enabled": {"x": True}, "max_overdue_days": 14}), \
             mock.patch.object(cp.cq, "pending_parse_issues", return_value=[]), \
             mock.patch.object(cp, "eligible", return_value=([item], [])), \
             mock.patch.object(cp, "last_auto_publication", return_value=None), \
             mock.patch.object(bank, "read_log", side_effect=ValueError("cabecera")):
            result = cp.run("x", apply=True, now=now, out=logs.append,
                            publishers={"x": lambda _: published.append(1) or "https://x.com/2"},
                            verify=lambda *_: None)
        self.assertIsNone(result)
        self.assertEqual(published, [])
        self.assertTrue(any("no verificable" in text for text in logs))
        self.assertTrue(any("ERROR" in text for text in logs))


if __name__ == "__main__":
    unittest.main()
