"""Regresiones del CRM común. Datos sintéticos: sin red ni estados reales."""
import csv
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import community_crm as cm

TODAY = date(2026, 10, 10)


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class CommunityCrmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inbound = self.root / "in.csv"
        self.outroot = self.root / "out"
        self.inbox = self.root / "inbox.json"
        self.tags = self.root / "tags.json"
        self.feed = [
            {"fecha": "2026-10-09", "red": "bluesky", "handle": "@Ana", "tipo": "comment"},
            {"fecha": "2026-10-09", "red": "bluesky", "handle": "ana", "tipo": "comment"},
            {"fecha": "2026-10-08", "red": "bluesky", "handle": "ANA", "tipo": "like"},
            {"fecha": "2026-10-02", "red": "bluesky", "handle": "ana", "tipo": "comment"},
            {"fecha": "2026-09-10", "red": "bluesky", "handle": "vieja", "tipo": "comment"},
            {"fecha": "2026-10-08", "red": "x", "handle": "ana", "tipo": "follow"},
            {"fecha": "2026-10-11", "red": "x", "handle": "futura", "tipo": "like"},
        ]
        self.save()
        self.inbox.write_text(json.dumps([
            {"network": "bluesky", "handle": "ana", "ref": "a", "thread": "h1", "date": "2026-10-08", "answered": False, "context_quality": "complete"},
            {"network": "bluesky", "handle": "ANA", "ref": "a", "thread": "h1", "date": "2026-10-08", "answered": False, "context_quality": "complete"},
            {"network": "bluesky", "handle": "ana", "ref": "b", "thread": "h1", "date": "2026-10-09", "answered": False},
            {"network": "x", "handle": "ana", "ref": "x1", "date": "2026-10-08", "answered": True},
            {"network": "bluesky", "handle": "vieja", "ref": "old", "date": "2026-09-10", "answered": False},
        ]), encoding="utf-8")
        self.tags.write_text(json.dumps({"BLUESKY:@Ana": ["lectora", "fantasía", "lectora"], "x:ana": ["autora"]}), encoding="utf-8")

    def save(self):
        write_csv(self.inbound, ["fecha", "red", "handle", "tipo"], self.feed)

    def build(self):
        return cm.build(self.inbound, self.outroot, inbox=self.inbox, labels=self.tags, as_of=TODAY)

    def test_scope_dedup_score_and_privacy(self):
        data = self.build()
        contacts = {(c["network"], c["handle"]): c for c in data["contacts"]}
        a = contacts["bluesky", "ana"]
        self.assertEqual(a["inbound"], {"comment": 2, "follow": 0, "like": 1, "repost": 0})
        self.assertEqual(a["score"], 3 * 2 + 1 + 2 + 3 + 5)
        self.assertEqual(a["pending"][0]["ref"], "b")
        self.assertEqual(a["pending"][0]["status"], "review_context")
        self.assertEqual(data["pending_threads"], 1)
        self.assertEqual(data["by_lane"], {"WEB": 0, "API": 1, "MOBILE": 0, "UNASSIGNED": 0})
        self.assertEqual(a["tags"], ["fantasía", "lectora"])
        self.assertEqual(contacts["x", "ana"]["pending"], [])
        self.assertNotIn(("x", "futura"), contacts)
        self.assertTrue(all("text" not in row for c in data["contacts"] for row in c["history"]))
        self.assertEqual(self.build(), data)

    def test_only_confirmed_outbound_and_no_invented_answer(self):
        path = self.outroot / "SISTEMA_DIARIO_BLUESKY" / "registro_interacciones.csv"
        write_csv(path, ["fecha", "cuenta", "tipo", "resultado"], [
            {"fecha": "2026-10-09", "cuenta": "ana", "tipo": "reply", "resultado": "confirmado"},
            {"fecha": "2026-10-09", "cuenta": "ana", "tipo": "reply", "resultado": "fallido"},
            {"fecha": "2026-10-09", "cuenta": "ana", "tipo": "reply", "resultado": "reservado"},
        ])
        ana = self.build()["contacts"][0]
        self.assertEqual(ana["outbound_confirmed"], 1)
        self.assertEqual(len(ana["pending"]), 1)  # sin correlación al ref no se cierra
        self.assertEqual(ana["last_outbound"], "2026-10-09")

    def test_newest_answered_thread_suppresses_earlier_unanswered(self):
        rows = json.loads(self.inbox.read_text(encoding="utf-8"))
        rows.append({"network": "bluesky", "handle": "ana", "ref": "c", "thread": "h1", "date": "2026-10-10", "answered": True})
        self.inbox.write_text(json.dumps(rows), encoding="utf-8")
        self.assertEqual(self.build()["pending_threads"], 0)

    def test_same_ref_answered_wins_regardless_of_input_order(self):
        rows = json.loads(self.inbox.read_text(encoding="utf-8"))
        rows.append({"network": "bluesky", "handle": "ana", "ref": "b", "thread": "h1", "date": "2026-10-09", "answered": True})
        for order in (rows, rows[::-1]):
            self.inbox.write_text(json.dumps(order), encoding="utf-8")
            self.assertEqual(self.build()["pending_threads"], 0)

    def test_newer_unanswered_reopens_after_older_answered(self):
        rows = [{"network": "reddit", "handle": "eva", "ref": "answered", "thread": "thread-1", "date": "2026-10-08", "answered": True},
                {"network": "reddit", "handle": "eva", "ref": "new", "thread": "thread-1", "date": "2026-10-09", "answered": False}]
        self.inbox.write_text(json.dumps(rows), encoding="utf-8")
        data = self.build()
        self.assertEqual(data["pending_threads"], 1)
        self.assertEqual(data["by_lane"]["UNASSIGNED"], 1)

    def test_no_necropost_even_when_csv_is_recent(self):
        self.inbox.write_text(json.dumps([{"network": "x", "handle": "ana", "ref": "old", "date": "2026-09-25", "answered": False}]), encoding="utf-8")
        self.assertEqual(self.build()["pending_threads"], 0)

    def test_schema_fail_closed_instead_of_silent_recommendation(self):
        errors = [
            [{"network": "x", "handle": "a", "ref": "r", "date": "2026-10-09", "answered": "false"}],
            [{"network": "unknown", "handle": "a", "ref": "r", "date": "2026-10-09", "answered": False}],
            [{"network": "x", "handle": "a", "ref": "r", "date": "2026-10-09", "answered": False},
             {"network": "x", "handle": "b", "ref": "r", "date": "2026-10-09", "answered": False}],
            [{"network": "x", "handle": "a", "ref": "r", "thread": "one", "date": "2026-10-09", "answered": False},
             {"network": "x", "handle": "a", "ref": "r", "thread": "two", "date": "2026-10-09", "answered": False}],
            [{"network": "x", "handle": "a", "ref": "r", "date": "2026-10-09", "answered": False, "context_quality": "guess"}],
        ]
        for case in errors:
            with self.subTest(case=case):
                self.inbox.write_text(json.dumps(case), encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.build()

    def test_context_quality_tie_prefers_verified_and_deterministic(self):
        rows = [
            {"network": "x", "handle": "ana", "ref": "a", "date": "2026-10-09", "answered": False, "context_quality": "partial"},
            {"network": "x", "handle": "ana", "ref": "a", "date": "2026-10-09", "answered": False, "context_quality": "complete"},
        ]
        for order in (rows, rows[::-1]):
            self.inbox.write_text(json.dumps(order), encoding="utf-8")
            x = next(c for c in self.build()["contacts"] if c["network"] == "x")
            self.assertEqual(x["pending"][0]["status"], "review_reply")

    def test_no_synthetic_tags_phantom_contacts(self):
        self.tags.write_text(json.dumps({"x:nadie": ["venderle"], "bluesky:ana": ["lectora"]}), encoding="utf-8")
        self.assertNotIn("nadie", json.dumps(self.build()))

    def test_cli_valid_json_and_read_only(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        cmd = [sys.executable, str(Path(cm.__file__)), "--inbound", str(self.inbound),
               "--registries-root", str(self.outroot), "--inbox", str(self.inbox),
               "--labels", str(self.tags), "--as-of", "2026-10-10"]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(proc.stdout)["pending_threads"], 1)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_history_and_windows_path_conventions(self):
        records = self.build()["contacts"]
        ana = next(c for c in records if c["network"] == "bluesky" and c["handle"] == "ana")
        self.assertEqual([r["date"] for r in ana["history"]], sorted(r["date"] for r in ana["history"]))
        self.assertTrue(all(set(r) == {"date", "direction", "kind"} for r in ana["history"]))
        self.assertEqual(ana["lane"], "API")

    def test_invalid_csv_column_halts_projection(self):
        self.inbound.write_text("fecha,red,handle\n2026-10-09,x,ana\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Cabeceras"):
            self.build()


if __name__ == "__main__":
    unittest.main()
