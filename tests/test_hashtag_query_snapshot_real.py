"""Integración offline del cache real de #63 al lector de #101 (sin cuentas)."""
import datetime
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from tools import discovery_terms
from tools import hashtag_expansion
from tools import hashtag_query_consumers as hqc


class LiveSnapshotReaderTests(unittest.TestCase):
    def test_actual_loader_fresh_expired_corrupt_across_nine_consumers(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        networks = {
            name: {"hashtags": [] if name == "reddit" else ["año"],
                   "busquedas": ["romantasy"]}
            for name in hqc.NETWORK_QUEUE
        }
        for scenario in ("fresh", "expired", "corrupt", "missing"):
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                static = root / "static.json"
                static.write_text("{}", encoding="utf-8")
                cache = root / "snapshot.json"
                snap = {
                    "schema": 1,
                    "as_of": (now - datetime.timedelta(hours=3)).isoformat(),
                    "expires_at": (now + datetime.timedelta(hours=3)
                                   if scenario == "fresh" else
                                   now - datetime.timedelta(hours=1)).isoformat(),
                    "networks": networks,
                }
                if scenario == "corrupt":
                    cache.write_text("{invalid-json", encoding="utf-8")
                elif scenario != "missing":
                    cache.write_text(json.dumps(snap, ensure_ascii=False),
                                     encoding="utf-8")
                fake_reciprocity = types.SimpleNamespace(
                    search_terms=lambda network, kind: [])
                with patch.dict(sys.modules, {
                    "hashtag_expansion": hashtag_expansion,
                    "reciprocity_signals": fake_reciprocity,
                }), patch.object(discovery_terms, "PATH", str(static)), patch.object(
                    hashtag_expansion, "DEFAULT_CACHE", cache
                ):
                    for name in hqc.NETWORK_QUEUE:
                        seeds, lexical = hqc.combine(
                            name, "busquedas", ["semilla"])
                        self.assertEqual(seeds, ["semilla lang:es"] if name == "x" else ["semilla"])
                        self.assertEqual(any("romantasy" in item for item in lexical), scenario == "fresh")
                        if name != "reddit":
                            _, tags = hqc.combine(name, "hashtags", [])
                            self.assertEqual(any(item.startswith("#año") for item in tags), scenario == "fresh")
                        if name in ("bluesky", "mastodon", "tiktok"):
                            config = ({"query_families": [{"name": "old", "queries": ["semilla"]}],
                                       "tag_queries": [], "hashtags": [], "coverage": {}}
                                      if name != "tiktok" else
                                      {"actor_queries": ["semilla"], "video_queries": ["semilla"],
                                       "budgets": {}})
                            extended = hqc.extend_native_config(name, config)
                            self.assertEqual("romantasy" in str(extended),
                                             scenario == "fresh")


if __name__ == "__main__":
    unittest.main()
