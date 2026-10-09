import pathlib
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import tiktok_build_plan as tb


class TikTokBuildPlanTests(unittest.TestCase):
    def setUp(self):
        self.scan = {
            "shortlist": [
                {
                    "id": "T001",
                    "handle": "lectora",
                    "sources": ["for_you"],
                    "actions": ["follow"],
                    "posts": [
                        {
                            "id": "T001-P1",
                            "url": "https://www.tiktok.com/@lectora/video/1",
                            "caption": "¿Qué fantasía estás leyendo?",
                            "source": "for_you",
                            "actions": ["like", "comment"],
                        }
                    ],
                }
            ]
        }

    def test_builds_compact_decisions(self):
        plan = tb.build(self.scan, {
            "actions": [
                {"candidate": "T001", "kind": "follow"},
                {"post": "T001-P1", "kind": "comment", "text": "Me apunto esa lectura."},
            ]
        })
        self.assertEqual([p["kind"] for p in plan], ["follow", "comment"])
        self.assertEqual(plan[1]["handle"], "lectora")
        self.assertIn("tiktok.com", plan[1]["url"])

    def test_rejects_action_not_proposed_by_scan(self):
        self.scan["shortlist"][0]["actions"] = []
        with self.assertRaisesRegex(ValueError, "no propuesto"):
            tb.build(self.scan, {
                "actions": [{"candidate": "T001", "kind": "follow"}]
            })

    def test_comment_requires_text_and_stable_url(self):
        with self.assertRaisesRegex(ValueError, "exige text"):
            tb.build(self.scan, {
                "actions": [{"post": "T001-P1", "kind": "comment"}]
            })
        self.scan["shortlist"][0]["posts"][0]["url"] = None
        with self.assertRaisesRegex(ValueError, "permalink"):
            tb.build(self.scan, {
                "actions": [
                    {"post": "T001-P1", "kind": "comment", "text": "Hola"}
                ]
            })


if __name__ == "__main__":
    unittest.main()
