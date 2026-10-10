"""Regresiones aisladas de QA final. Prohibido importar sesiones reales en tests."""
from __future__ import annotations

import ast
import contextlib
import importlib
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import voice_output_finalization as voice

SAMPLE = "¿Qué pasó con «Samuel – Entre mundos»? https://example.org #Fantasía Ñandú"
NETWORKS = sorted(voice.NETWORKS)
QUEUES = sorted(voice.QUEUES)


def fake_auditor(calls, *, findings=(), exc=None):
    module = types.ModuleType("spanish_voice_quality")

    def audit(text, *, network, queue):
        calls.append((text, network, queue))
        if exc:
            raise exc
        return {
            "schema_version": 1, "network": network, "queue": queue,
            "changed": False, "findings": list(findings),
        }

    module.audit = audit
    return module


class VoiceContractTests(unittest.TestCase):
    def test_nine_networks_three_queues_preserve_source_exactly(self):
        calls = []
        with mock.patch.dict(sys.modules, {"spanish_voice_quality": fake_auditor(calls)}):
            for network in NETWORKS:
                for queue in QUEUES:
                    self.assertEqual(voice.inspect(SAMPLE, network=network,
                                                   queue=queue, log=lambda _: None), [])
        self.assertEqual(len(calls), 27)
        self.assertTrue(all(text == SAMPLE for text, _, _ in calls))
        self.assertEqual({(n, q) for _, n, q in calls},
                         {(n, q) for n in NETWORKS for q in QUEUES})

    def test_findings_are_nonblocking_and_logged_without_source(self):
        events, calls = [], []
        issue = {"code": "locale_variant", "severity": "hint", "start": 1, "end": 3, "advice": "Revisar"}
        with mock.patch.dict(sys.modules, {"spanish_voice_quality":
                                            fake_auditor(calls, findings=[issue])}):
            out = voice.inspect(SAMPLE, network="reddit", queue="WEB", log=events.append)
        self.assertEqual(out, [issue])
        self.assertEqual(len(events), 1)
        self.assertIn("locale_variant", events[0])
        self.assertNotIn("Samuel", events[0])
        self.assertEqual(calls[0][0], SAMPLE)

    def test_fields_have_distinct_diagnostics_without_mutation(self):
        fields = {"titulo": "Ñandú «Samuel»", "descripcion": SAMPLE, "alt": "#Fantasía"}
        before = dict(fields)
        calls = []
        with mock.patch.dict(sys.modules, {"spanish_voice_quality": fake_auditor(calls)}):
            result = voice.inspect_fields(fields, network="pinterest", queue="WEB")
        self.assertEqual(fields, before)
        self.assertEqual([entry[0] for entry in calls], list(fields.values()))
        self.assertEqual(set(result), set(fields))

    def test_manual_queue_is_unknown_not_falsely_web(self):
        calls = []
        with mock.patch.dict(sys.modules, {"spanish_voice_quality": fake_auditor(calls)}):
            voice.inspect(SAMPLE, network="instagram", queue=None)
        self.assertEqual(calls, [(SAMPLE, "instagram", None)])

    def test_invalid_network_queue_and_types_never_call_auditor(self):
        calls = []
        with mock.patch.dict(sys.modules, {"spanish_voice_quality": fake_auditor(calls)}):
            for kwargs in ({"network": "unknown", "queue": "WEB"},
                           {"network": "x", "queue": "unknown"}):
                with self.assertRaises(ValueError):
                    voice.inspect(SAMPLE, **kwargs)
            with self.assertRaises(TypeError):
                voice.inspect(None, network="x", queue="WEB")
            with self.assertRaises(TypeError):
                voice.inspect_fields({"texto": None}, network="x", queue="WEB")
        self.assertEqual(calls, [])

    def test_technical_failure_is_fail_closed(self):
        for exc in (RuntimeError("no backend"), ValueError("bad result")):
            calls = []
            with mock.patch.dict(sys.modules, {"spanish_voice_quality":
                                                fake_auditor(calls, exc=exc)}):
                with self.assertRaises(voice.VoicePreflightUnavailable):
                    voice.inspect(SAMPLE, network="reddit", queue="WEB")
                self.assertEqual(len(calls), 1)

    def test_imported_auditor_without_public_api_is_controlled_failure(self):
        # A module can import successfully while its public audit symbol is absent.
        # Manual reports catch VoicePreflightUnavailable, not raw AttributeError.
        broken = types.ModuleType("spanish_voice_quality")
        with mock.patch.dict(sys.modules, {"spanish_voice_quality": broken}):
            with self.assertRaises(voice.VoicePreflightUnavailable):
                voice.inspect(SAMPLE, network="reddit", queue=None)

    def test_malformed_contract_is_not_treated_as_success(self):
        module = types.ModuleType("spanish_voice_quality")
        for output in ({}, {"changed": True, "findings": []},
                       {"changed": False, "findings": ["text"]},
                       {"schema_version": 2, "network": "x", "queue": "WEB", "changed": False, "findings": []},
                       {"schema_version": 1, "network": "instagram", "queue": "WEB", "changed": False, "findings": []}):
            module.audit = lambda *args, **kwargs: output
            with mock.patch.dict(sys.modules, {"spanish_voice_quality": module}):
                with self.assertRaises(voice.VoicePreflightUnavailable):
                    voice.inspect(SAMPLE, network="x", queue="WEB")

    def test_error_logger_must_not_break_preflight(self):
        def no_log(_):
            raise OSError("broken logger")
        calls = []
        module = fake_auditor(calls, findings=[{"code": "locale_variant", "severity": "hint", "start": 0, "end": 0, "advice": "Revisar"}])
        with mock.patch.dict(sys.modules, {"spanish_voice_quality": module}):
            self.assertEqual(len(voice.inspect(SAMPLE, network="x", queue="WEB", log=no_log)), 1)


    def test_empty_and_protected_only_texts_are_not_rewritten(self):
        values = ("", " ", "\n\n", "https://example.org", "#Fantasía @lectora")
        calls = []
        with mock.patch.dict(sys.modules, {"spanish_voice_quality": fake_auditor(calls)}):
            for value in values:
                self.assertEqual(voice.inspect(value, network="reddit", queue="WEB"), [])
            result = voice.inspect_fields({"vacio": "", "solo_espacio": " ", "url": values[3]},
                                          network="reddit", queue="WEB")
        self.assertNotIn("vacio", result)  # mandatory presence is checked upstream
        self.assertEqual([x[0] for x in calls], list(values) + [" ", values[3]])

    def test_invalid_fields_are_rejected_before_any_diagnostic(self):
        calls = []
        for source in ({"uno": SAMPLE, "dos": None},
                       {"uno": SAMPLE, "dos": b"bytes"},
                       {"uno": SAMPLE, "dos": bytearray(b"byte")},
                       {"uno": SAMPLE, 2: "texto"}):
            with mock.patch.dict(sys.modules, {"spanish_voice_quality": fake_auditor(calls)}):
                with self.assertRaises(TypeError):
                    voice.inspect_fields(source, network="reddit", queue="WEB")
        self.assertEqual(calls, [])

    def test_unicode_keys_and_str_subclass_remain_unchanged(self):
        class MyString(str):
            pass
        value = MyString("Pequeña ñandú")
        calls = []
        with mock.patch.dict(sys.modules, {"spanish_voice_quality": fake_auditor(calls)}):
            out = voice.inspect_fields({"título Ñ": value}, network="pinterest", queue="WEB")
        self.assertEqual(calls[0][0], value)
        self.assertEqual(set(out), {"título Ñ"})

    def test_reject_malformed_findings_without_source_logging(self):
        cases = [
            {"code": 1},
            {"code": SAMPLE, "severity": "hint", "start": 0, "end": 1, "advice": "x"},
            {"code": "locale_variant", "severity": 1, "start": 0, "end": 1, "advice": "x"},
            {"code": "locale_variant", "severity": "hint", "start": True, "end": 1, "advice": "x"},
            {"code": "locale_variant", "severity": "hint", "start": 0, "end": len(SAMPLE)+1, "advice": "x"},
            {"code": "locale_variant", "severity": "hint", "start": 2, "end": 1, "advice": "x"},
            {"code": "locale_variant", "severity": "hint", "start": 0, "end": 1, "advice": None},
            ["code", "hint"],  # lista anidada
        ]
        for finding in cases:
            with self.subTest(finding=finding):
                events = []
                module = fake_auditor([], findings=[finding])
                with mock.patch.dict(sys.modules, {"spanish_voice_quality": module}):
                    with self.assertRaises(voice.VoicePreflightUnavailable):
                        voice.inspect(SAMPLE, network="x", queue="WEB", log=events.append)
                self.assertEqual(events, [])

    def test_partial_auditor_failure_never_returns_fields(self):
        module = types.ModuleType("spanish_voice_quality")
        calls = []
        def audit(text, *, network, queue):
            calls.append(text)
            if len(calls) == 2:
                raise RuntimeError("synthetic failure")
            return {"schema_version": 1, "network": network, "queue": queue,
                    "changed": False, "findings": []}
        module.audit = audit
        with mock.patch.dict(sys.modules, {"spanish_voice_quality": module}):
            with self.assertRaises(voice.VoicePreflightUnavailable):
                voice.inspect_fields({"titulo": SAMPLE, "descripcion": "Otra frase"},
                                     network="reddit", queue="WEB", log=lambda _: None)
        self.assertEqual(calls, [SAMPLE, "Otra frase"])

    def test_concurrent_calls_have_no_mutable_cross_queue_state(self):
        from concurrent.futures import ThreadPoolExecutor
        calls = []
        import threading
        lock = threading.Lock()
        def audit(text, *, network, queue):
            with lock:
                calls.append((text, network, queue))
            return {"schema_version": 1, "network": network, "queue": queue,
                    "changed": False, "findings": []}
        module = types.ModuleType("spanish_voice_quality")
        module.audit = audit
        pairs = [(network, queue) for network in NETWORKS for queue in QUEUES]
        with mock.patch.dict(sys.modules, {"spanish_voice_quality": module}):
            with ThreadPoolExecutor(max_workers=9) as pool:
                results = list(pool.map(lambda pair: voice.inspect(
                    SAMPLE, network=pair[0], queue=pair[1], log=lambda _: None), pairs))
        self.assertEqual(results, [[]] * len(pairs))
        self.assertEqual(sorted(calls), sorted((SAMPLE, n, q) for n, q in pairs))

    def test_large_text_does_not_appear_in_diagnostic_logs(self):
        large = "Ñandú" * 2000
        events = []
        issue = {"code": "locale_variant", "severity": "hint", "start": 0, "end": 1, "advice": "Revisar"}
        with mock.patch.dict(sys.modules, {"spanish_voice_quality": fake_auditor([], findings=[issue])}):
            voice.inspect(large, network="pinterest", queue="WEB", log=events.append)
        self.assertEqual(len(events), 1)
        self.assertNotIn("Ñandú", events[0])
        self.assertLess(len(events[0]), 200)

