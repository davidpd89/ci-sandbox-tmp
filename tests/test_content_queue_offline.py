"""Regresiones de la cola, sin red ni publicaciones reales."""
import contextlib
import io
import datetime
import pathlib
import sys
import tempfile
import types
import unittest
from zoneinfo import ZoneInfo
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import content_queue as cq
import run_content_queue as queue


class ContentQueueTests(unittest.TestCase):

    def test_all_networks_are_report_only(self):
        self.assertEqual(queue.SCHEDULE_NATIVO, set())
        self.assertEqual(queue.PUBLICA_CUANDO_VENCE, set())
        self.assertEqual(queue.RUNNERS, {})
        self.assertEqual(queue.SOLO_INFORME, set(cq.RED_FOLDERS.keys()))

    def test_report_only_queue_never_requires_auto_opt_in(self):
        item = {
            "red": "mastodon",
            "fecha_hora": datetime.datetime(2000, 1, 1, 10),
            "carpeta": "demo",
            "texto": "Texto",
            "auto_ok": True,
        }
        with patch.object(queue.cq, "pending_parse_issues", return_value=[]), \
             patch.object(queue.cq, "future_items", return_value=[]), \
             patch.object(queue.cq, "due_items", return_value=[item]):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                result = queue.run("mastodon")
        self.assertEqual(result, [item])
        self.assertIn("NO publica ni programa", out.getvalue())

    def test_iso_date_format_already_used_by_queue_is_parseable(self):
        self.assertEqual(
            cq._parse_fecha_hora("**Fecha y hora:** 2026-09-28, 09:30 (Europe/Madrid)."),
            datetime.datetime(2026, 9, 28, 9, 30),
        )

    def test_iso_date_with_plain_fecha_label_is_parseable(self):
        self.assertEqual(
            cq._parse_fecha_hora('- **Fecha:** 2026-10-20, 18:00.'),
            datetime.datetime(2026, 10, 20, 18, 0),
        )

    def test_last_section_text_is_not_lost(self):
        self.assertEqual(cq._parse_texto("## Texto final propuesto\n\nHola, lectores.\n"),
                         "Hola, lectores.")
        fences = chr(96) * 3
        self.assertEqual(cq._parse_texto(
            "## Texto final\n\n" + fences + "text\nHola.\n" + fences + "\n"), "Hola.")

    def test_missing_state_cannot_be_published_repeatedly(self):
        with tempfile.TemporaryDirectory() as folder:
            sub = pathlib.Path(folder) / "publicaciones Bluesky GPT" / "2000-01-01"
            sub.mkdir(parents=True)
            md = sub / "publicacion.md"
            md.write_text("**Fecha y hora:** sábado 01/01/2000, 10:00\n"
                          "## Texto final\n\nHola.", encoding="utf-8")
            with patch.object(cq, "ROOT", folder):
                self.assertEqual(cq.due_items("bluesky"), [])
            with self.assertRaisesRegex(RuntimeError, "Estado"):
                cq.mark_done(str(md), "PUBLICADO")

    def test_auto_execution_requires_explicit_opt_in(self):
        self.assertTrue(cq._parse_auto_ok("**Auto:** sí\n"))
        self.assertTrue(cq._parse_auto_ok("**Auto:** YES\n"))
        self.assertFalse(cq._parse_auto_ok("**Estado:** lista para publicación\n"))
        self.assertFalse(cq._parse_auto_ok("**Auto:** pendiente\n"))

    def test_editorial_do_not_use_blocker_beats_auto_flag(self):
        content = "**Auto:** sí\n\n## Requisito\nNo usarlo todavía para esta pieza."
        self.assertIn("no usarlo todavía", cq._explicit_blockers(content))

    def test_uncertain_state_is_quarantined_from_future_runs(self):
        self.assertTrue(cq._ya_resuelto(
            "REVISAR MANUALMENTE - ESTADO INCIERTO (threads: RuntimeError)"
        ))

    def test_threads_is_report_only_until_alt_and_topic_are_supported(self):
        self.assertIn("threads", queue.SOLO_INFORME)
        self.assertNotIn("threads", queue.PUBLICA_CUANDO_VENCE)

    def test_tiktok_is_strictly_report_only_and_has_no_runner(self):
        self.assertIn("tiktok", queue.SOLO_INFORME)
        self.assertNotIn("tiktok", queue.SCHEDULE_NATIVO)
        self.assertNotIn("tiktok", queue.PUBLICA_CUANDO_VENCE)
        self.assertNotIn("tiktok", queue.RUNNERS)

    def test_bluesky_is_report_only_to_avoid_metricool_double_publish(self):
        self.assertIn("bluesky", queue.SOLO_INFORME)
        self.assertNotIn("bluesky", queue.PUBLICA_CUANDO_VENCE)
        self.assertNotIn("bluesky", queue.RUNNERS)

    def test_real_network_text_section_headings_are_parseable(self):
        cases = {
            "## Caption final\n\nTexto IG/TikTok.\n": "Texto IG/TikTok.",
            "## Texto\n\nCuerpo Reddit.\n": "Cuerpo Reddit.",
            "## Descripción\n\nDescripción Pinterest.\n": "Descripción Pinterest.",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(cq._parse_texto(raw), expected)

    def test_auto_opt_in_accepts_bulleted_metadata_only_when_explicit(self):
        self.assertTrue(cq._parse_auto_ok("- **Auto:** sí\n"))
        self.assertTrue(cq._parse_auto_ok("  - **Auto:** true.\n"))
        self.assertFalse(cq._parse_auto_ok("- **Programación:** sí\n"))
        self.assertFalse(cq._parse_auto_ok(
            "## Nota\n\nEjemplo de configuración:\n**Auto:** sí\n"
        ))

    def test_media_cannot_escape_publication_folder(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            pub = root / "publicacion"
            pub.mkdir()
            outside = root / "secreto.png"
            outside.write_bytes(b"x")

            raw = (
                "**Imagen:** `../secreto.png`\n"
                "**ALT:** No debe salir.\n"
            )
            entries = cq._parse_media_entries(raw, str(pub))
            self.assertEqual(len(entries), 1)
            self.assertFalse(entries[0]["exists"])
            self.assertIsNone(entries[0]["path"])

            absolute = (
                f"**Imagen:** `{outside}`\n"
                "**ALT:** Tampoco.\n"
            )
            entries = cq._parse_media_entries(absolute, str(pub))
            self.assertEqual(len(entries), 1)
            self.assertFalse(entries[0]["exists"])
            self.assertIsNone(entries[0]["path"])

    def test_media_list_is_detected_and_multi_media_blocks_auto(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "uno.png").write_bytes(b"x")
            raw = (
                "## Medios y ALT\n\n"
                "1. `uno.png`: ALT uno.\n"
                "2. `dos.png`: ALT dos.\n"
            )
            entries = cq._parse_media_entries(raw, str(root))
            self.assertEqual([e["filename"] for e in entries], ["uno.png", "dos.png"])
            self.assertTrue(entries[0]["exists"])
            self.assertFalse(entries[1]["exists"])

            item = {
                "md_path": "f.md", "estado": "lista",
                "fecha_hora": datetime.datetime(2099, 1, 1, 10),
                "texto": "Texto", "auto_ok": True, "blockers": [],
                "media": [
                    {"filename": "uno.png", "exists": True},
                    {"filename": "dos.png", "exists": True},
                ],
                "media_count": 2, "imagen": None, "alt": "",
            }
            with patch.object(cq, "scan_items", return_value=[item]):
                issues = cq.pending_parse_issues("x", auto_only=True)
            self.assertTrue(any(
                "varios archivos" in msg
                for _path, messages in issues
                for msg in messages
            ))

    def test_report_only_parse_issue_does_not_hide_valid_items(self):
        valid = {
            "red": "tiktok",
            "fecha_hora": datetime.datetime(2000, 1, 1, 10),
            "carpeta": "valid",
            "md_path": "valid.md",
            "texto": "Caption real",
            "imagen": None,
            "alt": "",
            "primera_respuesta": None,
            "auto_ok": False,
        }
        out = []
        with patch.object(
            queue.cq, "pending_parse_issues",
            return_value=[("rota.md", ["Texto final"])],
        ), patch.object(
            queue.cq, "due_items", return_value=[valid],
        ), patch("builtins.print", side_effect=lambda *a, **k: out.append(" ".join(map(str, a)))):
            queue.run("tiktok")
        joined = "\n".join(out)
        self.assertIn("rota.md", joined)
        self.assertIn("PENDIENTE MANUAL", joined)
        self.assertIn("Caption real", joined)

    def test_current_repository_publication_formats_parse_without_auto_opt_in(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        fixtures = (
            "publicaciones X GPT/2026-10-05/publicacion.md",
            "publicaciones Mastodon GPT/2026-10-05/publicacion.md",
            "publicaciones Bluesky GPT/2026-10-07/publicacion.md",
            "publicaciones Threads GPT/2026-10-05/publicacion.md",
            "publicaciones Facebook GPT/2026-10-06/publicacion.md",
            "publicaciones Instagram GPT/2026-10-05/publicacion.md",
            "publicaciones Pinterest GPT/2026-10-05/publicacion.md",
            "publicaciones Reddit GPT/2026-10-20/publicacion.md",
            "publicaciones TikTok GPT/2026-10-06/publicacion.md",
        )
        for relative in fixtures:
            with self.subTest(relative=relative):
                content = (root / relative).read_text(encoding="utf-8")
                self.assertIsNotNone(cq._parse_fecha_hora(content))
                self.assertTrue(cq._parse_estado(content))
                self.assertTrue(cq._parse_texto(content))
                self.assertFalse(cq._parse_auto_ok(content))

        x_content = (root / fixtures[0]).read_text(encoding="utf-8")
        x_media = cq._parse_media_entries(
            x_content, str((root / fixtures[0]).parent)
        )
        self.assertEqual(
            [entry["filename"] for entry in x_media],
            ["variedad-lexica-x.png"],
        )


if __name__ == "__main__":
    unittest.main()
