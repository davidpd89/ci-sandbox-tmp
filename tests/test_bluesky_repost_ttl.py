"""Limpieza TTL de reposts/citas (29/09): borrado programado, nunca ciego."""
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

# CI no instala requests: aislar bluesky_interact igual que el resto de
# tests Bluesky (ver test_bluesky_growth_surfaces.py) antes de importar
# bluesky_cleanup_ttl, que lo importa de verdad como "b".
_stub = types.ModuleType("bluesky_interact")
_stub.RateLimitExceeded = type("RateLimitExceeded", (RuntimeError,), {})
_stub.delete_own_record = lambda uri: "deleted"
with unittest.mock.patch.dict(sys.modules, {"bluesky_interact": _stub}):
    import bluesky_cleanup_ttl as cleanup


def _isolate(source, names, overrides=None):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    env = {"re": __import__("re")}
    env.update(overrides or {})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), env)
    return env


class DeleteOwnRecordTests(unittest.TestCase):
    def test_deletes_using_collection_and_rkey_from_own_uri(self):
        calls = []
        env = _isolate(
            TOOLS / "bluesky_interact.py",
            {"delete_own_record"},
            {
                "_require_credentials": lambda: None,
                "_session": lambda: {"did": "did:plc:david"},
                "_post_xrpc": lambda path, body: calls.append((path, body)) or {"commit": {}},
            },
        )
        result = env["delete_own_record"](
            "at://did:plc:david/app.bsky.feed.repost/abc123"
        )
        self.assertEqual(result, "deleted")
        self.assertEqual(calls[0][0], "com.atproto.repo.deleteRecord")
        self.assertEqual(calls[0][1], {
            "repo": "did:plc:david",
            "collection": "app.bsky.feed.repost",
            "rkey": "abc123",
        })

    def test_refuses_uri_outside_own_repo(self):
        env = _isolate(
            TOOLS / "bluesky_interact.py",
            {"delete_own_record"},
            {
                "_require_credentials": lambda: None,
                "_session": lambda: {"did": "did:plc:david"},
                "_post_xrpc": lambda path, body: (_ for _ in ()).throw(
                    AssertionError("no debe llegar a la red con un URI ajeno")
                ),
            },
        )
        with self.assertRaisesRegex(RuntimeError, "repo propio"):
            env["delete_own_record"]("at://did:plc:otra-persona/app.bsky.feed.post/xyz")

    def test_missing_confirmation_is_not_silently_accepted(self):
        env = _isolate(
            TOOLS / "bluesky_interact.py",
            {"delete_own_record"},
            {
                "_require_credentials": lambda: None,
                "_session": lambda: {"did": "did:plc:david"},
                "_post_xrpc": lambda path, body: None,
            },
        )
        with self.assertRaisesRegex(RuntimeError, "confirm"):
            env["delete_own_record"]("at://did:plc:david/app.bsky.feed.repost/abc123")