class XBankBoundaryTests(unittest.TestCase):
    def _execute(self, audit_side_effect=None):
        import x_bank_publish as xb
        import voice_output_finalization
        calls = []
        fake_action = types.ModuleType("action_ledger")
        fake_action.browser_session = lambda **_: contextlib.nullcontext()
        fake_cp = types.ModuleType("content_publisher")
        fake_cp.last_auto_publication = lambda *_, **__: None
        fake_x = types.ModuleType("x_interact")
        fake_x.post = lambda text: calls.append(text) or "https://x.com/example/status/123"
        item = {"id": "synthetic", "text": SAMPLE}
        with mock.patch.dict(sys.modules, {"action_ledger": fake_action,
                                            "content_publisher": fake_cp, "x_interact": fake_x}), \
             mock.patch.object(xb, "read_log", return_value=[]), \
             mock.patch.object(xb, "load_bank", return_value=[item]), \
             mock.patch.object(xb, "choose", return_value=(item, "ok")), \
             mock.patch.object(xb, "record") as record, \
             mock.patch("circuit_breaker.write_preflight", return_value=(True, "ok")), \
             mock.patch.object(voice_output_finalization, "inspect",
                               side_effect=audit_side_effect) as audit:
            if audit_side_effect is not None:
                with self.assertRaises(RuntimeError):
                    xb.main(["--apply"])
            else:
                self.assertEqual(xb.main(["--apply"]), 0)
            return audit, calls, record

    def test_x_bank_technical_failure_cannot_post_or_record(self):
        audit, posts, record = self._execute(RuntimeError("synthetic audit crash"))
        audit.assert_called_once_with(SAMPLE, network="x", queue="WEB")
        self.assertEqual(posts, [])
        record.assert_not_called()

    def test_x_bank_post_exactly_once_after_preflight(self):
        audit, posts, record = self._execute()
        audit.assert_called_once_with(SAMPLE, network="x", queue="WEB")
        self.assertEqual(posts, [SAMPLE])
        record.assert_called_once()



