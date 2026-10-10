"""Contrato de planes de nueve redes: fixtures sintéticos sin acciones remotas."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import social_plan_contract as s

FIXTURES = {
    "x": {"kind": "reply", "url": "https://x.com/f/status/1", "text": "Me interesó"},
    "bluesky": {"kind": "repost", "url": "https://bsky.app/profile/f/post/1"},
    "mastodon": {"kind": "favourite", "status_id": "100"},
    "reddit": {"kind": "vote", "url": "https://reddit.com/r/libros/comments/1", "subreddit": "libros"},
    "threads": {"kind": "reply", "handle": "f", "text_fragment": "fantasía", "text": "De acuerdo"},
    "instagram": {"kind": "comment", "handle": "f", "permalink": "https://instagram.com/p/1", "text": "Buena reseña"},
    "tiktok": {"kind": "like", "handle": "f", "url": "https://www.tiktok.com/@f/video/123"},
    "pinterest": {"kind": "save", "url": "https://pinterest.com/pin/1", "board": "Fantasía"},
    "facebook": {"kind": "comment", "index": 0, "text": "Gran lectura"},
}


class ContractTests(unittest.TestCase):
    def test_full_nine_network_registry_and_read_only_contract(self):
        reg = s.builtins()
        self.assertEqual(set(s.NETWORKS), set(FIXTURES))
        self.assertEqual({a.network for a in reg.all()}, set(s.NETWORKS))
        for network, item in FIXTURES.items():
            with self.subTest(network=network):
                adapter = reg.get(network)
                self.assertTrue(adapter.capabilities.source.startswith("tools/"))
                self.assertEqual(set(adapter.capabilities.native_kinds), {r.kind for r in s.NATIVE[network]})
                projection = adapter.project([item])
                self.assertEqual(len(projection.actions), 1, projection.issues)
                self.assertEqual(projection.issues, ())
                self.assertEqual(projection.actions[0].network, network)
                self.assertEqual(projection.actions[0].kind, item["kind"])

    def test_different_native_kinds_do_not_forge_equivalent_actions(self):
        reg = s.builtins()
        for network, kind in (("mastodon", "favourite"), ("reddit", "vote"), ("pinterest", "save")):
            self.assertEqual(reg.get(network).project([FIXTURES[network]]).actions[0].kind, kind)
        self.assertNotIn("vote", reg.get("x").capabilities.native_kinds)
        self.assertEqual(tuple(a.network for a in reg.by_kind("vote")), ("reddit",))
        self.assertNotIn("post", reg.get("mastodon").capabilities.native_kinds)

    def test_ambiguous_targets_not_portable(self):
        reg = s.builtins()
        for network in ("threads", "facebook", "mastodon"):
            self.assertFalse(reg.get(network).project([FIXTURES[network]]).actions[0].target_portable)
        self.assertTrue(reg.get("instagram").project([FIXTURES["instagram"]]).actions[0].target_portable)
        self.assertTrue(reg.get("tiktok").project([FIXTURES["tiktok"]]).actions[0].target_portable)

    def test_target_fallback_and_missing_is_not_invented(self):
        a = s.builtins().get("threads")
        valid = {"kind": "reply", "handle": "f", "reply_to_id": "id_1", "text": "Vale"}
        self.assertEqual(a.project([valid]).actions[0].target_scope, "reply_to_id")
        self.assertFalse(a.project([valid]).actions[0].target_portable)
        result = a.project([{"kind": "reply", "handle": "f", "text": "Vale"}])
        self.assertEqual(result.actions, ())
        self.assertEqual(result.issues[0].code, "missing_target")

    def test_invalid_shape_and_partial_item_fail_closed(self):
        adapter = s.builtins().get("reddit")
        with self.assertRaises(ValueError):
            adapter.project({"actions": [FIXTURES["reddit"]]})
        items = [None, {"kind": "follow", "handle": "f"},
                 {"kind": "vote", "url": "https://reddit.com/r/libros/comments/1"},
                 FIXTURES["reddit"]]
        result = adapter.project(items)
        self.assertEqual([x.code for x in result.issues],
                         ["not_object", "unsupported_kind", "missing_required_field"])
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].source_index, 3)

    def test_facebook_index_matches_native_default_and_rejects_bool(self):
        a = s.builtins().get("facebook")
        for index in (True, -1, "1", None):
            self.assertEqual(a.project([{"kind": "like", "index": index}]).issues[0].code,
                             "missing_target")
        self.assertEqual(a.project([{"kind": "like", "index": 0}]).actions[0].target, "0")
        self.assertEqual(a.project([{"kind": "like"}]).actions[0].target, "0")

    def test_required_text_and_cli_redaction(self):
        a = s.builtins().get("instagram")
        invalid = dict(FIXTURES["instagram"], text="   ")
        self.assertEqual(a.project([invalid]).issues[0].code, "missing_required_field")
        with tempfile.TemporaryDirectory() as temp:
            plan = Path(temp) / "plan.json"
            plan.write_text(json.dumps([FIXTURES["instagram"]]), encoding="utf-8")
            cmd = [sys.executable, str(Path(s.__file__)), "instagram", str(plan)]
            run = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            output = json.loads(run.stdout)
            self.assertEqual(output["accepted"], 1)
            self.assertEqual(output["schema"], 1)
            self.assertNotIn("Buena reseña", run.stdout)
            self.assertNotIn("instagram.com/p/1", run.stdout)
            self.assertNotIn("f", output["by_native_kind"])

    def test_result_mapping_exact_not_optimistic(self):
        a = s.builtins().get("bluesky")
        for raw, status in (
            ("confirmado", "confirmed"), ("publicado", "confirmed"),
            ("saltado_ya_hecho", "skipped"), ("ya_hecho", "skipped"),
            ("rechazado_kind", "rejected"), ("fallo_plan:timeout", "failed"),
            ("confirmado_pero_no", "unknown"), ("pending", "unknown"),
        ):
            with self.subTest(raw=raw):
                actual = a.observe({"kind": "like", "resultado": raw})
                self.assertEqual(actual.status, status)
                self.assertIsNone(actual.retryable)
        self.assertEqual(a.observe({"kind": "publish", "resultado": "confirmado"}).status, "unknown")

    def test_duplicate_networks_and_native_kinds_blocked(self):
        a = s.PlanAdapter("bluesky", s.NATIVE["bluesky"], s.SOURCES["bluesky"])
        reg = s.AdapterRegistry()
        reg.register(a)
        with self.assertRaises(ValueError):
            reg.register(a)
        with self.assertRaises(ValueError):
            s.PlanAdapter("unknown", s.NATIVE["bluesky"], "x")
        with self.assertRaises(ValueError):
            s.PlanAdapter("x", (s.NativeKind("like", "reaction", ("url",)),
                                s.NativeKind("like", "reaction", ("url",))), "x")

    def test_immutable_input(self):
        items = [dict(FIXTURES["reddit"])]
        before = json.dumps(items, sort_keys=True)
        s.builtins().get("reddit").project(items)
        self.assertEqual(json.dumps(items, sort_keys=True), before)

    def test_tiktok_mobile_requires_real_url_not_fragment(self):
        a = s.builtins().get("tiktok")
        invalid = {"kind": "like", "handle": "f", "text_fragment": "fantasía"}
        self.assertEqual(a.project([invalid]).issues[0].code, "missing_target")

    def test_fake_urls_are_not_considered_portable(self):
        a = s.builtins().get("bluesky")
        for url in ("invalid", "http://bsky.app/post/x", "https://evil.example/post/x",
                    "https://bsky.app.evil.example/post/x", "https://user:pw@bsky.app/post/x"):
            self.assertFalse(a.project([{"kind": "like", "url": url}]).actions[0].target_portable)
        mastodon = s.builtins().get("mastodon")
        action = mastodon.project([{"kind": "favourite", "url": "https://example.social/@author/123"}]).actions[0]
        self.assertTrue(action.target_portable)

    def test_all_kinds_have_target_and_family_and_family_filter_is_explicit(self):
        for network, rules in s.NATIVE.items():
            with self.subTest(network=network):
                self.assertGreaterEqual(len(rules), 2)
                self.assertTrue(all(r.target_fields and r.family for r in rules))
                self.assertEqual(len({r.kind for r in rules}), len(rules))
        reg = s.builtins()
        self.assertEqual([a.network for a in reg.by_family("vote")], ["reddit"])
        self.assertEqual([a.network for a in reg.by_family("curation")], ["pinterest"])
        with self.assertRaises(ValueError):
            reg.by_family("unknown")

    def test_confirmed_result_contract_for_all_nine(self):
        reg = s.builtins()
        for network, sample in FIXTURES.items():
            with self.subTest(network=network):
                adapter = reg.get(network)
                self.assertEqual(adapter.observe({"kind": sample["kind"], "resultado": "confirmado"}).status,
                                 "confirmed")
                self.assertEqual(adapter.observe({"kind": sample["kind"], "resultado": "pendiente"}).status,
                                 "unknown")


if __name__ == "__main__":
    unittest.main()
