import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import reciprocity as rc


class ClassifyTests(unittest.TestCase):
    def test_rober_is_a_super_reciprocator(self):
        self.assertEqual(rc.classify(33750, 37400, 4053), "super")

    def test_classes(self):
        self.assertEqual(rc.classify(5000, 6000, 900), "super")
        self.assertEqual(rc.classify(400, 500, 200), "reciprocal")
        self.assertIsNone(rc.classify(400, 50, 200))             # sigue a pocos: no devuelve follows
        self.assertIsNone(rc.classify(400000, 300000, 900))      # enorme: celebridad / granja
        self.assertIsNone(rc.classify(5000, 6000, 3))            # casi sin estados
        self.assertIsNone(rc.classify(None, 100))

    def test_bonus(self):
        self.assertEqual(rc.affinity_bonus(400, 500, 200), 2.0)
        self.assertEqual(rc.affinity_bonus(5000, 6000, 900), 1.0)
        self.assertEqual(rc.affinity_bonus(400, 20, 200), 0.0)


class SelectHubsTests(unittest.TestCase):
    def test_select_filters_and_orders(self):
        rows = [{"handle": "a", "followers": 5000, "following": 6000, "statuses": 500, "ok": True},
                {"handle": "b", "followers": 5000, "following": 9000, "statuses": 500, "ok": True},
                {"handle": "c", "followers": 5000, "following": 9000, "statuses": 500, "ok": False},
                {"handle": "puente@threads.net", "followers": 5000, "following": 9000, "statuses": 500, "ok": True},
                {"handle": "d", "followers": 5000, "following": 9000, "statuses": 500, "ok": True}]
        picks = rc.select_hubs(rows, exclude=["d"], n=5)
        self.assertEqual([p["handle"] for p in picks], ["b", "a"])

    def test_registry_keeps_discovery_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "hubs.json")
            rc.register("mastodon", [{"handle": "x", "followers": 1500, "following": 1500}], path=path)
            first = json.load(open(path, encoding="utf-8"))["mastodon"]["x"]["descubierto"]
            rc.register("mastodon", [{"handle": "x", "followers": 1600, "following": 1500}], path=path)
            data = json.load(open(path, encoding="utf-8"))["mastodon"]["x"]
            self.assertEqual(data["descubierto"], first)
            self.assertEqual(data["seguidores"], 1600)


if __name__ == "__main__":
    unittest.main()
