"""content_publisher (06/10): que ficha toca, comprobaciones y reintento seguro; sin red."""
import datetime
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import content_publisher as cp

NOW = datetime.datetime(2026, 10, 6, 12, 0)


def item(name, when, estado="lista.", blockers=(), media=(), texto="Texto de la ficha"):
    return {"md_path": f"/f/{name}/publicacion.md", "carpeta": f"/f/{name}", "fecha_hora": when, "estado": estado, "blockers": list(blockers),
            "media": list(media), "texto": texto, "imagen": None, "alt": ""}


class EligibilityTests(unittest.TestCase):
    config = {"enabled": {"bluesky": True}, "max_overdue_days": 3}

    def eligible(self, items, issues=None):
        orig = cp.cq.due_items
        cp.cq.due_items = lambda red, now=None: items
        try:
            return cp.eligible("bluesky", NOW, self.config, issues or {})
        finally:
            cp.cq.due_items = orig

    def test_ready_recent_items_are_publishable_oldest_first(self):
        ok, skipped = self.eligible([item("b", NOW - datetime.timedelta(hours=2)), item("a", NOW - datetime.timedelta(days=1))])
        self.assertEqual([i["carpeta"] for i in ok], ["/f/a", "/f/b"])
        self.assertEqual(skipped, [])

    def test_everything_doubtful_is_left_alone_with_a_reason(self):
        items = [item("verificar", NOW - datetime.timedelta(hours=1), estado="lista_manual."),
                 item("bloqueo", NOW - datetime.timedelta(hours=1), blockers=["no usarlo todavía"]),
                 item("vieja", NOW - datetime.timedelta(days=9)),
                 item("sinimagen", NOW - datetime.timedelta(hours=1), media=[{"filename": "x.png", "exists": False}]),
                 item("incompleta", NOW - datetime.timedelta(hours=1))]
        ok, skipped = self.eligible(items, issues={"/f/incompleta/publicacion.md": ["ALT de imagen"]})
        self.assertEqual(ok, [])
        reasons = {i["carpeta"]: " ".join(r) for i, r in skipped}
        self.assertIn("estado", reasons["/f/verificar"])
        self.assertIn("bloqueo", reasons["/f/bloqueo"])
        self.assertIn("vencida hace 9 dias", reasons["/f/vieja"])
        self.assertIn("falta el archivo", reasons["/f/sinimagen"])
        self.assertIn("ALT", reasons["/f/incompleta"])


    def test_requires_verify_state_is_publishable_once_the_network_check_ran(self):
        ok, skipped = self.eligible([item("v", NOW - datetime.timedelta(hours=1), estado="requiere verificar si se publicó o programó.")])
        self.assertEqual([i["carpeta"] for i in ok], ["/f/v"])

    def test_date_bound_text_is_not_published_late(self):
        ok, skipped = self.eligible([item("d", NOW - datetime.timedelta(days=1), texto="Hoy firmo en la feria, pasaos.")])
        self.assertEqual(ok, [])
        self.assertIn("depende de la fecha", " ".join(skipped[0][1]))


    def test_profile_link_label_blocks_until_the_link_is_in_the_profile(self):
        import json
        path = pathlib.Path(tempfile.mkdtemp()) / "enlaces.json"
        path.write_text(json.dumps({"instagram": ["Premios"]}), encoding="utf-8")
        self.assertTrue(cp.profile_link_ready("instagram", "premios", path))
        self.assertFalse(cp.profile_link_ready("instagram", "Kit de prensa", path))
        self.assertFalse(cp.profile_link_ready("instagram", "Premios", pathlib.Path(tempfile.mkdtemp()) / "no-existe.json"))
        ok_item = {**item("p", NOW - datetime.timedelta(hours=1)), "red": "instagram", "meta": {"etiqueta del enlace de perfil": "Kit de prensa"}}
        original = cp.PROFILE_LINKS
        cp.PROFILE_LINKS = str(path)
        try:
            reasons = cp.blockers_of(ok_item, {}, NOW)
        finally:
            cp.PROFILE_LINKS = original
        self.assertTrue(any("enlace de perfil" in r for r in reasons))


