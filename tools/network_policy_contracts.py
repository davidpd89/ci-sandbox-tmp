"""PR #73: inventario de rutas de ejecucion que deben aplicar la politica comun.

Solo metadatos de contrato; NO crea reglas de negocio ni ejecuta acciones.
Las capacidades reales y el calendario siguen en network_capabilities (PR #47).
Una ruta se certifica en tests mediante llamada a la funcion real y guardia
inyectada, no buscando nombres en el codigo fuente.
"""
from __future__ import annotations

from dataclasses import dataclass

from network_capabilities import NETWORKS


@dataclass(frozen=True)
class Route:
    network: str
    module: str
    entrypoint: str
    text_guard: str = "reply_writer.require_gpt"
    mode: str = "execute"


# Dos rutas TikTok: Python/Playwright heredada y movil Android; Pinterest no
# usa pinterest_execute.py para reaccionar/comentar, sino pinterest_growth.cmd_run.
# Reddit tambien dispone de rutas externas a reddit_execute (ver deuda auditada).
TEXT_EXECUTION_ROUTES = (
    Route("bluesky", "bluesky_execute", "run_plan"),
    Route("mastodon", "mastodon_execute", "run_plan"),
    Route("x", "x_execute", "run_plan"),
    Route("threads", "threads_execute", "run_plan"),
    Route("facebook", "facebook_execute", "run_plan"),
    Route("pinterest", "pinterest_growth", "cmd_run"),
    Route("reddit", "reddit_execute", "run_plan"),
    Route("tiktok", "tiktok_mobile_execute", "run_plan", mode="android"),
    Route("tiktok", "tiktok_execute", "run_plan", mode="legacy_web"),
)

# No declarar que la plataforma carece de capacidad. Un estado "pendiente" es
# exclusivamente una laguna de cobertura del codigo de este repositorio.
# "guarded" significa guardia identificada en código, NO prueba remota ni
# evaluación integral de afinidad editorial. Varias disponen de tests de #81.
GUARDED_DIRECT_WRITERS = (
    ("threads", "threads_api.publish_reply", "prueba #79, objetivo remoto y ledger SQLite con reserva atomica"),
    ("reddit", "reddit_comments.reply_in_thread", "prueba #79 antes del DOM"),
    ("x", "x_interact.like", "contexto leído del artículo antes del click"),
    ("x", "x_interact.like_latest", "contexto leído del artículo antes del click"),
    ("threads", "threads_interact.like_post", "contexto del post abierto por permalink"),
    ("threads", "threads_interact.like_latest", "contexto del post visible"),
    ("reddit", "reddit_interact.vote", "contexto del post exacto en el DOM"),
    ("tiktok", "tiktok_mobile_interact.TikTokMobileAdapter.like", "contexto del vídeo Android"),
)

UNCOVERED_DIRECT_WRITERS = (
    ("bluesky", "bluesky_interact.like", "crea reacción sin contexto en la función inferior"),
    ("mastodon", "mastodon_interact.favourite", "POST sin guardia en la función inferior"),
    ("facebook", "facebook_interact.like_external", "like ajeno sin comprobación temática inferior"),
    ("facebook", "facebook_interact.comment_external", "escritura textual directa sin certificado #79 inferior"),
    ("pinterest", "pinterest_growth.react", "reacción directa sin guardia de contenido"),
    ("pinterest", "pinterest_growth.comment", "escritura UI directa sin certificado inferior"),
    ("reddit", "reddit_interact.comment", "escritura directa fuera de reddit_execute"),
    ("tiktok", "tiktok_interact.like", "ruta web legada sin comprobar contexto semántico"),
)


def check_registry():
    """Errores estructurales; los tests de runtime verifican el comportamiento."""
    errors = []
    declared = {r.network for r in TEXT_EXECUTION_ROUTES}
    if declared != set(NETWORKS):
        errors.append(f"redes del contrato: falta {sorted(set(NETWORKS)-declared)}; sobra {sorted(declared-set(NETWORKS))}")
    keys = [(r.network, r.module, r.entrypoint) for r in TEXT_EXECUTION_ROUTES]
    if len(keys) != len(set(keys)):
        errors.append("rutas de ejecucion repetidas")
    for classification, routes in (
            ("guarded", GUARDED_DIRECT_WRITERS),
            ("uncovered", UNCOVERED_DIRECT_WRITERS)):
        for network, path, _ in routes:
            if network not in NETWORKS or "." not in path:
                errors.append(f"{classification}: ruta inferior invalida {network}/{path}")
    return errors


def build_report(*, matrix=None):
    """Informe offline: conexion declarada, NO pruebas ni capacidad de la API.

    Reutiliza el inventario #47 y añade las rutas protegidas/pendientes.
    Nunca transforma desconocido en capacidad imposible o contrato probado.
    """
    import network_capabilities as cap
    matrix = cap.build_matrix() if matrix is None else matrix
    return {
        "certification": "declarado_sin_ejecucion_remota",
        "networks": {
            net: {
                "capabilities": matrix.get(net, {}),
                "text_entrypoints": [
                    f"{route.module}.{route.entrypoint}"
                    for route in TEXT_EXECUTION_ROUTES if route.network == net
                ],
                "guarded_direct_writers": [
                    path for owner, path, reason in GUARDED_DIRECT_WRITERS
                    if owner == net
                ],
                "uncovered_direct_writers": [
                    {"path": path, "reason": reason}
                    for owner, path, reason in UNCOVERED_DIRECT_WRITERS if owner == net
                ],
                "runtime_tests": "requeridos",  # informe NO ejecuta tests
            } for net in NETWORKS
        },
    }


def main(argv=None):
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="informe sin red")
    args = parser.parse_args(argv)
    result = build_report()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for net, spec in result["networks"].items():
            print(f"{net}: {len(spec['text_entrypoints'])} rutas declaradas, "
                  f"{len(spec['uncovered_direct_writers'])} escrituras directas pendientes")
    return int(bool(check_registry()))


if __name__ == "__main__":
    raise SystemExit(main())
