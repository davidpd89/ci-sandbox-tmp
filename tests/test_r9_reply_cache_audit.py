"""La auditoría de migración R9 no imprime ni altera respuestas reales."""
import datetime
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import reply_cache_audit as audit


class CacheAuditTests(unittest.TestCase):
    def test_legacy_useful_answers_cannot_be_reconstructed_and_are_counted(self):
        now = datetime.datetime(2026, 10, 8, 15, 0, 0)
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            answers = {"a" * 16: {"reply": "Respuesta privada",
                                  "ts": "2026-10-08T14:00:00"},
                       "b" * 16: {"reply": None, "ts": "2026-10-08T14:00:00"},
                       "c" * 24: {"reply": "Nueva respuesta",
                                  "ts": "2026-10-08T14:00:00"}}
            (root / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
            before = (root / "answers.json").read_bytes()
            result = audit.audit(root, now=now)
            self.assertEqual(result["legacy_answers_total"], 2)
            self.assertEqual(result["legacy_answers_fresh_useful_unmigratable"], 1)
            self.assertEqual((root / "answers.json").read_bytes(), before)
            self.assertNotIn("Respuesta privada", json.dumps(result, ensure_ascii=False))

    def test_pending_rekey_coalesces_duplicate_equal_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            pending = {
                "old1": {"network": "bluesky", "author": "ana",
                         "text": "El mismo libro", "context": "original",
                         "ts": "2026-10-08T14:00:00"},
                "old2": {"network": "bluesky", "author": "ana",
                         "text": "El mismo libro", "context": "original",
                         "ts": "2026-10-08T14:00:00"},
            }
            (root / "pending.json").write_text(json.dumps(pending), encoding="utf-8")
            got = audit.audit(root, now=datetime.datetime(2026, 10, 8, 15, 0, 0))
            self.assertEqual(got["pending_possible_duplicates"], 1)

    def test_missing_state_files_are_read_only_empty(self):
        with tempfile.TemporaryDirectory() as root:
            result = audit.audit(root)
            self.assertEqual(result["legacy_answers_total"], 0)
            self.assertEqual(result["pending_total"], 0)


    def test_window_24h_is_distinct_from_36h_ttl(self):
        now = datetime.datetime(2026, 10, 8, 15, 0)
        with tempfile.TemporaryDirectory() as root:
            folder = pathlib.Path(root)
            (folder / "pending.json").write_text(json.dumps({
                "recent": {"network": "x", "author": "a", "text": "a", "ts": "2026-10-08T14:00:00"},
                "old-but-valid": {"network": "x", "author": "b", "text": "b", "ts": "2026-10-07T11:00:00"}
            }), encoding="utf-8")
            (folder / "answers.json").write_text(json.dumps({
                "a" * 16: {"reply": "sin texto público", "ts": "2026-10-08T14:00:00"},
                "b" * 16: {"reply": "sin texto público", "ts": "2026-10-07T11:00:00"}
            }), encoding="utf-8")
            result = audit.audit(folder, now=now)
            self.assertEqual(result["pending_fresh"], 2)
            self.assertEqual(result["pending_24h"], 1)
            self.assertEqual(result["legacy_answers_fresh_useful_unmigratable"], 2)
            self.assertEqual(result["legacy_answers_24h_useful_unmigratable"], 1)

if __name__ == "__main__":
    unittest.main()
