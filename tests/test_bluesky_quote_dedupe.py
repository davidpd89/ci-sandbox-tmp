"""Bluesky: una cita incierta no se duplica al reintentar el mismo payload."""
import ast
import pathlib
import types
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "bluesky_interact.py"
TARGET = "at://did:plc:lector/app.bsky.feed.post/abc"
ME = "did:plc:david"


def load(records):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {"_require_created_record", "_iter_own_posts", "_already_quoted", "quote"}
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    writes = []
    env = {
        "AUTH_BASE": "https://bsky.social/xrpc",
        "_require_credentials": lambda: None,
        "_check_length": lambda text: None,
        "_check_spanish_orthography": lambda text: None,
        "_url_to_uri": lambda value: TARGET,
        "_session": lambda: {"did": ME},
        "_get": lambda *a, **k: {"records": records},
        "_get_post_record": lambda uri: {
            "uri": TARGET, "cid": "cid-target", "root": None
        },
        "_add_richtext": lambda record: record,
        "_now": lambda: "2026-09-28T00:00:00.000Z",
        "_post_xrpc": lambda path, body: writes.append((path, body)) or {
            "uri": f"at://{ME}/app.bsky.feed.post/new",
            "cid": "cid-new",
        },
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), env)
    return env, writes


def own_quote(text):
    return {
        "uri": f"at://{ME}/app.bsky.feed.post/old",
        "value": {
            "$type": "app.bsky.feed.post",
            "text": text,
            "embed": {
                "$type": "app.bsky.embed.record",
                "record": {"uri": TARGET, "cid": "cid-target"},
            },
        },
    }


class BlueskyQuoteDedupeTests(unittest.TestCase):
    def test_identical_existing_quote_is_not_created_again(self):
        env, writes = load([own_quote("Mi cita")])
        self.assertEqual(env["quote"](TARGET, "Mi cita"), ("already", None))
        self.assertEqual(writes, [])

    def test_same_target_with_different_text_can_be_created(self):
        env, writes = load([own_quote("Texto anterior")])
        status, own_uri = env["quote"](TARGET, "Texto nuevo")
        self.assertEqual(status, "created")
        self.assertEqual(own_uri, f"at://{ME}/app.bsky.feed.post/new")
        self.assertEqual(len(writes), 1)
        record = writes[0][1]["record"]
        self.assertEqual(record["$type"], "app.bsky.feed.post")
        self.assertEqual(record["embed"]["record"]["uri"], TARGET)


if __name__ == "__main__":
    unittest.main()
