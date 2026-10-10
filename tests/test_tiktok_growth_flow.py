import json
import pathlib
import sys
import tempfile
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import tiktok_build_plan as bp
import tiktok_growth_flow as flow
import tiktok_growth_scan as ts
import tiktok_mobile_execute as ex

CONFIG = {"scoring": {"auto_follow_score_min": 8, "auto_like_score_min": 3}}


<<<<<<< HEAD
def candidate(cid, handle, score, *, follow=True, url=None):
=======
def candidate(cid, handle, score, *, follow=True, url=None, quality="eligible"):
>>>>>>> origin/research/public-reuse-parent
    posts = []
    if url:
        posts.append({"id": f"{cid}-P1", "url": url, "caption": "cap", "source": "seed:post",
                      "actions": ["like", "comment"]})
    return {"id": cid, "handle": handle, "score": score, "lane": "acquisition",
<<<<<<< HEAD
            "actions": ["follow"] if follow else [], "sources": ["user_search"], "posts": posts}
=======
            "actions": ["follow"] if follow else [], "sources": ["user_search"], "posts": posts,
            "quality": quality}
>>>>>>> origin/research/public-reuse-parent


class AutoPlanTests(unittest.TestCase):
    def test_auto_follow_and_like_thresholds(self):
        short = [
            candidate("T001", "alta", 10, url="https://vm.tiktok.com/a/"),
            candidate("T002", "media", 5),
            candidate("T003", "baja", 1, url="https://vm.tiktok.com/b/"),
        ]
        plan = ts.build_auto_plan(short, CONFIG)
        kinds = {(r["kind"], r["handle"]) for r in plan}
        self.assertEqual(kinds, {("follow", "alta"), ("like", "alta")})

<<<<<<< HEAD
=======
    def test_candidate_in_review_is_never_auto_followed(self):
        plan = ts.build_auto_plan([candidate("T001", "dudosa", 20, quality="review")], CONFIG)
        self.assertNotIn(("follow", "dudosa"), {(r["kind"], r["handle"]) for r in plan})

>>>>>>> origin/research/public-reuse-parent
    def test_comments_are_never_automatic(self):
        plan = ts.build_auto_plan([candidate("T001", "x", 20, url="https://vm.tiktok.com/a/")], CONFIG)
        self.assertNotIn("comment", {r["kind"] for r in plan})

    def test_ai_view_drops_auto_followed_without_posts(self):
        state = {"shortlist": [candidate("T001", "alta", 10), candidate("T002", "media", 5)],
                 "auto_plan": [{"kind": "follow", "handle": "alta"}]}
        ids = [c["id"] for c in ts.compact_ai_view(state)["candidates"]]
        self.assertEqual(ids, ["T002"])


class BuilderTests(unittest.TestCase):
    def test_decision_duplicating_auto_action_is_skipped_not_error(self):
        scan = {"shortlist": [candidate("T001", "alta", 10)],
                "auto_plan": [{"kind": "follow", "handle": "alta", "motivo": "auto"}]}
        plan = bp.build(scan, {"actions": [{"kind": "follow", "candidate": "T001"}]})
        self.assertEqual(len(plan), 1)


class FlowTests(unittest.TestCase):
    def test_build_writes_plan_from_state(self):
        state = {"shortlist": [candidate("T001", "alta", 10)], "auto_plan": [
            {"kind": "follow", "handle": "alta", "motivo": "auto"}]}
        with tempfile.TemporaryDirectory() as tmp:
            sp, pp = pathlib.Path(tmp, "s.json"), pathlib.Path(tmp, "p.json")
            sp.write_text(json.dumps(state), encoding="utf-8")
            args = flow.make_parser().parse_args(["build", "--state", str(sp), "--plan", str(pp)])
            self.assertEqual(args.func(args), 0)
            self.assertEqual(json.loads(pp.read_text(encoding="utf-8"))[0]["handle"], "alta")


class ExecutorOrderTests(unittest.TestCase):
    def test_humanize_order_caps_same_kind_runs_and_keeps_all_actions(self):
        import random
        plan = [{"kind": "follow", "handle": f"h{i}"} for i in range(10)] + [
            {"kind": "like", "url": f"u{i}"} for i in range(5)]
        out = ex.humanize_order(plan, random.Random(1))
        self.assertEqual(len(out), 15)
        run = longest = 0
        prev = None
        for item in out:
            run = run + 1 if item["kind"] == prev else 1
            longest, prev = max(longest, run), item["kind"]
        self.assertLessEqual(longest, 3 if longest < 10 else longest)
        self.assertEqual(sorted(map(str, plan)), sorted(map(str, out)))

    def test_run_plan_persists_each_confirmation_and_stops_on_error(self):
        class A:
            def follow(self, handle):
                if handle == "boom":
                    raise RuntimeError("ui")
                return "followed"
        saved = []
        plan = [{"kind": "follow", "handle": "a"}, {"kind": "follow", "handle": "boom"},
                {"kind": "follow", "handle": "c"}]
        res = ex.run_plan(plan, A(), pause=False, on_result=saved.append)
        self.assertEqual([r["resultado"].split(":")[0] for r in res], ["confirmado", "parada", "no_intentado"])
<<<<<<< HEAD
        self.assertEqual(len(saved), 3)
=======
        self.assertEqual([row['resultado'].split(':')[0] for row in saved],
                         ['pendiente_verificacion', 'confirmado', 'pendiente_verificacion', 'parada', 'no_intentado'])
>>>>>>> origin/research/public-reuse-parent

    def test_session_time_limit_skips_remaining(self):
        class A:
            def follow(self, handle):
                return "followed"
        ticks = iter([0, 0, 10_000, 10_000, 10_000])
        res = ex.run_plan([{"kind": "follow", "handle": "a"}, {"kind": "follow", "handle": "b"}], A(),
                          pause=False, max_minutes=1, clock=lambda: next(ticks))
        self.assertEqual(res[0]["resultado"], "confirmado")
        self.assertEqual(res[1]["resultado"], "no_intentado_tiempo_sesion")


if __name__ == "__main__":
    unittest.main()