class IsolatedActionBoundaryTests(unittest.TestCase):
    """Ejecuta funciones originales en un sandbox de dependencias falsas.

    No importa los SDK ni abre Edge/CDP/móvil: es una prueba funcional del
    orden de preflight, no una publicación simulada con cuenta.
    """

    @staticmethod
    def extract(path, name, env):
        code = (ROOT / "tools" / path).read_text(encoding="utf-8")
        tree = ast.parse(code, filename=path)
        nodes = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(nodes) != 1:
            raise AssertionError((path, name, len(nodes)))
        isolated = ast.Module(body=[nodes[0]], type_ignores=[])
        ast.fix_missing_locations(isolated)
        ns = dict(env)
        exec(compile(isolated, path, "exec"), ns)
        return ns[name]

    def test_manual_report_survives_missing_auditor(self):
        import io
        import tempfile
        import content_queue_alert as alert
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "pending.md"
            now = alert.datetime.datetime.now().replace(microsecond=0)
            item = {"texto": SAMPLE, "titulo": "Título sintético",
                    "fecha_hora": now, "md_path": str(Path(tmp) / "post.md")}
            statuses = {"due": [item], "today": [], "verified": [],
                        "unverifiable": True}
            mock_sys = types.SimpleNamespace(
                argv=[], stdout=types.SimpleNamespace(reconfigure=lambda **_: None))
            output = io.StringIO()
            with mock.patch.object(alert, "sys", mock_sys), \
                 mock.patch.object(alert, "classify", return_value=statuses), \
                 mock.patch.object(alert.cq, "RED_FOLDERS", {"reddit": "sintético"}), \
                 mock.patch.object(alert, "OUT_MD", str(report)), \
                 mock.patch.object(alert, "ROOT", tmp), \
                 mock.patch.object(voice, "inspect_fields",
                                   side_effect=voice.VoicePreflightUnavailable("synthetic")), \
                 contextlib.redirect_stdout(output):
                self.assertEqual(alert.main(["reddit", "--no-verify"]), 0)
            self.assertIn("VENCIDA", report.read_text(encoding="utf-8"))
            self.assertIn("auditor_es_no_disponible", output.getvalue())

    def test_reddit_root_comment_failure_cannot_connect(self):
        calls = []
        fn = self.extract("reddit_interact.py", "comment", {
            "_check_length": lambda _: None,
            "_check_micro_comment": lambda _: None,
            "_check_spanish_orthography": lambda _: None,
            "_validated_thread_url": lambda url: url,
            "_comment_history_state": lambda _: None,
            "_connect": lambda: calls.append("connect"),
        })
        with mock.patch.object(voice, "inspect",
                               side_effect=voice.VoicePreflightUnavailable("fake")):
            with self.assertRaises(voice.VoicePreflightUnavailable):
                fn("https://www.reddit.com/r/lectura/comments/123", SAMPLE)
        self.assertEqual(calls, [])

    def test_reddit_embedded_reply_failure_cannot_click(self):
        clicked = []
        fake_reddit = types.ModuleType("reddit_interact")
        fake_reddit._assert_thread_destination = lambda *_: None
        fake_reddit._thread_post_id = lambda *_: "123"
        fake_reddit.MY_USERNAME = "author"
        fake_reddit._check_spanish_orthography = lambda _: None
        fake_rw = types.ModuleType("reply_writer")
        fake_rw.require_gpt = lambda *_, **__: True
        fake_policy = types.ModuleType("conversation_turn_policy")
        fake_policy.check_execution = lambda *_, **__: (True, "ok")
        pg = types.SimpleNamespace(
            locator=lambda *_: clicked.append("locator"),
            evaluate=lambda expression: ([{"id": "synthetic", "depth": 0,
                                          "parent": "t3_123"}]
                                         if expression == "synthetic" else "author"))
        fn = self.extract("reddit_comments.py", "reply_in_thread", {
            "check_reply": lambda _: None,
            "_JS_COMMENTS": "synthetic",
            "_certified_dom_target": lambda *args: True,
        })
        with mock.patch.dict(sys.modules, {"reddit_interact": fake_reddit,
                                            "reply_writer": fake_rw,
                                            "conversation_turn_policy": fake_policy}), \
             mock.patch.object(voice, "inspect",
                               side_effect=voice.VoicePreflightUnavailable("fake")):
            with self.assertRaises(voice.VoicePreflightUnavailable):
                fn(pg, "https://www.reddit.com/r/lectura/comments/123",
                   {"text": SAMPLE, "id": "synthetic"})
        self.assertEqual(clicked, [])

    def test_tiktok_mobile_failure_cannot_open_target(self):
        opened = []
        instance = types.SimpleNamespace(
            _require_writes=lambda _: None,
            _open_target=lambda _: opened.append("open"),
        )
        fn = self.extract("tiktok_mobile_interact.py", "comment", {"Any": object})
        with mock.patch.object(voice, "inspect",
                               side_effect=voice.VoicePreflightUnavailable("fake")):
            with self.assertRaises(voice.VoicePreflightUnavailable):
                fn(instance, "https://www.tiktok.com/@fiction/video/123", SAMPLE)
        self.assertEqual(opened, [])

    def test_pinterest_pin_failure_cannot_open_browser(self):
        opened = []
        fn = self.extract("pinterest_publish.py", "publish_pin", {
            "resolve_board": lambda x: x,
            "TITLE_MAX": 100,
            "DESC_MAX": 1000,
            "os": types.SimpleNamespace(path=types.SimpleNamespace(
                exists=lambda _: True)),
            "sync_playwright": lambda: opened.append("open_browser"),
            "validate_web_pin_fields": lambda *a: None,
            "validate_web_pin_image": lambda *a: {"format": "PNG", "width": 1000,
                "height": 1500, "bytes": 100, "aspect_2_3": True},
            "PinPreflightError": ValueError,
            "PinterestPublishError": RuntimeError,
        })
        with mock.patch.object(voice, "inspect_fields",
                               side_effect=voice.VoicePreflightUnavailable("fake")) as audit:
            with self.assertRaises(voice.VoicePreflightUnavailable):
                fn("synthetic.png", "Fantasía", SAMPLE, "https://example.org",
                   "Portada ficticia", "Narrativa", apply=True)
        audit.assert_called_once_with(
            {"titulo": "Fantasía", "descripcion": SAMPLE, "alt": "Portada ficticia"},
            network="pinterest", queue="WEB", log=print)
        self.assertEqual(opened, [])



