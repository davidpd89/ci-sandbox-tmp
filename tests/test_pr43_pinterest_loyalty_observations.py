"""Pruebas sin red ni fuentes personales para el adaptador Pinterest PR43."""
import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
from pinterest_loyalty_observations import build_report


def snapshot(*users, date="2026-10-09T12:00:00+02:00", account="mi-cuenta", token=True):
    return {
        "fuente": "GET /user_account/followers", "permiso_verificado": token,
        "observado_en": date, "cuenta_id": account,
        "paginas": [{"solicitado_con_bookmark": None,
                     "respuesta": {"items": [{"username": u, "type": "user"} for u in users],
                                   "bookmark": None}}],
    }


class PinterestReadOnlyLoyaltyTests(unittest.TestCase):
    def test_missing_source_is_unknown_not_zero(self):
        result = build_report()
        self.assertEqual(result["estado_seguidores"], "no_aportado")
        self.assertIsNone(result["identificadores_visibles"])
        self.assertIsNone(result["reciprocidad_atribuida"])

    def test_verified_empty_list_is_a_real_zero_not_unknown(self):
        result = build_report(snapshot())
        self.assertEqual(result["identificadores_visibles"], 0)
        self.assertEqual(result["estado_comparacion"], "anterior_no_aportado")

    def test_denied_scope_does_not_get_a_follower_count(self):
        result = build_report(snapshot("ana", token=False))
        self.assertEqual(result["estado_seguidores"], "permiso_no_verificado")
        self.assertIsNone(result["identificadores_visibles"])

    def test_two_complete_snapshots_only_report_visible_difference(self):
        previous = snapshot("ana", "beto", date="2026-10-08T11:00:00Z")
        current = snapshot("ANA", "carla")
        result = build_report(current, previous)
        self.assertEqual(result["estado_comparacion"], "snapshots_completos")
        self.assertEqual(result["identificadores_visibles"], 2)
        self.assertEqual(result["identificadores_antes_no_visibles"], 1)
        self.assertEqual(result["identificadores_que_ya_no_aparecen"], 1)
        self.assertIsNone(result["reciprocidad_atribuida"])
        self.assertNotIn("carla", str(result))
        self.assertNotIn("beto", str(result))

    def test_cursor_chain_prevents_missing_pages(self):
        source = snapshot("ana")
        source["paginas"][0]["respuesta"]["bookmark"] = "cursor-2"
        self.assertEqual(build_report(source)["estado_seguidores"], "paginacion_incompleta")
        source["paginas"].append({
            "solicitado_con_bookmark": "cursor-2",
            "respuesta": {"items": [{"username": "beto", "type": "user"}], "bookmark": None},
        })
        self.assertEqual(build_report(source)["identificadores_visibles"], 2)
        source["paginas"][1]["solicitado_con_bookmark"] = "cursor-otro"
        self.assertEqual(build_report(source)["estado_seguidores"], "paginacion_invalida")

    def test_repeated_cursor_denied(self):
        source = snapshot("ana")
        source["paginas"][0]["respuesta"]["bookmark"] = "cursor-2"
        source["paginas"].append({"solicitado_con_bookmark": "cursor-2",
                                  "respuesta": {"items": [], "bookmark": "cursor-2"}})
        self.assertEqual(build_report(source)["estado_seguidores"], "paginacion_invalida")

    def test_cross_account_never_counts_apparent_follows(self):
        old = snapshot("a", account="otra", date="2026-10-08T11:00:00Z")
        new = snapshot("a", "b")
        self.assertEqual(build_report(new, old)["estado_comparacion"], "cuenta_o_orden_no_verificado")
        self.assertIsNone(build_report(new, old)["identificadores_antes_no_visibles"])

    def test_wrong_chronology_and_naive_time_are_rejected(self):
        now = dt.datetime.now(dt.timezone.utc)
        old = snapshot("a", date=(now - dt.timedelta(minutes=10)).isoformat())
        current = snapshot("a", date=(now - dt.timedelta(minutes=30)).isoformat())
        self.assertEqual(build_report(current, old)["estado_comparacion"], "cuenta_o_orden_no_verificado")
        source = snapshot("a", date="2026-10-09T10:00:00")
        self.assertEqual(build_report(source)["estado_seguidores"], "formato_invalido")

    def test_future_snapshot_and_api_error_never_invent_a_follower_count(self):
        source = snapshot("ana", date=(dt.datetime.now(dt.timezone.utc)
                                       + dt.timedelta(hours=1)).isoformat())
        self.assertEqual(build_report(source)["estado_seguidores"], "fecha_futura")
        self.assertIsNone(build_report(source)["identificadores_visibles"])
        bad = snapshot("ana")
        bad["paginas"][0]["respuesta"]["error"] = "API permission denied"
        self.assertEqual(build_report(bad)["estado_seguidores"], "formato_invalido")

    def test_invalid_rows_are_not_partially_counted(self):
        src = snapshot("ana")
        src["paginas"][0]["respuesta"]["items"].append({"username": ""})
        self.assertEqual(build_report(src)["estado_seguidores"], "formato_invalido")

    def test_duplicate_usernames_are_one_observed_id(self):
        self.assertEqual(build_report(snapshot("ana", "ANA"))["identificadores_visibles"], 1)

    def test_second_page_repeating_previous_page_is_not_reliable(self):
        current = snapshot("ana")
        current["paginas"][0]["respuesta"]["bookmark"] = "b2"
        current["paginas"].append({
            "solicitado_con_bookmark": "b2",
            "respuesta": {"items": [{"username": "ANA", "type": "user"}],
                          "bookmark": None},
        })
        result = build_report(current)
        self.assertEqual(result["estado_seguidores"], "paginacion_inestable")
        self.assertIsNone(result["identificadores_visibles"])

    def test_unsupported_type_or_missing_type_is_not_counted(self):
        current = snapshot("ana")
        current["paginas"][0]["respuesta"]["items"][0].pop("type")
        self.assertEqual(build_report(current)["estado_seguidores"], "formato_invalido")
        current["paginas"][0]["respuesta"]["items"][0]["type"] = "board"
        self.assertEqual(build_report(current)["estado_seguidores"], "formato_invalido")

    def test_freshness_and_observation_dates_are_always_explicit(self):
        clock = dt.datetime(2026, 10, 9, 13, tzinfo=dt.timezone.utc)
        recent = snapshot("ana", date="2026-10-09T12:00:00Z")
        prior = snapshot("beto", date="2026-10-08T11:00:00Z")
        result = build_report(recent, prior, now=clock)
        self.assertEqual(result["vigencia"], "reciente")
        self.assertFalse(result["instantanea_atomica"])
        self.assertEqual(result["fecha_observacion_utc"], "2026-10-09T12:00:00+00:00")
        self.assertEqual(result["fecha_anterior_utc"], "2026-10-08T11:00:00+00:00")
        self.assertEqual(result["fuente_permisos"],
                         "declarados_por_el_productor_no_autenticados")
        old = build_report(recent, now=clock + dt.timedelta(days=4))
        self.assertEqual(old["vigencia"], "historica")
        self.assertEqual(old["identificadores_visibles"], 1)

    def test_injected_clock_boundaries_and_invalid_clock(self):
        clock = dt.datetime(2026, 10, 9, 12, tzinfo=dt.timezone.utc)
        recent = snapshot("ana", date="2026-10-09T12:04:59Z")
        self.assertEqual(build_report(recent, now=clock)["estado_seguidores"],
                         "observado")
        self.assertEqual(build_report(recent, now=clock)["vigencia"],
                         "desfase_adelantado")
        future = snapshot("ana", date="2026-10-09T12:05:01Z")
        self.assertEqual(build_report(future, now=clock)["estado_seguidores"],
                         "fecha_futura")
        with self.assertRaises(ValueError):
            build_report(recent, now=dt.datetime(2026, 10, 9, 12))
        with self.assertRaises(ValueError):
            build_report(recent, now=0)
        with self.assertRaises(ValueError):
            build_report(recent, now=clock, max_age_hours=0)
        with self.assertRaises(ValueError):
            build_report(recent, now=clock, max_age_hours=True)

    def test_oversized_bookmark_is_invalid_not_exported(self):
        current = snapshot("ana")
        current["paginas"][0]["respuesta"]["bookmark"] = "s" * 3000
        result = build_report(current)
        self.assertEqual(result["estado_seguidores"], "formato_invalido")
        self.assertNotIn("s" * 20, str(result))

    def test_analytics_or_outbound_data_not_masqueraded_as_inbound(self):
        result = build_report(snapshot("ana"))
        for key in ("likes_entrantes_identificados", "comentarios_entrantes_identificados",
                    "guardados_entrantes_identificados", "reciprocidad_atribuida", "visitas_atribuidas"):
            self.assertIsNone(result[key])


if __name__ == "__main__":
    unittest.main()
