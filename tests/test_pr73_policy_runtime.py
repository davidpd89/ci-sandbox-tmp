"""PR #73: contratos ejecutables offline de nueve rutas de ocho redes.

El test de interceptacion invoca funciones reales; un caller nuevo que omita
require_gpt falla indicando red y ruta. No autentica cuentas ni abre UI.
"""
import csv
import datetime
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import network_capabilities as capabilities
import network_policy_contracts as contracts
import reply_writer as writer


class ReachedPolicy(BaseException):
    """Corta la llamada en la barrera, antes de preflight/API/UI."""


class ExecutionEntryPointContracts(unittest.TestCase):
    def _invoke(self, route, temp):
        module = importlib.import_module(route.module)
        if route.module == "pinterest_growth":
            path = os.path.join(temp, "pinterest_plan.json")
            with open(path, "w", encoding="utf-8") as stream:
                json.dump([], stream)
            with (mock.patch.object(module, "PLAN_JSON", path),
                  mock.patch.object(importlib.import_module("circuit_breaker"),
                                    "check", return_value=(True, "offline")),
                  mock.patch.object(module, "_connect", side_effect=AssertionError(
                      "pinterest/cmd_run: interfaz remota antes de require_gpt"))):
                module.cmd_run()
        elif route.module == "tiktok_mobile_execute":
            module.run_plan([], mock.Mock(), pause=False)
        else:
            getattr(module, route.entrypoint)([])

    def _assert_guarded_route(self, route, temp):
        label = f"{route.network}/{route.module}.{route.entrypoint}"
        reached = []
        def trip(plan, network="", **kwargs):
            reached.append(network)
            raise ReachedPolicy
        # Un salto correcto lanza antes de preflight/API/UI; cada mutante
        # sin llamada a require_gpt debe hacer fallar ESTE metodo con ruta.
        with mock.patch.object(writer, "require_gpt", side_effect=trip):
            try:
                self._invoke(route, temp)
            except ReachedPolicy:
                self.assertEqual(reached, [route.network], label)
            except Exception as exc:
                self.fail(f"{label}: fallo ANTES de guardia ({type(exc).__name__}: {exc})")
            else:
                self.fail(f"{label}: caller sin guardia reply_writer.require_gpt")

    def test_each_real_entrypoint_reaches_common_text_guard(self):
        self.assertEqual(contracts.check_registry(), [])
        self.assertEqual(set(capabilities.NETWORKS),
                         {route.network for route in contracts.TEXT_EXECUTION_ROUTES})
        for route in contracts.TEXT_EXECUTION_ROUTES:
            label = f"{route.network}/{route.module}.{route.entrypoint}"
            with self.subTest(route=label), tempfile.TemporaryDirectory() as temp:
                self._assert_guarded_route(route, temp)

    def test_mutation_missing_guard_is_detected_with_network_and_route(self):
        route = next(r for r in contracts.TEXT_EXECUTION_ROUTES if r.network == "bluesky")
        module = importlib.import_module(route.module)
        # Mutante deliberado solo en mock: una ruta que omite la guardia.
        with mock.patch.object(module, route.entrypoint, return_value=[]), \
             tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(
                    AssertionError,
                    r"bluesky/bluesky_execute.run_plan: caller sin guardia"):
                self._assert_guarded_route(route, temp)

    def test_pipelines_point_at_declared_main_route_or_delegator(self):
        from mechanical_round import PIPELINES
        for network in capabilities.NETWORKS:
            if network == "reddit":
                self.assertNotIn(network, PIPELINES)  # Reddit tiene CLI propia.
                continue
            entry = PIPELINES[network]["execute"]
            cmd = " ".join(str(p).replace("\\", "/") for p in entry)
            if network == "tiktok":
                self.assertIn("tiktok_growth_flow.py", cmd)
                # tiktok_growth_flow delega al ejecutor Android; ruta legacy aparte.
            else:
                route = next(r for r in contracts.TEXT_EXECUTION_ROUTES if r.network == network)
                self.assertIn(route.module + ".py", cmd, network)

    def test_runtime_report_uses_capabilities_and_never_claims_remote_verification(self):
        supplied = {n: {"pipeline": n == "bluesky"}
                    for n in capabilities.NETWORKS}
        result = contracts.build_report(matrix=supplied)
        self.assertEqual(set(result["networks"]), set(capabilities.NETWORKS))
        self.assertEqual(result["certification"], "declarado_sin_ejecucion_remota")
        for network, metadata in result["networks"].items():
            with self.subTest(network=network):
                self.assertEqual(metadata["capabilities"], supplied[network])
                self.assertTrue(metadata["text_entrypoints"])
                self.assertEqual(metadata["runtime_tests"], "requeridos")

    def test_unproved_text_filtered_even_with_global_suite_flag(self):
        # conftest.py suele habilitar RRSS_ALLOW_UNMARKED_TEXT=1. Suprimir
        # la marca pytest para reproducir el comportamiento productivo.
        plan = [
            {"kind": "reply", "handle": "lectora", "text": "Frase sin certificado", "authored": "manual"},
            {"kind": "comment", "text": "Más texto sin prueba", "url": "https://example.invalid/post"},
            {"kind": "follow", "handle": "lectora"},
            {"kind": "like", "url": "https://example.invalid/post"},
        ]
        with tempfile.TemporaryDirectory() as temp:
            proof_path = os.path.join(temp, "missing_proofs.json")
            with mock.patch.dict(os.environ, {"RRSS_ALLOW_UNMARKED_TEXT": "1",
                                               "PYTEST_CURRENT_TEST": ""}):
                for network in capabilities.NETWORKS:
                    with self.subTest(network=network):
                        logs = []
                        got = writer.require_gpt(plan, network, path=proof_path, log=logs.append)
                        self.assertEqual(got, plan[2:],
                                         f"{network}/require_gpt: filtro no fail-closed")
                        self.assertTrue(any("sin_prueba=2" in line for line in logs), network)

    def test_reddit_direct_reply_rejects_before_touching_dom(self):
        import reddit_comments
        pg = mock.Mock()
        item = {"id": "t1_abc123", "text": "Frase sin procedencia", "author": "lectora"}
        with mock.patch.dict(os.environ, {"RRSS_ALLOW_UNMARKED_TEXT": "",
                                           "PYTEST_CURRENT_TEST": ""}):
            result = reddit_comments.reply_in_thread(
                pg, "https://www.reddit.com/r/libros/comments/abc/post/", item,
                log=lambda _: None)
        self.assertFalse(result)
        pg.assert_not_called()
        self.assertFalse(pg.mock_calls, "reddit/reply_in_thread: DOM tocado sin prueba")

    def test_inbound_vs_first_comment_conversation_rule_in_all_networks(self):
        import conversation_turn_policy as turn
        recent = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
        for network in capabilities.NETWORKS:
            with self.subTest(network=network):
                first, _ = turn.check_execution(network, {
                    "kind": "reply", "reply_to_us": False, "post_text": "Me encantó ese final", "post_created_at": recent})
                ended, why = turn.check_execution(network, {
                    "kind": "reply", "reply_to_us": True, "post_text": "Gracias.", "post_created_at": recent})
                self.assertTrue(first)
                self.assertFalse(ended)
                self.assertEqual(why, "cierre_social")