class NativeDispatchBoundaryTests(unittest.TestCase):
    def test_nine_network_output_dispatches_have_preflight(self):
        scenarios = [
            ("x_execute.py", "run_plan", 'voice.inspect(item["text"], network="x", queue="WEB")', 'outcome = x.reply_to('),
            ("bluesky_execute.py", "run_plan", 'voice.inspect(item["text"], network="bluesky", queue="API")', 'b.reply_to('),
            ("mastodon_execute.py", "_do", 'voice.inspect(item["text"], network="mastodon", queue="API")', 'created = m.reply_to('),
            ("threads_execute.py", "run_plan", 'voice.inspect(item["text"], network="threads", queue="API")', 'api.publish_reply('),
            ("facebook_execute.py", "run_plan", 'voice.inspect(item["text"], network="facebook", queue="WEB")', 'outcome = fb.comment('),
            ("instagram_execute.py", "run_plan", 'voice.inspect(item["text"], network="instagram",', 'outcome = ig.comment('),
        ]
        for path, scope, audit, action in scenarios:
            with self.subTest(path=path):
                StaticLastBoundaryTests().assert_before(path, audit, action, scope)

    def test_secondary_native_dispatch_branches_audited(self):
        cases = [
            ("x_execute.py", 'elif kind == "quote":', 'voice.inspect(item["text"], network="x", queue="WEB")', 'x.repost('),
            ("threads_execute.py", 'elif kind == "reply":', 'voice.inspect(item["text"], network="threads", queue="WEB")', 't.reply_to('),
            ("facebook_execute.py", 'elif kind == "comment_external":', 'voice.inspect(item["text"], network="facebook", queue="WEB")', 'fb.comment_external('),
        ]
        for file, branch, audit, action in cases:
            s = (ROOT / "tools" / file).read_text(encoding="utf-8")
            part = s[s.index(branch):]
            self.assertLess(part.index(audit), part.index(action), file)
        s = (ROOT / "tools" / "bluesky_execute.py").read_text(encoding="utf-8")
        self.assertIn("else _voice_quote(", s)

    def test_instagram_web_mobile_queue_before_comment(self):
        cb = types.ModuleType("circuit_breaker")
        cb.write_preflight = lambda _: (True, "ok")
        ctp = types.ModuleType("conversation_turn_policy")
        ctp.check_execution = lambda *args: (True, "ok")
        item = {"kind": "comment", "handle": "demo",
                "permalink": "https://example.org/p/1", "text": SAMPLE}
        for backend, queue in (("web", "WEB"), ("mobile", "MOBILE")):
            with self.subTest(backend=backend):
                sent, seen = [], []
                ig = types.SimpleNamespace(
                    _refuse_if_paused=lambda: None,
                    comment=lambda url, text: sent.append(text) or "created",
                    BotWarningDetected=type("BotWarningDetected", (Exception,), {}),
                    AlreadyCommented=type("AlreadyCommented", (Exception,), {}),
                )
                fn = IsolatedActionBoundaryTests.extract(
                    "instagram_execute.py", "run_plan", {"ig": ig, "BACKEND": backend})
                with mock.patch.dict(sys.modules, {
                    "circuit_breaker": cb, "conversation_turn_policy": ctp
                }), mock.patch.object(voice, "inspect",
                    side_effect=lambda text, *, network, queue: seen.append(
                        (text, network, queue))):
                    result = fn([item], prevalidated=True)
                self.assertEqual(result[0]["resultado"], "confirmado")
                self.assertEqual(seen, [(SAMPLE, "instagram", queue)])
                self.assertEqual(sent, [SAMPLE])
                sent.clear()
                with mock.patch.dict(sys.modules, {
                    "circuit_breaker": cb, "conversation_turn_policy": ctp
                }), mock.patch.object(voice, "inspect",
                    side_effect=voice.VoicePreflightUnavailable("fake")):
                    failure = fn([item], prevalidated=True)
                self.assertEqual(sent, [])
                self.assertTrue(failure[0]["resultado"].startswith("fallo:"))

    def test_mastodon_reply_failure_cannot_send(self):
        sent = []
        fn = IsolatedActionBoundaryTests.extract("mastodon_execute.py", "_do", {
            "m": types.SimpleNamespace(reply_to=lambda *_: sent.append(True)),
        })
        with mock.patch.object(voice, "inspect",
                               side_effect=voice.VoicePreflightUnavailable("fake")):
            with self.assertRaises(voice.VoicePreflightUnavailable):
                fn("reply", {"status_id": "123", "text": SAMPLE})
        self.assertEqual(sent, [])

    def test_bluesky_quote_failure_cannot_send(self):
        sent = []
        fn = IsolatedActionBoundaryTests.extract("bluesky_execute.py", "_voice_quote", {})
        bridge = types.SimpleNamespace(quote=lambda *_: sent.append(True))
        with mock.patch.object(voice, "inspect",
                               side_effect=voice.VoicePreflightUnavailable("fake")):
            with self.assertRaises(voice.VoicePreflightUnavailable):
                fn({"url": "https://bsky.app/profile/demo/post/id", "text": SAMPLE}, bridge)
        self.assertEqual(sent, [])

