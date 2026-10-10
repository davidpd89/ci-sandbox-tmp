import datetime
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import content_publisher as publisher
import content_queue as cq


class PublicationDstDisambiguationTests(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_unambiguous_datetime_classification(self):
        # 2026-05-15 10:00 Europe/Madrid (Normal summer time CEST +02:00)
        dt = datetime.datetime(2026, 5, 15, 10, 0)
        status = cq.classify_local_datetime(dt)
        self.assertEqual(status, "unambiguous")

        cls, dt_utc, err = cq.resolve_dst_datetime(dt)
        self.assertEqual(cls, "unambiguous")
        self.assertIsNone(err)
        # 10:00 CEST -> 08:00 UTC
        expected_utc = datetime.datetime(2026, 5, 15, 8, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(dt_utc, expected_utc)

    def test_spring_forward_non_existent_gap(self):
        # 2026-03-29 02:30 Europe/Madrid does not exist (clocks jump 02:00 -> 03:00)
        dt = datetime.datetime(2026, 3, 29, 2, 30)
        status = cq.classify_local_datetime(dt)
        self.assertEqual(status, "non_existent")

        cls, dt_utc, err = cq.resolve_dst_datetime(dt)
        self.assertEqual(cls, "non_existent")
        self.assertIsNone(dt_utc)
        self.assertIn("imposible", err)

    def test_fall_back_ambiguous_without_explicit_resolution_fails(self):
        # 2026-10-25 02:30 Europe/Madrid occurs twice (02:00 CEST -> 02:00 CET)
        dt = datetime.datetime(2026, 10, 25, 2, 30)
        status = cq.classify_local_datetime(dt)
        self.assertEqual(status, "ambiguous")

        # Without meta fold/offset
        cls, dt_utc, err = cq.resolve_dst_datetime(dt, meta={})
        self.assertEqual(cls, "ambiguous")
        self.assertIsNone(dt_utc)
        self.assertIn("se requiere offset o fold explícito", err)

    def test_fall_back_ambiguous_resolved_with_fold(self):
        dt = datetime.datetime(2026, 10, 25, 2, 30)

        # fold=0 (First 02:30, CEST +02:00 -> 00:30 UTC)
        cls0, dt_utc0, err0 = cq.resolve_dst_datetime(dt, meta={"fold": "0"})
        self.assertEqual(cls0, "ambiguous")
        self.assertIsNone(err0)
        self.assertEqual(dt_utc0, datetime.datetime(2026, 10, 25, 0, 30, tzinfo=datetime.timezone.utc))

        # fold=1 (Second 02:30, CET +01:00 -> 01:30 UTC)
        cls1, dt_utc1, err1 = cq.resolve_dst_datetime(dt, meta={"fold": "1"})
        self.assertEqual(cls1, "ambiguous")
        self.assertIsNone(err1)
        self.assertEqual(dt_utc1, datetime.datetime(2026, 10, 25, 1, 30, tzinfo=datetime.timezone.utc))

    def test_fall_back_ambiguous_resolved_with_offset(self):
        dt = datetime.datetime(2026, 10, 25, 2, 30)

        # Offset +02:00 -> fold 0 (00:30 UTC)
        cls0, dt_utc0, err0 = cq.resolve_dst_datetime(dt, meta={"offset": "+02:00"})
        self.assertIsNone(err0)
        self.assertEqual(dt_utc0, datetime.datetime(2026, 10, 25, 0, 30, tzinfo=datetime.timezone.utc))

        # Offset +01:00 -> fold 1 (01:30 UTC)
        cls1, dt_utc1, err1 = cq.resolve_dst_datetime(dt, meta={"offset": "+01:00"})
        self.assertIsNone(err1)
        self.assertEqual(dt_utc1, datetime.datetime(2026, 10, 25, 1, 30, tzinfo=datetime.timezone.utc))

    def test_fall_back_ambiguous_resolved_with_utc_instant(self):
        dt = datetime.datetime(2026, 10, 25, 2, 30)

        cls, dt_utc, err = cq.resolve_dst_datetime(dt, meta={"instante utc": "2026-10-25T01:30:00Z"})
        self.assertIsNone(err)
        self.assertEqual(dt_utc, datetime.datetime(2026, 10, 25, 1, 30, tzinfo=datetime.timezone.utc))

    def test_due_items_filters_out_invalid_dst_and_compares_utc(self):
        mock_items = [
            # Gap item (non existent)
            {
                "red": "bluesky",
                "md_path": "/path/gap.md",
                "fecha_hora": datetime.datetime(2026, 3, 29, 2, 30),
                "fecha_hora_utc": None,
                "dst_status": "non_existent",
                "dst_err": "fecha/hora imposible (salto DST / spring-forward gap)",
                "texto": "Hola",
                "estado": "lista",
            },
            # Ambiguous without explicit fold (error)
            {
                "red": "bluesky",
                "md_path": "/path/amb.md",
                "fecha_hora": datetime.datetime(2026, 10, 25, 2, 30),
                "fecha_hora_utc": None,
                "dst_status": "ambiguous",
                "dst_err": "se requiere offset o fold explícito",
                "texto": "Hola",
                "estado": "lista",
            },
            # Valid due item
            {
                "red": "bluesky",
                "md_path": "/path/valid.md",
                "fecha_hora": datetime.datetime(2026, 5, 15, 10, 0),
                "fecha_hora_utc": datetime.datetime(2026, 5, 15, 8, 0, tzinfo=datetime.timezone.utc),
                "dst_status": "unambiguous",
                "dst_err": None,
                "texto": "Hola",
                "estado": "lista",
            },
        ]

        with patch("content_queue.scan_items", return_value=mock_items):
            # Evaluate at 2026-05-15 11:00 Europe/Madrid (09:00 UTC)
            now = datetime.datetime(2026, 5, 15, 11, 0, tzinfo=ZoneInfo("Europe/Madrid"))
            due = cq.due_items("bluesky", now=now)
            self.assertEqual(len(due), 1)
            self.assertEqual(due[0]["md_path"], "/path/valid.md")

    def test_publisher_blockers_and_eligible_with_utc_dates(self):
        item = {
            "red": "bluesky",
            "md_path": "/path/item.md",
            "fecha_hora": datetime.datetime(2026, 5, 1, 10, 0),
            "fecha_hora_utc": datetime.datetime(2026, 5, 1, 8, 0, tzinfo=datetime.timezone.utc),
            "texto": "Post especial para hoy",
            "estado": "lista",
        }

        # Evaluated 2 days later: text contains "hoy" and item is 2 days overdue
        now_later = datetime.datetime(2026, 5, 3, 10, 0, tzinfo=ZoneInfo("Europe/Madrid"))
        reasons = publisher.blockers_of(item, issues_by_path={}, now=now_later)
        self.assertTrue(any("depende de la fecha" in r for r in reasons))


if __name__ == "__main__":
    unittest.main()
