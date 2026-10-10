"""Contrato PR75: offline, portable, sin acceso a APIs, perfiles ni sesiones."""
import contextlib
import io
import json
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import offload_study as study


class StudyTests(unittest.TestCase):
    def test_matrix_all_nine_networks_plus_cpu(self):
        seen = {t.network for t in study.TASKS}
        self.assertTrue({"bluesky", "mastodon", "x", "threads", "facebook", "pinterest",
                         "reddit", "tiktok", "instagram", "multi"} <= seen)
        self.assertEqual(len(study.TASKS), len({(t.name, t.network) for t in study.TASKS}))

    def test_only_synthetic_cpu_public_safe(self):
        approved = [task for task in study.TASKS if study.assess(task)["piloto_publico_seguro"]]
        self.assertEqual([t.name for t in approved], ["analisis_anonimizado"])

    def test_api_does_not_mean_remote_permission(self):
        for task in study.TASKS:
            if task.resource == "api":
                self.assertFalse(study.assess(task)["piloto_publico_seguro"])
                self.assertIn("credenciales", study.assess(task)["bloqueos"])

    def test_each_local_resource_is_blocked(self):
        for task in study.TASKS:
            if task.resource in ("edge", "android"):
                self.assertIn("sesion_local", study.assess(task)["bloqueos"])

    def test_new_cpu_task_requires_explicit_audit(self):
        t = study.Task("nueva_tarea", "bluesky", "cpu")
        assessment = study.assess(t)
        self.assertFalse(assessment["piloto_publico_seguro"])
        self.assertIn("tarea_no_auditada", assessment["bloqueos"])
        unknown = study.Task("otro", "multi", "desconocido")
        self.assertIn("recurso_desconocido", study.assess(unknown)["bloqueos"])

    def test_credentialless_mutation_cannot_be_public(self):
        t = study.Task("sim", "bluesky", "cpu", remote_write=True)
        self.assertFalse(study.assess(t)["piloto_publico_seguro"])

    def test_credentialless_shared_state_cannot_be_public(self):
        t = study.Task("sim", "bluesky", "cpu", shared_state=True)
        self.assertFalse(study.assess(t)["piloto_publico_seguro"])

    def test_personal_data_blocks_even_without_credentials(self):
        t = study.Task("sim", "bluesky", "cpu", personal_data=True)
        self.assertFalse(study.assess(t)["piloto_publico_seguro"])

    def test_fixed_workload_reproducible(self):
        self.assertEqual(study.synthetic_hash_work(100), study.synthetic_hash_work(100))
        self.assertNotEqual(study.synthetic_hash_work(100), study.synthetic_hash_work(101))

    def test_absent_remote_assumptions_are_null_not_zero(self):
        r = study.benchmark(items=100, samples=1)
        self.assertIsNone(r["remoto_modelado_no_medido"]["latencia_ms_proyectada"])
        self.assertIsNone(r["remoto_modelado_no_medido"]["coste_usd_proyectado"])
        self.assertFalse(r["ejecucion_remota_realizada"])
        self.assertIsNone(r["local_medido"]["rss_sistema_medido"])

    def test_complete_projection_marked_assumed_not_measured(self):
        r = study.benchmark(samples=1, items=100, startup_ms=50, rtt_ms=20,
                            payload_kib=1, response_kib=2, uplink_mbps=10,
                            downlink_mbps=20, queue_ms=15, speedup=2,
                            remote_usd_per_min=0.1)
        rem = r["remoto_modelado_no_medido"]
        self.assertTrue(rem["supuestos_completos"])
        self.assertGreater(rem["latencia_ms_proyectada"], 70)
        self.assertGreater(rem["coste_usd_proyectado"], 0)
        self.assertFalse(r["ejecucion_remota_realizada"])

    def test_missing_one_assumption_prevents_prediction(self):
        r = study.benchmark(samples=1, items=100, startup_ms=0, rtt_ms=0,
                            payload_kib=0, uplink_mbps=10)
        self.assertIsNone(r["remoto_modelado_no_medido"]["latencia_ms_proyectada"])

    def test_zero_cost_requires_explicit_zero_price(self):
        r = study.benchmark(items=100, samples=1, startup_ms=0, rtt_ms=0,
                            payload_kib=0, response_kib=0, uplink_mbps=10,
                            downlink_mbps=10, queue_ms=0, speedup=1,
                            remote_usd_per_min=0)
        self.assertEqual(r["remoto_modelado_no_medido"]["coste_usd_proyectado"], 0)

    def test_power_without_tariff_returns_null(self):
        r = study.benchmark(items=100, samples=1, local_watts=100)
        self.assertIsNone(r["local_medido"]["coste_eur_estimado"])

    def test_local_cost_is_explicit_assumption(self):
        r = study.benchmark(items=100, samples=1, local_watts=100,
                            local_eur_per_kwh=0.20)
        self.assertIsNotNone(r["local_medido"]["coste_eur_estimado"])

    def test_bad_types_nan_and_infinity_rejected(self):
        for invalid in (-1, float("nan"), float("inf"), True):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(ValueError):
                    study.benchmark(items=100, samples=1, speedup=invalid)

    def test_bounded_workload(self):
        for items in (0, 99, 20001, False, 1.5):
            with self.assertRaises(ValueError):
                study.benchmark(items=items, samples=1)
        for samples in (0, 51, True, 1.1):
            with self.assertRaises(ValueError):
                study.benchmark(items=100, samples=samples)

    def test_json_has_no_handles_or_secret_fields(self):
        data = json.dumps(study.benchmark(items=100, samples=1))
        for sensitive in ("cookie", "token", "account_id", "post_uri", "password", "session_id"):
            self.assertNotIn(sensitive, data.lower())

    def test_main_prints_safe_json(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(study.main(["--items", "100", "--samples", "1"]), 0)
        doc = json.loads(stdout.getvalue())
        self.assertFalse(doc["ejecucion_remota_realizada"])

    def test_main_invalid_cli_fails_before_network(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as e:
                study.main(["--items", "0"])
        self.assertEqual(e.exception.code, 2)

    def test_p95_requires_sufficient_samples(self):
        short = study.benchmark(items=100, samples=19)
        enough = study.benchmark(items=100, samples=20)
        self.assertIsNone(short["local_medido"]["wall_p95_ms"])
        self.assertFalse(short["local_medido"]["p95_muestra_suficiente"])
        self.assertIsNotNone(enough["local_medido"]["wall_p95_ms"])
        self.assertTrue(enough["local_medido"]["p95_muestra_suficiente"])

    def test_existing_tracemalloc_is_not_stopped_or_reset(self):
        import tracemalloc
        tracemalloc.start()
        try:
            before = tracemalloc.is_tracing()
            data = study.benchmark(items=100, samples=1)
            self.assertTrue(before)
            self.assertTrue(tracemalloc.is_tracing())
            self.assertIsNone(data["local_medido"]["pico_asignaciones_python_kib"])
            self.assertTrue(data["local_medido"]["pico_no_disponible_por_tracer_externo"])
        finally:
            tracemalloc.stop()

    def test_model_needs_queue_and_downlink_and_response(self):
        base = dict(startup_ms=0, queue_ms=0, rtt_ms=0,
                    payload_kib=0, response_kib=0, uplink_mbps=10,
                    downlink_mbps=10, speedup=1)
        for missing in ("queue_ms", "response_kib", "downlink_mbps"):
            one = dict(base)
            del one[missing]
            r = study.benchmark(items=100, samples=1, **one)
            self.assertIsNone(r["remoto_modelado_no_medido"]["latencia_ms_proyectada"])

    def test_asymmetric_link_and_queue_affect_projection(self):
        base = dict(startup_ms=50, queue_ms=30, rtt_ms=20,
                    payload_kib=10, response_kib=20,
                    uplink_mbps=10, downlink_mbps=10, speedup=2)
        slow = study.benchmark(items=100, samples=1, **base)
        faster = dict(base, downlink_mbps=100, queue_ms=0)
        fast = study.benchmark(items=100, samples=1, **faster)
        self.assertGreater(slow["remoto_modelado_no_medido"]["latencia_ms_proyectada"],
                           fast["remoto_modelado_no_medido"]["latencia_ms_proyectada"])

    def test_external_tracer_cannot_produce_remote_estimates(self):
        import tracemalloc
        tracemalloc.start()
        try:
            result = study.benchmark(items=100, samples=1,
                                     startup_ms=0, queue_ms=0, rtt_ms=0,
                                     payload_kib=0, response_kib=0,
                                     uplink_mbps=10, downlink_mbps=10,
                                     speedup=1, local_watts=80,
                                     local_eur_per_kwh=0.2)
            self.assertIsNone(result["remoto_modelado_no_medido"]["latencia_ms_proyectada"])
            self.assertIsNone(result["local_medido"]["coste_eur_estimado"])
            self.assertTrue(tracemalloc.is_tracing())
        finally:
            tracemalloc.stop()

    def test_approval_metadata_does_not_authorize_real_activities(self):
        example = study.assess(study.TASKS[-1])
        self.assertTrue(example["piloto_publico_seguro"])
        self.assertTrue(example["evaluacion_solo_estatica"])
        self.assertFalse(example["uso_publico_autorizado"])

    def test_extreme_values_fail_closed_without_nan_inf(self):
        with self.assertRaisesRegex(ValueError, "numero invalido"):
            study.benchmark(items=100, samples=1, speedup=10 ** 1000)
        with self.assertRaisesRegex(ValueError, "latencia_modelada_no_finita"):
            study.benchmark(items=100, samples=1, startup_ms=0, queue_ms=0,
                            rtt_ms=0, payload_kib=1000, response_kib=1000,
                            uplink_mbps=5e-324, downlink_mbps=5e-324, speedup=1)

    def test_no_network_or_file_i_o_in_benchmark(self):
        with mock.patch("builtins.open", side_effect=AssertionError("file access")), \
             mock.patch("socket.socket", side_effect=AssertionError("network")):
            r = study.benchmark(items=100, samples=1)
        self.assertFalse(r["ejecucion_remota_realizada"])


if __name__ == "__main__":
    unittest.main()
