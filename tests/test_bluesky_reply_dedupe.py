"""Dedupe Bluesky contra los registros propios, no contra una vista de hilo."""
import ast
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "bluesky_interact.py"
URI = "at://did:plc:lector/app.bsky.feed.post/123"
OTHER = "at://did:plc:otra/app.bsky.feed.post/456"


def load_checker(getter):
    functions = [
        node for node in ast.parse(SOURCE.read_text(encoding="utf-8")).body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"_iter_own_posts", "_own_reply_parent_uris", "_already_commented"}
    ]
    env = {
        "AUTH_BASE": "https://bsky.social/xrpc",
        "_session": lambda: {"did": "did:plc:david"},
        "_get": getter,
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), env)
    return env["_already_commented"]


def post(parent_uri=None):
    value = {"text": "hola"}
    if parent_uri:
        value["reply"] = {
            "root": {"uri": URI, "cid": "root"},
            "parent": {"uri": parent_uri, "cid": "parent"},
        }
    return {"uri": "at://did:plc:david/app.bsky.feed.post/x",
            "cid": "cid", "value": value}


class BlueskyReplyDedupeTests(unittest.TestCase):
    def test_own_root_or_reply_to_someone_else_does_not_block_target(self):
        check = load_checker(lambda *a, **k: {
            "records": [post(), post(OTHER)]
        })
        self.assertFalse(check(URI))

    def test_parent_uri_set_is_built_in_one_repo_pass(self):
        calls = []
        def getter(base, path, params, auth):
            calls.append(dict(params))
            return {"records": [post(URI), post(OTHER)]}

        functions = [
            node for node in ast.parse(SOURCE.read_text(encoding="utf-8")).body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"_iter_own_posts", "_own_reply_parent_uris"}
        ]
        env = {
            "AUTH_BASE": "https://bsky.social/xrpc",
            "_session": lambda: {"did": "did:plc:david"},
            "_get": getter,
        }
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), "exec"), env)
        parents = env["_own_reply_parent_uris"]()
        self.assertEqual(parents, {URI, OTHER})
        self.assertEqual(len(calls), 1)

    def test_direct_reply_from_our_repo_is_detected(self):
        check = load_checker(lambda *a, **k: {"records": [post(URI)]})
        self.assertTrue(check(URI))

    def test_paginates_until_direct_reply_is_found(self):
        calls = []
        def getter(base, path, params, auth):
            calls.append(dict(params))
            if "cursor" not in params:
                return {"records": [post(OTHER)], "cursor": "next"}
            return {"records": [post(URI)]}

        check = load_checker(getter)
        self.assertTrue(check(URI))
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["cursor"], "next")
        self.assertEqual(calls[0]["collection"], "app.bsky.feed.post")
        self.assertTrue(calls[0]["reverse"])

    def test_invalid_pagination_fails_closed(self):
        check = load_checker(lambda *a, **k: {
            "records": [post(OTHER)], "cursor": "repeat"
        })
        with self.assertRaisesRegex(RuntimeError, "Paginación"):
            check(URI)


if __name__ == "__main__":
    unittest.main()
