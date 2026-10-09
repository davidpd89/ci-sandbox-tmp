"""Pruebas offline del builder compacto de planes Bluesky."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import bluesky_build_plan as bp


SCAN = {
    "auto_plan": [{
        "handle": "conocida.bsky.social",
        "kind": "like",
        "url": "https://bsky.app/profile/conocida.bsky.social/post/a",
        "motivo": "auto",
    }],
    "shortlist": [
        {
            "id": "G001",
            "lane": "acquisition",
            "handle": "lectora.bsky.social",
            "sources": ["post_search", "thread_commenter"],
            "actions": ["follow", "interact"],
            "posts": [{
                "id": "G001-P1",
                "url": "https://bsky.app/profile/lectora.bsky.social/post/b",
                "sources": ["post_search"],
                "actions": ["like", "reply", "repost"],
            }],
        },
        {
            "id": "G002",
            "lane": "community",
            "handle": "autora.bsky.social",
            "sources": ["actor_search"],
            "actions": ["follow"],
            "posts": [],
        },
    ],
}


class BuildPlanTests(unittest.TestCase):
    def test_ids_expand_to_real_plan(self):
        decisions = {
            "actions": [
                {"candidate": "G001", "kind": "follow"},
                {"post": "G001-P1", "kind": "reply", "text": "Respuesta concreta."},
            ]
        }
        plan = bp.build(SCAN, decisions)
        self.assertEqual(len(plan), 3)
        self.assertEqual(plan[1]["handle"], "lectora.bsky.social")
        self.assertEqual(plan[1]["kind"], "follow")
        self.assertEqual(plan[1]["lane"], "acquisition")
        self.assertIn("lane=acquisition", plan[1]["motivo"])
        self.assertEqual(plan[2]["lane"], "acquisition")
        self.assertEqual(plan[2]["url"], SCAN["shortlist"][0]["posts"][0]["url"])
        self.assertEqual(plan[2]["text"], "Respuesta concreta.")

    def test_unproposed_action_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no propuesto"):
            bp.build(SCAN, {
                "actions": [{"post": "G001-P1", "kind": "quote", "text": "x"}]
            })

    def test_unknown_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "desconocido"):
            bp.build(SCAN, {
                "actions": [{"candidate": "G999", "kind": "follow"}]
            })

    def test_builder_does_not_apply_a_fixed_action_count(self):
        scan = dict(SCAN)
        scan["auto_plan"] = [
            {
                "handle": f"lector{i}.bsky.social",
                "kind": "like",
                "url": f"https://bsky.app/profile/lector{i}.bsky.social/post/{i}",
                "motivo": "auto",
            }
            for i in range(40)
        ]
        plan = bp.build(scan, {"actions": []})
        self.assertEqual(len(plan), 40)


if __name__ == "__main__":
    unittest.main()
