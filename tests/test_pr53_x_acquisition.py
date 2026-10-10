"""PR53: diagnóstico de adquisición en X, sin red ni archivos productivos."""
import contextlib
import csv
import importlib
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import x_acquisition_audit as xa
import x_build_plan as build
import x_execute as executor


@contextlib.contextmanager
def optional_integration_guards():
    """La rama de PR53 antecede a varios guards integrados; ambos refs son válidos."""
    guards = (
        ("reply_writer", "require_gpt", {"side_effect": lambda rows, network: rows}),
        ("conversation_turn_policy", "check_execution", {"return_value": (True, "ok")}),
        ("like_context_policy", "check_execution", {"return_value": (True, "ok")}),
        ("circuit_breaker", "write_preflight", {"return_value": (True, "ok")}),
    )
    with contextlib.ExitStack() as stack:
        for name, method, kwargs in guards:
            try:
                module = importlib.import_module(name)
            except ModuleNotFoundError as exc:
                if exc.name == name:
                    continue
                raise
            if hasattr(module, method):
                stack.enter_context(mock.patch.object(module, method, **kwargs))
        yield


class AcquisitionTests(unittest.TestCase):
    def test_status_id_canonicalizes_domains_and_query(self):
        self.assertEqual(xa.status_id("https://twitter.com/Lector/status/000123?s=20"), "123")
        self.assertEqual(xa.status_id("https://x.com/otro/status/123"), "123")
        self.assertEqual(xa.status_id("https://www.x.com/otro/status/123/"), "123")

    def test_status_id_rejects_unrelated_or_ambiguous_targets(self):
        for url in ("https://notx.com/u/status/1", "http://x.com/u/status/1",
                    "https://evil@x.com/u/status/1", "https://x.com/u/status/no",
                    "https://x.com/i/web/status/1/other", "https://x.com/i/web/status/no",
                    "https://x.com/u/status/1/other",
                    "https://x.com:999/u/status/1", "", None):
            with self.subTest(url=url):
                self.assertIsNone(xa.status_id(url))

    def test_i_web_and_decimal_aliases_are_same_post(self):
        aliases = ("123", "000123", "https://x.com/i/web/status/000123",
                   "https://twitter.com/i/web/status/123?s=20",
                   "https://x.com/Lector/status/123",
                   "https://www.x.com/lector/status/000123/")
        for alias in aliases:
            with self.subTest(alias=alias):
                self.assertEqual(xa.status_id(alias), "123")

    def test_history_blocks_same_post_across_i_web_alias_and_numeric_id(self):
        history = self._history([
            ("2026-10-10", "@Lectora", "reply", "https://x.com/Lectora/status/000123",
             "texto", "pendiente_verificacion", ""),
            ("2026-10-10", "@Otra", "quote", "https://x.com/i/web/status/000456",
             "texto", "publicado", ""),
        ])
        follows, posts = xa.read_history(history)
        kept, counts = xa.filter_known_plan([
            {"kind": "reply", "url": "https://x.com/i/web/status/123"},
            {"kind": "repost", "url": "https://twitter.com/Otra/status/456"},
            {"kind": "repost", "url": "456"},
            {"kind": "reply", "url": "https://x.com/Nueva/status/789"},
        ], follows, posts)
        self.assertEqual([item["url"] for item in kept],
                         ["https://x.com/Nueva/status/789"])
        self.assertEqual(counts["sin_fuente"]["descartadas_registro"], 3)

    def test_new_vs_known_is_registry_scope_not_remote_relationship(self):
        summary = xa.candidate_summary([
            {"source": "search:tema privado", "handle": "Autora", "known_date": None},
            {"source": "search:otra consulta", "handle": "@autora", "known_date": None},
            {"source": "search:tema privado", "handle": "Lector", "known_date": "2026-10-08"},
            {"source": "notif:reply_recibido", "handle": "Lector", "known_date": "2026-10-08"},
        ])
        self.assertEqual(summary["busqueda"],
                         {"propuestas": 3, "cuentas_sin_registro": 1, "cuentas_con_registro": 1})
        self.assertEqual(summary["notificaciones"]["cuentas_con_registro"], 1)
        self.assertNotIn("tema privado", str(summary))

    def test_source_bucket_never_exposes_query_or_handle(self):
        self.assertEqual(xa.source_family("growth:pool:score=10:src=search:tema"), "busqueda")
        self.assertEqual(xa.source_family("growth:scan:src=lista:Editoriales"), "lista")
        self.assertEqual(xa.source_family("followers:cuenta"), "seguidores_semilla")

    def _history(self, rows):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = pathlib.Path(temp.name) / "historial.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            w = csv.writer(stream)
            w.writerow(("fecha", "cuenta", "tipo", "post_resumen", "texto_usado", "resultado", "notas"))
            w.writerows(rows)
        return path

    def test_missing_history_fails_closed_instead_of_enabling_replay(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(xa.HistoryReadError):
                xa.read_history(pathlib.Path(td) / "absent.csv")

    def test_confirmed_and_pending_are_distinct_from_known_accounts(self):
        path = self._history([
            ("2026-10-08", "@YaSeguido", "follow", "", "", "confirmado", ""),
            ("2026-10-09", "@Solicitud", "follow", "", "", "pendiente_aprobacion", ""),
            ("2026-10-09", "@Incierto", "follow", "", "", "pendiente_verificacion", ""),
            ("2026-10-09", "@Conocido", "like", "https://x.com/Conocido/status/9", "", "confirmado", ""),
            ("2026-10-09", "@Fallido", "follow", "", "", "fallo:no confirmado", ""),
        ])
        follows, posts = xa.read_history(path)
        self.assertEqual(follows, {"yaseguido", "solicitud", "incierto"})
        self.assertEqual(posts, {"9"})
        self.assertNotIn("conocido", follows)
        self.assertNotIn("fallido", follows)

    def test_conservative_filter_rejects_replayed_follow_and_post(self):
        path = self._history([
            ("2026-10-09", "@A", "follow", "", "", "confirmado", ""),
            ("2026-10-09", "@B", "like", "https://twitter.com/B/status/100", "", "pendiente_verificacion", ""),
        ])
        f, p = xa.read_history(path)
        plan = [
            {"kind": "follow", "handle": "@a", "motivo": "growth:scan:src=lista"},
            {"kind": "like", "url": "https://x.com/b/status/100?s=1", "motivo": "growth:pool:src=search:libros"},
            {"kind": "follow", "handle": "ConocidoSolo", "motivo": "growth:scan:src=lista"},
            {"kind": "like_latest", "handle": "C", "motivo": "growth:acct:src=profiles"},
        ]
        kept, counts = xa.filter_known_plan(plan, f, p)
        self.assertEqual([x["kind"] for x in kept], ["follow", "like_latest"])
        self.assertEqual(counts["lista"]["descartadas_registro"], 1)
        self.assertEqual(counts["busqueda"]["descartadas_registro"], 1)

    def test_filter_before_follow_cap_preserves_new_candidate(self):
        candidates = [
            {"kind": "follow", "handle": f"repetida{i}", "source": "profiles:autores"}
            for i in range(12)
        ] + [{"kind": "follow", "handle": "nueva", "source": "profiles:autores"}]
        previous = {f"repetida{i}" for i in range(12)}
        eligible, summary = xa.filter_known_plan(candidates, previous, set())
        plan, _ = build.build(eligible, max_follows=12)
        self.assertEqual([item["handle"] for item in plan], ["nueva"])
        self.assertEqual(summary["perfiles"]["descartadas_registro"], 12)

    def test_uncertain_latest_like_blocks_only_that_account(self):
        p = self._history([
            ("2026-10-09", "@Lectora", "like_latest", "", "",
             "pendiente_verificacion", "growth:acct:src=profiles"),
        ])
        follows, posts = xa.read_history(p)
        kept, report = xa.filter_known_plan([
            {"kind": "like_latest", "handle": "Lectora"},
            {"kind": "like_latest", "handle": "Otra"},
        ], follows, posts)
        self.assertEqual([x["handle"] for x in kept], ["Otra"])
        self.assertEqual(report["sin_fuente"]["descartadas_registro"], 1)

    def test_unverified_post_without_permalink_fails_closed(self):
        p = self._history([
            ("2026-10-09", "@Lectora", "like", "texto fragmentado", "",
             "pendiente_verificacion", ""),
        ])
        with self.assertRaises(xa.HistoryReadError):
            xa.read_history(p)

    def test_different_post_is_not_blocked_by_same_author(self):
        kept, _ = xa.filter_known_plan(
            [{"kind": "like", "url": "https://x.com/A/status/101"}],
            {"a"}, {"100"})
        self.assertEqual(len(kept), 1)

    def test_observed_source_outcomes_do_not_invent_failed_action_success(self):
        import datetime
        today = datetime.date(2026, 10, 9)
        path = self._history([
            ("2026-10-09", "@A", "follow", "", "", "confirmado",
             "growth:scan:src=perfiles"),
            ("2026-10-09", "@B", "like", "https://x.com/B/status/1", "",
             "pendiente_verificacion", "growth:pool:src=search:books"),
            ("2026-10-09", "@C", "follow", "", "", "fallo:no confirmado",
             "growth:scan:src=lista"),
            ("2026-10-08", "@D", "follow", "", "", "confirmado",
             "growth:scan:src=lista"),
        ])
        result = xa.observed_results(path, today=today)
        self.assertEqual(result, {
            "busqueda": {"confirmadas": 0, "pendientes": 1, "ya_observadas": 0},
            "perfiles": {"confirmadas": 1, "pendientes": 0, "ya_observadas": 0},
        })
        self.assertNotIn("lista", result, "sin ACK ni resultado persistido no hay conversión")

    def test_executor_records_observed_already_without_fake_confirmation(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "registro.csv"
            path.write_text(
                "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n",
                encoding="utf-8",
            )
            with mock.patch.object(executor, "REGISTRO_CSV", str(path)):
                executor._append_registro([
                    {"kind": "follow", "handle": "Lectora", "resultado": "saltado_ya_seguido",
                     "motivo": "growth:scan:src=perfiles"},
                    {"kind": "like", "url": "https://x.com/Autora/status/21",
                     "resultado": "saltado_ya_like", "motivo": "growth:pool:src=search:libros"},
                    {"kind": "like", "url": "https://x.com/Autora/status/22",
                     "resultado": "fallo:no confirmado"},
                ])
            with path.open(encoding="utf-8", newline="") as stream:
                observed = list(csv.reader(stream))
            self.assertEqual([row[5] for row in observed[1:]],
                             ["saltado_ya_seguido", "saltado_ya_like"])
            follows, posts = xa.read_history(path)
            self.assertIn("lectora", follows)
            self.assertIn("21", posts)
            self.assertNotIn("22", posts)

    def test_incomplete_csv_fails_closed_instead_of_empty_budget(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "registro.csv"
            p.write_text("fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n"
                         "2026-10-09,@A,follow,,,confirmado\n", encoding="utf-8")
            with self.assertRaises(xa.HistoryReadError):
                xa.read_history(p)
            p.write_text("fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n"
                         "2026-10-09,@A,follow,,,confirmado,ok,extra\n", encoding="utf-8")
            with self.assertRaises(xa.HistoryReadError):
                xa.read_history(p)

    def test_duplicate_header_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "registro.csv"
            p.write_text("cuenta,tipo,post_resumen,resultado,resultado\n"
                         "a,follow,,confirmado,confirmado\n", encoding="utf-8")
            with self.assertRaises(xa.HistoryReadError):
                xa.read_history(p)

    def test_uncertain_click_stops_rest_of_batch_without_retry(self):
        plan = [
            {"kind": "follow", "handle": "primera"},
            {"kind": "follow", "handle": "otra"},
        ]
        saved = []
        import repost_policy
        with optional_integration_guards(), \
             mock.patch.object(repost_policy, "guard", side_effect=lambda rows, path: rows), \
             mock.patch.object(executor.x, "beat"), \
             mock.patch.object(executor.x, "follow",
                               side_effect=executor.x.XWriteUnverified("ACK incierto")) as follow:
            results = executor.run_plan(plan, prevalidated=True, on_result=saved.append)
        self.assertEqual([r["resultado"] for r in results],
                         ["pendiente_verificacion", "no_intentado"])
        self.assertEqual([r["resultado"] for r in saved],
                         ["pendiente_verificacion", "no_intentado"])
        follow.assert_called_once()

    def test_executor_rejects_incompatible_csv_before_append(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "registro.csv"
            contents = "fecha,tipo,cuenta,resultado\n"
            path.write_text(contents, encoding="utf-8")
            with mock.patch.object(executor, "REGISTRO_CSV", str(path)):
                with self.assertRaises(ValueError):
                    executor._append_registro([
                        {"kind": "follow", "handle": "lectora", "resultado": "confirmado"}
                    ])
            self.assertEqual(path.read_text(encoding="utf-8"), contents)

    def test_writer_fsync_failure_is_not_silently_swallowed(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "registro.csv"
            path.write_text(
                "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n",
                encoding="utf-8",
            )
            with mock.patch.object(executor, "REGISTRO_CSV", str(path)), \
                 mock.patch.object(executor.os, "fsync", side_effect=OSError("disco")):
                with self.assertRaises(OSError):
                    executor._append_registro([
                        {"kind": "like", "url": "https://x.com/a/status/5",
                         "resultado": "pendiente_verificacion"}
                    ])

    def test_write_click_timeout_is_uncertain_without_retry(self):
        with self.assertRaises(executor.x.XWriteUnverified):
            executor.x._write_tap_with_uncertain_transport(
                lambda: (_ for _ in ()).throw(TimeoutError("click")), "like")

    def test_safety_warning_after_tap_keeps_possible_write(self):
        warning = executor.x.BotWarningDetected("restricción")
        with mock.patch.object(executor.x, "_check_bot_warning", side_effect=warning):
            with self.assertRaises(executor.x.BotWarningDetected) as ctx:
                executor.x._check_warning_after_tap(object())
        self.assertTrue(ctx.exception.possible_write)

    def test_uncertain_platform_warning_stops_batch_with_pending(self):
        warning = executor.x.BotWarningDetected("restricción")
        warning.possible_write = True
        plan = [{"kind": "follow", "handle": "primero"},
                {"kind": "follow", "handle": "otro"}]
        import repost_policy
        with optional_integration_guards(), \
             mock.patch.object(repost_policy, "guard", side_effect=lambda rows, path: rows), \
             mock.patch.object(executor.x, "beat"), \
             mock.patch.object(executor.x, "follow", side_effect=warning) as follow:
            results = executor.run_plan(plan, prevalidated=True)
        self.assertEqual([r["resultado"] for r in results],
                         ["pendiente_verificacion", "no_intentado"])
        follow.assert_called_once()

    def test_follow_without_ack_never_clicks_twice(self):
        process = mock.MagicMock()
        page = mock.MagicMock()
        control = mock.MagicMock()
        with mock.patch.object(executor.x, "_connect", return_value=(process, page)), \
             mock.patch.object(executor.x, "_check_bot_warning"), \
             mock.patch.object(executor.x, "_assert_active_account"), \
             mock.patch.object(executor.x, "_top_profile_follow_control",
                               return_value=control), \
             mock.patch.object(executor.x, "_profile_follow_state",
                               side_effect=["follow", "follow"]):
            with self.assertRaises(executor.x.XWriteUnverified):
                executor.x.follow("lectora")
        control.click.assert_called_once_with(force=True)
        process.stop.assert_called_once()

    def test_quote_without_ack_stops_other_actions(self):
        plan = [{"kind": "quote", "url": "https://x.com/a/status/1", "text": "Texto"},
                {"kind": "follow", "handle": "otra"}]
        import repost_policy
        with optional_integration_guards(), \
             mock.patch.object(repost_policy, "guard", side_effect=lambda rows, path: rows), \
             mock.patch.object(executor.x, "beat"), \
             mock.patch.object(executor.x, "repost", return_value=("unverified", None)), \
             mock.patch.object(executor.x, "follow") as follow:
            results = executor.run_plan(plan, prevalidated=True)
        self.assertEqual([r["resultado"] for r in results],
                         ["pendiente_verificacion", "no_intentado"])
        follow.assert_not_called()

    def test_reordered_legacy_header_is_blocked_before_write(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "registro.csv"
            p.write_text(
                "fecha,tipo,cuenta,post_resumen,texto_usado,resultado,notas\n"
                "2026-10-09,follow,@a,,,confirmado,\n", encoding="utf-8")
            with self.assertRaises(xa.HistoryReadError):
                xa.read_history(p)

    def test_observed_latest_like_is_persisted_and_suppressed(self):
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "registro.csv"
            path.write_text(
                "fecha,cuenta,tipo,post_resumen,texto_usado,resultado,notas\n",
                encoding="utf-8",
            )
            with mock.patch.object(executor, "REGISTRO_CSV", str(path)):
                executor._append_registro([
                    {"kind": "like_latest", "handle": "Autora",
                     "resultado": "saltado_ya_like"},
                ])
            followed, posts = xa.read_history(path)
            kept, _ = xa.filter_known_plan(
                [{"kind": "like_latest", "handle": "autora"}], followed, posts)
            self.assertEqual(kept, [])
            self.assertEqual(
                xa.observed_results(path)["sin_fuente"]["ya_observadas"], 1)

    def test_legacy_fragment_like_blocks_latest_for_same_account(self):
        path = self._history([
            ("2026-10-09", "@autora", "like", "Fragmento antiguo", "",
             "confirmado", ""),
        ])
        followed, posts = xa.read_history(path)
        kept, _ = xa.filter_known_plan(
            [{"kind": "like_latest", "handle": "autora"}], followed, posts)
        self.assertEqual(kept, [])

    def test_pool_never_marks_unattempted_as_failed(self):
        self.assertIsNone(executor._pool_post_status("no_intentado"))
        self.assertIsNone(executor._pool_post_status("saltado_like_contexto"))
        self.assertIsNone(executor._pool_post_status("fallo:pre_tap"))
        self.assertEqual(executor._pool_post_status("pendiente_verificacion"), "uncertain")
        self.assertEqual(executor._pool_post_status("saltado_ya_like"), "done")

    def test_global_ledger_contract_for_other_networks_unchanged(self):
        import action_ledger
        self.assertEqual(action_ledger.outcome_to_status("saltado_ya_like"),
                         action_ledger.CONFIRMED)
        self.assertEqual(action_ledger.outcome_to_status("pendiente_verificacion"),
                         action_ledger.UNCERTAIN)

    def test_builder_preserves_previous_contract_when_no_source(self):
        plan, replies = build.build([
            {"kind": "follow", "handle": "una"},
            {"kind": "like", "url": "https://x.com/otra/status/1"},
        ])
        self.assertEqual(plan, [{"kind": "follow", "handle": "una"}])      # sin auto-like
        self.assertEqual(replies, [])

    def test_builder_records_only_source_family_not_raw_query(self):
        plan, _ = build.build([
            {"kind": "follow", "handle": "autora", "source": "profiles:nombre muy personal"},
            {"kind": "follow", "handle": "lectora", "source": "search:tema no divulgar"},
        ])
        self.assertEqual(plan[0]["motivo"], "growth:scan:src=perfiles")
        self.assertEqual(plan[1]["motivo"], "growth:scan:src=busqueda")
        self.assertNotIn("no divulgar", str(plan))
