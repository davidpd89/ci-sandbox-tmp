"""Limpieza TTL de reposts/citas en X (29/09): borrado programado, nunca ciego."""
import ast
import csv
import datetime
import pathlib
import sys
import tempfile
import types
import unittest
import unittest.mock

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

_stub = types.ModuleType("x_interact")
_stub.unrepost = lambda url: None
_stub.delete_post = lambda url: None
_stub.ensure_browser = lambda: None
with unittest.mock.patch.dict(sys.modules, {"x_interact": _stub}):
    import x_cleanup_ttl as cleanup


def _isolate(source, names, overrides=None):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    env = {}
    env.update(overrides or {})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), env)
    return env


class AppendRepostTtlTests(unittest.TestCase):
    def test_only_confirmed_repost_and_quote_with_own_uri_are_scheduled(self):
        env = _isolate(
            TOOLS / "x_execute.py",
            {"_append_repost_ttl"},
            {
                "datetime": datetime,
                "os": __import__("os"),
                "csv": csv,
                "REPOST_QUOTE_TTL_DAYS": 21,
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "reposts_activos.csv"
            env["REPOST_TTL_CSV"] = str(path)
            env["_append_repost_ttl"]([
                {
                    "kind": "repost", "handle": "@autora",
                    "url": "https://x.com/autora/status/1",
                    "resultado": "confirmado",
                },
                {
                    "kind": "quote", "handle": "@otra",
                    "url": "https://x.com/otra/status/2",
                    "own_uri": "https://x.com/autorademodiaz/status/999",
                    "text": "comentario", "resultado": "confirmado",
                },
                # like: nunca deja rastro de post propio, nunca se programa.
                {
                    "kind": "like", "handle": "@otra",
                    "url": "https://x.com/otra/status/3", "resultado": "confirmado",
                },
                # cita sin own_uri localizado: mejor no borrar nunca que
                # borrar a ciegas el post equivocado.
                {
                    "kind": "quote", "handle": "@tercera",
                    "url": "https://x.com/tercera/status/4",
                    "resultado": "confirmado",
                },
                # no confirmado: nunca se programa.
                {
                    "kind": "repost", "handle": "@cuarta",
                    "url": "https://x.com/cuarta/status/5",
                    "resultado": "saltado_ya_reposteado",
                },
            ])
            with open(path, encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["kind"], "repost")
        self.assertEqual(rows[0]["own_uri"], "")
        self.assertEqual(rows[0]["estado"], "pendiente")
        self.assertEqual(rows[1]["kind"], "quote")
        self.assertEqual(rows[1]["own_uri"], "https://x.com/autorademodiaz/status/999")
        expected_due = (datetime.date.today() + datetime.timedelta(days=21)).isoformat()
        self.assertEqual(rows[0]["borrar_el"], expected_due)


class CleanupTtlTests(unittest.TestCase):
    def _write_csv(self, path, rows):
        with open(path, "w", newline="", encoding="utf-8") as stream:
            w = csv.writer(stream)
            w.writerow(["fecha", "kind", "handle", "url", "own_uri", "borrar_el", "estado"])
            for row in rows:
                w.writerow(row)

    def test_due_rows_only_returns_pending_past_or_equal_today(self):
        today = datetime.date(2026, 10, 20)
        rows = [
            {"estado": "pendiente", "borrar_el": "2026-10-19"},
            {"estado": "pendiente", "borrar_el": "2026-10-20"},
            {"estado": "pendiente", "borrar_el": "2026-10-21"},
            {"estado": "borrado", "borrar_el": "2026-10-01"},
        ]
        due = cleanup.due_rows(rows, today)
        self.assertEqual(len(due), 2)

    def test_run_uses_unrepost_for_repost_and_delete_post_for_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ttl.csv"
            self._write_csv(path, [
                ["2026-09-08", "repost", "@autora", "https://x.com/autora/status/1",
                 "", "2026-09-29", "pendiente"],
                ["2026-09-08", "quote", "@otra", "https://x.com/otra/status/2",
                 "https://x.com/autorademodiaz/status/999", "2026-09-29", "pendiente"],
            ])
            unreposted, deleted = [], []
            fake_x = types.SimpleNamespace(
                unrepost=lambda url: unreposted.append(url),
                delete_post=lambda url: deleted.append(url),
            )
            with unittest.mock.patch.object(cleanup, "TTL_CSV", str(path)), \
                 unittest.mock.patch.object(cleanup, "x", fake_x), \
                 unittest.mock.patch.object(cleanup.sc, "pause", lambda *a, **k: None):
                rows = cleanup.run(today=datetime.date(2026, 9, 29))
            self.assertEqual(unreposted, ["https://x.com/autora/status/1"])
            self.assertEqual(deleted, ["https://x.com/autorademodiaz/status/999"])
            self.assertTrue(all(r["estado"] == "borrado" for r in rows))

    def test_dry_run_deletes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ttl.csv"
            self._write_csv(path, [
                ["2026-09-08", "repost", "@autora", "https://x.com/autora/status/1",
                 "", "2026-09-29", "pendiente"],
            ])
            unreposted = []
            fake_x = types.SimpleNamespace(unrepost=lambda url: unreposted.append(url))
            with unittest.mock.patch.object(cleanup, "TTL_CSV", str(path)), \
                 unittest.mock.patch.object(cleanup, "x", fake_x):
                cleanup.run(dry_run=True, today=datetime.date(2026, 9, 29))
            self.assertEqual(unreposted, [])


if __name__ == "__main__":
    unittest.main()