class SharedPolicyBoundaryContracts(unittest.TestCase):
    TODAY = datetime.date(2026, 10, 9)

    def test_follow_cleanup_day_six_vs_day_seven(self):
        import follow_review as review
        import growth_policy as policy
        self.assertEqual(policy.NONRECIPROCAL_DAYS, 7)
        rows = []
        for name, delta in (("madura", 7), ("reciente", 6)):
            rows.append({"fecha": (self.TODAY - datetime.timedelta(days=delta)).isoformat(),
                         "tipo": "follow", "cuenta": "@" + name, "resultado": "confirmado"})
        out = review.review(rows, [], self.TODAY, days=policy.NONRECIPROCAL_DAYS)
        self.assertEqual([entry["account"] for entry in out], ["madura"])

    def test_second_chance_at_day_twenty_one_and_three_attempts(self):
        import relationship_policy as rp
        def write(path, dates):
            with open(path, "w", encoding="utf-8", newline="") as fh:
                writer_csv = csv.DictWriter(fh, fieldnames=(
                    "fecha", "tipo", "cuenta", "resultado", "notas"))
                writer_csv.writeheader()
                for when in dates:
                    writer_csv.writerow({"fecha": when, "tipo": "unfollow",
                        "cuenta": "@lectora", "resultado": "confirmado",
                        "notas": "no devuelve el follow tras 7 dias"})
        with tempfile.TemporaryDirectory() as temp:
            path = os.path.join(temp, "registro.csv")
            first = (self.TODAY - datetime.timedelta(days=20)).isoformat()
            write(path, [first])
            self.assertIn("lectora", rp.blocked_accounts(path, today=self.TODAY))
            write(path, [(self.TODAY - datetime.timedelta(days=21)).isoformat()])
            self.assertNotIn("lectora", rp.blocked_accounts(path, today=self.TODAY))
            write(path, [(self.TODAY - datetime.timedelta(days=d)).isoformat()
                         for d in (70, 50, 21)])
            self.assertIn("lectora", rp.blocked_accounts(path, today=self.TODAY))

    def test_curated_reposts_have_single_shared_quota(self):
        import growth_policy as gp
        import repost_policy as rep
        self.assertEqual(gp.SHARE_TTL_DAYS, 1)  # dias, NO certifica 24h exactas
        self.assertEqual(rep.MAX_PER_DAY, 3)
        items = [
            {"kind": "like"}, {"kind": "repost", "curated": False},
            {"kind": "boost", "curated": True}, {"kind": "quote", "curated": True},
            {"kind": "repost", "curated": True}, {"kind": "boost", "curated": True},
            {"kind": "follow"},
        ]
        result, omitted = rep.filter_plan(items, already=1)
        self.assertEqual([i["kind"] for i in result],
                         ["like", "boost", "quote", "follow"])
        self.assertEqual(omitted, 3)


if __name__ == "__main__":
    unittest.main()
