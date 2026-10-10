"""PR #75: estudio OFFLINE de portabilidad y coste computacional.

No lee .env, colas, cuentas, CSV, perfiles, sesiones, procesos ni red. Los datos
son sinteticos. Una proyeccion nunca se etiqueta como medida de la nube.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import time
import tracemalloc
from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    name: str
    network: str
    resource: str
    credentials: bool = False
    personal_data: bool = False
    remote_write: bool = False
    shared_state: bool = False


# Fuente: mechanical_round.PIPELINES, round_queue.WEB/API/PHONE,
# chatgpt_consult, mobile_runtime, reddit_publish y content_publisher.
# Clasifica la ejecucion real, NO las capacidades teoricas de una plataforma.
TASKS = (
    Task("ronda_api", "bluesky", "api", True, True, True, True),
    Task("ronda_api", "mastodon", "api", True, True, True, True),
    Task("ronda_edge", "x", "edge", True, True, True, True),
    Task("ronda_edge", "threads", "edge", True, True, True, True),
    Task("ronda_edge", "facebook", "edge", True, True, True, True),
    Task("ronda_edge", "pinterest", "edge", True, True, True, True),
    Task("publicacion_reddit", "reddit", "edge", True, True, True, True),
    Task("ronda_android", "tiktok", "android", True, True, True, True),
    Task("ronda_android", "instagram", "android", True, True, True, True),
    Task("publicacion_api", "facebook", "api", True, True, True, True),
    Task("publicacion_api", "instagram", "api", True, True, True, True),
    Task("redaccion_chatgpt", "multi", "edge", True, True, True, True),
    Task("analisis_anonimizado", "multi", "cpu", False, False, False, False),
)


# Un tipo nuevo no obtiene acceso publico solo por omitir campos de riesgo.
# Cada piloto debe ser auditado y agregado explicitamente a esta lista.
APPROVED_PUBLIC_PILOTS = frozenset({("analisis_anonimizado", "multi", "cpu")})


def assess(task: Task) -> dict:
    """Autorizacion conservadora SOLO para pruebas en runner publico sin datos."""
    blockers = []
    if (task.name, task.network, task.resource) not in APPROVED_PUBLIC_PILOTS:
        blockers.append("tarea_no_auditada")
    if task.resource not in ("edge", "android", "api", "cpu"):
        blockers.append("recurso_desconocido")
    if task.resource in ("edge", "android"):
        blockers.append("sesion_local")
    if task.credentials:
        blockers.append("credenciales")
    if task.personal_data:
        blockers.append("datos_de_terceros")
    if task.remote_write:
        blockers.append("efecto_remoto")
    if task.shared_state:
        blockers.append("estado_compartido_o_ack")
    return {
        "red": task.network,
        "tarea": task.name,
        "recurso": task.resource,
        "piloto_publico_seguro": not blockers,
        "bloqueos": blockers,
        "produccion_remota_autorizada": False,
        "evaluacion_solo_estatica": True,
        "uso_publico_autorizado": False,
    }


def synthetic_hash_work(items: int) -> str:
    """Carga CPU pura y reproducible: no admite documentos ni entradas externas."""
    acc = b"rrss-pr75-offline-v1"
    for idx in range(items):
        acc = hashlib.sha256(acc + idx.to_bytes(4, "big")).digest()
    return acc.hex()


def _positive(value, label, *, maximum=None, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}: numero invalido")
    try:
        finite = math.isfinite(value)
    except OverflowError as exc:
        raise ValueError(f"{label}: numero invalido") from exc
    if not finite:
        raise ValueError(f"{label}: numero invalido")
    if value < 0 or (value == 0 and not allow_zero) or (maximum is not None and value > maximum):
        raise ValueError(f"{label}: fuera de rango")
    return value


def benchmark(*, samples=3, items=2000, startup_ms=None, queue_ms=None,
              rtt_ms=None, payload_kib=None, response_kib=None,
              uplink_mbps=None, downlink_mbps=None, speedup=None,
              remote_usd_per_min=None, local_watts=None, local_eur_per_kwh=None) -> dict:
    if type(samples) is not int or not 1 <= samples <= 50:
        raise ValueError("samples: 1..50")
    if type(items) is not int or not 100 <= items <= 20000:
        raise ValueError("items: 100..20000")
    optional = {
        "startup_ms": (startup_ms, 3600000, True),
        "queue_ms": (queue_ms, 3600000, True),
        "rtt_ms": (rtt_ms, 3600000, True),
        "payload_kib": (payload_kib, 1048576, True),
        "response_kib": (response_kib, 1048576, True),
        "uplink_mbps": (uplink_mbps, 100000, False),
        "downlink_mbps": (downlink_mbps, 100000, False),
        "speedup": (speedup, 1000, False),
        "remote_usd_per_min": (remote_usd_per_min, 1000, True),
        "local_watts": (local_watts, 100000, False),
        "local_eur_per_kwh": (local_eur_per_kwh, 100, True),
    }
    for key, (value, maximum, allow_zero) in optional.items():
        if value is not None:
            _positive(value, key, maximum=maximum, allow_zero=allow_zero)
    # Calentamiento fuera del cronometro, para comparar una carga ya importada.
    expected = synthetic_hash_work(items)
    durations, cpu = [], []
    for _ in range(samples):
        start_wall, start_cpu = time.perf_counter_ns(), time.process_time_ns()
        digest = synthetic_hash_work(items)
        wall_ns = time.perf_counter_ns() - start_wall
        cpu_ns = time.process_time_ns() - start_cpu
        if digest != expected:
            raise RuntimeError("resultado_sintetico_inestable")
        durations.append(wall_ns / 1e6)
        cpu.append(cpu_ns / 1e6)

    # Medir asignaciones DESPUES de los tiempos. No perturbar un tracer previo
    # de pytest, otro modulo o del interprete; en ese caso no hay pico aislado.
    peak_kib = None
    tracing_external = tracemalloc.is_tracing()
    if not tracing_external:
        tracemalloc.start()
        try:
            if synthetic_hash_work(items) != expected:
                raise RuntimeError("resultado_sintetico_inestable")
            _, peak = tracemalloc.get_traced_memory()
            peak_kib = round(peak / 1024, 3)
        finally:
            tracemalloc.stop()

    wall_median = statistics.median(durations)
    cpu_median = statistics.median(cpu)
    # Una sola muestra o n reducido NO autoriza a presentar p95 fiable.
    p95 = statistics.quantiles(durations, n=100, method="inclusive")[94] if samples >= 20 else None
    cpu_p95 = statistics.quantiles(cpu, n=100, method="inclusive")[94] if samples >= 20 else None
    # Hipotesis remota: cola/arranque, ida y vuelta, CPU hipotetica. La
    # transferencia usa velocidades y tamanos separados por direccion.
    needed = (startup_ms, queue_ms, rtt_ms, payload_kib, response_kib,
              uplink_mbps, downlink_mbps, speedup)
    # Un tracer externo distorsiona la CPU; no convertirla en coste remoto.
    assumed = not tracing_external and all(v is not None for v in needed)
    transfer_ms = ((payload_kib * 1024 * 8 / (uplink_mbps * 1e6)
                    + response_kib * 1024 * 8 / (downlink_mbps * 1e6)) * 1000) if assumed else None
    projected = (startup_ms + queue_ms + rtt_ms + transfer_ms + cpu_median / speedup) if assumed else None
    if projected is not None and not math.isfinite(projected):
        raise ValueError("latencia_modelada_no_finita")
    remote_usd = (projected / 60000 * remote_usd_per_min
                  if projected is not None and remote_usd_per_min is not None else None)
    if remote_usd is not None and not math.isfinite(remote_usd):
        raise ValueError("coste_modelado_no_finito")
    local_eur = (wall_median / 3600000 * local_watts / 1000 * local_eur_per_kwh
                 if (not tracing_external and local_watts is not None
                     and local_eur_per_kwh is not None) else None)
    return {
        "tipo": "estudio_offline_sintetico_sin_credenciales",
        "ejecucion_remota_realizada": False,
        "muestra": {"iteraciones": samples, "elementos_sinteticos": items},
        "local_medido": {"wall_mediana_ms": round(wall_median, 3),
                         "wall_p95_ms": round(p95, 3) if p95 is not None else None,
                         "cpu_mediana_ms": round(cpu_median, 3),
                         "cpu_p95_ms": round(cpu_p95, 3) if cpu_p95 is not None else None,
                         "p95_muestra_suficiente": samples >= 20,
                         "tarea_demasiado_corta_para_comparar_infraestructuras": wall_median < 10,
                         "tiempos_sin_tracemalloc": not tracing_external,
                         "pico_asignaciones_python_kib": peak_kib,
                         "pico_no_disponible_por_tracer_externo": tracing_external,
                         "rss_sistema_medido": None, "coste_eur_estimado":
                         round(local_eur, 8) if local_eur is not None else None},
        "remoto_modelado_no_medido": {
            "latencia_ms_proyectada": round(projected, 3) if projected is not None else None,
            "coste_usd_proyectado": round(remote_usd, 8) if remote_usd is not None else None,
            "memoria_ram_remota": None,
            "coste_presupone_facturacion_wall_time": remote_usd is not None,
            "supuestos_completos": assumed,
            "supuestos": {k: value for k, (value, _max, _zero) in optional.items()},
        },
        "matriz": [assess(task) for task in TASKS],
        "aviso": "Solo laboratorio: ni permiso para ejecutar redes ni prueba de ahorro real.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="PR75: benchmark offline sintético; nunca red ni .env")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--items", type=int, default=2000)
    for name in ("startup-ms", "queue-ms", "rtt-ms", "payload-kib", "response-kib",
                 "uplink-mbps", "downlink-mbps", "speedup", "remote-usd-per-min",
                 "local-watts", "local-eur-per-kwh"):
        parser.add_argument("--" + name, type=float)
    args = vars(parser.parse_args(argv))
    try:
        print(json.dumps(benchmark(**{k.replace("-", "_"): v for k, v in args.items()}),
                         ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    except (ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
