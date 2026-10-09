"""R11: un intento saltado por bloqueo/403 no se vuelve 'confirmado'.

Regresión del mapeo común: un unfollow saltado puede liberar erróneamente
el estado de un follow confirmado, aunque no se haya enviado ninguna orden.
SQLite y todas las cuentas se simulan en tempfile, sin servicios externos.
"""
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import action_ledger as al


class LedgerSkipOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = al.ActionLedger(os.path.join(self.tmp.name, "actions.sqlite"))

    def tearDown(self):
        self.tmp.cleanup()


    def test_late_settlement_cannot_overwrite_terminal_or_holdout_status(self):
        self.assertEqual(self.ledger.reserve("follow", "ana"), "ok")
        self.ledger.settle("follow", "ana", al.CONFIRMED, "confirmado")
        self.ledger.settle("follow", "ana", al.FAILED, "fallo:tarde")
        self.assertEqual(self.ledger.status("follow", "ana"), al.CONFIRMED)
        self.assertEqual(self.ledger.reserve("follow", "ana"), al.CONFIRMED)

        self.assertEqual(self.ledger.reserve("follow", "control"), "ok")
        self.ledger.hold("follow", "control")
        self.ledger.settle("follow", "control", al.CONFIRMED, "confirmado:tardio")
        self.assertEqual(self.ledger.status("follow", "control"), al.HOLDOUT)

    def test_rejected_stale_unfollow_result_cannot_release_follow(self):
        self.assertEqual(self.ledger.reserve("follow", "ana"), "ok")
        self.ledger.settle("follow", "ana", al.CONFIRMED)
        self.assertEqual(self.ledger.reserve("unfollow", "ana"), "ok")
        self.ledger.hold("unfollow", "ana")
        self.ledger.settle_results({("unfollow", "ana")}, [
            {"kind": "unfollow", "handle": "ana", "resultado": "confirmado"},
        ])
        self.assertEqual(self.ledger.status("unfollow", "ana"), al.HOLDOUT)
        self.assertEqual(self.ledger.status("follow", "ana"), al.CONFIRMED)

    def test_replayed_old_unfollow_cannot_delete_newer_follow(self):
        now = [1_000.0]
        ledger = al.ActionLedger(os.path.join(self.tmp.name, "follow-replay.sqlite"),
                                 clock=lambda: now[0])
        ledger.reserve("follow", "ana")
        ledger.settle("follow", "ana", al.CONFIRMED)
        now[0] += 10
        ledger.reserve("unfollow", "ana")
        ledger.settle_results({("unfollow", "ana")}, [
            {"kind": "unfollow", "handle": "ana", "resultado": "confirmado"},
        ])
        self.assertIsNone(ledger.status("follow", "ana"))

        # Otro ciclo legítimo sí puede volver a seguir, una vez hubo unfollow.
        now[0] += 10
        self.assertEqual(ledger.reserve("follow", "ana"), "ok")
        ledger.settle("follow", "ana", al.CONFIRMED)
        ledger.settle_results({("unfollow", "ana")}, [
            {"kind": "unfollow", "handle": "ana", "resultado": "confirmado"},
        ])
        self.assertEqual(ledger.status("follow", "ana"), al.CONFIRMED)

    def test_confirmed_unfollow_preserves_follow_holdout(self):
        self.ledger.hold("follow", "ana")
        self.assertEqual(self.ledger.reserve("unfollow", "ana"), "ok")
        self.ledger.settle_results({("unfollow", "ana")}, [
            {"kind": "unfollow", "handle": "ana", "resultado": "confirmado"},
        ])
        self.assertEqual(self.ledger.status("unfollow", "ana"), al.CONFIRMED)
        self.assertEqual(self.ledger.status("follow", "ana"), al.HOLDOUT)
        # La liberación MANUAL explícita del holdout conserva su comportamiento.
        self.ledger.release("follow", "ana")
        self.assertIsNone(self.ledger.status("follow", "ana"))

    def test_403_skipped_unfollow_must_not_release_confirmed_follow(self):
        self.ledger.reserve("follow", "ana")
        self.ledger.settle("follow", "ana", al.CONFIRMED)
        self.ledger.reserve("unfollow", "ana")
        al.settle_results(self.ledger, {("unfollow", "ana")}, [
            {"kind": "unfollow", "handle": "@Ana", "resultado": "saltado_api_403"}
        ])
        self.assertEqual(self.ledger.status("follow", "ana"), al.CONFIRMED)
        self.assertEqual(self.ledger.status("unfollow", "ana"), al.FAILED)

    def test_concurrent_unfollow_reserved_by_other_process_never_releases_follow(self):
        # bluesky_execute.run_plan devuelve saltado_en_ledger:reserved cuando
        # otro proceso posee la reserva. Este proceso no reserva nada:
        # settle_results NO debe liberar el follow histórico.
        self.ledger.reserve("follow", "ana")
        self.ledger.settle("follow", "ana", al.CONFIRMED)
        self.ledger.reserve("unfollow", "ana")  # reserva ajena, aún pendiente
        al.settle_results(self.ledger, set(), [
            {"kind": "unfollow", "handle": "@Ana",
             "resultado": "saltado_en_ledger:reserved"}
        ])
        self.assertEqual(self.ledger.status("follow", "ana"), al.CONFIRMED)
        self.assertEqual(self.ledger.status("unfollow", "ana"), al.RESERVED)

    def test_other_skip_without_remote_confirmation_is_not_confirmed(self):
        retryable = ("saltado_en_ledger:reserved", "saltado_api_403",
                     "saltado_sin_contexto", "saltado_objetivo_no_resuelto")
        for result in retryable:
            with self.subTest(result=result):
                self.assertEqual(al.outcome_to_status(result), al.FAILED)
        for result in ("saltado_cierre_conversacion:gracias",
                       "saltado_perfil:bio_en_otro_idioma",
                       "saltado_like_contexto:irrelevante"):
            with self.subTest(result=result):
                self.assertEqual(al.outcome_to_status(result), al.SKIPPED_POLICY)

    def test_remote_already_done_still_confirms_and_releases_follow(self):
        self.ledger.reserve("follow", "ana")
        self.ledger.settle("follow", "ana", al.CONFIRMED)
        self.ledger.reserve("unfollow", "ana")
        al.settle_results(self.ledger, {("unfollow", "ana")}, [
            {"kind": "unfollow", "handle": "ana", "resultado": "saltado_ya_no_seguido"}
        ])
        self.assertEqual(self.ledger.status("follow", "ana"), None)
        self.assertEqual(self.ledger.status("unfollow", "ana"), al.CONFIRMED)

    def test_remote_already_commented_still_means_confirmed(self):
        self.assertEqual(al.outcome_to_status("saltado_ya_comentado"), al.CONFIRMED)
        self.assertEqual(al.outcome_to_status("saltado_ya_reaccionado"), al.CONFIRMED)
        self.assertEqual(al.outcome_to_status("saltado_ya_seguido"), al.CONFIRMED)

    def test_policy_skip_is_not_replanned_until_its_ttl(self):
        now = [1000.0]
        ledger = al.ActionLedger(os.path.join(self.tmp.name, "policy.sqlite"),
                                 clock=lambda: now[0])
        self.assertEqual(ledger.reserve("follow", "ana"), "ok")
        ledger.settle("follow", "ana", al.outcome_to_status("saltado_perfil:bio"),
                      "saltado_perfil:bio")
        self.assertEqual(ledger.status("follow", "ana"), al.SKIPPED_POLICY)
        now[0] += 6 * 86400
        self.assertEqual(ledger.reserve("follow", "ana"), al.SKIPPED_POLICY)
        now[0] += 86400 + 1
        self.assertEqual(ledger.reserve("follow", "ana"), "ok")

    def test_conversation_policy_skip_expires_after_one_day(self):
        now = [2000.0]
        ledger = al.ActionLedger(os.path.join(self.tmp.name, "closure.sqlite"),
                                 clock=lambda: now[0])
        self.assertEqual(ledger.reserve("reply", "at://a/post/1"), "ok")
        ledger.settle("reply", "at://a/post/1",
                      al.outcome_to_status("saltado_cierre_conversacion:gracias"),
                      "saltado_cierre_conversacion:gracias")
        now[0] += 3600
        self.assertEqual(ledger.reserve("reply", "at://a/post/1"), al.SKIPPED_POLICY)
        now[0] += 24 * 3600
        self.assertEqual(ledger.reserve("reply", "at://a/post/1"), "ok")

    def test_403_and_foreign_ledger_reservation_remain_retryable(self):
        for result in ("saltado_api_403", "saltado_en_ledger:reserved"):
            with self.subTest(result=result):
                self.assertEqual(al.outcome_to_status(result), al.FAILED)

    def test_uncertain_and_stop_remain_distinct(self):
        self.assertEqual(al.outcome_to_status("pendiente_verificacion:timeout"), al.UNCERTAIN)
        # Una escritura de resultado desconocido NO es reintentable por
        # llevar un prefijo genérico "saltado".
        self.assertEqual(al.outcome_to_status("saltado_pendiente_verificacion"), al.UNCERTAIN)
        self.assertEqual(al.outcome_to_status("parada_rate_limit:429"), al.FAILED)
        self.assertEqual(al.outcome_to_status("confirmado"), al.CONFIRMED)

    def test_extended_policy_cases_and_unknown_fallback(self):
        for reason in ("saltado_fase_calentamiento", "saltado_techo_sesion",
                       "saltado_duplicado"):
            with self.subTest(reason=reason):
                self.assertEqual(al.outcome_to_status(reason), al.SKIPPED_POLICY)
        with self.assertLogs("action_ledger", level="WARNING"):
            self.assertEqual(al.outcome_to_status("saltado_nuevo_sin_catalogar"),
                             al.SKIPPED_POLICY)
        self.assertEqual(al.outcome_to_status("saltado_ya_boost"), al.CONFIRMED)
        self.assertEqual(al.outcome_to_status("saltado_api_404"), al.FAILED)

    def test_unknown_skip_replans_only_after_six_hours(self):
        now = [500.0]
        ledger = al.ActionLedger(os.path.join(self.tmp.name, "unknown.sqlite"),
                                 clock=lambda: now[0])
        ledger.reserve("follow", "ana")
        with self.assertLogs("action_ledger", level="WARNING"):
            status = al.outcome_to_status("saltado_nuevo_sin_catalogar")
        ledger.settle("follow", "ana", status, "saltado_nuevo_sin_catalogar")
        now[0] += 6 * 3600 - 1
        self.assertEqual(ledger.reserve("follow", "ana"), al.SKIPPED_POLICY)
        now[0] += 1
        self.assertEqual(ledger.reserve("follow", "ana"), "ok")

    def test_skipped_policy_does_not_use_daily_budget(self):
        for i, reason in enumerate(("saltado_fase_calentamiento",
                                    "saltado_duplicado", "saltado_perfil:idioma")):
            self.ledger.reserve("follow", f"usuario-{i}")
            self.ledger.settle("follow", f"usuario-{i}",
                               al.outcome_to_status(reason), reason)
        self.assertEqual(self.ledger.count_since(0), 0)
        self.ledger.reserve("follow", "confirmado")
        self.ledger.settle("follow", "confirmado", al.CONFIRMED)
        self.assertEqual(self.ledger.count_since(0), 1)

    def test_editorial_skip_must_reserve_before_appending_result(self):
        import ast
        root = pathlib.Path(__file__).resolve().parents[1]
        for network in ("bluesky", "mastodon"):
            path = root / "tools" / f"{network}_execute.py"
            tree = ast.parse(path.read_text(encoding="utf-8"))
            func = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "run_plan")
            loops = [n for n in ast.walk(func) if isinstance(n, ast.For)]
            loop = next(n for n in loops if "ctp.check_execution" in ast.unparse(n))
            body = ast.unparse(loop)
            self.assertLess(body.index("ledger.reserve("),
                            body.index("ctp.check_execution("),
                            f"{network}: el skip editorial no alcanza SQLite")

    def test_active_tool_literal_skip_codes_are_catalogued(self):
        import ast
        import re
        tools = pathlib.Path(__file__).resolve().parents[1] / "tools"
        missing = []
        for source in sorted(tools.glob("*.py")):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                    continue
                value = node.value
                if not value.startswith("saltado_"):
                    continue
                code = value.split(":", 1)[0]
                if code in ("saltado_ya_", "saltado_api_"):
                    # Prefijos de f-string; se validan las familias en outcome_to_status.
                    continue
                if re.fullmatch(r"saltado_[a-z_]+", code) and code not in al.OUTCOME_CLASS:
                    missing.append(f"{source.name}:{node.lineno}:{code}")
        self.assertEqual(missing, [], "Falta clasificar: " + ", ".join(missing))

    def test_both_executor_paths_persist_closed_conversations(self):
        from unittest import mock
        import reply_writer
        import repost_policy
        import conversation_turn_policy as ctp
        import bluesky_execute
        import mastodon_execute
        item = {"kind": "reply", "handle": "lectora.example", "status_id": "4711",
                "url": "https://example.com/post/4711", "text": "Gracias por comentarlo.",
                "reply_to_us": True, "post_text": "Gracias."}
        for name, execute in (("bluesky", bluesky_execute), ("mastodon", mastodon_execute)):
            with self.subTest(network=name):
                ledger = al.ActionLedger(os.path.join(self.tmp.name, f"{name}.sqlite"))
                with (
                    mock.patch.object(reply_writer, "require_gpt", side_effect=lambda p, network: p),
                    mock.patch.object(repost_policy, "guard", side_effect=lambda p, log: p),
                    mock.patch.object(execute, "_preflight_plan", side_effect=lambda p: p),
                    mock.patch.object(execute, "_prefetch_window"),
                    mock.patch.object(execute.sc, "report_plan_style"),
                    mock.patch.object(ctp, "check_execution", return_value=(False, "cierre_social")),
                ):
                    options = {"ledger": ledger}
                    if name == "mastodon":
                        options["prevalidated"] = True
                    result = execute.run_plan([dict(item)], **options)
                    self.assertEqual(result[0]["resultado"], "saltado_cierre_conversacion:cierre_social")
                    self.assertEqual(ledger.status("reply", "4711"), al.SKIPPED_POLICY)
                    second = execute.run_plan([dict(item)], **options)
                    self.assertEqual(second[0]["resultado"], "saltado_en_ledger:skipped_policy")
                    self.assertEqual(ledger.count_since(0), 0)

    def test_legacy_reclassification_needs_backup_and_keeps_timestamps(self):
        import sqlite3
        import r11_policy_migrate as migration
        db = os.path.join(self.tmp.name, "old.sqlite")
        clock = lambda: 100.0
        ledger = al.ActionLedger(db, clock=clock)
        for target, reason in (("perfil", "saltado_perfil:idioma"),
                               ("cierre", "saltado_cierre_conversacion:gracias"),
                               ("hecho", "saltado_ya_comentado")):
            ledger.reserve("reply", target)
            ledger.settle("reply", target, al.CONFIRMED, reason)
        backup = os.path.join(self.tmp.name, "old.backup.sqlite")
        self.assertEqual(len(migration.candidates(db)), 2)
        self.assertEqual(sum(count for _, _, count in migration.summary(db)), 3)
        self.assertTrue(all(status == al.CONFIRMED
                            for status, _, _ in migration.summary(db)))
        with self.assertRaises(ValueError):
            migration.apply(db, backup)
        self.assertFalse(os.path.exists(backup))
        self.assertEqual(migration.apply(db, backup, offline_confirmed=True), 2)
        self.assertEqual(ledger.status("reply", "perfil"), al.SKIPPED_POLICY)
        self.assertEqual(ledger.status("reply", "cierre"), al.SKIPPED_POLICY)
        self.assertEqual(ledger.status("reply", "hecho"), al.CONFIRMED)
        self.assertEqual(ledger.count_since(0), 1)
        import contextlib
        # with sqlite3.connect() NO cierra la conexión: Windows retiene la
        # base y TemporaryDirectory.cleanup() lanza WinError 32.
        with contextlib.closing(sqlite3.connect(db)) as conn:
            self.assertEqual(conn.execute(
                "SELECT created,updated FROM actions WHERE target='perfil'"
            ).fetchone(), (100.0, 100.0))
        with contextlib.closing(sqlite3.connect(backup)) as conn:
            self.assertEqual(conn.execute("PRAGMA quick_check").fetchone(), ("ok",))
            self.assertEqual(conn.execute(
                "SELECT count(*) FROM actions WHERE status='confirmed'"
            ).fetchone()[0], 3)
        with self.assertRaises(FileExistsError):
            migration.apply(db, backup, offline_confirmed=True)


    def test_duplicate_skipped_target_preserves_intermediate_policy_state(self):
        """La segunda omisión no debe sobreescribir el primer descarte."""
        from unittest import mock
        import reply_writer
        import repost_policy
        import conversation_turn_policy as ctp
        import bluesky_execute
        import mastodon_execute
        item = {"kind": "reply", "handle": "lectora.example", "status_id": "4711",
                "url": "https://example.com/post/4711", "text": "Gracias por comentarlo.",
                "reply_to_us": True, "post_text": "Gracias."}
        for name, execute in (("bluesky", bluesky_execute), ("mastodon", mastodon_execute)):
            with self.subTest(network=name):
                ledger = al.ActionLedger(os.path.join(self.tmp.name, f"duplicate-{name}.sqlite"))
                intermediate = []

                def on_result(result):
                    intermediate.append((result["resultado"], ledger.status("reply", "4711")))

                with (
                    mock.patch.object(reply_writer, "require_gpt", side_effect=lambda p, network: p),
                    mock.patch.object(repost_policy, "guard", side_effect=lambda p, log: p),
                    mock.patch.object(execute, "_preflight_plan", side_effect=lambda p: p),
                    mock.patch.object(execute, "_prefetch_window"),
                    mock.patch.object(execute.sc, "report_plan_style"),
                    mock.patch.object(ctp, "check_execution", return_value=(False, "cierre_social")),
                ):
                    options = {"ledger": ledger, "on_result": on_result}
                    if name == "mastodon":
                        options["prevalidated"] = True
                    results = execute.run_plan([dict(item), dict(item)], **options)
                self.assertEqual([x["resultado"] for x in results],
                                 ["saltado_cierre_conversacion:cierre_social",
                                  "saltado_en_ledger:already_in_plan"])
                self.assertEqual(intermediate, [
                    ("saltado_cierre_conversacion:cierre_social", al.SKIPPED_POLICY),
                    ("saltado_en_ledger:already_in_plan", al.SKIPPED_POLICY),
                ])
                self.assertEqual(ledger.status("reply", "4711"), al.SKIPPED_POLICY)


    def test_failed_first_attempt_is_not_retried_for_duplicate_in_same_plan(self):
        """Evita doble escritura remota y settlement engañoso tras un fallo inicial."""
        from unittest import mock
        import reply_writer
        import repost_policy
        import conversation_turn_policy as ctp
        import bluesky_execute
        import mastodon_execute
        item = {"kind": "follow", "handle": "ana"}
        for name, execute in (("bluesky", bluesky_execute), ("mastodon", mastodon_execute)):
            with self.subTest(network=name):
                ledger = al.ActionLedger(os.path.join(self.tmp.name, f"fail-duplicate-{name}.sqlite"))
                calls = []
                with (
                    mock.patch.object(reply_writer, "require_gpt", side_effect=lambda p, network: p),
                    mock.patch.object(repost_policy, "guard", side_effect=lambda p, log: p),
                    mock.patch.object(execute, "_preflight_plan", side_effect=lambda p: p),
                    mock.patch.object(execute, "_prefetch_window"),
                    mock.patch.object(execute, "_pause"),
                    mock.patch.object(execute.sc, "report_plan_style"),
                    mock.patch.object(ctp, "check_execution", return_value=(True, "ok")),
                ):
                    if name == "bluesky":
                        with mock.patch.object(execute.b, "follow",
                                               side_effect=RuntimeError("simulated failure")) as remote:
                            results = execute.run_plan([dict(item), dict(item)], ledger=ledger,
                                                       on_result=lambda r: calls.append(r["resultado"]))
                    else:
                        with mock.patch.object(execute, "_pace_for_rate_limit"), \
                             mock.patch.object(execute, "_attempt",
                                               side_effect=RuntimeError("simulated failure")) as remote:
                            results = execute.run_plan([dict(item), dict(item)], ledger=ledger,
                                                       on_result=lambda r: calls.append(r["resultado"]),
                                                       prevalidated=True)
                self.assertEqual(remote.call_count, 1)
                self.assertEqual(len(results), 2)
                self.assertTrue(results[0]["resultado"].startswith("fallo:"))
                self.assertEqual(results[1]["resultado"], "saltado_en_ledger:already_in_plan")
                self.assertEqual(ledger.status("follow", "ana"), al.FAILED)
                self.assertEqual(calls, [r["resultado"] for r in results])

    def test_unowned_confirmed_unfollow_does_not_release_a_confirmed_follow(self):
        # Un resultado de un ejecutor ajeno no acredita la propiedad de la
        # reserva. Antes, el segundo bucle de settle_results soltaba el follow.
        self.ledger.reserve("follow", "ana")
        self.ledger.settle("follow", "ana", al.CONFIRMED)
        self.ledger.reserve("unfollow", "ana")  # trabajo de otro proceso
        al.settle_results(self.ledger, set(), [
            {"kind": "unfollow", "handle": "ana", "resultado": "confirmado"},
        ])
        self.assertEqual(self.ledger.status("follow", "ana"), al.CONFIRMED)
        self.assertEqual(self.ledger.status("unfollow", "ana"), al.RESERVED)

    def test_second_conflicting_result_does_not_release_follow(self):
        self.ledger.reserve("follow", "ana")
        self.ledger.settle("follow", "ana", al.CONFIRMED)
        self.ledger.reserve("unfollow", "ana")
        al.settle_results(self.ledger, {("unfollow", "ana")}, [
            {"kind": "unfollow", "handle": "ana", "resultado": "saltado_api_403"},
            {"kind": "unfollow", "handle": "ana", "resultado": "confirmado"},
        ])
        self.assertEqual(self.ledger.status("follow", "ana"), al.CONFIRMED)
        self.assertEqual(self.ledger.status("unfollow", "ana"), al.FAILED)

    def test_dynamic_mastodon_already_codes_match_allowed_kinds(self):
        import ast
        src = pathlib.Path(__file__).resolve().parents[1] / "tools" / "mastodon_execute.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        allowed = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign) and
                       any(isinstance(t, ast.Name) and t.id == "ALLOWED_KINDS"
                           for t in node.targets))
        for kind in allowed:
            with self.subTest(kind=kind):
                self.assertEqual(al.outcome_to_status(f"saltado_ya_{kind}"),
                                 al.CONFIRMED)

    def test_migration_audit_uses_read_only_connection(self):
        from unittest import mock
        import r11_policy_migrate as migration
        db = os.path.join(self.tmp.name, "read-only-audit.sqlite")
        ledger = al.ActionLedger(db)
        ledger.reserve("reply", "target")
        ledger.settle("reply", "target", al.CONFIRMED,
                      "saltado_cierre_conversacion:cierre_social")
        original_connect = migration._connect_existing
        with mock.patch.object(migration, "_connect_existing",
                               wraps=original_connect) as opener:
            self.assertEqual(len(migration.candidates(db)), 1)
            self.assertEqual(migration.summary(db)[0][2], 1)
        self.assertEqual(opener.call_args_list, [
            mock.call(db, readonly=True), mock.call(db, readonly=True),
        ])
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(migration.main(["--db", db]), 0)
        self.assertIn("Estado | prefijo del motivo", output.getvalue())
        self.assertIn("confirmed históricas elegibles: 1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
