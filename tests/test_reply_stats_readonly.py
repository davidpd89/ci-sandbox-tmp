"""Stats diagnóstico: nunca usa el lector R8 con saneamiento de producción."""
import io
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reply_queue as rq


class Sink(io.StringIO):
    def reconfigure(self, **kwargs):
        return None


class ReplyStatsReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        patches = [
            mock.patch.object(rq, "PENDING", str(self.root / "pending.json")),
            mock.patch.object(rq, "ANSWERS", str(self.root / "answers.json")),
            mock.patch.object(rq, "LOCK", str(self.root / "worker.lock")),
            mock.patch.object(rq, "worker_running", return_value=False),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_valid(self):
        (self.root / "pending.json").write_text(json.dumps({
            "p1": {"network": "mastodon", "text": "Texto ficticio", "ts": "2026-10-09T08:00:00"}
        }), encoding="utf-8")
        (self.root / "answers.json").write_text(json.dumps({
            "a1": {"reply": "respuesta", "ts": "2026-10-09T08:00:00"},
            "a2": {"reply": None, "ts": "2026-10-09T08:00:00"},
        }), encoding="utf-8")

    def files(self):
        return {p.name: (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.iterdir() if p.is_file()}

    def test_stats_uses_no_mutating_load_and_preserves_all_bytes(self):
        self.write_valid()
        before = self.files()
        with mock.patch.object(rq, "_load", side_effect=AssertionError("unsafe _load called")):
            stats = rq.stats_snapshot()
        self.assertEqual(stats["pendientes"], 1)
        self.assertEqual(stats["respuestas"], 1)
        self.assertEqual(stats["descartadas"], 1)
        self.assertEqual(stats["ficheros_ausentes"], [])
        self.assertEqual(self.files(), before)

    def test_bad_json_causes_failure_without_quarantine_or_replacement(self):
        self.write_valid()
        (self.root / "answers.json").write_text('{"truncado":', encoding="utf-8")
        before = self.files()
        with self.assertRaisesRegex(rq.QueueStateCorrupted, "SNAPSHOT_CORRUPTO"):
            rq.stats_snapshot()
        self.assertEqual(self.files(), before)

    def test_invalid_entries_refused_without_sanitizing(self):
        self.write_valid()
        (self.root / "pending.json").write_text(
            json.dumps({"broken": {"ts": "2026-10-09T08:00:00"}}), encoding="utf-8")
        before = self.files()
        with self.assertRaisesRegex(rq.QueueStateCorrupted, "SNAPSHOT_INVALIDO"):
            rq.stats_snapshot()
        self.assertEqual(self.files(), before)

    def test_missing_files_reported_not_misrepresented_as_healthy(self):
        result = rq.stats_snapshot()
        self.assertEqual(result["pendientes"], 0)
        self.assertEqual(set(result["ficheros_ausentes"]),
                         {"pending.json", "answers.json"})
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cli_stats_and_readonly_alias_same_result(self):
        self.write_valid()
        before = self.files()
        outputs = []
        for args in (["stats"], ["stats", "--readonly"]):
            sink = Sink()
            with mock.patch.object(rq.sys, "stdout", sink):
                self.assertEqual(rq.main(args), 0)
            outputs.append(json.loads(sink.getvalue()))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(self.files(), before)

    def test_cli_stats_reports_corruption_without_mutation(self):
        (self.root / "answers.json").write_text("not-json", encoding="ascii")
        before = self.files()
        out = Sink()
        err = io.StringIO()
        with mock.patch.object(rq.sys, "stdout", out), \
             mock.patch.object(rq.sys, "stderr", err):
            self.assertEqual(rq.main(["stats", "--readonly"]), 2)
        self.assertIn("SNAPSHOT_CORRUPTO", err.getvalue())
        self.assertEqual(self.files(), before)


if __name__ == "__main__":
    unittest.main()
