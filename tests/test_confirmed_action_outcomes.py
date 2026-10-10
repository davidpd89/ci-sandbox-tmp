"""Estados de escritura: un no-op o una acción incierta nunca cuentan como éxito."""
import ast
import pathlib
import re
import types
import unittest
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1] / "tools"


def load_function(filename, name, namespace):
    source = ROOT / filename
    node = next(
        n for n in ast.parse(source.read_text(encoding="utf-8")).body
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[name]


class Dup:
    @staticmethod
    def check(text):
        return []


class ConfirmedOutcomeTests(unittest.TestCase):
    def test_x_executor_separates_already_pending_and_unverified(self):
        XStop = type("BotWarningDetected", (RuntimeError,), {})
        XWrong = type("WrongAccountActive", (RuntimeError,), {})
        XAlready = type("AlreadyCommented", (RuntimeError,), {})
        x = types.SimpleNamespace(
            BotWarningDetected=XStop, WrongAccountActive=XWrong, AlreadyCommented=XAlready,
            follow=lambda h, vet=None: "already",
            like=lambda u: "created",
            reply_to=lambda u, t: "created",
            repost=lambda u, *args: ("unverified", None) if args else ("already", None),
            beat=lambda: None, ProfileRejected=type("ProfileRejected", (RuntimeError,), {}),
        )
        ns = {"x": x, "dup": Dup(), "_drop_stacked_actions": lambda p: p,
              "_pause": lambda: None, "ec": __import__("exec_common"), "_follow_vet": lambda info: None}
        run = load_function("x_execute.py", "run_plan", ns)
        plan = [
            {"kind": "follow", "handle": "@a"},
            {"kind": "like", "url": "https://x.com/a/status/1"},
            {"kind": "quote", "curated": True, "url": "https://x.com/a/status/2", "text": "cita"},
            {"kind": "repost", "curated": True, "url": "https://x.com/a/status/3"},
        ]
        result = run(plan, prevalidated=True)
        self.assertEqual(
            [r["resultado"] for r in result],
            ["saltado_ya_seguido", "confirmado", "pendiente_verificacion",
             "saltado_ya_reposteado"],
        )

    def test_threads_executor_never_confirms_unverified_reply(self):
        Stop = type("BotWarningDetected", (RuntimeError,), {})
        Wrong = type("WrongAccountActive", (RuntimeError,), {})
        Already = type("AlreadyCommented", (RuntimeError,), {})
        t = types.SimpleNamespace(
            BotWarningDetected=Stop, WrongAccountActive=Wrong, AlreadyCommented=Already,
            follow=lambda h: "already",
            like_in_feed=lambda *a: "created",
            reply_to=lambda *a: "unverified",
        )
        ns = {"t": t, "dup": Dup(), "_drop_stacked_actions": lambda p: p,
              "_pause": lambda: None, "ec": __import__("exec_common"), "_already_replied_via_api": lambda text: False,
              "_verified_via_api": lambda text: False}
        run = load_function("threads_execute.py", "run_plan", ns)
        result = run([
            {"kind": "follow", "handle": "@a"},
            {"kind": "like", "handle": "@b", "text_fragment": "x"},
            {"kind": "reply", "handle": "@c", "text_fragment": "y", "text": "respuesta"},
        ], prevalidated=True)
        self.assertEqual(
            [r["resultado"] for r in result],
            ["saltado_ya_seguido", "confirmado", "pendiente_verificacion"],
        )
        ns["_verified_via_api"] = lambda text: True   # la API oficial si ve la respuesta: queda confirmada
        result = load_function("threads_execute.py", "run_plan", ns)(
            [{"kind": "reply", "handle": "@c", "text_fragment": "y", "text": "respuesta"}], prevalidated=True)
        self.assertEqual([r["resultado"] for r in result], ["confirmado"])

    def test_instagram_pending_private_follow_is_not_confirmed(self):
        Stop = type("BotWarningDetected", (RuntimeError,), {})
        Already = type("AlreadyCommented", (RuntimeError,), {})
        ig = types.SimpleNamespace(
            BotWarningDetected=Stop, AlreadyCommented=Already,
            follow=lambda h: "pending",
            like=lambda u: "already",
            comment=lambda u, t: "created",
            _refuse_if_paused=lambda: None,  # la pausa real se prueba en test_instagram_paused
        )
        ns = {"ig": ig, "dup": Dup(), "_drop_stacked_actions": lambda p: p,
              "_pause": lambda: None, "ec": __import__("exec_common")}
        run = load_function("instagram_execute.py", "run_plan", ns)
        result = run([
            {"kind": "follow", "handle": "@a"},
            {"kind": "like", "handle": "@b", "permalink": "https://instagram.com/p/1"},
            {"kind": "comment", "handle": "@c", "permalink": "https://instagram.com/p/2",
             "text": "comentario"},
        ], prevalidated=True)
        self.assertEqual(
            [r["resultado"] for r in result],
            ["pendiente_aprobacion", "saltado_ya_like", "confirmado"],
        )

    def test_facebook_executor_keeps_unverified_comments_pending(self):
        Stop = type("BotWarningDetected", (RuntimeError,), {})
        Already = type("AlreadyCommented", (RuntimeError,), {})
        like_calls = []

        def like(index=0):
            like_calls.append(index)
            return "created"

        fb = types.SimpleNamespace(
            BotWarningDetected=Stop,
            AlreadyCommented=Already,
            like=like,
            comment=lambda text, index=0: "unverified",
            like_external=lambda url: "created",
            comment_external=lambda text, url: "unverified",
        )
        ns = {
            "fb": fb,
            "dup": Dup(),
            "_drop_stacked_actions": lambda p: p,
            "_pause": lambda: None, "ec": __import__("exec_common"),
        }
        run = load_function("facebook_execute.py", "run_plan", ns)
        result = run([
            {"kind": "like", "index": 0,
             "post_text": "Mi biblioteca reúne novelas de fantasía juvenil y recomiendo esta lectura a quienes disfrutan de los libros",
             "media_present": False},
            {"kind": "comment", "index": 1, "text": "comentario"},
            {"kind": "like_external", "permalink": "https://www.facebook.com/p/1",
             "post_text": "Hoy presento mi nueva novela juvenil de fantasía, con una portada inspirada en los mundos que imaginé"},
            # Imagen sin texto del post: abstenerse aunque el mock indique éxito.
            {"kind": "like", "index": 2, "media_present": True},
            {
                "kind": "comment_external",
                "permalink": "https://www.facebook.com/p/2",
                "text": "otro comentario",
            },
        ], prevalidated=True)
        self.assertEqual(
            [r["resultado"] for r in result],
            [
                "confirmado",
                "pendiente_verificacion",
                "confirmado",
                "saltado_like_contexto:sin_texto_interpretable",
                "pendiente_verificacion",
            ],
        )

        self.assertEqual(like_calls, [0], "un post solo imagen no debe pulsar like")

    def test_tiktok_executor_distinguishes_already_created_and_unverified(self):
        Stop = type("BotWarningDetected", (RuntimeError,), {})
        Already = type("AlreadyCommented", (RuntimeError,), {})
        calls = {"like": 0}

        def like(handle, fragment):
            calls["like"] += 1
            return "already" if calls["like"] == 1 else "created"

        tt = types.SimpleNamespace(
            BotWarningDetected=Stop,
            AlreadyCommented=Already,
            follow=lambda h: "followed",
            like=like,
            comment=lambda *a: "unverified",
        )
        ns = {
            "tt": tt,
            "dup": Dup(),
            "_pause": lambda: None, "ec": __import__("exec_common"),
        }
        run = load_function("tiktok_execute.py", "run_plan", ns)
        result = run([
            {"kind": "like", "handle": "@a", "text_fragment": "fragmento suficientemente largo"},
            {"kind": "like", "handle": "@b", "text_fragment": "otro fragmento suficientemente largo"},
            {
                "kind": "comment",
                "handle": "@c",
                "text_fragment": "tercer fragmento suficientemente largo",
                "text": "comentario",
            },
        ])
        self.assertEqual(
            [r["resultado"] for r in result],
            ["saltado_ya_like", "confirmado", "pendiente_verificacion"],
        )

    def test_threads_pending_follow_is_not_confirmed(self):
        Stop = type("BotWarningDetected", (RuntimeError,), {})
        Wrong = type("WrongAccountActive", (RuntimeError,), {})
        Already = type("AlreadyCommented", (RuntimeError,), {})
        t = types.SimpleNamespace(
            BotWarningDetected=Stop,
            WrongAccountActive=Wrong,
            AlreadyCommented=Already,
            follow=lambda h: "pending",
            like_in_feed=lambda *a: "created",
            reply_to=lambda *a: "created",
        )
        ns = {
            "t": t,
            "dup": Dup(),
            "_drop_stacked_actions": lambda p: p,
            "_pause": lambda: None, "ec": __import__("exec_common"),
        }
        run = load_function("threads_execute.py", "run_plan", ns)
        result = run([{"kind": "follow", "handle": "@privada"}], prevalidated=True)
        self.assertEqual(result[0]["resultado"], "pendiente_aprobacion")

    def test_x_status_url_must_be_exact_x_host(self):
        ns = {"re": re, "urlsplit": urlsplit}
        fn = load_function("x_interact.py", "_validated_status_url", ns)
        self.assertEqual(
            fn("https://twitter.com/Autora/status/123?ref=x"),
            "https://x.com/Autora/status/123",
        )
        self.assertEqual(fn("123"), "https://x.com/i/web/status/123")
        for bad in (
            "https://x.com.evil.example/a/status/123",
            "https://evil.example/x.com/a/status/123",
            "http://x.com/a/status/123",
            "https://x.com/a/notstatus/123",
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                fn(bad)


if __name__ == "__main__":
    unittest.main()
