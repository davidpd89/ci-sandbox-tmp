"""Contracto fecha escáner -> builder -> ejecución, con datos sintéticos.

Prueba la pieza que faltaba: el escáner obtenía la fecha pero los planes
Bluesky/Mastodon la eliminaban antes del filtro compartido.
"""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import bluesky_build_plan as bb
import mastodon_build_plan as mb
import post_age_policy as age

NOW = dt.datetime(2026, 10, 9, 12, 0, tzinfo=dt.timezone.utc)


def stamp(days):
    return (NOW - dt.timedelta(days=days)).isoformat()


class SourceTimePropagationTests(unittest.TestCase):
    def _bluesky(self, created):
        scan = {"auto_plan": [], "shortlist": [{
            "id": "G001", "handle": "lector.bsky.social", "lane": "acquisition",
            "actions": ["interact"], "posts": [{
                "id": "G001-P1", "url": "https://bsky.app/profile/lector.bsky.social/post/test",
                "uri": "at://did:plc:lector/app.bsky.feed.post/test",
                "created_at": created, "actions": ["reply", "like"],
                "text": "Una lectura de fantasía.",
            }]
        }]}
        return bb.build(scan, {"actions": [{"post": "G001-P1", "kind": "reply",
                                            "text": "Qué detalle interesante."}]})[0]

    def _mastodon(self, created):
        scan = {"shortlist": [{
            "id": "M001", "acct": "lectora@mastodon.social", "lane": "community",
            "actions": [], "posts": [{
                "id": "M001-P1", "url": "https://mastodon.social/@lectora/12345",
                "status_id": "12345", "created_at": created,
                "actions": ["reply", "favourite"],
                "text": "Una lectura de fantasía.",
            }]
        }]}
        return mb.build(scan, {"actions": [{"post": "M001-P1", "kind": "reply",
                                            "text": "Qué detalle interesante."}]})[0]

    def test_old_and_recent_bluesky_post_are_checked_from_source(self):
        for days in (1, 8):
            with self.subTest(days=days):
                action = self._bluesky(stamp(days))
                self.assertEqual(action["post_created_at"], stamp(days))
                self.assertEqual(age.check("bluesky", action, now=NOW),
                                 (days <= 3, "edad_ok" if days <= 3 else "post_antiguo"))

    def test_old_and_recent_mastodon_post_are_checked_from_source(self):
        for days in (1, 8):
            with self.subTest(days=days):
                action = self._mastodon(stamp(days))
                self.assertEqual(action["post_created_at"], stamp(days))
                self.assertEqual(age.check("mastodon", action, now=NOW),
                                 (days <= 3, "edad_ok" if days <= 3 else "post_antiguo"))

    def test_missing_post_age_is_not_replaced_by_scan_age(self):
        for network, builder in (("bluesky", self._bluesky),
                                 ("mastodon", self._mastodon)):
            with self.subTest(network=network):
                item = builder(None)
                self.assertIsNone(item["post_created_at"])
                self.assertEqual(age.check(network, item, now=NOW),
                                 (False, "edad_desconocida"))

    def test_auto_bluesky_scan_rejects_indexed_at_as_publication_time(self):
        # Se extrae solo la función pura de scan para no cargar clientes de red.
        import ast
        import inspect
        import textwrap
        path = pathlib.Path(__file__).resolve().parents[1] / "tools" / "bluesky_growth_scan.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == "_created_at")
        ns = {}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), ns)
        self.assertEqual(ns["_created_at"](
            {"indexedAt": stamp(0), "record": {"text": "post sin fecha"}}), "")
        self.assertEqual(ns["_created_at"](
            {"indexedAt": stamp(0), "record": {"createdAt": stamp(9)}}), stamp(9))


if __name__ == "__main__":
    unittest.main()
