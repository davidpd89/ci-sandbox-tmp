"""Preflight X debe bloquear el lote completo ante errores locales."""
import ast
import pathlib
import re
import types
import unittest
from urllib.parse import urlsplit
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[1] / "tools"))
import scan_common as _real_sc

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "x_execute.py"


def _drop_stacked(plan, *, cheap_kinds, rich_kinds, key):
    rich = {
        row.get(key) for row in plan
        if row.get("kind") in rich_kinds and row.get(key)
    }
    return [
        row for row in plan
        if not (row.get("kind") in cheap_kinds and row.get(key) in rich)
    ]


def _canonical(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("status URL obligatorio")
    value = value.strip()
    if value.isdigit():
        return f"https://x.com/i/web/status/{value}"
    parsed = urlsplit(value)
    if parsed.scheme != "https" or parsed.hostname not in {
        "x.com", "www.x.com", "twitter.com", "www.twitter.com",
    }:
        raise ValueError("URL X inválida")
    match = re.search(r"/status/(\d+)", parsed.path)
    if not match:
        raise ValueError("status ID inválido")
    return f"https://x.com/i/web/status/{match.group(1)}"


def _check_length(_text):
    return None


def _check_spanish_orthography(_text):
    return None


def load_executor(duplicate_check=lambda _text: []):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    names = {"_drop_stacked_actions", "_preflight_plan", "run_plan"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    writes = []

    class BotWarningDetected(RuntimeError):
        pass

    class WrongAccountActive(RuntimeError):
        pass

    class AlreadyCommented(RuntimeError):
        pass

    x = types.SimpleNamespace(
        _validated_status_url=_canonical,
        _check_length=lambda _text: None,
        _check_spanish_orthography=lambda _text: None,
        reply_to=lambda url, text: writes.append(("reply", url, text)) or "created",
        repost=lambda url, text=None: writes.append(("repost", url, text)) or "created",
        follow=lambda handle, vet=None: writes.append(("follow", handle)) or "followed",
        beat=lambda: None,
        ProfileRejected=type("ProfileRejected", (RuntimeError,), {}),
        like=lambda url: writes.append(("like", url)) or "created",
        BotWarningDetected=BotWarningDetected,
        WrongAccountActive=WrongAccountActive,
        AlreadyCommented=AlreadyCommented,
    )
    env = {
        "x": x,
        "dup": types.SimpleNamespace(check=duplicate_check),
        "sc": types.SimpleNamespace(drop_stacked_actions=_drop_stacked, guard_plan_item=_real_sc.guard_plan_item, report_plan_style=lambda plan: None),
        "_CONTENT_KINDS": {"like", "repost", "reply", "quote"},
        "_TEXT_KINDS": {"reply", "quote"},
        "_VALID_KINDS": {"follow", "like", "repost", "reply", "quote", "like_latest"},
        "_HANDLE_KINDS": {"follow", "like_latest"},
        "_follow_vet": lambda info: None,
        "ec": __import__("exec_common"),
        "_check_length": _check_length,
        "_check_spanish_orthography": _check_spanish_orthography,
        "_pause": lambda *_args: None,
        "print": lambda *_args, **_kwargs: None,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), env)
    return env, writes


class XExecutePreflightTests(unittest.TestCase):
    def test_later_invalid_item_blocks_first_write(self):
        env, writes = load_executor()
        result = env["run_plan"]([
            {"kind": "follow", "handle": "lectora"},
            {"kind": "invented", "handle": "otra"},
        ])
        self.assertEqual(writes, [])
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))

    def test_two_alias_urls_to_same_post_are_rejected_before_write(self):
        env, writes = load_executor()
        result = env["run_plan"]([
            {"kind": "like", "url": "https://twitter.com/lectora/status/123"},
            {"kind": "repost", "curated": True, "url": "https://x.com/lectora/status/123?ref=home"},
        ])
        self.assertEqual(writes, [])
        self.assertIn("varias interacciones", result[0]["resultado"])

    def test_like_is_removed_when_same_post_has_editorial_reply(self):
        env, writes = load_executor()
        result = env["run_plan"]([
            {"kind": "like", "url": "https://x.com/lectora/status/123"},
            {
                "kind": "reply",
                "url": "https://x.com/lectora/status/123",
                "text": "Respuesta concreta sobre este libro.",
            },
        ])
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0], "reply")
        self.assertEqual(result[0]["resultado"], "confirmado")

    def test_duplicate_phrase_in_later_reply_prevents_all_writes(self):
        env, writes = load_executor(
            lambda text: ["repetida"] if text == "duplicada" else []
        )
        result = env["run_plan"]([
            {"kind": "follow", "handle": "lectora"},
            {
                "kind": "reply",
                "url": "https://x.com/otra/status/456",
                "text": "duplicada",
            },
        ])
        self.assertEqual(writes, [])
        self.assertTrue(result[0]["resultado"].startswith("fallo_plan:"))


if __name__ == "__main__":
    unittest.main()
