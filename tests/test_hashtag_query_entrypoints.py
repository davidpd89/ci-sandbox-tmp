"""Verifica puntos de consumo reales sin importar clientes de redes."""
import ast
from collections import defaultdict
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
                self.assertTrue(any(query.startswith(("#año", "#ano")) for query in x(3)))
                self.assertEqual(x(0), [], "X no debe buscar con presupuesto cero")
                t = isolate("threads_scan.py", "_rotate_searches",
                            datetime=datetime, SEARCH_POOL=["lectores"])
                self.assertEqual(len(t(3, round_index=0)), 3)
                self.assertEqual(t(0, round_index=0), [], "Threads no debe buscar con presupuesto cero")
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
                self.assertEqual(p(today=datetime.date(2026, 10, 10), n=0), [], "Pinterest no debe buscar con presupuesto cero")
                rd = isolate("reddit_scan.py", "_discovery_sources",
                             datetime=datetime,
                             SUBREDDITS=["libros", "lectura_es"])
                samples = [rd(today=datetime.date(2026, 10, 10), reader=synthetic,
                              round_index=i) for i in range(4)]
                self.assertTrue(any("search" in [row[0] for row in round_]
                                    for round_ in samples))
                self.assertTrue(all(len(round_) == 2 for round_ in samples))
                self.assertEqual([any(row[0] == "search" for row in sample)
                                  for sample in samples], [False, True, False, True])


    def test_web_entrypoints_dedup_after_final_format(self):
        def colliding(network, kind):
            return ["año"] if kind == "hashtags" else ["#año", "lectura ñ"]
        with patch.dict(sys.modules, {"hashtag_query_consumers": hqc}):
            with patch.object(hqc, "_read", side_effect=colliding):
                x = isolate("x_scan.py", "_lexical_queries",
                            datetime=datetime,
                            SEARCH_POOL=["lectores lang:es", "#año lang:es"])
                t = isolate("threads_scan.py", "_rotate_searches",
                            datetime=datetime,
                            SEARCH_POOL=["lectores", "#año"])
                p = isolate("pinterest_growth.py", "day_queries",
                            datetime=datetime, QUERIES_PER_DAY=3,
                            QUERY_POOL=[("lectores", None), ("#año", None)])
                for network, queries in (
                    ("x", x(3)),
                    ("threads", t(3, round_index=1)),
                    ("pinterest", [name for name, _ in p(
                        today=datetime.date(2026, 10, 10), n=3, round_index=1)]),
                ):
                    with self.subTest(network=network):
                        self.assertEqual(len(queries), 3)
                        self.assertEqual(len(set(map(str.casefold, queries))), 3)
                        self.assertIn(
                            hqc.format_term(network, "hashtags", "año"), queries)

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

    def test_bluesky_native_selector_executes_lexical_with_same_38_calls(self):
        families = [
            {"name": f"family_{i}", "queries": [f"old_{i}_a", f"old_{i}_b"]}
            for i in range(19)
        ]
        fake_gc = types.SimpleNamespace(
            rank_keys=lambda queries, stats, **kwargs: queries)
        selection = isolate(
            "bluesky_growth_scan.py", "_query_selection", gc=fake_gc)
        with patch.dict(sys.modules, {"hashtag_query_consumers": hqc}):
            for fresh in (["fantasía juvenil"], []):
                collector = types.SimpleNamespace(
                    config={"coverage": {"post_queries_per_family": 2},
                            "query_families": families, "lexical_queries": fresh},
                    query_stats={}, today=datetime.date(2026, 10, 10),
                )
                chosen = selection(collector)
                self.assertEqual(len(chosen), 38)
                self.assertEqual(
                    any(query == "fantasía juvenil" for _, query in chosen),
                    bool(fresh))
                self.assertTrue(any(name.startswith("family_") for name, _ in chosen))

    def test_mastodon_native_selector_reaches_19th_family_under_15_quota(self):
        families = [
            {"name": f"family_{i}", "queries": [f"old_{i}"]}
            for i in range(18)
        ]
        selection = isolate(
            "mastodon_growth_scan.py", "_query_selection",
            defaultdict=defaultdict,
            _rank_queries=lambda queries, *args: queries,
        )
        with patch.dict(sys.modules, {"hashtag_query_consumers": hqc}):
            for fresh in (["lectura ñ"], []):
                collector = types.SimpleNamespace(
                    config={"coverage": {"post_queries_per_round": 15},
                            "query_families": families, "lexical_queries": fresh},
                    metrics={}, today=datetime.date(2026, 10, 10),
                )
                chosen = selection(collector)
                self.assertEqual(len(chosen), 15)
                self.assertEqual(
                    any(query == "lectura ñ" for _, query in chosen), bool(fresh))
                self.assertTrue(any(name.startswith("family_") for name, _ in chosen))

    def test_mastodon_native_tag_selector_reserves_fresh_without_extra_reads(self):
        selection = isolate(
            "mastodon_growth_scan.py", "_tag_selection",
            defaultdict=defaultdict, _rank_queries=lambda terms, *args: terms,
            _hits=lambda tag, terms: 0,
        )
        config = {"coverage": {"hashtags_per_round": 3},
                  "hashtags": ["semilla_a", "semilla_b", "semilla_c", "semilla_d"],
                  "niche_terms": [], "lexical_tags": ["año"]}
        collector = types.SimpleNamespace(
            config=config, metrics={}, today=datetime.date(2026, 10, 10))
        with patch.dict(sys.modules, {"hashtag_query_consumers": hqc}):
            selected = selection(collector)
            self.assertEqual(len(selected), 3)
            self.assertIn("año", selected)
            config["lexical_tags"] = []
            self.assertNotIn("año", selection(collector))

    def test_tiktok_selected_queries_reach_run_surface_with_existing_budget(self):
        seen_calls = []
        native_disc = types.SimpleNamespace(
            load_seen=lambda: {}, load_stats=lambda: {},
            load_seed_pool=lambda: [],
            pick_queries=lambda queries, surface, stats, n: queries[:n],
            run_surface=lambda nav, surface, query, config, ctx:
                (seen_calls.append((surface, query)) or
                 ([], {"rows": 0, "valid": 0, "new": 0})),
            save_seen=lambda *args: None,
            append_metrics=lambda *args: None,
            update_seed_pool=lambda *args: None,
        )
        runner = isolate(
            "tiktok_growth_scan.py", "_run_discovery",
            _progress=lambda msg: None, _checkpoint=lambda rows: None,
            _run_frontier=lambda *args: None,
            _run_author_posts=lambda *args: None,
        )
        config = {
            "surfaces": {"user_search": True, "video_search": True},
            "actor_queries": [f"old_actor_{i}" for i in range(86)],
            "video_queries": [f"old_video_{i}" for i in range(144)],
            "lexical_actor_queries": ["autoría ñ"],
            "lexical_video_queries": ["fantasía juvenil"],
            "budgets": {"user_search_queries": 12, "video_search_queries": 5},
        }
        with patch.dict(sys.modules, {
            "hashtag_query_consumers": hqc,
            "tiktok_discovery": native_disc,
            "tiktok_mobile_nav": types.SimpleNamespace(
                TikTokNavigator=lambda adapter: object()),
        }):
            totals = runner(None, config, {}, {}, set(), [], [])
            self.assertEqual(len(totals["user_search"]["queries"]), 12)
            self.assertEqual(len(totals["video_search"]["queries"]), 5)
            self.assertIn(("user_search", "autoría ñ"), seen_calls)
            self.assertIn(("video_search", "fantasía juvenil"), seen_calls)
            self.assertEqual(len(seen_calls), 17)
            seen_calls.clear()
            config["lexical_actor_queries"] = []
            config["lexical_video_queries"] = []
            runner(None, config, {}, {}, set(), [], [])
            self.assertFalse(any("ñ" in q or "fantasía" in q for _, q in seen_calls))

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
