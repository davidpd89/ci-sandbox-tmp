"""Verifica puntos de consumo reales sin importar clientes de redes."""
import ast
import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from tools import hashtag_query_consumers as hqc

ROOT = Path(__file__).resolve().parents[1] / "tools"


def isolate(filename, func, **variables):
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
    fn = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef) and node.name == func)
    scope = dict(variables)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), filename, "exec"), scope)
    return scope[func]


def synthetic(network, kind, reader=None):
    return ["año", "ano"] if kind == "hashtags" else ["fantasía juvenil", "lectura ñ"]


class EntrypointTests(unittest.TestCase):
    def test_web_and_mobile_consumers(self):
        with patch.dict(sys.modules, {"hashtag_query_consumers": hqc}):
            with patch.object(hqc, "_read", side_effect=synthetic):
                x = isolate("x_scan.py", "_lexical_queries",
                            datetime=datetime, SEARCH_POOL=["lectores lang:es"])
                self.assertEqual(len(x(3)), 3)
                self.assertTrue(any(query.startswith("#año") for query in x(3)))
                t = isolate("threads_scan.py", "_rotate_searches",
                            datetime=datetime, SEARCH_POOL=["lectores"])
                self.assertEqual(len(t(3, round_index=0)), 3)
                fb = isolate("facebook_scan.py", "_rotate_searches",
                             _round_index=lambda: 1, SEARCH_POOL=["lectores"])
                tags = isolate("facebook_scan.py", "_rotate_hashtags",
                               _round_index=lambda: 1, HASHTAG_POOL=["libros"])
                self.assertEqual(len(fb(2)), 2)
                self.assertEqual(len(tags(2)), 2)
                self.assertTrue(all(not tag.startswith("#") for tag in tags(2)))
                p = isolate("pinterest_growth.py", "day_queries",
                            datetime=datetime, QUERIES_PER_DAY=2,
                            QUERY_POOL=[("lectores", None)])
                self.assertEqual(len(p(today=datetime.date(2026, 10, 10), n=2)), 2)
                rd = isolate("reddit_scan.py", "_discovery_sources",
                             datetime=datetime,
                             SUBREDDITS=["libros", "lectura_es"])
                samples = [rd(today=datetime.date(2026, 10, d), reader=synthetic)
                           for d in (9, 10)]
                self.assertTrue(any("search" in [row[0] for row in round_]
                                    for round_ in samples))
                self.assertTrue(all(len(round_) == 2 for round_ in samples))

    def test_native_config_loaders_preserve_budgets(self):
        config = {
            "version": 1, "mode": "supervised_native",
            "query_families": [{"name": "old", "queries": ["lectura"]}],
            "tag_queries": [{"tag": "lectura", "query": "lectura"}],
            "hashtags": ["lectura"],
            "actor_queries": ["lectura"], "video_queries": ["lectura"],
            "coverage": {"hashtags_per_round": 2},
            "budgets": {"video_search_queries": 2},
        }
        with patch.dict(sys.modules, {"hashtag_query_consumers": hqc}):
            with patch.object(hqc, "_read", side_effect=synthetic):
                for file in ("bluesky_growth_scan.py",
                             "mastodon_growth_scan.py", "tiktok_growth_scan.py"):
                    with self.subTest(file=file):
                        loader = isolate(file, "_load_config", os=os, json=json,
                                         CONFIG_PATH="NOT_THE_TEMP_CONFIG")
                        with tempfile.TemporaryDirectory() as folder:
                            path = Path(folder) / "config.json"
                            path.write_text(json.dumps(config), encoding="utf-8")
                            result = loader(str(path))
                        self.assertIn("fantasía juvenil", str(result))
                        self.assertIn("año", str(result))
                        self.assertEqual(result["budgets"], config["budgets"])
                        self.assertEqual(result["coverage"], config["coverage"])

    def test_instagram_trial_not_auto_promoted(self):
        trial = isolate("instagram_scan.py", "_rotate_queries",
                        datetime=datetime,
                        QUERY_POOL=["lectura", "escritura"],
                        TRIAL_QUERY_POOL=["semilla"])
        injected = types.SimpleNamespace(
            terms=lambda network, kind: synthetic(network, kind))
        with patch.dict(sys.modules, {"discovery_terms": injected,
                                      "hashtag_query_consumers": hqc}):
            results = trial(2)
        self.assertEqual(len(results), 3)
        self.assertEqual([tag for _, tag in results],
                         ["validada", "validada", "prueba_no_validada"])


if __name__ == "__main__":
    unittest.main()
