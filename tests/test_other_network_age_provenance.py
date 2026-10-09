"""Proveniencia de publicación para planes WEB/MOBILE, sin conexiones externas."""
import ast
import datetime as dt
import pathlib
import sys
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import facebook_build_plan as facebook
import threads_build_plan as threads
import tiktok_build_plan as tiktok
import post_age_policy as age

NOW = dt.datetime(2026, 10, 9, 12, tzinfo=dt.timezone.utc)


def ts(days):
    return (NOW - dt.timedelta(days=days)).isoformat()


class CrossNetworkPlanTimeTests(unittest.TestCase):
    def test_threads_scan_source_date_reaches_like_plan(self):
        rows = [{"handle": "lectora", "text": "Novela fantástica que estoy leyendo",
                 "created_at": ts(30)}]
        plan = threads.build(rows, max_follows=0)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["post_created_at"], ts(30))
        self.assertEqual(age.check("threads", plan[0], now=NOW),
                         (False, "post_antiguo"))

    def test_facebook_scan_source_date_reaches_like_plan(self):
        rows = [{"autor": "Lectora", "text": "Lectura de fantasía",
                 "permalink": "https://www.facebook.com/example/posts/1234",
                 "created_time": ts(30)}]
        plan = facebook.build(rows, max_likes=1)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["post_created_at"], ts(30))
        self.assertEqual(age.check("facebook", plan[0], now=NOW),
                         (False, "post_antiguo"))

    def test_tiktok_source_video_date_reaches_editorial_plan(self):
        scan = {"auto_plan": [], "shortlist": [{
            "id": "T001", "handle": "lectora", "actions": [],
            "posts": [{"id": "T001-P1", "url": "https://www.tiktok.com/@lectora/video/123",
                       "created_time": ts(10), "caption": "Estoy leyendo",
                       "actions": ["comment"]}]}]}
        result = tiktok.build(scan, {"actions": [
            {"kind": "comment", "post": "T001-P1", "text": "Me interesa."}]})
        self.assertEqual(result[0]["post_created_at"], ts(10))
        self.assertEqual(age.check("tiktok", result[0], now=NOW),
                         (False, "post_antiguo"))

    def test_tiktok_automatic_like_carries_shortlist_date(self):
        path = TOOLS / "tiktok_growth_scan.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef)
                  and x.name == "build_auto_plan")
        ns = {}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), ns)
        candidate = {"id": "T001", "handle": "lectora", "score": 12,
                     "actions": [], "sources": [],
                     "posts": [{"id": "T001-P1", "url": "https://tiktok.test/video/123",
                                "actions": ["like"], "caption": "Fantasia",
                                "created_at": ts(30)}]}
        actions = ns["build_auto_plan"]([candidate], {"scoring": {
            "auto_follow_score_min": 100, "auto_like_score_min": 1}})
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["post_created_at"], ts(30))
        self.assertEqual(age.check("tiktok", actions[0], now=NOW),
                         (False, "post_antiguo"))

    def test_tiktok_scanner_to_shortlist_to_builder_to_age_gate(self):
        import types
        path = TOOLS / "tiktok_growth_scan.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fn = next(x for x in tree.body if isinstance(x, ast.FunctionDef)
                  and x.name == "_compact_shortlist")
        ns = {"sc": types.SimpleNamespace(
            is_conversation_closer=lambda text: False),
            "_lane": lambda candidate: "acquisition"}
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec"), ns)
        rows = [{"handle": "lectora", "known": False, "known_date": None,
                 "followed": False, "source": "video_search",
                 "caption": "Libros de fantasía", "url": "https://tiktok.test/video/123",
                 "niche_hits": 4, "score": 10, "create_time": ts(10)}]
        shortlist = ns["_compact_shortlist"](rows, limit=2)
        self.assertEqual(shortlist[0]["posts"][0]["created_at"], ts(10))
        plan = tiktok.build({"shortlist": shortlist, "auto_plan": []}, {
            "actions": [{"post": "T001-P1", "kind": "comment",
                         "text": "Me interesan los libros."}]})
        self.assertEqual(plan[0]["post_created_at"], ts(10))
        self.assertEqual(age.check("tiktok", plan[0], now=NOW),
                         (False, "post_antiguo"))

    def test_missing_source_does_not_turn_scan_time_into_post_time(self):
        threads_plan = threads.build(
            [{"handle": "lectora", "text": "Libros de fantasía"}], max_follows=0)
        facebook_plan = facebook.build(
            [{"autor": "Lectora", "text": "Libros de fantasía",
              "permalink": "https://www.facebook.com/example/posts/1234"}], max_likes=1)
        for network, plan in (("threads", threads_plan), ("facebook", facebook_plan)):
            self.assertEqual(len(plan), 1)
            self.assertEqual(plan[0]["post_created_at"], "")
            self.assertEqual(age.check(network, plan[0], now=NOW),
                             (True, "edad_desconocida"))


if __name__ == "__main__":
    unittest.main()
