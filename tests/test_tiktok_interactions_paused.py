"""TikTok queda solo para publicación: ninguna automatización de cuenta puede abrir navegador."""
import ast
import pathlib
import types
import unittest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools"
INTERACT = TOOLS / "tiktok_interact.py"
SCAN = TOOLS / "tiktok_scan.py"
EXECUTE = TOOLS / "tiktok_execute.py"


def _load_guarded_functions(names):
    tree = ast.parse(INTERACT.read_text(encoding="utf-8"))
    wanted = set(names) | {"_refuse_if_paused"}
    nodes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "InteractionsPaused":
            nodes.append(node)
        elif isinstance(node, ast.Assign):
            if any(
                isinstance(target, ast.Name) and target.id == "INTERACTIONS_PAUSED"
                for target in node.targets
            ):
                nodes.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted:
            nodes.append(node)

    trap_calls = []

    def trap(*args, **kwargs):
        trap_calls.append((args, kwargs))
        raise AssertionError("No debía alcanzarse ninguna operación de navegador")

    env = {
        "_cdp_alive": trap,
        "sync_playwright": types.SimpleNamespace(start=trap),
        "subprocess": types.SimpleNamespace(Popen=trap),
    }
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(INTERACT), "exec"),
        env,
    )
    env["INTERACTIONS_PAUSED"] = True   # 04/10: la cuenta esta reactivada; aqui se prueba el MECANISMO de pausa
    return env, trap_calls


class TikTokPausedTests(unittest.TestCase):
    def test_pause_mechanism_refuses_when_flag_is_true(self):
        env, _ = _load_guarded_functions([])
        with self.assertRaises(env["InteractionsPaused"]):
            env["_refuse_if_paused"]()

    def test_browser_entrypoints_fail_before_any_browser_operation(self):
        names = [
            "ensure_browser",
            "_connect",
            "health",
            "dump_following_feed",
            "dump_profile",
        ]
        env, trap_calls = _load_guarded_functions(names)

        for name, args in (
            ("ensure_browser", ()),
            ("_connect", ()),
            ("health", ()),
            ("dump_following_feed", ()),
            ("dump_profile", (None,)),
        ):
            with self.subTest(name=name):
                with self.assertRaises(env["InteractionsPaused"]):
                    env[name](*args)

        self.assertEqual(trap_calls, [])

    def test_navigation_helpers_fail_before_touching_page(self):
        names = ["_dump_following_feed", "_dump_profile", "_open_post"]
        env, _ = _load_guarded_functions(names)

        class TrapPage:
            def __getattr__(self, name):
                raise AssertionError(
                    f"No debía accederse a page.{name} con TikTok pausado"
                )

        pg = TrapPage()
        for name, args in (
            ("_dump_following_feed", (pg,)),
            ("_dump_profile", (pg, None)),
            ("_open_post", (pg, 0)),
        ):
            with self.subTest(name=name):
                with self.assertRaises(env["InteractionsPaused"]):
                    env[name](*args)

    def test_scan_guard_is_first_executable_statement(self):
        tree = ast.parse(SCAN.read_text(encoding="utf-8"))
        fn = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "scan"
        )
        first = fn.body[0]
        self.assertIsInstance(first, ast.Expr)
        self.assertIsInstance(first.value, ast.Call)
        self.assertIsInstance(first.value.func, ast.Attribute)
        self.assertEqual(first.value.func.attr, "_refuse_if_paused")

    def test_execute_main_guard_runs_before_reading_plan_or_browser(self):
        tree = ast.parse(EXECUTE.read_text(encoding="utf-8"))
        block = next(
            node for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        )
        first = block.body[0]
        self.assertIsInstance(first, ast.Expr)
        self.assertIsInstance(first.value, ast.Call)
        self.assertIsInstance(first.value.func, ast.Attribute)
        self.assertEqual(first.value.func.attr, "_refuse_if_paused")


if __name__ == "__main__":
    unittest.main()
