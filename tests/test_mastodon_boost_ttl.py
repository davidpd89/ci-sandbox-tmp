"""Limpieza TTL de boosts en Mastodon (29/09): borrado programado, nunca ciego."""
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

_requests_stub = types.ModuleType("requests")
_requests_stub.get = lambda *a, **k: None
_requests_stub.post = lambda *a, **k: None
_requests_stub.delete = lambda *a, **k: None
_x_stub = types.ModuleType("x_interact")
_x_stub._check_spanish_orthography = lambda text: None
with unittest.mock.patch.dict(sys.modules, {"requests": _requests_stub, "x_interact": _x_stub}):
    import mastodon_interact as m
    import mastodon_cleanup_ttl as cleanup


def _isolate(source, names, overrides=None):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    env = {}
    env.update(overrides or {})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), env)
    return env


class UnboostTests(unittest.TestCase):
    def test_unboost_calls_unreblog_and_confirms(self):
        calls = []
        with unittest.mock.patch.object(m, "_status_id", return_value="42"), \
             unittest.mock.patch.object(m, "_get", return_value={"reblogged": True}), \
             unittest.mock.patch.object(
                 m, "_post",
                 side_effect=lambda path, **k: calls.append(path) or {"reblogged": False},
             ):
            result = m.unboost("https://mastodon.social/@x/42")
        self.assertEqual(result, "unboosted")
        self.assertEqual(calls, ["statuses/42/unreblog"])

    def test_unboost_is_idempotent_when_already_not_boosted(self):
        with unittest.mock.patch.object(m, "_status_id", return_value="42"), \
             unittest.mock.patch.object(m, "_get", return_value={"reblogged": False}), \
             unittest.mock.patch.object(
                 m, "_post", side_effect=AssertionError("no debe llamar a la API")):
            result = m.unboost("https://mastodon.social/@x/42")
        self.assertEqual(result, "already")


class AppendBoostTtlTests(unittest.TestCase):
    def test_only_confirmed_boosts_with_status_id_are_scheduled(self):
        env = _isolate(
            TOOLS / "mastodon_execute.py",
            {"_append_boost_ttl"},
            {"datetime": datetime, "os": __import__("os"), "csv": csv, "BOOST_TTL_DAYS": 5},
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "boost_ttl.csv"
            env["BOOST_TTL_CSV"] = str(path)
            env["_append_boost_ttl"]([
                {
                    "kind": "boost", "handle": "@autora", "status_id": "42",
                    "url": "https://mastodon.social/@autora/42", "resultado": "confirmado",
                },
                # favourite: nunca deja rastro visible en el perfil propio.
                {
                    "kind": "favourite", "handle": "@otra", "status_id": "7",
                    "resultado": "confirmado",
                },
                # no confirmado: nunca se programa.
                {
                    "kind": "boost", "handle": "@tercera", "status_id": "9",
                    "resultado": "saltado_ya_boost",
                },
            ])
            with open(path, encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status_id"], "42")
        self.assertEqual(rows[0]["estado"], "pendiente")
        expected_due = (datetime.date.today() + datetime.timedelta(days=5)).isoformat()
        self.assertEqual(rows[0]["borrar_el"], expected_due)


class CleanupTtlTests(unittest.TestCase):
    def _write_csv(self, path, rows):
        with open(path, "w", newline="", encoding="utf-8") as stream:
            w = csv.writer(stream)
            w.writerow(["fecha", "acct", "status_id", "url", "borrar_el", "estado"])
            for row in rows:
                w.writerow(row)

    def test_due_rows_only_returns_pending_past_or_equal_today(self):
        today = datetime.date(2026, 10, 4)
        rows = [
            {"estado": "pendiente", "borrar_el": "2026-10-03"},
            {"estado": "pendiente", "borrar_el": "2026-10-04"},
            {"estado": "pendiente", "borrar_el": "2026-10-05"},
            {"estado": "borrado", "borrar_el": "2026-10-01"},
        ]
        due = cleanup.due_rows(rows, today)
        self.assertEqual(len(due), 2)

    def test_run_unboosts_due_rows_and_marks_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ttl.csv"
            self._write_csv(path, [
                ["2026-09-24", "@autora", "42", "https://mastodon.social/@autora/42",
                 "2026-09-29", "pendiente"],
            ])
            unboosted = []
            fake_m = types.SimpleNamespace(
                unboost=lambda sid: unboosted.append(sid),
                MastodonRateLimitExceeded=type("MastodonRateLimitExceeded", (RuntimeError,), {}),
            )
            with unittest.mock.patch.object(cleanup, "TTL_CSV", str(path)), \
                 unittest.mock.patch.object(cleanup, "m", fake_m), \
                 unittest.mock.patch.object(cleanup.sc, "pause", lambda *a, **k: None):
                rows = cleanup.run(today=datetime.date(2026, 9, 29))
            self.assertEqual(unboosted, ["42"])
            self.assertEqual(rows[0]["estado"], "retirado")

    def test_dry_run_unboosts_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ttl.csv"
            self._write_csv(path, [
                ["2026-09-24", "@autora", "42", "https://mastodon.social/@autora/42",
                 "2026-09-29", "pendiente"],
            ])
            unboosted = []
            fake_m = types.SimpleNamespace(unboost=lambda sid: unboosted.append(sid))
            with unittest.mock.patch.object(cleanup, "TTL_CSV", str(path)), \
                 unittest.mock.patch.object(cleanup, "m", fake_m):
                cleanup.run(dry_run=True, today=datetime.date(2026, 9, 29))
            self.assertEqual(unboosted, [])


if __name__ == "__main__":
    unittest.main()
