"""Pruebas offline; únicamente fichas sintéticas, sin llamadas sociales."""
import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import publication_calendar as cal

NOW = datetime(2026, 10, 9, 20, 0, tzinfo=timezone.utc)


def item(red="bluesky", *, when=datetime(2026, 10, 10, 10),
         text="Una historia sobre un mapa.", state="lista", folder="2026-10-10",
         auto=True, media=None, blockers=None):
    return dict(md_path=f"C:/temp/publicaciones {red} GPT/{folder}/publicacion.md",
                fecha_hora=when, texto=text, estado=state, auto_ok=auto,
                media=[] if media is None else media,
                blockers=[] if blockers is None else blockers, imagen_declarada=False)


def plan(data, **kwargs):
    return cal.build_calendar(now=NOW, networks=list(data),
                              scanner=lambda red: data[red], **kwargs)


class CalendarTests(unittest.TestCase):
    def test_nine_networks_three_independent_lanes(self):
        self.assertEqual(set(cal.LANES), set(cal.cq.RED_FOLDERS))
        self.assertEqual(set(cal.LANES.values()), {"WEB", "API", "MOBILE"})

    def test_madrid_utc_and_no_absolute_paths(self):
        p = plan({"bluesky": [item()]})["items"][0]
        self.assertEqual(p["time_utc"], "2026-10-10T08:00:00Z")
        self.assertEqual(p["status"], "future")
        self.assertEqual(p["lane"], "API")
        self.assertNotIn("temp", p["source"])

    def test_timezone_override_changes_utc(self):
        p = plan({"x": [item("x")]}, zone_name="UTC")["items"][0]
        self.assertEqual(p["time_utc"], "2026-10-10T10:00:00Z")

    def test_nonexistent_dst_wall_time(self):
        p = plan({"bluesky": [item(when=datetime(2026, 3, 29, 2, 30))]})["items"][0]
        self.assertEqual(p["status"], "invalid")
        self.assertEqual(p["issues"], ["hora_inexistente"])
        self.assertIsNone(p["time_utc"])

    def test_ambiguous_dst_wall_time(self):
        p = plan({"bluesky": [item(when=datetime(2026, 10, 25, 2, 30))]})["items"][0]
        self.assertEqual(p["status"], "invalid")
        self.assertEqual(p["issues"], ["hora_ambigua"])

    def test_unambiguous_after_dst_change(self):
        p = plan({"bluesky": [item(when=datetime(2026, 10, 25, 3, 30))]})["items"][0]
        self.assertEqual(p["time_utc"], "2026-10-25T02:30:00Z")

    def test_due_and_stale(self):
        a = item(folder="a", when=datetime(2026, 10, 9, 10))
        b = item(folder="b", when=datetime(2026, 9, 1, 10), text="Anterior.")
        rows = plan({"bluesky": [a, b]})["items"]
        self.assertEqual({p["source"].split("/")[-2]: p["status"] for p in rows},
                         {"a": "due", "b": "stale"})

    def test_resolved_is_never_due(self):
        p = plan({"bluesky": [item(state="publicada por la ronda")]})["items"][0]
        self.assertEqual(p["status"], "resolved")

    def test_review_and_editorial_blocker(self):
        a = item(folder="a", state="borrador")
        b = item(folder="b", blockers=["pendiente de verificar"], text="Otro.")
        rows = plan({"bluesky": [a, b]})["items"]
        self.assertEqual([p["status"] for p in rows], ["review", "invalid"])
        self.assertIn("bloqueo_editorial", rows[1]["issues"])

    def test_negated_or_manual_ready_state_is_never_due(self):
        for state in ("no lista para publicar", "lista solo manual", "lista negra"):
            with self.subTest(state=state):
                row = plan({"bluesky": [item(state=state, when=datetime(2026, 10, 9, 10))]})["items"][0]
                self.assertEqual(row["status"], "review")

    def test_missing_required_fields_media_alt(self):
        p = plan({"bluesky": [item(text="", state="", when=None,
                     media=[{"exists": False, "alt": ""}])]})["items"][0]
        self.assertEqual(set(p["issues"]),
                         {"estado_ausente", "texto_ausente", "fecha_ausente",
                          "medio_ausente", "alt_ausente"})

    def test_repeated_text_same_network_only_warning(self):
        a = item(folder="a")
        b = item(folder="b", when=datetime(2026, 10, 11, 10),
                 text="  una  historia  sobre un mapa. ")
        rows = plan({"bluesky": [a, b]})["items"]
        self.assertTrue(all("possible_duplicate" in p["issues"] for p in rows))
        self.assertEqual(len({p["id"] for p in rows}), 2)

    def test_historical_published_copy_warns_future_repost(self):
        past = item(folder="already-posted", state="publicada por la ronda",
                    when=datetime(2026, 10, 1, 10))
        pending = item(folder="future", when=datetime(2026, 10, 11, 10))
        rows = plan({"bluesky": [past, pending]})["items"]
        future = next(p for p in rows if p["status"] == "future")
        self.assertIn("possible_duplicate", future["issues"])

    def test_reuse_cross_platform_is_allowed(self):
        rows = plan({"bluesky": [item()], "mastodon": [item("mastodon")]})["items"]
        self.assertTrue(all("possible_duplicate" not in p["issues"] for p in rows))

    def test_collision_same_network_not_different_network(self):
        a = item(folder="a")
        b = item(folder="b", text="Otro contenido.")
        c = item("x")
        rows = plan({"bluesky": [a, b], "x": [c]})["items"]
        self.assertEqual(sum("slot_collision" in p["issues"] for p in rows), 2)

    def test_hour_alone_does_not_create_collision(self):
        a = item(folder="a")
        b = item(folder="b", when=datetime(2026, 10, 11, 10), text="Otro.")
        rows = plan({"bluesky": [a, b]})["items"]
        self.assertTrue(all("slot_collision" not in p["issues"] for p in rows))

    def test_opt_in_is_information_not_execution(self):
        p = plan({"tiktok": [item("tiktok", auto=False)]})["items"][0]
        self.assertFalse(p["auto_opt_in"])
        self.assertEqual(p["lane"], "MOBILE")
        self.assertTrue(plan({"tiktok": []})["read_only"])

    def test_invalid_inputs_fail_explicitly(self):
        with self.assertRaises(ValueError):
            cal.build_calendar(now=datetime(2026, 10, 9), networks=[])
        with self.assertRaises(ValueError):
            plan({"unknown": []})
        with self.assertRaises(ValueError):
            plan({"x": []}, max_overdue_days=-1)
        with self.assertRaises(ValueError):
            cal.build_calendar(now=NOW, networks=["x", "x"], scanner=lambda _: [])

    def test_no_mutation_and_repeatability(self):
        x = item()
        before = dict(x)
        data = {"bluesky": [x]}
        self.assertEqual(plan(data), plan(data))
        self.assertEqual(x, before)

    def test_cli_json_is_read_only(self):
        old = cal.cq.scan_items
        try:
            cal.cq.scan_items = lambda red: [item(red)] if red == "x" else []
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cal.main(["--network", "x"]), 0)
            obj = json.loads(output.getvalue())
            self.assertEqual(len(obj["items"]), 1)
            self.assertTrue(obj["read_only"])
        finally:
            cal.cq.scan_items = old

    def test_legacy_queue_cli_calendar_routes_only_to_read_only_preview(self):
        import runpy
        from unittest import mock
        script = str(Path(__file__).resolve().parents[1] / "tools" / "run_content_queue.py")
        with mock.patch.object(sys, "argv",
                               [script, "--calendar", "--network", "x"]), \
             mock.patch.object(cal, "main", return_value=0) as preview:
            with self.assertRaises(SystemExit) as exit_:
                runpy.run_path(script, run_name="__main__")
        self.assertEqual(exit_.exception.code, 0)
        preview.assert_called_once_with(["--network", "x"])

    def test_portability_across_roots(self):
        a = item()
        b = item()
        b["md_path"] = "/tmp/other/publicaciones Bluesky GPT/2026-10-10/publicacion.md"
        self.assertEqual(plan({"bluesky": [a]})["items"][0]["id"],
                         plan({"bluesky": [b]})["items"][0]["id"])

    def test_zero_overdue_days(self):
        p = plan({"bluesky": [item(when=datetime(2026, 10, 9, 21))]},
                 max_overdue_days=0)["items"][0]
        self.assertEqual(p["status"], "stale")


if __name__ == "__main__":
    unittest.main()
