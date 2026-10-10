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
import time_utils


class PublicationDstDisambiguationTests(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    def test_unambiguous_datetime_classification(self):
        # 2026-05-15 10:00 Europe/Madrid (Normal summer time CEST +02:00)
        dt = datetime.datetime(2026, 5, 15, 10, 0)
        status = time_utils.classify_local_datetime(dt)
        self.assertEqual(status, "unambiguous")

        cls, dt_utc, err = time_utils.resolve_dst_datetime(dt)
        self.assertEqual(cls, "unambiguous")
        self.assertIsNone(err)
        # 10:00 CEST -> 08:00 UTC
        expected_utc = datetime.datetime(2026, 5, 15, 8, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(dt_utc, expected_utc)

    def test_spring_forward_non_existent_gap(self):
        # 2026-03-29 02:30 Europe/Madrid does not exist (clocks jump 02:00 -> 03:00)
        dt = datetime.datetime(2026, 3, 29, 2, 30)
        status = time_utils.classify_local_datetime(dt)
        self.assertEqual(status, "non_existent")

        cls, dt_utc, err = time_utils.resolve_dst_datetime(dt)
        self.assertEqual(cls, "non_existent")
        self.assertIsNone(dt_utc)
        self.assertIn("imposible", err)

    def test_exact_dst_boundary_conditions(self):
        # 2026-03-29 02:00:00 in Europe/Madrid is the start of spring-forward gap
        dt_gap_start = datetime.datetime(2026, 3, 29, 2, 0)
        self.assertEqual(time_utils.classify_local_datetime(dt_gap_start), "non_existent")

        # 2026-03-29 03:00:00 in Europe/Madrid is valid unambiguous post-jump local time
        dt_gap_end = datetime.datetime(2026, 3, 29, 3, 0)
        self.assertEqual(time_utils.classify_local_datetime(dt_gap_end), "unambiguous")

        # 2026-10-25 02:00:00 in Europe/Madrid is the start of fall-back overlap
        dt_overlap_start = datetime.datetime(2026, 10, 25, 2, 0)
        self.assertEqual(time_utils.classify_local_datetime(dt_overlap_start), "ambiguous")

        # 2026-10-25 03:00:00 in Europe/Madrid is unambiguous after fall-back window closes
        dt_overlap_end = datetime.datetime(2026, 10, 25, 3, 0)
        self.assertEqual(time_utils.classify_local_datetime(dt_overlap_end), "unambiguous")

    def test_fall_back_ambiguous_without_explicit_resolution_fails(self):
        # 2026-10-25 02:30 Europe/Madrid occurs twice (02:00 CEST -> 02:00 CET)
        dt = datetime.datetime(2026, 10, 25, 2, 30)
        status = time_utils.classify_local_datetime(dt)
        self.assertEqual(status, "ambiguous")

        # Without meta fold/offset
        cls, dt_utc, err = time_utils.resolve_dst_datetime(dt, meta={})
        self.assertEqual(cls, "ambiguous")
        self.assertIsNone(dt_utc)
        self.assertIn("se requiere offset o fold explícito", err)

    def test_fall_back_ambiguous_resolved_with_fold(self):
        dt = datetime.datetime(2026, 10, 25, 2, 30)

        # fold=0 (First 02:30, CEST +02:00 -> 00:30 UTC)
        cls0, dt_utc0, err0 = time_utils.resolve_dst_datetime(dt, meta={"fold": "0"})
        self.assertEqual(cls0, "ambiguous")
        self.assertIsNone(err0)
        self.assertEqual(dt_utc0, datetime.datetime(2026, 10, 25, 0, 30, tzinfo=datetime.timezone.utc))

        # fold=1 (Second 02:30, CET +01:00 -> 01:30 UTC)
        cls1, dt_utc1, err1 = time_utils.resolve_dst_datetime(dt, meta={"fold": "1"})
        self.assertEqual(cls1, "ambiguous")
        self.assertIsNone(err1)
        self.assertEqual(dt_utc1, datetime.datetime(2026, 10, 25, 1, 30, tzinfo=datetime.timezone.utc))

    def test_fall_back_ambiguous_resolved_with_offset(self):
        dt = datetime.datetime(2026, 10, 25, 2, 30)

        # Offset +02:00 -> fold 0 (00:30 UTC)
        cls0, dt_utc0, err0 = time_utils.resolve_dst_datetime(dt, meta={"offset": "+02:00"})
        self.assertIsNone(err0)
        self.assertEqual(dt_utc0, datetime.datetime(2026, 10, 25, 0, 30, tzinfo=datetime.timezone.utc))

        # Offset +01:00 -> fold 1 (01:30 UTC)
        cls1, dt_utc1, err1 = time_utils.resolve_dst_datetime(dt, meta={"offset": "+01:00"})
        self.assertIsNone(err1)
        self.assertEqual(dt_utc1, datetime.datetime(2026, 10, 25, 1, 30, tzinfo=datetime.timezone.utc))

    def test_fall_back_ambiguous_resolved_with_utc_instant(self):
        dt = datetime.datetime(2026, 10, 25, 2, 30)

        cls, dt_utc, err = time_utils.resolve_dst_datetime(dt, meta={"instante utc": "2026-10-25T01:30:00Z"})
        self.assertIsNone(err)
        self.assertEqual(dt_utc, datetime.datetime(2026, 10, 25, 1, 30, tzinfo=datetime.timezone.utc))

    def test_conflicting_metadata_rejection(self):
        dt = datetime.datetime(2026, 10, 25, 2, 30)

        # Fold 1 (01:30 UTC) vs Offset +02:00 (which implies fold 0, 00:30 UTC)
        cls, dt_utc, err = time_utils.resolve_dst_datetime(dt, meta={"fold": "1", "offset": "+02:00"})
        self.assertEqual(cls, "ambiguous")
        self.assertIsNone(dt_utc)
        self.assertIn("contradictorios", err)

    def test_invalid_offset_rejection(self):
        dt = datetime.datetime(2026, 10, 25, 2, 30)

        # Invalid offset format or value not matching Madrid's folds
        cls, dt_utc, err = time_utils.resolve_dst_datetime(dt, meta={"offset": "+25:00"})
        self.assertEqual(cls, "ambiguous")
        self.assertIsNone(dt_utc)
        self.assertIn("se requiere offset o fold explícito", err)

    def test_configurable_timezone_canary(self):
        # 2026-03-29 01:30 in Atlantic/Canary is the spring-forward gap start (WET +00:00 -> WEST +01:00)
        dt_canary_gap = datetime.datetime(2026, 3, 29, 1, 30)
        self.assertEqual(time_utils.classify_local_datetime(dt_canary_gap, tz_name="Atlantic/Canary"), "non_existent")

    def test_idempotency_with_aware_datetime(self):
        aware_utc = datetime.datetime(2026, 10, 25, 1, 30, tzinfo=datetime.timezone.utc)
        cls, dt_utc, err = time_utils.resolve_dst_datetime(aware_utc)
        self.assertEqual(cls, "unambiguous")
        self.assertEqual(dt_utc, aware_utc)
        self.assertIsNone(err)

    def test_due_items_filters_out_invalid_dst_and_compares_utc(self):
        mock_items = [
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

        now_later = datetime.datetime(2026, 5, 3, 10, 0, tzinfo=ZoneInfo("Europe/Madrid"))
        reasons = publisher.blockers_of(item, issues_by_path={}, now=now_later)
        self.assertTrue(any("depende de la fecha" in r for r in reasons))

    def test_markdown_card_scan_integration(self):
        folder = os.path.join(self.tmp_dir, "publicaciones Bluesky GPT", "2026-10-25")
        os.makedirs(folder, exist_ok=True)
        card_path = os.path.join(folder, "publicacion.md")
        content = (
            "**Estado:** lista\n"
            "- **Auto:** sí\n"
            "- **Fecha y hora:** domingo 25/10/2026, 02:30\n"
            "- **Fold:** 1\n\n"
            "## Texto final\n\n"
            "Lectura nocturna de otoño.\n"
        )
        with open(card_path, "w", encoding="utf-8") as f:
            f.write(content)

        with patch("content_queue.ROOT", self.tmp_dir):
            items = cq.scan_items("bluesky")
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item["dst_status"], "ambiguous")
            self.assertIsNone(item["dst_err"])
            expected_utc = datetime.datetime(2026, 10, 25, 1, 30, tzinfo=datetime.timezone.utc)
            self.assertEqual(item["fecha_hora_utc"], expected_utc)


if __name__ == "__main__":
    unittest.main()