class RunTests(unittest.TestCase):
    def setUp(self):
        self.calls, self.marked, self.logged = [], [], []
        self.orig = (cp.cq.due_items, cp.cq.mark_done, cp.cq.pending_parse_issues, cp._log, cp.load_config)
        self.orig_last = cp.last_auto_publication
        cp.last_auto_publication = lambda red, log_path=None: None      # el registro real tiene publicaciones de hoy
        self.items = [item("a", NOW - datetime.timedelta(hours=3))]
        cp.cq.due_items = lambda red, now=None: list(self.items)
        cp.cq.mark_done = lambda path, note: self.marked.append((path, note))
        cp.cq.pending_parse_issues = lambda red, auto_only=False: []
        cp._log = lambda red, it, url: self.logged.append(url)
        cp.load_config = lambda: {"enabled": {"bluesky": True, "x": False}, "max_overdue_days": 3}

    def tearDown(self):
        cp.cq.due_items, cp.cq.mark_done, cp.cq.pending_parse_issues, cp._log, cp.load_config = self.orig
        cp.last_auto_publication = self.orig_last

    def test_dry_run_publishes_nothing(self):
        self.assertIsNone(cp.run("bluesky", apply=False, now=NOW, out=lambda *_: None, publishers={"bluesky": lambda i: self.calls.append(i)}, verify=lambda r, n: None))
        self.assertEqual(self.calls, [])

    def test_apply_publishes_one_marks_and_logs(self):
        self.items.append(item("b", NOW - datetime.timedelta(hours=1)))
        url = cp.run("bluesky", apply=True, now=NOW, out=lambda *_: None, publishers={"bluesky": lambda i: f"https://x/{i['carpeta']}"}, verify=lambda r, n: None)
        self.assertEqual(url, "https://x//f/a")               # solo la mas antigua; la otra sale en la siguiente ejecucion
        self.assertEqual(len(self.marked), 1)
        self.assertIn("publicada por la ronda", self.marked[0][1])
        self.assertEqual(len(self.logged), 1)

    def test_two_publications_are_never_back_to_back(self):
        import os
        import tempfile
        cp.last_auto_publication = self.orig_last
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "log.csv")
            with open(log, "w", encoding="utf-8") as f:
                f.write("fecha_hora,red,ficha,programada,url" + chr(10))
                f.write(f"{(NOW - datetime.timedelta(hours=1)).isoformat(timespec='minutes')},bluesky,x,y,z" + chr(10))
            self.assertIsNone(cp.run("bluesky", apply=True, now=NOW, out=lambda *_: None, publishers={"bluesky": lambda i: self.calls.append(i)}, verify=lambda r, n: None, log_path=log))
            self.assertEqual(self.calls, [])
            with open(log, "w", encoding="utf-8") as f:
                f.write("fecha_hora,red,ficha,programada,url" + chr(10))
                f.write(f"{(NOW - datetime.timedelta(hours=5)).isoformat(timespec='minutes')},bluesky,x,y,z" + chr(10))
            self.assertEqual(cp.run("bluesky", apply=True, now=NOW, out=lambda *_: None, publishers={"bluesky": lambda i: "https://ok"}, verify=lambda r, n: None, log_path=log), "https://ok")

    def test_disabled_network_is_never_touched(self):
        self.assertIsNone(cp.run("x", apply=True, now=NOW, out=lambda *_: None, publishers={"x": lambda i: self.calls.append(i)}, verify=lambda r, n: None))
        self.assertEqual(self.calls, [])

    def test_a_publish_error_that_actually_went_out_is_not_retried(self):
        def boom(i):
            self.items.clear()                                 # tras el fallo del cliente, la comprobacion en la red ya ve la ficha publicada
            raise RuntimeError("no hay un unico permalink nuevo verificable")
        result = cp.run("bluesky", apply=True, now=NOW, out=lambda *_: None, publishers={"bluesky": boom}, verify=lambda r, n: None)
        self.assertEqual(result, "confirmada por API")
        self.assertEqual(self.marked, [])

    def test_a_publish_error_that_did_not_go_out_is_raised(self):
        def boom(i):
            raise RuntimeError("fallo real")
        with self.assertRaises(RuntimeError):
            cp.run("bluesky", apply=True, now=NOW, out=lambda *_: None, publishers={"bluesky": boom}, verify=lambda r, n: None)
        self.assertEqual(self.marked, [])


if __name__ == "__main__":
    unittest.main()