class StaticLastBoundaryTests(unittest.TestCase):
    """Comprobación AST de orden/cola por ruta; no sustituye un canario real."""

    @staticmethod
    def source(path):
        return (ROOT / "tools" / path).read_text(encoding="utf-8")

    def assert_before(self, path, earlier, later, scope):
        src = self.source(path)
        parsed = ast.parse(src, filename=path)
        matches = [node for node in ast.walk(parsed)
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name == scope]
        self.assertEqual(len(matches), 1, (path, scope))
        node = matches[0]
        segment = "\n".join(src.splitlines()[node.lineno - 1:node.end_lineno])
        self.assertIn(earlier, segment, (path, scope))
        self.assertIn(later, segment, (path, scope))
        self.assertLess(segment.index(earlier), segment.index(later), (path, scope))

    def test_reddit_post_audited_before_durable_intent(self):
        self.assert_before("reddit_publish.py", "voice.inspect_fields(",
                           'before_submit()', "publish_post")

    def test_reddit_inline_reply_before_ui(self):
        self.assert_before("reddit_comments.py", 'voice.inspect(item["text"]',
                           "node = pg.locator(", "reply_in_thread")

    def test_reddit_direct_comment_before_browser_connect(self):
        self.assert_before("reddit_interact.py", "voice.inspect(text, network=",
                           "p, pg = _connect()", "comment")

    def test_tiktok_mobile_before_open_target(self):
        self.assert_before("tiktok_mobile_interact.py", "voice.inspect(text, network=",
                           "self._open_target(url)", "comment")

    def test_pinterest_direct_before_playwright_and_no_second_caption(self):
        self.assert_before("pinterest_publish.py", "voice.inspect_fields(fields,",
                           "p = sync_playwright().start()", "publish_pin")
        self.assertNotIn("voice_checked", self.source("content_publisher.py"))
        self.assertNotIn("voice_checked", self.source("pinterest_publish.py"))
        self.assertIn('"descripcion": description', self.source("pinterest_publish.py"))

    def test_manual_pending_is_not_marked_web(self):
        self.assert_before("content_queue_alert.py", "voice.inspect_fields(fields,",
                           'with open(OUT_MD, "w"', "main")
        self.assertIn("queue=None", self.source("content_queue_alert.py"))

    def test_all_paths_share_only_one_audit_engine(self):
        self.assertEqual(self.source("voice_output_finalization.py").count(
            'import_module("spanish_voice_quality").audit'), 1)
        for path in ("reddit_publish.py", "reddit_comments.py", "reddit_interact.py",
                     "tiktok_mobile_interact.py", "x_bank_publish.py",
                     "pinterest_publish.py", "content_queue_alert.py"):
            self.assertIn("import voice_output_finalization as voice", self.source(path))



