"""Tests sintéticos de telemetría read-only: no API ni disco real."""
import datetime
import contextlib
import io
import json
import pathlib
import tempfile
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reply_quality_metrics as metrics

NOW = datetime.datetime(2026, 10, 9, 12, 0)


def fresh(entry):
    try:
        return 0 <= (NOW - datetime.datetime.fromisoformat(entry["ts"])).total_seconds() < 36 * 3600
    except (KeyError, TypeError, ValueError):
        return False


def entry(net, state, reply=None, stamp="2026-10-09T10:00:00"):
    return {"network": net, "state": state, "reply": reply, "ts": stamp,
            "source_hash": "test" if state == "written" else None}


class QualitySnapshotTests(unittest.TestCase):
    def report(self, pending=None, answers=None, **kw):
        return metrics.summarize(pending or {}, answers or {}, fresh=fresh,
                                 prefix=lambda s: " ".join(s.lower().split()[:2]),
                                 supported=("bluesky", "mastodon", "tiktok", "pinterest"), **kw)

    def test_separates_networks_and_does_not_invent_replies(self):
        rows = self.report(answers={"1": entry("bluesky", "written", "Buen giro"),
                                    "2": entry("mastodon", "null"),
                                    "3": entry("bluesky", "rejected")})["redes"]
        self.assertEqual(rows["bluesky"]["escritas"], 1)
        self.assertEqual(rows["bluesky"]["rechazos_formales"], 1)
        self.assertEqual(rows["mastodon"]["abstenciones_explicitas"], 1)
        self.assertEqual(rows["tiktok"]["escritas"], 0)
        self.assertEqual(rows["bluesky"]["tasa_escritura_resueltas"], 0.5)
        self.assertIsNone(rows["bluesky"]["replicas_atribuidas"])
        self.assertIsNone(rows["bluesky"]["publicadas_atribuidas"])

    def test_legacy_is_not_relabelled_as_rejection(self):
        value = entry("tiktok", "null")
        del value["state"]
        out = self.report(answers={"a": value})["redes"]["tiktok"]
        self.assertEqual(out["estados_legacy_indeterminados"], 1)
        self.assertEqual(out["abstenciones_explicitas"], 0)
        self.assertIsNone(out["tasa_escritura_resueltas"])

    def test_expired_and_future_entries_not_included(self):
        out = self.report(pending={"old": entry("tiktok", "null", stamp="2026-10-01T08:00:00")},
                          answers={"a": entry("tiktok", "written", "No repetir", "2026-10-01T08:00:00")})["redes"]["tiktok"]
        self.assertEqual(out["respuestas_caducadas"], 1)
        self.assertEqual(out["pendientes_caducados"], 1)
        self.assertEqual(out["escritas"], 0)

    def test_variety_minimum_sample_and_no_text_leak(self):
        answers = {str(i): entry("bluesky", "written", f"Buen libro {i}") for i in range(10)}
        data = self.report(answers=answers)
        self.assertEqual(data["redes"]["bluesky"]["tasa_variedad_arranques"], 0.1)
        self.assertNotIn("Buen libro", json.dumps(data))
        self.assertNotIn("test", json.dumps(data))

    def test_missing_cache_not_reported_as_zero_confidence(self):
        result = self.report(answers_missing=True, pending_missing=True)
        self.assertTrue(result["datos_parciales"])
        self.assertIsNone(result["redes"]["bluesky"]["tasa_escritura_resueltas"])

    def test_mismatched_and_missing_network_explicitly_unattributed(self):
        data = self.report(answers={"legacy": {"state": "written", "reply": "Texto",
                                                     "ts": "2026-10-09T10:00:00"}})
        self.assertEqual(data["otros"]["respuestas_sin_red_soportada"], 1)

    def test_snapshot_uses_only_nondestructive_reader(self):
        queue = types.ModuleType("reply_queue")
        queue.PENDING, queue.ANSWERS = "pending.json", "answers.json"
        queue._fresh = fresh
        queue.TTL_HOURS = 36
        writer = types.ModuleType("reply_writer")
        writer.MAX_CHARS = {"bluesky": 200}
        writer._start = lambda s: s
        with tempfile.TemporaryDirectory() as directory:
            queue.PENDING = str(pathlib.Path(directory) / "pending.json")
            queue.ANSWERS = str(pathlib.Path(directory) / "answers.json")
            with patch.dict(sys.modules, {"reply_queue": queue, "reply_writer": writer}):
                report = metrics.snapshot()
                self.assertTrue(report["datos_parciales"])
                self.assertIsNone(report["redes"]["bluesky"]["tasa_escritura_resueltas"])

    def test_invalid_snapshot_fails_closed_and_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "answers.json"
            path.write_text('{"k": {"state": "written", "reply": "x"}}', encoding="utf-8")
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                metrics._read_only_json(path, "answers")
            self.assertEqual(before, path.read_bytes())


    def test_old_answer_without_network_disables_rate_for_every_network(self):
        data = self.report(answers={
            "old": {"reply": "Un texto válido", "ts": "2026-10-09T10:00:00"},
            "new": entry("bluesky", "written", "Qué sorpresa"),
        })
        self.assertTrue(data["datos_parciales"])
        self.assertTrue(data["atribucion_incompleta"])
        self.assertEqual(data["otros"]["respuestas_sin_red_soportada"], 1)
        self.assertIsNone(data["redes"]["bluesky"]["tasa_escritura_resueltas"])
        self.assertFalse(data["redes"]["mastodon"]["atribuible_completo"])

    def test_rejected_json_with_duplicate_keys_never_changes_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "answers.json"
            source = ('{"a":{"reply":null,"state":"null",'
                      '"ts":"2026-10-09T10:00:00"},'
                      '"a":{"reply":"Inyección","state":"written",'
                      '"ts":"2026-10-09T10:00:00"}}')
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "clave_json_duplicada"):
                metrics._read_only_json(path, "answers")
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_nested_duplicate_key_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "answers.json"
            path.write_text('{"a":{"reply":null,"reply":"x","ts":"2026-10-09T10:00:00"}}',
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "clave_json_duplicada"):
                metrics._read_only_json(path, "answers")

    def test_nan_in_json_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "answers.json"
            path.write_text('{"a":{"reply":null,"ts":"2026-10-09T10:00:00","x":NaN}}',
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "numero_json_no_finito"):
                metrics._read_only_json(path, "answers")

    def test_malformed_dates_fail_as_value_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "answers.json"
            for value in ("no-es-fecha", 9, True, None, "2026-10-09T10:00:00+02:00"):
                path.write_text(json.dumps({"a": {"ts": value, "reply": None}}),
                                encoding="utf-8")
                with self.assertRaises(ValueError):
                    metrics._read_only_json(path, "answers")

    def test_pending_without_text_or_network_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "pending.json"
            for pending in ({"network": "tiktok", "text": ""},
                            {"network": "", "text": "Algo"},
                            {"network": "tiktok", "text": 5}):
                path.write_text(json.dumps({"k": dict(pending, ts="2026-10-09T10:00:00")}),
                                encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "pendiente_invalido"):
                    metrics._read_only_json(path, "pending")

    def test_bad_answer_status_and_type_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "answers.json"
            for data in ({"reply": "Texto", "state": None},
                         {"reply": "Texto", "state": "futuro"},
                         {"reply": None, "state": "written"},
                         {"reply": "Texto", "state": "rejected"},
                         {"reply": [], "state": "written"},
                         {"reply": "Texto", "network": 1}):
                path.write_text(json.dumps({"k": dict(data, ts="2026-10-09T10:00:00")}),
                                encoding="utf-8")
                with self.assertRaises(ValueError):
                    metrics._read_only_json(path, "answers")

    def test_future_answers_and_expired_answers_not_counted_in_synthetic_clock(self):
        answers = {
            "future": entry("bluesky", "written", "Todavía no",
                            stamp="2026-10-09T12:10:00"),
            "old": entry("bluesky", "null",
                         stamp="2026-10-06T08:00:00"),
        }
        data = self.report(answers=answers)
        self.assertEqual(data["redes"]["bluesky"]["escritas"], 0)
        self.assertEqual(data["redes"]["bluesky"]["respuestas_caducadas"], 2)

    def test_does_not_claim_rate_on_pending_without_answers_file(self):
        data = self.report(
            pending={"k": entry("tiktok", "null")},
            answers_missing=True,
        )
        self.assertEqual(data["redes"]["tiktok"]["pendientes"], 1)
        self.assertIsNone(data["redes"]["tiktok"]["tasa_escritura_resueltas"])


    def test_full_snapshot_v3_with_real_temp_files_and_pending_overlap(self):
        queue = types.ModuleType("reply_queue")
        queue.TTL_HOURS = 36
        writer = types.ModuleType("reply_writer")
        writer.MAX_CHARS = {"bluesky": 200, "mastodon": 230}
        writer._start = lambda text: " ".join(text.lower().split()[:2])
        with tempfile.TemporaryDirectory() as directory:
            queue.PENDING = str(pathlib.Path(directory) / "pending.json")
            queue.ANSWERS = str(pathlib.Path(directory) / "answers.json")
            pending = {"k": {"ts": "2026-10-09T11:00:00", "network": "bluesky",
                             "text": "Quiero leer este libro"}}
            answers = {
                "k": {"ts": "2026-10-09T11:00:00", "network": "bluesky",
                      "state": "written", "reply": "Tiene buena pinta",
                      "source_hash": "a" * 64},
                "z": {"ts": "2026-10-09T11:00:00", "network": "bluesky",
                      "state": "null", "reply": None},
            }
            pathlib.Path(queue.PENDING).write_text(json.dumps(pending), encoding="utf-8")
            pathlib.Path(queue.ANSWERS).write_text(json.dumps(answers), encoding="utf-8")
            before = tuple(pathlib.Path(p).read_bytes() for p in (queue.PENDING, queue.ANSWERS))
            with patch.dict(sys.modules, {"reply_queue": queue, "reply_writer": writer}):
                result = metrics.snapshot(now=NOW)
            row = result["redes"]["bluesky"]
            self.assertFalse(result["datos_parciales"])
            self.assertEqual(row["escritas"], 1)
            self.assertEqual(row["abstenciones_explicitas"], 1)
            self.assertEqual(row["con_huella_contextual"], 1)
            self.assertEqual(row["solapan_respuesta"], 1)
            self.assertEqual(row["tasa_escritura_resueltas"], 0.5)
            self.assertEqual(tuple(pathlib.Path(p).read_bytes()
                                   for p in (queue.PENDING, queue.ANSWERS)), before)

    def test_full_snapshot_legacy_v1_cannot_attribute_old_replies(self):
        queue = types.ModuleType("reply_queue")
        queue.TTL_HOURS = 36
        writer = types.ModuleType("reply_writer")
        writer.MAX_CHARS = {"bluesky": 200, "tiktok": 90}
        writer._start = lambda text: text.lower().split()[0]
        with tempfile.TemporaryDirectory() as directory:
            queue.PENDING = str(pathlib.Path(directory) / "pending.json")
            queue.ANSWERS = str(pathlib.Path(directory) / "answers.json")
            pathlib.Path(queue.PENDING).write_text("{}", encoding="utf-8")
            pathlib.Path(queue.ANSWERS).write_text(
                '{"old":{"reply":"Qué bien","ts":"2026-10-09T10:00:00"}}',
                encoding="utf-8")
            with patch.dict(sys.modules, {"reply_queue": queue, "reply_writer": writer}):
                result = metrics.snapshot(now=NOW)
            self.assertTrue(result["atribucion_incompleta"])
            self.assertEqual(result["otros"]["respuestas_sin_red_soportada"], 1)
            self.assertIsNone(result["redes"]["bluesky"]["tasa_escritura_resueltas"])

    def test_invalid_contextual_hash_and_retry_metadata_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            answers = pathlib.Path(directory) / "answers.json"
            pending = pathlib.Path(directory) / "pending.json"
            for hash_value in ("test", "a" * 63, "z" * 64, None):
                answers.write_text(json.dumps({"a": {
                    "ts": "2026-10-09T10:00:00", "state": "written",
                    "reply": "Texto", "source_hash": hash_value}}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "huella_contextual_invalida"):
                    metrics._read_only_json(answers, "answers")
            for value in (True, -1, 5, 1.5):
                pending.write_text(json.dumps({"a": {
                    "network": "bluesky", "text": "Texto", "ts": "2026-10-09T10:00:00",
                    "incomplete_attempts": value}}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "reintentos_invalidos"):
                    metrics._read_only_json(pending, "pending")
            pending.write_text(json.dumps({"a": {
                "network": "bluesky", "text": "Texto", "ts": "2026-10-09T10:00:00",
                "retry_after": "2026-10-09T12:00:00+02:00"}}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reintento_fecha_invalida"):
                metrics._read_only_json(pending, "pending")

    def test_invalid_kind_and_aware_clock_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "tipo_snapshot_no_admitido"):
                metrics._read_only_json(pathlib.Path(directory) / "nunca.json", "unknown")
        with patch.dict(sys.modules, {"reply_queue": types.ModuleType("reply_queue"),
                                      "reply_writer": types.ModuleType("reply_writer")}):
            with self.assertRaisesRegex(ValueError, "reloj_invalido"):
                metrics.snapshot(now=datetime.datetime(2026, 10, 9, tzinfo=datetime.timezone.utc))

    def test_cli_failure_does_not_leak_private_data(self):
        stream = io.StringIO()
        with patch.object(metrics, "snapshot", side_effect=RuntimeError("clave-secreta")), \
             contextlib.redirect_stderr(stream):
            code = metrics.main()
        self.assertEqual(code, 2)
        self.assertNotIn("clave-secreta", stream.getvalue())
        self.assertIn("RuntimeError", stream.getvalue())

    def test_bad_ttl_fails_without_reporting_zeros(self):
        queue = types.ModuleType("reply_queue")
        writer = types.ModuleType("reply_writer")
        for invalid in (None, 0, -1, True, "36", float("nan")):
            queue.TTL_HOURS = invalid
            with patch.dict(sys.modules, {"reply_queue": queue, "reply_writer": writer}):
                with self.assertRaisesRegex(ValueError, "ttl_invalido"):
                    metrics.snapshot(now=NOW)

    def test_absent_file_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "answers.json"
            self.assertEqual(metrics._read_only_json(path, "answers"), ({}, True))
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
