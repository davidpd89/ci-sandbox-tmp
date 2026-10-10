"""Terminos de descubrimiento ampliados con GPT (consulta M, 07/10/2026: `00_OPERATIVO/_consultas_gpt/RESPUESTA_M_descubrimiento.md`).

David: «no me puedo creer que una red social se termine con lo que tenemos». Las listas de busquedas, hashtags y hubs por red salen de `00_OPERATIVO/descubrimiento_gpt.json`; cada escaner las
suma a sus propios pools con `terms(red, "busquedas")`. Para ampliar solo hay que editar ese JSON (o volver a consultar a GPT).
"""
from __future__ import annotations

import json
import os

PATH = os.path.join(os.path.dirname(__file__), "..", "00_OPERATIVO", "descubrimiento_gpt.json")


def terms(network, kind="busquedas", suffix="", skip=()):
    """Lista de terminos (sin duplicados ni los de `skip`), con `suffix` opcional (p. ej. ' lang:es' en X). [] si falta el fichero."""
    try:
        with open(PATH, encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        data = {}
    # Ampliación común: los escáneres que usan terms(red, kind) reciben
    # consultas explícitas de reciprocidad sin ninguna operación adicional.
    try:
        from reciprocity_signals import search_terms
    except ImportError:
        from tools.reciprocity_signals import search_terms
    extra = search_terms(network, kind)
    skip_keys = {str(s).casefold() for s in skip}
    out, seen = [], set()
    for term in list((data.get(network) or {}).get(kind) or []) + list(extra):
        text = str(term).strip().lstrip("#") if kind == "hashtags" else str(term).strip()
        key = text.casefold()
        if text and key not in seen and key not in skip_keys:
            seen.add(key)
            out.append(text + suffix)
    return out
