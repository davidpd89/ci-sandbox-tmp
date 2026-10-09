"""Regresiones de rate limit Bluesky; cero red real."""
import ast
import pathlib
import types
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
INTERACT = TOOLS / "bluesky_interact.py"
EXECUTE = TOOLS / "bluesky_execute.py"


def _rate_env():
    tree = ast.parse(INTERACT.read_text(encoding="utf-8"))
    nodes = [
        node for node in tree.body
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "RateLimitExceeded"
        ) or (
            isinstance(node, ast.FunctionDef)
            and node.name == "_raise_if_rate_limited"
        )
    ]
    env = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(INTERACT), "exec"), env)
    return env


class RateLimitTests(unittest.TestCase):
    def test_429_exposes_retry_after(self):
        env = _rate_env()
        response = types.SimpleNamespace(
            status_code=429,
            headers={"Retry-After": "37"},
        )
        with self.assertRaises(env["RateLimitExceeded"]) as ctx:
            env["_raise_if_rate_limited"](response, "POST createRecord")
        self.assertEqual(ctx.exception.retry_after, "37")
        self.assertIn("429", str(ctx.exception))

    def test_non_429_is_ignored_by_guard(self):
        env = _rate_env()
        response = types.SimpleNamespace(status_code=200, headers={})
        self.assertIsNone(env["_raise_if_rate_limited"](response, "GET timeline"))

    def test_executor_stops_remaining_plan_after_rate_limit(self):
        rate = type("RateLimitExceeded", (RuntimeError,), {})
        calls = []

        def like(url):
            calls.append(url)
            raise rate("429")

        fake_b = types.SimpleNamespace(
            like=like,
            repost=lambda url: calls.append(url) or "created",
            follow=lambda handle: "followed",
            unfollow=lambda handle: "unfollowed",
            quote=lambda url, text: "created",
            reply_to=lambda url, text: None,
            RateLimitExceeded=rate,
            BotWarningDetected=type("BotWarningDetected", (RuntimeError,), {}),
            AlreadyCommented=type("AlreadyCommented", (RuntimeError,), {}),
        )
        tree = ast.parse(EXECUTE.read_text(encoding="utf-8"))
        fn = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "run_plan"
        )
        env = {
            "sc": __import__("types").SimpleNamespace(report_plan_style=lambda plan: None, guard_plan_item=lambda *a, **k: None, drop_stacked_actions=lambda plan, **k: plan),
            "b": fake_b,
            "RateLimitExceeded": rate,
            "_preflight_plan": lambda plan: plan,
            "_pause": lambda: None,
            "ec": __import__("exec_common"),
            "_hourly_guard": lambda *a, **k: 0,   # la guarda horaria (05/10) tiene sus propios tests
            "PREFETCH_WINDOW": 100,
            "_prefetch_window": lambda items: None,
        }
        exec(compile(ast.Module(body=[fn], type_ignores=[]), str(EXECUTE), "exec"), env)
        plan = [
            {
                "kind": "like",
                "handle": "uno.bsky.social",
                "url": "https://bsky.app/profile/uno.bsky.social/post/a",
            },
            {
                "kind": "like",
                "handle": "dos.bsky.social",
                "url": "https://bsky.app/profile/dos.bsky.social/post/b",
            },
        ]
        result = env["run_plan"](plan)
        self.assertTrue(result[0]["resultado"].startswith("parada_rate_limit:"))
        self.assertEqual(result[1]["resultado"], "no_intentado")
        self.assertEqual(calls, [plan[0]["url"]])

    def test_finalize_does_not_fetch_metrics_after_stop(self):
        tree = ast.parse(EXECUTE.read_text(encoding="utf-8"))
        names = {"_stop_result", "_finalize"}
        nodes = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        calls = []
        env = {
            "sc": __import__("types").SimpleNamespace(report_plan_style=lambda plan: None, guard_plan_item=lambda *a, **k: None, drop_stacked_actions=lambda plan, **k: plan),
            "_append_registro": lambda results: calls.append("registro"),
            "_append_repost_ttl": lambda results: calls.append("repost_ttl"),
            "_fetch_metrics": lambda: calls.append("metricas") or {},
            "_append_metricas": lambda results, metrics: calls.append("append_metricas"),
            "_update_estado": lambda results, metrics: calls.append("estado"),
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(EXECUTE), "exec"), env)
        result = env["_finalize"]([
            {"resultado": "confirmado"},
            {"resultado": "parada_rate_limit:429"},
        ])
        self.assertIsNone(result)
        self.assertEqual(calls, ["registro", "repost_ttl"])

    def test_bluesky_pause_defaults_are_short(self):
        tree = ast.parse(EXECUTE.read_text(encoding="utf-8"))
        fn = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_pause"
        )
        defaults = [node.value for node in fn.args.defaults]
        self.assertEqual(defaults, [1.5, 5.0])  # ritmo humano variable (03/10), nunca 15-25 min de espera


if __name__ == "__main__":
    unittest.main()