class RealAuditorAndPublisherTests(unittest.TestCase):
    def test_real_base_auditor_contract_and_nonmutation(self):
        import spanish_voice_quality
        actual = spanish_voice_quality.audit(SAMPLE, network="bluesky", queue="API")
        self.assertEqual(actual["schema_version"], 1)
        self.assertEqual(actual["network"], "bluesky")
        self.assertEqual(actual["queue"], "API")
        self.assertIs(actual["changed"], False)
        self.assertIsInstance(actual["findings"], list)
        self.assertEqual(voice.inspect(SAMPLE, network="bluesky", queue="API", log=lambda _: None),
                         actual["findings"])

    def test_six_auto_publishers_fail_closed_and_preserve_exact_fields(self):
        import datetime
        import content_publisher as cp
        import x_bank_publish as xb
        now = datetime.datetime(2026, 10, 10, 13, 0)
        for red in ("bluesky", "mastodon", "threads", "x", "facebook", "instagram"):
            with self.subTest(red=red):
                item = {"texto": SAMPLE, "red": red, "fecha_hora": now,
                        "carpeta": "synthetic", "md_path": "synthetic.md",
                        "media": [{"exists": True, "alt": "Portada de Samuel, ñandú"}]
                                 if red in ("facebook", "instagram") else []}
                if red in ("bluesky", "mastodon"):
                    item.update(imagen="synthetic.png", alt="Portada de Samuel")
                hits, audits, verifies, logs = [], [], [], []
                def publish(source):
                    hits.append(source["texto"])
                    return "https://example.org/post"
                def verify(*args):
                    verifies.append(args)
                    return {"unverifiable": False}
                def inspect_fields(fields, *, network, queue, log):
                    audits.append((dict(fields), network, queue))
                    return {}
                with mock.patch.object(cp, "load_config", return_value={"enabled": {red: True}}), \
                     mock.patch.object(cp.cq, "pending_parse_issues", return_value=[]), \
                     mock.patch.object(cp, "eligible", return_value=([item], [])), \
                     mock.patch.object(cp, "last_auto_publication", return_value=None), \
                     mock.patch.object(cp, "blockers_of", return_value=[]), \
                     mock.patch.object(cp, "_voice_diagnostics", return_value=[]), \
                     mock.patch.object(cp.cq, "mark_done") as done, \
                     mock.patch.object(cp, "_log"), \
                     mock.patch.object(xb, "read_log", return_value=[]), \
                     mock.patch("circuit_breaker.write_preflight", return_value=(True, "ok")), \
                     mock.patch.object(voice, "inspect_fields",
                                       side_effect=voice.VoicePreflightUnavailable("fake")):
                    with self.assertRaises(voice.VoicePreflightUnavailable):
                        cp.run(red, apply=True, now=now, publishers={red: publish},
                               verify=verify, out=logs.append)
                    self.assertFalse(hits, red)
                    done.assert_not_called()
                    self.assertEqual(len(verifies), 1, red)
                verifies.clear()
                with mock.patch.object(cp, "load_config", return_value={"enabled": {red: True}}), \
                     mock.patch.object(cp.cq, "pending_parse_issues", return_value=[]), \
                     mock.patch.object(cp, "eligible", return_value=([item], [])), \
                     mock.patch.object(cp, "last_auto_publication", return_value=None), \
                     mock.patch.object(cp, "blockers_of", return_value=[]), \
                     mock.patch.object(cp, "_voice_diagnostics", return_value=[]), \
                     mock.patch.object(cp.cq, "mark_done") as done, \
                     mock.patch.object(cp, "_log"), \
                     mock.patch.object(xb, "read_log", return_value=[]), \
                     mock.patch("circuit_breaker.write_preflight", return_value=(True, "ok")), \
                     mock.patch.object(voice, "inspect_fields", side_effect=inspect_fields):
                    self.assertEqual(cp.run(red, apply=True, now=now,
                                            publishers={red: publish}, verify=verify,
                                            out=logs.append), "https://example.org/post")
                    done.assert_called_once()
                self.assertEqual(hits, [SAMPLE])
                self.assertEqual(len(audits), 1)
                fields, network, queue = audits[0]
                self.assertEqual(fields["texto"], SAMPLE)
                self.assertEqual(network, red)
                self.assertEqual(queue, "WEB" if red in cp.BROWSER else "API")
                if red in ("facebook", "instagram"):
                    self.assertEqual(fields["alt_0"], "Portada de Samuel, ñandú")
                if red in ("bluesky", "mastodon"):
                    self.assertEqual(fields["alt"], "Portada de Samuel")

if __name__ == "__main__":
    unittest.main()
