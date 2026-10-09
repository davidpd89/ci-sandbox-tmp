"""Bluesky: ningún error determinista del plan puede aparecer después de escribir."""
import ast
import pathlib
import types
import unittest
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / "tools"))
import scan_common as _real_sc

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "bluesky_execute.py"


def _drop(plan, *, cheap_kinds, rich_kinds, key):
    rich = {
        p[key] for p in plan
        if p.get("kind") in rich_kinds and key in p and p[key] is not None
    }
    return [
        p for p in plan
        if not (
            p.get("kind") in cheap_kinds
            and key in p and p[key] is not None
            and p[key] in rich
        )
    ]


def load_executor(dup_check=lambda text: []):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {
        "_drop_stacked_actions", "_validated_plan_item",
        "_preflight_plan", "run_plan",
    }
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    writes = []

    class BotWarningDetected(RuntimeError):
        pass

    class AlreadyCommented(RuntimeError):
        pass

    def uri(url):
        marker = "/post/"
        suffix = url.split(marker, 1)[1] if marker in url else url.rsplit("/", 1)[-1]
        return f"at://did:plc:target/app.bsky.feed.post/{suffix}"

    b = types.SimpleNamespace(
        _url_to_uri=uri,
        _check_length=lambda text: None,
        _check_spanish_orthography=lambda text: None,
        follow=lambda handle: writes.append(("follow", handle)) or "followed",
        unfollow=lambda handle: writes.append(("unfollow", handle)) or "unfollowed",
        like=lambda url: writes.append(("like", url)) or "created",
        repost=lambda url: writes.append(("repost", url)) or ("created", uri(url).replace("post", "repost", 1)),
        quote=lambda url, text: writes.append(("quote", url, text)) or ("created", uri(url).replace("abc", "newquote", 1)),
        reply_to=lambda url, text: writes.append(("reply", url, text)),
        BotWarningDetected=BotWarningDetected,
        AlreadyCommented=AlreadyCommented,
    )
    env = {
        "b": b,
        "dup": types.SimpleNamespace(check=dup_check),
        "sc": types.SimpleNamespace(drop_stacked_actions=_drop, guard_plan_item=_real_sc.guard_plan_item, report_plan_style=lambda plan: None),
        "_pause": lambda: None,
            "ec": __import__("exec_common"),
        "_hourly_guard": lambda *a, **k: 0,
        "PREFETCH_WINDOW": 100,
        "_prefetch_window": lambda items: None,
        "_CONTENT_KINDS": {"like", "repost", "reply", "quote"},
        "_TEXT_KINDS": {"reply", "quote"},
        "_RELATION_KINDS": {"follow", "unfollow"},
    }
    env["_VALID_KINDS"] = env["_CONTENT_KINDS"] | env["_RELATION_KINDS"]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), env)
    return env, writes


class BlueskyPreflightTests(unittest.TestCase):
    def test_later_invalid_item_blocks_first_write(self):
        env, writes = load_executor()
        result = env["run_plan"]([
            {"kind": "follow", "handle": "lectora.bsky.social"},
            {"kind": "inventado", "handle": "otra.bsky.social"},
        ])
        self.assertEqual(writes, [])
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))

    def test_later_duplicate_text_blocks_first_write(self):
        env, writes = load_executor(
            lambda text: ["frase repetida"] if text == "duplicado" else []
        )
        result = env["run_plan"]([
            {"kind": "follow", "handle": "lectora.bsky.social"},
            {
                "kind": "reply",
                "handle": "otra.bsky.social",
                "url": "https://bsky.app/profile/otra.bsky.social/post/abc",
                "text": "duplicado",
            },
        ])
        self.assertEqual(writes, [])
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))

    def test_two_cheap_actions_same_post_are_rejected(self):
        env, writes = load_executor()
        result = env["run_plan"]([
            {
                "kind": "like", "handle": "lectora.bsky.social",
                "url": "https://bsky.app/profile/lectora.bsky.social/post/abc",
            },
            {
                "kind": "repost", "curated": True, "handle": "lectora.bsky.social",
                "url": "https://bsky.app/profile/lectora.bsky.social/post/abc",
            },
        ])
        self.assertEqual(writes, [])
        self.assertIn("varias interacciones", result[0]["resultado"])

    def test_like_is_dropped_when_same_post_has_reply(self):
        env, writes = load_executor()
        result = env["run_plan"]([
            {
                "kind": "like", "handle": "lectora.bsky.social",
                "url": "https://bsky.app/profile/lectora.bsky.social/post/abc",
            },
            {
                "kind": "reply", "handle": "lectora.bsky.social",
                "url": "https://bsky.app/profile/lectora.bsky.social/post/abc",
                "text": "Respuesta distinta y útil.",
            },
        ])
        self.assertEqual(writes, [
            (
                "reply",
                "https://bsky.app/profile/lectora.bsky.social/post/abc",
                "Respuesta distinta y útil.",
            )
        ])
        self.assertEqual(result[0]["resultado"], "confirmado")


