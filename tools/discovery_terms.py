"""Consulta del banco operativo más expansión local de intención lectora.

El banco original vive en 00_OPERATIVO/descubrimiento_gpt.json (puede faltar
intencionadamente en el espejo público). Sin cambiar escáneres ni credenciales,
las búsquedas reciben términos del nicho antes de que la rotación existente elija
sus consultas. Hashtags/hubs/semillas no se modifican; #63/#99/#101 los gestionan.
"""
from __future__ import annotations

import json
import os
import unicodedata

from niche_query_bank import NETWORKS, queries

PATH = os.path.join(os.path.dirname(__file__), "..", "00_OPERATIVO", "descubrimiento_gpt.json")


def _key(raw):
    return " ".join(unicodedata.normalize("NFC", str(raw)).casefold().split())


def terms(network, kind="busquedas", suffix="", skip=(), *, include_niche=True):
    """Lista estable, sin repetidos, con sufijo del adaptador (p.ej. lang:es).

    Sin IO de redes. Si el JSON no existe o está dañado, únicamente «busquedas»
    recibe frases editoriales estáticas, nunca inventa estados de cuenta.
    """
    try:
        with open(PATH, encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        data = {}
    catalog = data.get(network) if isinstance(data, dict) else {}
    catalog = catalog if isinstance(catalog, dict) else {}
    rows = catalog.get(kind)
    rows = rows if isinstance(rows, list) else []
    if kind == "busquedas" and include_niche and network in NETWORKS:
        rows = [*rows, *queries(network)]
    skip_keys = {_key(s) for s in skip if isinstance(s, str)}
    out, seen = [], set()
    for raw in rows:
        if not isinstance(raw, str):
            continue
        text = raw.strip().lstrip("#") if kind == "hashtags" else raw.strip()
        key = _key(text)
        if text and key not in seen and key not in skip_keys:
            seen.add(key)
            out.append(text + suffix)
    return out
