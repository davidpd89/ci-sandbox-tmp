"""Terminos de descubrimiento ampliados con GPT (consulta M, 07/10/2026: `00_OPERATIVO/_consultas_gpt/RESPUESTA_M_descubrimiento.md`).

David: «no me puedo creer que una red social se termine con lo que tenemos». Las listas de busquedas, hashtags y hubs por red salen de `00_OPERATIVO/descubrimiento_gpt.json`; cada escaner las
suma a sus propios pools con `terms(red, "busquedas")`. Para ampliar solo hay que editar ese JSON (o volver a consultar a GPT).
"""
from __future__ import annotations

import json
import os

PATH = os.path.join(os.path.dirname(__file__), "..", "00_OPERATIVO", "descubrimiento_gpt.json")


def terms(network, kind="busquedas", suffix="", skip=()):
    """Mezcla catálogo estático y expansión local no vencida, sin escribir."""
    import unicodedata
    def norm(value):
        folded = unicodedata.normalize("NFKD", str(value).strip().lstrip("#").casefold())
        return "".join(c for c in folded if not unicodedata.combining(c))

    try:
        with open(PATH, encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    static = (data.get(network) or {}).get(kind) or []
    if not isinstance(static, list):
        static = []

    # Import interno: escáneres siguen funcionando cuando no hay caché.
    from hashtag_expansion import snapshot_terms
    observed = snapshot_terms(network, kind)

    skip_keys = {norm(item) for item in skip}
    out, seen = [], set()
    for item in static + observed:
        if not isinstance(item, str):
            continue
        value = item.strip().lstrip("#") if kind == "hashtags" else item.strip()
        key = norm(value)
        if value and key not in seen and key not in skip_keys:
            seen.add(key)
            out.append(value + suffix)
    return out
