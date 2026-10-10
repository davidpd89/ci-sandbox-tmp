"""PR #59: pruebas sintéticas herméticas; ningún acceso a cuentas o red."""
import contextlib
import datetime as dt
import json
import pathlib
import random
import sys
import tempfile
import unittest
from unittest import mock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import circuit_breaker as cb
import mechanical_round as mr
import round_canaries as rc
import round_queue as rq

try:
    MADRID = ZoneInfo("Europe/Madrid")
    HAS_TZDATA = True
except ZoneInfoNotFoundError:
    # Windows estándar puede carecer de IANA; probar el núcleo sin DST.
    MADRID = dt.timezone(dt.timedelta(hours=2))
    HAS_TZDATA = False
UTC = dt.timezone.utc
NOW = dt.datetime(2026, 10, 9, 11, 0, tzinfo=MADRID)


class CircuitPolicyTests(unittest.TestCase):
    def test_causa_tipificada_distingue_fallos(self):
        for stage, expected in (("plan", cb.FailureCause.PLAN),
                                ("preflight", cb.FailureCause.PREFLIGHT),
                                ("ineligible", cb.FailureCause.INELIGIBLE),
                                ("storage", cb.FailureCause.STORAGE),
                                ("edge_timeout", cb.FailureCause.EDGE_TIMEOUT),
                                ("execute", cb.FailureCause.UNKNOWN)):
            with self.subTest(stage=stage):
                self.assertEqual(cb.cause_for(stage=stage), expected)
        self.assertEqual(cb.cause_for(stage="execute", signal="rate"),
                         cb.FailureCause.RATE_LIMIT)
        self.assertEqual(cb.cause_for(stage="execute", signal="auth"),
                         cb.FailureCause.AUTH)
        self.assertEqual(cb.cause_for(stage="execute", signal="auth",
                          output="captcha required"), cb.FailureCause.CAPTCHA)
        self.assertEqual(cb.cause_for(stage="execute", code=503),
                         cb.FailureCause.REMOTE_5XX)

    def test_captcha_estructurado_abre_auth_y_no_texto_literario(self):
        self.assertEqual(cb.detect("TikTokMobileChallenge: CAPTCHA_REQUIRED"), "auth")
        self.assertEqual(cb.detect("verificación captcha requerida"), "auth")
        self.assertIsNone(cb.detect("El libro contiene un capítulo sobre captcha"))
        with tempfile.TemporaryDirectory() as root:
            cb.record(root, False, signal=cb.detect("captcha_required"), now=NOW)
            self.assertFalse(cb.check(root, NOW + dt.timedelta(hours=11))[0])
            self.assertTrue(cb.check(root, NOW + dt.timedelta(hours=13))[0])

    def test_aislamiento_ocho_redes_y_reinicio(self):
        with tempfile.TemporaryDirectory() as root:
            networks = ("bluesky", "mastodon", "x", "threads", "facebook",
                        "pinterest", "reddit", "tiktok", "instagram")
            folders = {n: str(pathlib.Path(root, n)) for n in networks}
            cb.record(folders["mastodon"], False, signal="auth", now=NOW)
            for n in networks:
                permitted, _ = cb.check(folders[n], now=NOW)
                self.assertEqual(permitted, n != "mastodon")
            self.assertFalse(cb.check(folders["mastodon"], now=NOW)[0])
            data = cb.load(folders["mastodon"])
            self.assertEqual(data["cause"], "auth")
            self.assertEqual(data["timezone"], "Europe/Madrid")
            self.assertIsNotNone(dt.datetime.fromisoformat(data["open_until"]).tzinfo)
            if HAS_TZDATA:
                self.assertIn("+02:00", data["open_until"])

    def test_restriccion_detectada_incluso_sin_exit_no_cero(self):
        with tempfile.TemporaryDirectory() as root:
            cb.record(root, True, signal="auth", now=NOW)
            self.assertFalse(cb.check(root, now=NOW)[0])

    def test_retry_after_numerico_http_date_invalido(self):
        self.assertEqual(cb.parse_retry_after("10800", now=NOW), 10800)
        self.assertEqual(cb.parse_retry_after("Fri, 09 Oct 2026 12:00:00 GMT", now=NOW),
                         10800)
        for raw in ("-5", "nan", "250.5", "nonsense", "", None, "9" * 200):
            with self.subTest(raw=raw):
                self.assertIsNone(cb.parse_retry_after(raw, now=NOW))
        self.assertEqual(cb.retry_after_from_output(
            "HTTP 429 Too Many Requests\nRetry-After: 14400\nbody: red"), "14400")
        self.assertIsNone(cb.retry_after_from_output(
            "El protagonista dice Retry-After: 14400\nNo hay respuesta HTTP"))

    def test_respeta_retry_after_mayor_que_politica_y_no_acorta(self):
        with tempfile.TemporaryDirectory() as root:
            cb.record(root, False, signal="rate", now=NOW, retry_after="18000")
            end = dt.datetime.fromisoformat(cb.load(root)["open_until"])
            self.assertEqual(end.astimezone(UTC) - NOW.astimezone(UTC),
                             dt.timedelta(hours=5))
            cb.record(root, False, signal="rate", now=NOW + dt.timedelta(minutes=1),
                      retry_after="1")
            self.assertEqual(dt.datetime.fromisoformat(cb.load(root)["open_until"]), end)

    def test_prioridad_causa_y_origen_de_pausa_anterior(self):
        with tempfile.TemporaryDirectory() as root:
            cb.record(root, False, signal="auth", now=NOW, origin="tiktok_executor")
            original = cb.load(root)
            cb.record(root, False, signal="rate", now=NOW, retry_after="1",
                      origin="another_worker")
            new_state = cb.load(root)
            self.assertEqual(new_state["open_until"], original["open_until"])
            self.assertEqual(new_state["cause"], "auth")
            self.assertEqual(new_state["origin"], "tiktok_executor")

    @unittest.skipUnless(HAS_TZDATA, 'requiere tzdata Europe/Madrid')
    def test_no_reabrir_temprano_en_cambio_horario_invierno(self):
        start = dt.datetime(2026, 10, 25, 1, 30, tzinfo=MADRID)
        with tempfile.TemporaryDirectory() as root:
            cb.record(root, False, signal="rate", now=start)
            end = dt.datetime.fromisoformat(cb.load(root)["open_until"])
            self.assertEqual(end.astimezone(UTC) - start.astimezone(UTC),
                             dt.timedelta(hours=3))
            self.assertFalse(cb.check(root, start.astimezone(UTC) +
                                      dt.timedelta(hours=2, minutes=59))[0])
            self.assertTrue(cb.check(root, start.astimezone(UTC) +
                                     dt.timedelta(hours=3))[0])

    @unittest.skipUnless(HAS_TZDATA, 'requiere tzdata Europe/Madrid')
    def test_no_reabrir_temprano_en_cambio_horario_verano(self):
        start = dt.datetime(2026, 3, 29, 1, 30, tzinfo=MADRID)
        with tempfile.TemporaryDirectory() as root:
            cb.record(root, False, signal="rate", now=start)
            end = dt.datetime.fromisoformat(cb.load(root)["open_until"])
            self.assertEqual(end.astimezone(UTC) - start.astimezone(UTC),
                             dt.timedelta(hours=3))

    def test_legacy_naive_se_consulta_sin_migracion_destruc(self):
        with tempfile.TemporaryDirectory() as root:
            folder = pathlib.Path(root, "cache")
            folder.mkdir()
            (folder / "breaker.json").write_text(json.dumps({
                "fails": 3, "open_until": "2026-10-09T14:00", "reason": "execute"
            }), encoding="utf-8")
            self.assertFalse(cb.check(root, now=dt.datetime(2026, 10, 9, 11))[0])
            self.assertTrue(cb.check(root, now=dt.datetime(2026, 10, 9, 15))[0])

    def test_json_corrupto_es_bloqueo_y_no_se_sobrescribe(self):
        with tempfile.TemporaryDirectory() as root:
            path = pathlib.Path(root, "cache", "breaker.json")
            path.parent.mkdir()
            path.write_text('{"fails":', encoding="utf-8")
            self.assertFalse(cb.check(root, now=NOW)[0])
            with self.assertRaises(ValueError):
                cb.record(root, True, now=NOW)
            self.assertEqual(path.read_text(encoding="utf-8"), '{"fails":')

    def test_json_con_tipos_malformados_bloquea_sin_false_ok(self):
        for invalid in ({"fails": True, "open_until": None},
                        {"fails": -1, "open_until": None},
                        {"fails": 0, "open_until": []},
                        {"fails": 0}):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as root:
                path = pathlib.Path(root, "cache", "breaker.json")
                path.parent.mkdir()
                path.write_text(json.dumps(invalid), encoding="utf-8")
                self.assertFalse(cb.check(root, now=NOW)[0])

    def test_scheduler_respeta_cooldown_persistido_y_estado_corrupto(self):
        with tempfile.TemporaryDirectory() as root:
            net = pathlib.Path(root, "SISTEMA_DIARIO_REDDIT")
            cb.record(str(net), False, signal="rate", now=NOW)
            with mock.patch.object(rq, "ROOT", root), \
                 mock.patch.object(rq.random, "uniform", return_value=720), \
                 mock.patch.object(cb, "_madrid_timezone", return_value=MADRID):
                done, delay, alert = rq.classify_round_state(
                    "saltada", 0, network="reddit", now=NOW.replace(tzinfo=None))
                self.assertFalse(done)
                self.assertGreaterEqual(delay, 3 * 3600 - 1)
                self.assertFalse(alert)
                (net / "cache" / "breaker.json").write_text("{", encoding="utf-8")
                _, delay_corrupt, _ = rq.classify_round_state(
                    "saltada", 0, network="reddit", now=NOW.replace(tzinfo=None))
                self.assertGreaterEqual(delay_corrupt, 3 * 3600)

    def test_canario_comprende_offset_y_cuarentena_invalida(self):
        with tempfile.TemporaryDirectory() as root:
            net = pathlib.Path(root, "SISTEMA_DIARIO_BLUESKY")
            cb.record(str(net), False, signal="rate", now=NOW)
            with mock.patch.object(cb, "_madrid_timezone", return_value=MADRID):
                alerts = rc._breaker_alerts(pathlib.Path(root), NOW.replace(tzinfo=None))
            self.assertEqual([(a["network"], a["code"]) for a in alerts],
                             [("bluesky", "CORTACIRCUITOS_ABIERTO")])
            path = net / "cache" / "breaker.json"
            path.write_text("{", encoding="utf-8")
            alerts = rc._breaker_alerts(pathlib.Path(root), NOW.replace(tzinfo=None))
            self.assertEqual(alerts[0]["code"], "BREAKER_INVALIDO")


