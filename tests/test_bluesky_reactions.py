"""Pruebas aisladas de idempotencia Bluesky; no hacen peticiones de red."""
import ast
import pathlib
import types
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "bluesky_interact.py"
URI = "at://did:plc:lector/app.bsky.feed.post/post1"


def reaction_env(viewer, *, response=None, prefetched=None):
    code = SOURCE.read_text(encoding="utf-8")
    fns = [n for n in ast.parse(code).body
           if isinstance(n, ast.FunctionDef)
           and n.name in (
               "_require_created_record", "_reaction_state",
               "_react_once", "like", "repost",
           )]
    actions, gets = [], []
    env = {
        "_prefetched": lambda key: prefetched,
        "AUTH_BASE": "https://bsky.social/xrpc",
        "_require_credentials": lambda: None,
        "_url_to_uri": lambda url: URI,
        "_get": lambda *args, **kwargs: gets.append(args) or {"posts": [{"uri": URI, "viewer": viewer}]},
        "_get_post_record": lambda uri: gets.append(uri) or {"uri": uri, "cid": "bafy"},
        "_session": lambda: {"did": "did:plc:autor"},
        "_post_xrpc": lambda path, body: actions.append((path, body))
                       or ({
                           "uri": f"at://did:plc:autor/{body['collection']}/xyz",
                           "cid": "bafy",
                       } if response is None else response),
        "_now": lambda: "2026-09-24T00:00:00.000Z",
    }
    exec(compile(ast.Module(body=fns, type_ignores=[]), str(SOURCE), "exec"), env)
    env["_gets"] = gets
    return env, actions


class BlueskyReactions(unittest.TestCase):
    def test_existing_like_and_repost_never_create_records(self):
        env, actions = reaction_env({"like": URI, "repost": URI})
        self.assertEqual(env["like"](URI), "already")
        self.assertEqual(env["repost"](URI), ("already", None))
        self.assertEqual(actions, [])

    def test_absent_authenticated_viewer_fails_closed(self):
        env, actions = reaction_env(None)
        with self.assertRaisesRegex(RuntimeError, "viewer"):
            env["like"](URI)
        self.assertEqual(actions, [])

    def test_new_repost_creates_record_once(self):
        env, actions = reaction_env({})
        status, own_uri = env["repost"](URI)
        self.assertEqual(status, "created")
        self.assertEqual(own_uri, "at://did:plc:autor/app.bsky.feed.repost/xyz")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0][1]["collection"], "app.bsky.feed.repost")
        self.assertEqual(
            actions[0][1]["record"]["$type"], "app.bsky.feed.repost"
        )

    def test_missing_api_create_confirmation_is_not_success(self):
        env, actions = reaction_env({}, response={})
        with self.assertRaisesRegex(RuntimeError, "URI/CID"):
            env["like"](URI)
        self.assertEqual(len(actions), 1)

    def test_prefetched_state_needs_no_reads_and_still_dedupes(self):
        """05/10: con la precarga en lote cada like es UNA peticion (createRecord); sin ella eran tres."""
        env, actions = reaction_env({}, prefetched={"cid": "bafy-pre", "viewer": {}})
        self.assertEqual(env["like"](URI), "created")
        self.assertEqual(env["_gets"], [])
        self.assertEqual(actions[0][1]["record"]["subject"], {"uri": URI, "cid": "bafy-pre"})
        env, actions = reaction_env({}, prefetched={"cid": "bafy-pre", "viewer": {"like": URI}})
        self.assertEqual(env["like"](URI), "already")
        self.assertEqual(actions, [])

    def test_without_prefetch_the_usual_reads_still_happen(self):
        env, actions = reaction_env({})
        env["like"](URI)
        self.assertEqual(len(env["_gets"]), 2)


if __name__ == "__main__":
    unittest.main()
