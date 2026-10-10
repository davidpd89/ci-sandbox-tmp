"""Inventario verificable de capacidades observadas por red (PR #47 y #43).

No ejecuta ninguna acción externa ni consulta cuentas. Lee únicamente las
declaraciones de los orquestadores y los adaptadores Python existentes.

Tres estados a distinguir:
* wired: hay módulo/adaptador Y está conectado al pipeline automático.
* available_not_wired: código común existe pero no está programado en esta red.
* missing: no existe adaptador; NO significa que la plataforma lo prohíba.

La existencia de un adaptador no garantiza que la interfaz siga funcionando.
Los tests de contrato operativos pertenecen a #73.
"""
from __future__ import annotations

import argparse
import json

NETWORKS = (
    "bluesky", "mastodon", "x", "threads",
    "facebook", "instagram", "pinterest", "reddit", "tiktok",
)
FEATURES = (
    "pipeline", "unfollow_adapter", "unfollow_scheduled",
    "inbound_harvest", "loyalty_scheduled", "gpt_writer_scheduled",
)

def _commands(steps):
    """Extrae scripts de pre/post sin ejecutarlos."""
    for entry in steps or ():
        if isinstance(entry, (list, tuple)):
            yield tuple(str(piece).replace("\\", "/") for piece in entry)


def _scheduled(pipeline, filename, network=None, *, sections=("pre", "post")):
    for section in sections:
        for argv in _commands(pipeline.get(section)):
            if any(v.endswith("/" + filename) or v == filename for v in argv):
                if network is None or network in argv:
                    return True
    return False


def build_matrix(*, pipelines=None, cleanup_adapters=None, harvesters=None):
    """Matriz de capacidades observadas; inyectable para tests offline."""
    if pipelines is None:
        from mechanical_round import PIPELINES
        pipelines = PIPELINES
    if cleanup_adapters is None:
        from unfollow_cleanup import ADAPTERS
        cleanup_adapters = ADAPTERS
    if harvesters is None:
        from loyalty import HARVEST
        harvesters = HARVEST

    out = {}
    for net in NETWORKS:
        pipe = pipelines.get(net) or {}
        has_adapter = net in cleanup_adapters
        has_harvest = net in harvesters
        unfollow_job = _scheduled(pipe, "unfollow_cleanup.py", net)
        loyalty_job = _scheduled(pipe, "loyalty.py", net)
        writer_job = any(
            _scheduled(pipe, filename, sections=("pre",))
            for filename in ("reply_writer.py", "api_comment_writer.py", "tiktok_comment_writer.py")
        )
        out[net] = {
            "pipeline": bool(pipe),
            "unfollow_adapter": has_adapter,
            "unfollow_scheduled": unfollow_job if has_adapter else False,
            "inbound_harvest": has_harvest,
            "loyalty_scheduled": loyalty_job if has_harvest else False,
            "gpt_writer_scheduled": writer_job,
        }
    return out


def gaps(matrix):
    """Hallazgos de cobertura, nunca afirmaciones sobre límites de una plataforma."""
    out = {}
    for net, caps in matrix.items():
        problems = []
        if not caps["pipeline"]:
            problems.append("pipeline no identificado")
        if not caps["unfollow_adapter"]:
            problems.append("adaptador de unfollow no implementado")
        elif not caps["unfollow_scheduled"]:
            problems.append("adaptador de unfollow sin paso automático")
        if not caps["inbound_harvest"]:
            problems.append("cosecha de inbound no implementada en loyalty.HARVEST")
        elif not caps["loyalty_scheduled"]:
            problems.append("cosecha inbound sin paso en el pipeline")
        if not caps["gpt_writer_scheduled"]:
            problems.append("escritor GPT no programado en pre; revisar rutas alternativas")
        out[net] = problems
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    matrix = build_matrix()
    if args.json:
        print(json.dumps({"capabilities": matrix, "gaps": gaps(matrix)}, ensure_ascii=False, indent=2))
    else:
        print("MATRIZ REAL (conexión en el pipeline; no prueba ejecución remota)")
        for net, caps in matrix.items():
            missing = gaps(matrix)[net]
            print(f"{net:10} | " + ", ".join(
                f"{name}={'sí' if enabled else 'no'}" for name, enabled in caps.items()
            ))
            if missing:
                print(" " * 13 + "Pendientes: " + "; ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