class OrchestrationTests(unittest.TestCase):
    def _run_stub(self, result):
        messages = []
        with mock.patch("action_ledger.exclusive", return_value=contextlib.nullcontext()), \
             mock.patch.object(mr.cb, "check", return_value=(True, "")), \
             mock.patch.object(mr, "_run", return_value=dict(result)), \
             mock.patch.object(mr.cb, "record", return_value={}) as record, \
             mock.patch.object(mr, "_record_plan_failure"):
            got = mr.run("mastodon", rng=random.Random(7), out=messages.append)
        return got, record, messages

    def test_plan_local_no_penaliza_cuenta(self):
        _, recorded, _ = self._run_stub({
            "ok": False, "failure_kind": "plan", "stage": "plan"})
        recorded.assert_not_called()

    def test_restricted_tipado_prevalece_sobre_exit_cero(self):
        _, recorded, _ = self._run_stub({
            "ok": False, "failure_kind": "execute", "stage": "execute",
            "exit_code": 0, "signal": "auth"})
        self.assertEqual(recorded.call_args.kwargs["signal"], "auth")

    def test_tiktok_bulk_restricted_señal_inmediata_y_sin_otros_pasos(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = {"dir": "TEST", "pre": [["python", "tools/tiktok_bulk_follow.py"]],
                   "decisions_default": None, "write_decisions": None,
                   "build": ["python", "tools/build.py"], "plan": "plan.json",
                   "execute": ["python", "tools/execute.py"], "post": [], "shape": False}
            calls = []
            def fake_runner(cmd):
                calls.append(cmd[1])
                if cmd[1].endswith("tiktok_bulk_follow.py"):
                    return 0, "TIKTOK_STEP_STATUS=restricted"
                return 0, ""
            with mock.patch.object(mr, "ROOT", root), \
                 mock.patch.dict(mr.PIPELINES, {"tiktok": cfg}):
                result = mr._run("tiktok", shape=False, runner=fake_runner,
                                 signals=[], out=lambda *_: None)
            self.assertEqual(result["signal"], "auth")
            self.assertEqual(result["failure_kind"], "execute")
            self.assertNotIn("tools/build.py", calls)
            self.assertNotIn("tools/execute.py", calls)

    def test_http429_etapa_previa_propaga_retry_after_y_aborta(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = {"dir": "TEST", "pre": [["python", "fake_scan.py"]],
                   "decisions_default": None, "write_decisions": None,
                   "build": None, "plan": "plan.json",
                   "execute": ["python", "fake_execute.py"],
                   "post": [], "shape": False}
            seen = []
            def runner(cmd):
                seen.append(cmd[1])
                return 1, "HTTP 429 Too Many Requests\nRetry-After: 20000"
            with (
                mock.patch.object(mr, "ROOT", root),
                mock.patch.dict(mr.PIPELINES, {"mastodon": cfg}),
                mock.patch.object(mr, "CONTENT_QUEUE_NETWORKS", {"mastodon"}),
                mock.patch.object(mr, "PUBLISH_NETWORKS", set()),
                mock.patch("action_ledger.exclusive", return_value=contextlib.nullcontext()),
                mock.patch.object(mr.cb, "check", return_value=(True, "")),
                mock.patch.object(mr.cb, "record", return_value={}) as rec,
            ):
                result = mr.run("mastodon", rng=random.Random(42),
                                runner=runner, out=lambda *_: None)
            self.assertFalse(result["ok"])
            self.assertEqual(result["failure_kind"], "execute")
            self.assertEqual(rec.call_args.kwargs["signal"], "rate")
            self.assertEqual(rec.call_args.kwargs["retry_after"], "20000")
            self.assertEqual(seen, ["tools/content_queue_alert.py"])

    def test_ack_edge_incierto_no_reejecuta_ni_abre_breaker(self):
        with tempfile.TemporaryDirectory() as root:
            pathlib.Path(root, "plan.json").write_text("[]", encoding="utf-8")
            config = {"dir": "TEST", "pre": [], "decisions_default": None,
                      "write_decisions": None, "build": None,
                      "plan": "plan.json", "execute": ["python", "fake_execute.py"],
                      "post": [["python", "fake_post.py"]], "shape": False, "browser": True}
            calls = []
            def runner(cmd):
                calls.append(cmd[1])
                return 0, "VIGILANTE: Edge no responde"
            with mock.patch.object(mr, "ROOT", root), \
                 mock.patch.dict(mr.PIPELINES, {"synthetic": config}):
                result = mr._run("synthetic", shape=False, runner=runner,
                                 signals=[], out=lambda *_: None)
            self.assertEqual(result["error_reason"], "edge_ack_uncertain")
            self.assertEqual(calls.count("fake_execute.py"), 1)
            self.assertNotIn("fake_post.py", calls)



class DurableUncertainAckTests(unittest.TestCase):
    def test_manual_hold_no_expira_ni_se_reset_por_exito_automatico(self):
        with tempfile.TemporaryDirectory() as root:
            cb.hold_for_review(root, "edge_ack_uncertain", now=NOW)
            state = cb.load(root)
            self.assertTrue(state["manual_hold"])
            self.assertEqual(state["manual_hold_reason"], "edge_ack_uncertain")
            self.assertFalse(cb.check(root, now=NOW + dt.timedelta(days=40))[0])
            cb.record(root, True, now=NOW + dt.timedelta(days=1))
            self.assertEqual(cb.load(root)["manual_hold_at"], state["manual_hold_at"])
            cb.record(root, False, signal="rate", now=NOW)
            self.assertTrue(cb.load(root)["manual_hold"])

    def test_fallo_de_fsync_conserva_estado_previo_sin_dar_falsa_garantia(self):
        with tempfile.TemporaryDirectory() as root:
            cb.record(root, False, signal="auth", now=NOW)
            path = pathlib.Path(root, "cache", "breaker.json")
            before = path.read_bytes()
            with mock.patch.object(cb.os, "fsync", side_effect=OSError("synthetic I/O")):
                with self.assertRaises(OSError):
                    cb.hold_for_review(root, "edge_ack_uncertain", now=NOW)
            self.assertEqual(path.read_bytes(), before)
            self.assertFalse(cb.check(root, now=NOW)[0])

    def test_hold_invalido_no_crea_excepcion_que_abra_red(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                cb.hold_for_review(root, "untrusted_free_text", now=NOW)
            self.assertTrue(cb.check(root, now=NOW)[0])

    def test_cuarentena_manual_señalada_por_canario_y_scheduler(self):
        with tempfile.TemporaryDirectory() as root:
            network_dir = pathlib.Path(root, "SISTEMA_DIARIO_THREADS")
            cb.hold_for_review(str(network_dir), "edge_ack_uncertain", now=NOW)
            alerts = rc._breaker_alerts(pathlib.Path(root), NOW)
            self.assertEqual([(a["network"], a["code"]) for a in alerts],
                             [("threads", "BREAKER_REVISION_MANUAL")])
            with mock.patch.object(rq, "ROOT", root), \
                 mock.patch.object(rq.random, "uniform", return_value=720):
                _, delay, _ = rq.classify_round_state("saltada", 0,
                                                      network="threads", now=NOW)
            self.assertGreaterEqual(delay, 3 * 3600)

    def test_watchdog_y_429_conservan_ambas_cuarentenas(self):
        with tempfile.TemporaryDirectory() as root:
            pathlib.Path(root, "plan.json").write_text("[]", encoding="utf-8")
            cfg = {"dir": "TEST", "pre": [], "decisions_default": None,
                   "write_decisions": None, "build": None, "plan": "plan.json",
                   "execute": ["python", "fake_execute.py"], "post": [],
                   "shape": False, "browser": True}
            def runner(cmd):
                if cmd[1] == "fake_execute.py":
                    return 1, "VIGILANTE: Edge timeout\nHTTP 429 Too Many Requests\nRetry-After: 18000"
                return 0, "workers reanudados"
            with mock.patch.object(mr, "ROOT", root), \
                 mock.patch.dict(mr.PIPELINES, {"synthetic": cfg}), \
                 mock.patch("action_ledger.exclusive",
                            return_value=contextlib.nullcontext()), \
                 mock.patch("action_ledger.browser_session",
                            return_value=contextlib.nullcontext()), \
                 mock.patch.object(mr, "_record_plan_failure", return_value=True):
                result = mr.run("synthetic", shape=False, rng=random.Random(3),
                                runner=runner, out=lambda *_: None)
            state = cb.load(str(pathlib.Path(root, "TEST")))
            self.assertEqual(result["error_reason"], "edge_ack_uncertain")
            self.assertTrue(state["manual_hold"])
            self.assertEqual(state["cause"], "rate_limit")
            self.assertFalse(cb.check(str(pathlib.Path(root, "TEST")),
                                      now=NOW + dt.timedelta(days=10))[0])

    def test_watchdog_sin_confirmaciones_queda_bloqueado_tras_reinicio(self):
        with tempfile.TemporaryDirectory() as root:
            pathlib.Path(root, "plan.json").write_text("[]", encoding="utf-8")
            config = {"dir": "TEST", "pre": [], "decisions_default": None,
                      "write_decisions": None, "build": None, "plan": "plan.json",
                      "execute": ["python", "fake_execute.py"], "post": [],
                      "shape": False, "browser": True}
            calls = []
            def runner(cmd):
                calls.append(cmd[1])
                if cmd[1] == "fake_execute.py":
                    return 0, "VIGILANTE: sin confirmación"
                return 0, "workers recuperados"
            with mock.patch.object(mr, "ROOT", root), \
                 mock.patch.dict(mr.PIPELINES, {"synthetic": config}), \
                 mock.patch("action_ledger.exclusive",
                            return_value=contextlib.nullcontext()), \
                 mock.patch("action_ledger.browser_session",
                            return_value=contextlib.nullcontext()), \
                 mock.patch.object(mr, "_record_plan_failure", return_value=True):
                result = mr.run("synthetic", shape=False, rng=random.Random(3),
                                runner=runner, out=lambda *_: None)
                again = mr.run("synthetic", shape=False, rng=random.Random(3),
                               runner=runner, out=lambda *_: None)
            self.assertFalse(result["ok"])
            self.assertEqual(result["error_reason"], "edge_ack_uncertain")
            self.assertEqual(calls.count("fake_execute.py"), 1)
            self.assertTrue(again["skipped"])
            self.assertFalse(cb.check(str(pathlib.Path(root, "TEST")), NOW)[0])


if __name__ == "__main__":
    unittest.main()
