"""Contrato común de las redes en el ciclo automático (rondas mecánicas).

`mechanical_round.py` (Bluesky/Mastodon/Threads/X/…) describe cada red como un dict `PIPELINES[red]`
con pasos pre -> build -> execute -> post. TikTok (móvil Android) usa el mismo contrato; lo único
distinto es el recurso que se turna: el MÓVIL (`mobile_runtime.mobile_session_lock`, un solo
teléfono) en vez del Edge CDP 9223. Aquí vive la definición de TikTok y las reglas comunes que
cualquier red por móvil necesita, para que el planificador no tenga código específico:

    from growth_core import pipeline_for
    PIPELINES["tiktok"] = pipeline_for("tiktok", PY)

El ejecutor imprime `confirmado <tipo> @cuenta`, que es lo que `mechanical_round.summarize` cuenta.
Los comentarios de TikTok los escribe la IA (calidad); la ronda mecánica ejecuta follows y likes del
auto_plan y los comentarios que haya en `tiktok_decisions.json` si existe.
"""
from __future__ import annotations

import sys

PHONE_RESOURCE = "phone_android"      # bloqueo entre rondas (equivale a `edge_browser` en las de navegador)

_COMMON = {
    "phone": True,                 # => se turna con otras rondas por móvil, no por Edge
    "shape": False,                # el techo diario sale de growth_config.json (action_ceiling)
    "runs_per_day": 2,
    "min_plan": 20,
    "decisions": None,
    "write_decisions": None,
}


def pipeline_for(network: str, py: str | None = None) -> dict:
    py = py or sys.executable
    if network != "tiktok":
        raise KeyError(f"red por móvil sin pipeline: {network}")
    return {
        **_COMMON,
        "dir": "SISTEMA_DIARIO_TIKTOK",
        "plan": "tiktok_plan.json",
        "pre": [[py, "tools/tiktok_growth_flow.py", "prepare"]],
        "build": [py, "tools/tiktok_growth_flow.py", "build", "--plan", "tiktok_plan.json"],
        "execute": [py, "tools/tiktok_growth_flow.py", "run", "--apply", "--plan", "tiktok_plan.json"],
        "post": [],
    }


def uses_phone(spec: dict) -> bool:
    return bool(spec.get("phone"))
