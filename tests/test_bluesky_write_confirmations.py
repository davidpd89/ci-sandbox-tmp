"""Las escrituras ATProto no deben parecer confirmadas por un HTTP 200 vacío."""
import ast
import pathlib
import re
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1] / "tools"
DID = "did:plc:abcdefghij234567"
POST = "at://did:plc:lector/app.bsky.feed.post/3abc"


def isolated(source, names, overrides=None):
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    env = {
        "sc": __import__("types").SimpleNamespace(report_plan_style=lambda plan: None, guard_plan_item=lambda *a, **k: None, drop_stacked_actions=lambda plan, **k: plan),
        "re": re,
        "_require_credentials": lambda: None,
        "_check_length": lambda text: None,
        "_check_spanish_orthography": lambda text: None,
        "_url_to_uri": lambda url: POST,
        "_get_post_record": lambda uri: {
            "uri": POST, "cid": "cid-post", "root": None,
        },
        "_already_commented": lambda uri: False,
        "_already_quoted": lambda uri, text: False,
        "_session": lambda: {"did": DID},
        "_add_richtext": lambda record: record,
        "_now": lambda: "2026-09-24T00:00:00.000Z",
        "_get": lambda *a, **k: {"viewer": {}},
        "_post_xrpc": lambda *a, **k: {},
        "AUTH_BASE": "https://bsky.social/xrpc",
        "AlreadyCommented": type("AlreadyCommented", (RuntimeError,), {}),
    }
    env.update(overrides or {})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), env)
    return env


class BlueskyWriteTests(unittest.TestCase):
    def test_quote_reply_post_need_uri_and_cid(self):
        source = ROOT / "bluesky_interact.py"
        names = ["_require_created_record", "quote", "reply_to", "post"]
        for action, args in (
            ("quote", (POST, "Cita")),
            ("reply_to", (POST, "Respuesta")),
            ("post", ("Publicación",)),
        ):
            with self.subTest(action=action):
                env = isolated(source, names)
                with self.assertRaisesRegex(RuntimeError, "URI/CID"):
                    env[action](*args)
                env["_post_xrpc"] = lambda *a, **kw: {
                    "uri": f"at://{DID}/app.bsky.feed.post/newrecord",
                    "cid": "cid-created",
                }
                result = env[action](*args)
                if action == "quote":
                    self.assertEqual(
                        result,
                        ("created", f"at://{DID}/app.bsky.feed.post/newrecord"),
                    )
                else:
                    self.assertIsNone(result)

    def test_main_image_and_alt_posting_survive_this_pr(self):
        calls = []
        embed = {"$type": "app.bsky.embed.images",
                 "images": [{"alt": "Fotografía de una biblioteca", "image": {"ref": "blob"}}]}
        env = isolated(ROOT / "bluesky_interact.py",
                       ["_require_created_record", "post"], {
            "_upload_image": lambda path, alt: calls.append(("upload", path, alt)) or embed,
            "_post_xrpc": lambda method, payload: calls.append(("create", payload)) or {
                "uri": f"at://{DID}/app.bsky.feed.post/newrecord", "cid": "cid-created",
            },
        })
        env["post"]("Una lectura", "foto.jpg", "Fotografía de una biblioteca")
        self.assertEqual(calls[0], ("upload", "foto.jpg", "Fotografía de una biblioteca"))
        self.assertEqual(calls[1][1]["record"]["embed"], embed)
        self.assertEqual(calls[1][1]["record"]["$type"], "app.bsky.feed.post")

    def test_unfollow_uses_viewer_uri_and_never_pages_follow_collection(self):
        source = ROOT / "bluesky_interact.py"
        calls = []
        own = f"at://{DID}/app.bsky.graph.follow/3abc"
        env = isolated(source, ["unfollow"], {
            "_get": lambda base, path, params, auth: calls.append(("GET", path))
                    or {"viewer": {"following": own}},
            "_post_xrpc": lambda method, body: calls.append(("DELETE", body)) or {},
        })
        self.assertEqual(env["unfollow"]("lectora.bsky.social"), "unfollowed")
        self.assertEqual(calls[0], ("GET", "app.bsky.actor.getProfile"))
        self.assertEqual(calls[1][1]["rkey"], "3abc")
        self.assertEqual(len(calls), 2)

    def test_no_relation_does_not_get_recorded_as_unfollow(self):
        env = isolated(ROOT / "bluesky_interact.py", ["unfollow"])
        self.assertEqual(env["unfollow"]("lectora.bsky.social"), "already")
        env["_get"] = lambda *a, **k: {
            "viewer": {"following": "at://did:plc:otra/app.bsky.graph.follow/x"}
        }
        with self.assertRaisesRegex(RuntimeError, "propio"):
            env["unfollow"]("lectora.bsky.social")

    def test_executor_skips_unfollow_that_was_not_performed(self):
        fake = types.SimpleNamespace(unfollow=lambda h: "already")
        env = isolated(ROOT / "bluesky_execute.py", ["run_plan"], {
            "b": fake, "dup": types.SimpleNamespace(check=lambda txt: []),
            "_preflight_plan": lambda plan: plan,
            "_pause": lambda: None,
            "ec": __import__("exec_common"),
            "_hourly_guard": lambda *a, **k: 0,
            "PREFETCH_WINDOW": 100,
            "_prefetch_window": lambda items: None,
        })
        plan = [{"kind": "unfollow", "handle": "lectora.bsky.social"}]
        self.assertEqual(env["run_plan"](plan)[0]["resultado"], "saltado_ya_no_seguido")


if __name__ == "__main__":
    unittest.main()
