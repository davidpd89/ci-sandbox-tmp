"""Preflight offline para los lotes de Facebook y Threads."""
import ast
import pathlib
import sys
import types
import unittest
from unittest.mock import patch
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / "tools"))
import scan_common as _real_sc

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))


def drop_stacked(plan, *, cheap_kinds, rich_kinds, key, normalize=lambda value: value):
    rich = {
        normalize(row.get(key)) for row in plan
        if row.get("kind") in rich_kinds and row.get(key) is not None
    }
    return [
        row for row in plan
        if not (
            row.get("kind") in cheap_kinds
            and row.get(key) is not None
            and normalize(row.get(key)) in rich
        )
    ]


def load_functions(filename, names, env):
    path = TOOLS / filename
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in set(names)
    ]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), env)
    return env


class BrowserBatchPreflightTests(unittest.TestCase):
    def test_cli_preflight_precedes_browser_start(self):
        for filename, browser_call in (
            ("facebook_execute.py", "fb.ensure_browser()"),
            ("threads_execute.py", "t.ensure_browser()"),
            ("instagram_execute.py", "ig.ensure_browser()"),
            ("x_execute.py", "x.ensure_browser()"),
            ("reddit_execute.py", "r.ensure_browser()"),
        ):
            with self.subTest(filename=filename):
                source = (TOOLS / filename).read_text(encoding="utf-8")
                entrypoint = source.index('if __name__ == "__main__":')
                self.assertLess(
<<<<<<< HEAD
                    source.index("plan = _preflight_plan(plan)", entrypoint),
=======
                    source.index("plan = _preflight_plan(plan, skipped=preflight_skipped)" if filename == "reddit_execute.py" else "plan = _preflight_plan(plan)", entrypoint),
>>>>>>> origin/research/public-reuse-parent
                    source.index(browser_call, entrypoint),
                )

    def test_facebook_loaded_feed_indices_are_checked_before_execution(self):
        source = (TOOLS / "facebook_execute.py").read_text(encoding="utf-8")
        entrypoint = source.index('if __name__ == "__main__":')
        self.assertLess(
            source.index("_validate_own_indices(plan, available_counts)", entrypoint),
            source.index("results = run_plan(plan, prevalidated=True)", entrypoint),
        )
        env = load_functions("facebook_execute.py", ["_validate_own_indices"], {})
        with self.assertRaisesRegex(ValueError, "fuera del feed"):
            env["_validate_own_indices"](
                [{"kind": "comment", "index": 1}], {"like": 0, "comment": 1}
            )
        env["_validate_own_indices"](
            [{"kind": "comment", "index": 0}], {"like": 0, "comment": 1}
        )

    def test_facebook_later_invalid_target_blocks_all_clicks(self):
        writes = []
        bot_warning = type("BotWarningDetected", (RuntimeError,), {})
        already = type("AlreadyCommented", (RuntimeError,), {})
        fb = types.SimpleNamespace(
            BotWarningDetected=bot_warning,
            AlreadyCommented=already,
            _validated_facebook_permalink=lambda value: value if value.startswith("https://www.facebook.com/") else (_ for _ in ()).throw(ValueError("invalid permalink")),
            _check_length=lambda text: None,
            _check_spanish_orthography=lambda text: None,
            like=lambda index: writes.append(("like", index)) or "created",
            comment=lambda text, index: writes.append(("comment", index, text)) or "created",
            like_external=lambda url: writes.append(("like_external", url)) or "created",
            comment_external=lambda text, url: writes.append(("comment_external", url)) or "created",
        )
        env = {
            "fb": fb,
            "dup": types.SimpleNamespace(check=lambda _text: []),
            "sc": types.SimpleNamespace(drop_stacked_actions=drop_stacked, guard_plan_item=_real_sc.guard_plan_item, report_plan_style=lambda plan: None),
            "_ALLOWED_KINDS": {"like", "comment", "like_external", "comment_external"},
            "_pause": lambda *_args: None, "ec": __import__("exec_common"),
        }
        load_functions("facebook_execute.py", ["_drop_stacked_actions", "_preflight_plan", "run_plan"], env)
        result = env["run_plan"]([
            {"kind": "like", "index": 0},
            {"kind": "comment_external", "permalink": "https://example.org/post/1", "text": "Un comentario concreto"},
        ])
        self.assertEqual(writes, [])
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))

    def test_threads_duplicate_text_blocks_follow_before_execution(self):
        writes = []
        warning = type("BotWarningDetected", (RuntimeError,), {})
        wrong = type("WrongAccountActive", (RuntimeError,), {})
        already = type("AlreadyCommented", (RuntimeError,), {})
        t = types.SimpleNamespace(
            BotWarningDetected=warning,
            WrongAccountActive=wrong,
            AlreadyCommented=already,
            _check_length=lambda text: None,
            _check_spanish_orthography=lambda text: None,
            follow=lambda handle: writes.append(("follow", handle)) or "followed",
            like_in_feed=lambda *_args: writes.append(("like",)) or "created",
            reply_to=lambda *_args: writes.append(("reply",)) or "created",
        )
        env = {
            "t": t,
            "dup": types.SimpleNamespace(check=lambda text: ["duplicate"] if text == "copied" else []),
            "sc": types.SimpleNamespace(drop_stacked_actions=drop_stacked, guard_plan_item=_real_sc.guard_plan_item, report_plan_style=lambda plan: None),
            "_VALID_KINDS": {"follow", "like", "reply"},
            "_check_length": lambda text: None,
            "_check_spanish_orthography": lambda text: None,
            "_pause": lambda *_args: None, "ec": __import__("exec_common"),
        }
        load_functions("threads_execute.py", ["_drop_stacked_actions", "_preflight_plan", "run_plan"], env)
        result = env["run_plan"]([
            {"kind": "follow", "handle": "lectora"},
            {"kind": "reply", "handle": "autora", "text_fragment": "fragment", "text": "copied"},
        ])
        self.assertEqual(writes, [])
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))

    def test_threads_duplicate_follow_in_one_plan_blocks_the_whole_batch(self):
        writes = []
        t = types.SimpleNamespace(
            BotWarningDetected=RuntimeError, WrongAccountActive=RuntimeError, AlreadyCommented=RuntimeError,
            follow=lambda handle: writes.append(("follow", handle)) or "followed",
        )
        env = {
            "t": t, "dup": types.SimpleNamespace(check=lambda text: []),
            "sc": types.SimpleNamespace(drop_stacked_actions=drop_stacked, guard_plan_item=_real_sc.guard_plan_item,
                                        report_plan_style=lambda plan: None),
            "_VALID_KINDS": {"follow", "like", "reply"}, "_pause": lambda *_args: None, "ec": __import__("exec_common"),
        }
        load_functions("threads_execute.py", ["_drop_stacked_actions", "_preflight_plan", "run_plan"], env)
        result = env["run_plan"]([{"kind": "follow", "handle": "lectora"}, {"kind": "follow", "handle": "@Lectora"}])
        self.assertEqual(writes, [])
        self.assertIn("duplicada", result[0]["resultado"])

    def test_threads_invalid_later_fragment_prevents_follow(self):
        writes = []
        warning = type("BotWarningDetected", (RuntimeError,), {})
        wrong = type("WrongAccountActive", (RuntimeError,), {})
        already = type("AlreadyCommented", (RuntimeError,), {})
        t = types.SimpleNamespace(
            BotWarningDetected=warning,
            WrongAccountActive=wrong,
            AlreadyCommented=already,
            _check_length=lambda text: None,
            _check_spanish_orthography=lambda text: None,
            follow=lambda handle: writes.append(("follow", handle)) or "followed",
            like_in_feed=lambda *_args: writes.append(("like",)) or "created",
            reply_to=lambda *_args: writes.append(("reply",)) or "created",
        )
        env = {
            "t": t,
            "dup": types.SimpleNamespace(check=lambda _text: []),
            "sc": types.SimpleNamespace(drop_stacked_actions=drop_stacked, guard_plan_item=_real_sc.guard_plan_item, report_plan_style=lambda plan: None),
            "_VALID_KINDS": {"follow", "like", "reply"},
            "_check_length": lambda text: None,
            "_check_spanish_orthography": lambda text: None,
            "_pause": lambda *_args: None, "ec": __import__("exec_common"),
        }
        load_functions("threads_execute.py", ["_drop_stacked_actions", "_preflight_plan", "run_plan"], env)
        result = env["run_plan"]([
            {"kind": "follow", "handle": "lectora"},
            {"kind": "like", "handle": "autora", "text_fragment": ""},
        ])
        self.assertEqual(writes, [])
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))

    def test_instagram_invalid_permalink_prevents_follow(self):
        writes = []
        warning = type("BotWarningDetected", (RuntimeError,), {})
        already = type("AlreadyCommented", (RuntimeError,), {})
        ig = types.SimpleNamespace(
            BotWarningDetected=warning,
            AlreadyCommented=already,
            _validated_post_permalink=lambda value: (
                value if isinstance(value, str) and "instagram.com/" in value
                else (_ for _ in ()).throw(ValueError("invalid Instagram permalink"))
            ),
            _check_length=lambda text: None,
            _check_spanish_orthography=lambda text: None,
            follow=lambda handle: writes.append(("follow", handle)) or "followed",
            like=lambda url: writes.append(("like", url)) or "created",
            comment=lambda url, text: writes.append(("comment", url, text)) or "created",
        )
        env = {
            "ig": ig,
            "dup": types.SimpleNamespace(check=lambda _text: []),
            "sc": types.SimpleNamespace(drop_stacked_actions=drop_stacked, guard_plan_item=_real_sc.guard_plan_item, report_plan_style=lambda plan: None),
            "_VALID_KINDS": {"follow", "like", "comment"},
            "_drop_stacked_actions": lambda plan: drop_stacked(
                plan, cheap_kinds=("like",), rich_kinds=("comment",), key="permalink"
            ),
            "_pause": lambda *_args: None, "ec": __import__("exec_common"),
        }
        load_functions("instagram_execute.py", ["_preflight_plan", "run_plan"], env)
        result = env["run_plan"]([
            {"kind": "follow", "handle": "lectora"},
            {"kind": "like", "handle": "autora", "permalink": "https://evil.example/p/1"},
        ])
        self.assertEqual(writes, [])
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))


if __name__ == "__main__":
    unittest.main()