class AppendRepostTtlTests(unittest.TestCase):
    def test_only_confirmed_repost_and_quote_with_own_uri_are_scheduled(self):
        env = _isolate(
            TOOLS / "bluesky_execute.py",
            {"_append_repost_ttl"},
            {
                "datetime": datetime,
                "os": __import__("os"),
                "csv": csv,
                "REPOST_QUOTE_TTL_DAYS": 5,
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "repost_quote_ttl.csv"
            env["TTL_CSV"] = str(path)
            env["_append_repost_ttl"]([
                {
                    "kind": "repost", "handle": "autora.bsky.social",
                    "url": "https://bsky.app/profile/autora.bsky.social/post/p1",
                    "own_uri": "at://did:plc:david/app.bsky.feed.repost/r1",
                    "resultado": "confirmado",
                },
                {
                    "kind": "quote", "handle": "otra.bsky.social",
                    "url": "https://bsky.app/profile/otra.bsky.social/post/p2",
                    "own_uri": "at://did:plc:david/app.bsky.feed.post/q1",
                    "text": "comentario", "resultado": "confirmado",
                },
                # like: nunca se programa, no deja rastro de post propio.
                {
                    "kind": "like", "handle": "otra.bsky.social",
                    "url": "https://bsky.app/profile/otra.bsky.social/post/p3",
                    "resultado": "confirmado",
                },
                # repost sin own_uri (plan/ejecutor antiguo): mejor no borrar
                # nunca que borrar a ciegas sin saber que registro es.
                {
                    "kind": "repost", "handle": "tercera.bsky.social",
                    "url": "https://bsky.app/profile/tercera.bsky.social/post/p4",
                    "resultado": "confirmado",
                },
                # no confirmado: nunca se programa.
                {
                    "kind": "repost", "handle": "cuarta.bsky.social",
                    "url": "https://bsky.app/profile/cuarta.bsky.social/post/p5",
                    "own_uri": "at://did:plc:david/app.bsky.feed.repost/r5",
                    "resultado": "saltado_ya_reaccionado",
                },
            ])
            with open(path, encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["kind"], "repost")
        self.assertEqual(rows[0]["own_uri"], "at://did:plc:david/app.bsky.feed.repost/r1")
        self.assertEqual(rows[0]["estado"], "pendiente")
        self.assertEqual(rows[1]["kind"], "quote")
        expected_due = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
        self.assertEqual(rows[0]["borrar_el"], expected_due)


class CleanupTtlTests(unittest.TestCase):
    def _write_csv(self, path, rows):
        with open(path, "w", newline="", encoding="utf-8") as stream:
            w = csv.writer(stream)
            w.writerow(["fecha", "kind", "handle", "own_uri", "target_url", "borrar_el", "estado"])
            for row in rows:
                w.writerow(row)

    def test_due_rows_only_returns_pending_past_or_equal_today(self):
        today = datetime.date(2026, 10, 5)
        rows = [
            {"estado": "pendiente", "borrar_el": "2026-10-04"},  # vencida
            {"estado": "pendiente", "borrar_el": "2026-10-05"},  # vence hoy
            {"estado": "pendiente", "borrar_el": "2026-10-06"},  # todavia no
            {"estado": "borrado", "borrar_el": "2026-10-01"},    # ya procesada
        ]
        due = cleanup.due_rows(rows, today)
        self.assertEqual(len(due), 2)

    def test_run_deletes_due_rows_and_marks_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ttl.csv"
            self._write_csv(path, [
                [
                    "2026-09-29", "repost", "@autora.bsky.social",
                    "at://did:plc:david/app.bsky.feed.repost/r1",
                    "https://bsky.app/profile/autora.bsky.social/post/p1",
                    "2026-10-04", "pendiente",
                ],
                [
                    "2026-09-29", "quote", "@otra.bsky.social",
                    "at://did:plc:david/app.bsky.feed.post/q1",
                    "https://bsky.app/profile/otra.bsky.social/post/p2",
                    "2026-11-01", "pendiente",
                ],
            ])
            deleted = []
            fake_b = types.SimpleNamespace(
                delete_own_record=lambda uri: deleted.append(uri) or "deleted",
                RateLimitExceeded=type("RateLimitExceeded", (RuntimeError,), {}),
            )
            with unittest.mock.patch.object(cleanup, "TTL_CSV", str(path)), \
                 unittest.mock.patch.object(cleanup, "b", fake_b), \
                 unittest.mock.patch.object(cleanup.sc, "pause", lambda *a, **k: None):
                rows = cleanup.run(today=datetime.date(2026, 10, 5))
            self.assertEqual(deleted, ["at://did:plc:david/app.bsky.feed.repost/r1"])
            due_now = [r for r in rows if r["own_uri"].endswith("/r1")]
            self.assertEqual(due_now[0]["estado"], "borrado")
            still_pending = [r for r in rows if r["own_uri"].endswith("/q1")]
            self.assertEqual(still_pending[0]["estado"], "pendiente")

    def test_dry_run_deletes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ttl.csv"
            self._write_csv(path, [
                [
                    "2026-09-29", "repost", "@autora.bsky.social",
                    "at://did:plc:david/app.bsky.feed.repost/r1",
                    "https://bsky.app/profile/autora.bsky.social/post/p1",
                    "2026-10-04", "pendiente",
                ],
            ])
            deleted = []
            fake_b = types.SimpleNamespace(
                delete_own_record=lambda uri: deleted.append(uri) or "deleted",
                RateLimitExceeded=type("RateLimitExceeded", (RuntimeError,), {}),
            )
            with unittest.mock.patch.object(cleanup, "TTL_CSV", str(path)), \
                 unittest.mock.patch.object(cleanup, "b", fake_b):
                cleanup.run(dry_run=True, today=datetime.date(2026, 10, 5))
            self.assertEqual(deleted, [])


if __name__ == "__main__":
    unittest.main()
