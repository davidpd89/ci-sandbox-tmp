"""R6.3: evento de cuarentena R8 se ve en informe agregado sin textos."""
import datetime
import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import round_canaries as rc


class RecoveryCanaryTests(unittest.TestCase):
    def test_event_is_visible_and_private_text_is_never_read(self):
        with tempfile.TemporaryDirectory() as root:
            base = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            base.mkdir(parents=True)
            now = datetime.datetime(2026, 10, 8, 16)
            (base / "test.json").write_text(json.dumps({
                "code": "COLA_CORRUPTA_RECUPERADA", "at": "2026-10-08T15:50:00",
                "quarantined": "pending.json.corrupto-anon",
                "texto_no_exportar": "Texto de terceros privado"
            }), encoding="utf-8")
            result = rc.collect(root, now=now, pid_alive=lambda _: False)
            matching = [a for a in result["alerts"] if a["code"] == "COLA_CORRUPTA_RECUPERADA"]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["events_in_24h"], 1)
            self.assertNotIn("Texto de terceros privado", json.dumps(result, ensure_ascii=False))

    def test_old_event_does_not_repeat_alarm_forever(self):
        with tempfile.TemporaryDirectory() as root:
            base = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            base.mkdir(parents=True)
            (base / "old.json").write_text(json.dumps({
                "code": "COLA_CORRUPTA_RECUPERADA", "at": "2026-10-01T15:50:00"
            }), encoding="utf-8")
            result = rc.collect(root, now=datetime.datetime(2026, 10, 8, 16),
                                pid_alive=lambda _: False)
            self.assertNotIn("COLA_CORRUPTA_RECUPERADA", [a["code"] for a in result["alerts"]])

    def test_real_emitter_shape_three_events_escalate_and_identify_files(self):
        with tempfile.TemporaryDirectory() as root:
            folder = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            folder.mkdir(parents=True)
            for i, file_name in enumerate(("pending.json", "answers.json", "pending.json")):
                (folder / f"{i}.json").write_text(json.dumps({
                    "code": "COLA_CORRUPTA_RECUPERADA", "file": file_name,
                    "at": f"2026-10-08T15:5{i}:00",
                    "reason": "JSONDecodeError",
                    "quarantined": f"{file_name}.corrupto-secreto",
                    "text": "PRIVADO-NO-EXPORTAR",
                }), encoding="utf-8")
            report = rc.collect(root, now=datetime.datetime(2026, 10, 8, 16),
                                pid_alive=lambda _: False)
            alerts = [x for x in report["alerts"] if x["code"] == "COLA_CORRUPTA_RECUPERADA"]
            self.assertEqual(len(alerts), 1)
            self.assertEqual(alerts[0]["events_in_24h"], 3)
            self.assertEqual(alerts[0]["severity"], "alta")
            self.assertEqual(alerts[0]["files"], ["answers.json", "pending.json"])
            self.assertEqual(alerts[0]["last_event_age_minutes"], 8)
            self.assertNotIn("PRIVADO-NO-EXPORTAR", json.dumps(report))
            self.assertNotIn("secreto", json.dumps(report))

    def test_one_recovery_is_medium_not_high_and_no_private_paths_leak(self):
        with tempfile.TemporaryDirectory() as root:
            folder = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            folder.mkdir(parents=True)
            (folder / "1.json").write_text(json.dumps({
                "code": "COLA_CORRUPTA_RECUPERADA", "at": "2026-10-08T15:45:00",
                "file": "C:/Users/privado/pending.json"
            }), encoding="utf-8")
            report = rc.collect(root, now=datetime.datetime(2026, 10, 8, 16),
                                pid_alive=lambda _: False)
            match = next(x for x in report["alerts"] if x["code"] == "COLA_CORRUPTA_RECUPERADA")
            self.assertEqual(match["severity"], "media")
            self.assertEqual(match["files"], ["desconocido"])
            self.assertEqual(match["last_event_age_minutes"], 15)
            self.assertNotIn("Users", json.dumps(report))

    def test_malformed_json_roots_timestamps_other_codes_and_size_are_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            folder = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            folder.mkdir(parents=True)
            invalid = ('{', '[]', 'null', '42', '"cad"', '{"at":null}',
                       '{"code":"OTRO", "at":"2026-10-08T15:00:00"}')
            for i, content in enumerate(invalid):
                (folder / f"bad-{i}.json").write_text(content, encoding="utf-8")
            for i, stamp in enumerate((None, 1, True, "nada", "2026-10-09T16:00:00")):
                (folder / f"date-{i}.json").write_text(json.dumps({
                    "code": "COLA_CORRUPTA_RECUPERADA", "at": stamp
                }), encoding="utf-8")
            (folder / "oversized.json").write_text(json.dumps({
                "code": "COLA_CORRUPTA_RECUPERADA", "at": "2026-10-08T15:00:00",
                "untrusted": "X" * (rc.MAX_EVENT_BYTES + 1)
            }), encoding="utf-8")
            report = rc.collect(root, now=datetime.datetime(2026, 10, 8, 16),
                                pid_alive=lambda _: False)
            self.assertFalse(any(a["code"] == "COLA_CORRUPTA_RECUPERADA"
                                 for a in report["alerts"]))

    def test_offset_dates_and_exact_24h_boundary_are_handled(self):
        with tempfile.TemporaryDirectory() as root:
            folder = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            folder.mkdir(parents=True)
            for i, stamp in enumerate(("2026-10-08T15:45:00+02:00",
                                       "2026-10-07T16:00:00+02:00",
                                       "2026-10-07T15:59:59+02:00",
                                       "2026-10-08T16:00:01+02:00")):
                (folder / f"date{i}.json").write_text(json.dumps({
                    "code": "COLA_CORRUPTA_RECUPERADA", "at": stamp,
                    "file": "answers.json"
                }), encoding="utf-8")
            local = datetime.timezone(datetime.timedelta(hours=2))
            report = rc.collect(root, now=datetime.datetime(2026, 10, 8, 16, tzinfo=local),
                                pid_alive=lambda _: False)
            match = next(x for x in report["alerts"] if x["code"] == "COLA_CORRUPTA_RECUPERADA")
            self.assertEqual(match["events_in_24h"], 2)
            self.assertEqual(match["last_event_age_minutes"], 15)

    def test_retention_7d_only_known_events_on_both_directories(self):
        with tempfile.TemporaryDirectory() as root:
            cache = pathlib.Path(root, "00_OPERATIVO", "cache")
            queue, plan = cache / "errores_cola", cache / "errores_plan"
            queue.mkdir(parents=True)
            plan.mkdir(parents=True)
            old = "2026-09-30T16:00:00"
            recent = "2026-10-08T15:00:00"
            events = (
                (queue, "old", {"code": "COLA_CORRUPTA_RECUPERADA", "at": old}),
                (queue, "fresh", {"code": "COLA_CORRUPTA_RECUPERADA", "at": recent}),
                (queue, "unknown", {"code": "OTRO", "at": old}),
                (plan, "old", {"schema": 1, "red": "mastodon", "stage": "plan", "at": old}),
                (plan, "unknown", {"red": "desconocida", "stage": "plan", "at": old}),
            )
            for directory, name, data in events:
                (directory / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")
            (queue / "invalid.json").write_text("{truncado", encoding="utf-8")
            old_epoch = datetime.datetime(2026, 9, 30, 16).timestamp()
            os.utime(queue / "old.json", (old_epoch, old_epoch))
            os.utime(plan / "old.json", (old_epoch, old_epoch))
            now = datetime.datetime(2026, 10, 8, 16)
            self.assertEqual(rc.prune_event_history(root, now=now), 2)
            self.assertFalse((queue / "old.json").exists())
            self.assertFalse((plan / "old.json").exists())
            self.assertTrue((queue / "fresh.json").exists())
            self.assertTrue((queue / "unknown.json").exists())
            self.assertTrue((queue / "invalid.json").exists())
            self.assertTrue((plan / "unknown.json").exists())
            self.assertEqual(rc.prune_event_history(root, now=now), 0)

    def test_collect_and_check_only_never_delete_history(self):
        from contextlib import redirect_stdout
        from io import StringIO
        with tempfile.TemporaryDirectory() as root:
            queue = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            queue.mkdir(parents=True)
            path = queue / "old.json"
            path.write_text(json.dumps({
                "code": "COLA_CORRUPTA_RECUPERADA", "at": "2001-01-01T00:00:00"
            }), encoding="utf-8")
            rc.collect(root, now=datetime.datetime(2026, 10, 8, 16),
                       pid_alive=lambda _: False)
            self.assertTrue(path.exists())
            with redirect_stdout(StringIO()):
                self.assertEqual(rc.main(["--root", root, "--check-only"]), 0)
            self.assertTrue(path.exists())
            self.assertFalse(pathlib.Path(root, "00_OPERATIVO", "cache",
                                          "alertas_rondas.json").exists())

    def test_default_cli_exports_and_prunes_old_events(self):
        from contextlib import redirect_stdout
        from io import StringIO
        with tempfile.TemporaryDirectory() as root:
            queue = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            queue.mkdir(parents=True)
            path = queue / "old.json"
            path.write_text(json.dumps({
                "code": "COLA_CORRUPTA_RECUPERADA", "at": "2001-01-01T00:00:00"
            }), encoding="utf-8")
            os.utime(path, (datetime.datetime(2001, 1, 1).timestamp(),) * 2)
            with redirect_stdout(StringIO()):
                self.assertEqual(rc.main(["--root", root]), 0)
            self.assertFalse(path.exists())
            output = pathlib.Path(root, "00_OPERATIVO", "cache", "alertas_rondas.json")
            self.assertTrue(output.is_file())
            self.assertNotIn("COLA_CORRUPTA_RECUPERADA",
                             [a["code"] for a in json.loads(output.read_text(encoding="utf-8"))["alerts"]])


    def test_old_payload_created_today_is_never_deleted(self):
        with tempfile.TemporaryDirectory() as root:
            cache = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            cache.mkdir(parents=True)
            path = cache / "fresh.json"
            path.write_text(json.dumps({
                "code": "COLA_CORRUPTA_RECUPERADA", "at": "2001-01-01T00:00:00"
            }), encoding="utf-8")
            now = datetime.datetime.now()  # la fecha de escritura es actual
            self.assertEqual(rc.prune_event_history(root, now=now), 0)
            self.assertTrue(path.exists())

    def test_replaced_event_is_not_unlinked_during_cleanup(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as root:
            cache = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            cache.mkdir(parents=True)
            path = cache / "old.json"
            old_at = "2001-01-01T00:00:00"
            event = {"code": "COLA_CORRUPTA_RECUPERADA", "at": old_at}
            path.write_text(json.dumps(event), encoding="utf-8")
            os.utime(path, (datetime.datetime(2001, 1, 1).timestamp(),) * 2)
            original = rc._read_local_event

            def concurrent_writer(p):
                value = original(p)
                if p == path:
                    path.write_text(json.dumps({"code": "OTRO", "at": old_at,
                                                "text": "NO BORRAR"}), encoding="utf-8")
                return value

            with mock.patch.object(rc, "_read_local_event", side_effect=concurrent_writer):
                self.assertEqual(rc.prune_event_history(root), 0)
            self.assertTrue(path.exists())
            self.assertIn("NO BORRAR", path.read_text(encoding="utf-8"))

    def test_bad_json_duplicate_keys_nonstandard_numbers_and_utf8(self):
        with tempfile.TemporaryDirectory() as root:
            cache = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            cache.mkdir(parents=True)
            records = [
                b'{"code":"COLA_CORRUPTA_RECUPERADA","code":"OTRO","at":"2026-10-08T15:00:00"}',
                b'{"code":"COLA_CORRUPTA_RECUPERADA","at":"2026-10-08T15:00:00","extra":NaN}',
                b'{"code":"COLA_CORRUPTA_RECUPERADA","at":"2026-10-08T15:00:00","extra":Infinity}',
                bytes((255, 254)),
            ]
            for i, raw in enumerate(records):
                (cache / f"bad{i}.json").write_bytes(raw)
            self.assertEqual(rc.collect(root, now=datetime.datetime(2026, 10, 8, 16),
                                        pid_alive=lambda _: False)["alerts"], [])

    def test_file_limit_is_bytes_not_codepoints(self):
        with tempfile.TemporaryDirectory() as root:
            cache = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            cache.mkdir(parents=True)
            path = cache / "large.json"
            path.write_text(json.dumps({
                "code": "COLA_CORRUPTA_RECUPERADA", "at": "2026-10-08T15:00:00",
                "extra": "á" * (rc.MAX_EVENT_BYTES // 2),
            }, ensure_ascii=False), encoding="utf-8")
            self.assertGreater(path.stat().st_size, rc.MAX_EVENT_BYTES)
            self.assertIsNone(rc._read_local_event(path))

    def test_plan_event_without_schema_one_not_auto_deleted(self):
        with tempfile.TemporaryDirectory() as root:
            p = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_plan")
            p.mkdir(parents=True)
            path = p / "unknown.json"
            path.write_text(json.dumps({"red": "mastodon", "stage": "plan",
                                        "at": "2001-01-01T00:00:00"}), encoding="utf-8")
            os.utime(path, (datetime.datetime(2001, 1, 1).timestamp(),) * 2)
            self.assertEqual(rc.prune_event_history(root), 0)
            self.assertTrue(path.exists())

    def test_directory_failure_reports_high_severity_without_private_paths(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as root:
            directory = pathlib.Path(root, "00_OPERATIVO", "cache", "errores_cola")
            directory.mkdir(parents=True)
            previous = pathlib.Path.glob

            def broken(folder, pattern):
                if folder == directory:
                    raise PermissionError("C:/Users/privado")
                return previous(folder, pattern)

            with mock.patch.object(pathlib.Path, "glob", broken):
                alert = rc._queue_recovery_alerts(pathlib.Path(root), datetime.datetime.now())
            self.assertEqual(len(alert), 1)
            self.assertEqual(alert[0]["code"], "REGISTRO_EVENTOS_COLA_INACCESIBLE")
            self.assertEqual(alert[0]["severity"], "alta")
            self.assertNotIn("privado", json.dumps(alert))


if __name__ == "__main__":
    unittest.main()