class LedgerIntegrationTests(unittest.TestCase):
    def test_second_execution_of_the_same_plan_does_nothing_and_stale_retry_is_possible(self):
        import os, tempfile
        import action_ledger as al
        plan = [
            {"kind": "reply", "handle": "lectora.bsky.social",
             "url": "https://bsky.app/profile/lectora.bsky.social/post/abc", "text": "Respuesta única."},
            {"kind": "like", "handle": "otra.bsky.social",
             "url": "https://bsky.app/profile/otra.bsky.social/post/xyz"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            ledger = al.ActionLedger(os.path.join(tmp, "ledger.sqlite"))
            env, writes = load_executor()
            first = env["run_plan"](list(plan), ledger=ledger)
            self.assertEqual([r["resultado"] for r in first], ["confirmado", "confirmado"])
            self.assertEqual(len(writes), 2)
            env2, writes2 = load_executor()
            second = env2["run_plan"](list(plan), ledger=ledger)
            self.assertEqual(writes2, [])
            self.assertTrue(all(r["resultado"] == "saltado_en_ledger:confirmed" for r in second))

    def test_concurrent_reservation_by_another_process_skips_the_write(self):
        import os, tempfile
        import action_ledger as al
        with tempfile.TemporaryDirectory() as tmp:
            ledger = al.ActionLedger(os.path.join(tmp, "ledger.sqlite"))
            item = {"kind": "like", "handle": "otra.bsky.social",
                    "url": "https://bsky.app/profile/otra.bsky.social/post/xyz"}
            env, writes = load_executor()
            # el harness no pasa por _validated_plan_item real: el objetivo cae a la url
            target = item["url"]
            self.assertEqual(ledger.reserve("like", target), "ok")  # otro proceso se adelanto
            result = env["run_plan"]([item], ledger=ledger)
            self.assertEqual((writes, result[0]["resultado"]), ([], "saltado_en_ledger:reserved"))

    def test_without_a_ledger_nothing_changes(self):
        env, writes = load_executor()
        env["run_plan"]([{"kind": "like", "handle": "a.bsky.social",
                          "url": "https://bsky.app/profile/a.bsky.social/post/q"}])
        self.assertEqual(len(writes), 1)


if __name__ == "__main__":
    unittest.main()


class UnresolvableTargetTests(unittest.TestCase):
    """05/10: un handle que no resuelve se omite; antes tumbaba el lote entero."""

    def test_one_dead_account_does_not_abort_the_batch(self):
        import importlib
        sys_path = str(__import__("pathlib").Path(__file__).resolve().parents[1] / "tools")
        if sys_path not in __import__("sys").path:
            __import__("sys").path.insert(0, sys_path)
        be = importlib.import_module("bluesky_execute")

        def fake_uri(url):
            if "muerta" in url:
                raise RuntimeError('GET com.atproto.identity.resolveHandle fallo (400): {"message":"Unable to resolve handle"}')
            return "at://did:plc:x/app.bsky.feed.post/" + url.rsplit("/", 1)[-1]

        old = be.b._url_to_uri
        be.b._url_to_uri = fake_uri
        try:
            plan = [{"kind": "like", "handle": "viva.bsky.social", "url": "https://bsky.app/profile/viva.bsky.social/post/a1"},
                    {"kind": "like", "handle": "muerta.bsky.social", "url": "https://bsky.app/profile/muerta.bsky.social/post/b2"},
                    {"kind": "follow", "handle": "otra.bsky.social"}]
            out = be._preflight_plan(plan)
        finally:
            be.b._url_to_uri = old
        self.assertEqual([i["handle"] for i in out], ["viva.bsky.social", "otra.bsky.social"])


class CrashSafetyTests(unittest.TestCase):
    """05/10: si el proceso muere a mitad de un lote, lo ya hecho debe estar registrado y asentado en el ledger."""

    def test_each_action_is_persisted_as_it_happens(self):
        import importlib
        import tempfile
        import types as _types
        tools = str(__import__("pathlib").Path(__file__).resolve().parents[1] / "tools")
        if tools not in __import__("sys").path:
            __import__("sys").path.insert(0, tools)
        be = importlib.import_module("bluesky_execute")
        import action_ledger as al
        calls = []

        def like(url):
            calls.append(url)
            if len(calls) == 3:
                raise KeyboardInterrupt("proceso cortado")
            return "created"

        plan = [{"kind": "like", "handle": f"u{i}.bsky.social", "url": f"https://bsky.app/profile/u{i}.bsky.social/post/p{i}"} for i in range(3)]
        saved = []
        with tempfile.TemporaryDirectory() as d:
            ledger = al.ActionLedger(__import__("os").path.join(d, "l.sqlite"))
            old = (be.b, be._pause, be._hourly_guard, be._preflight_plan)
            be.b = _types.SimpleNamespace(like=like, RateLimitExceeded=type("R", (Exception,), {}),
                                          BotWarningDetected=type("B", (Exception,), {}), AlreadyCommented=type("A", (Exception,), {}))
            be._pause, be._hourly_guard, be._preflight_plan = (lambda *a, **k: None), (lambda *a, **k: 0), (lambda p: p)
            try:
                with self.assertRaises(KeyboardInterrupt):
                    be.run_plan(plan, ledger=ledger, on_result=saved.append)
            finally:
                be.b, be._pause, be._hourly_guard, be._preflight_plan = old
            self.assertEqual([r["handle"] for r in saved], ["u0.bsky.social", "u1.bsky.social"])
            self.assertEqual(ledger.status("like", ledger.target_for("like", plan[0])), al.CONFIRMED)
            self.assertEqual(ledger.status("like", ledger.target_for("like", plan[1])), al.CONFIRMED)
            self.assertEqual(ledger.status("like", ledger.target_for("like", plan[2])), al.RESERVED)   # la que estaba en curso queda reservada
