"""Terminos de descubrimiento ampliados con GPT (consulta M, 07/10/2026: `00_OPERATIVO/_consultas_gpt/RESPUESTA_M_descubrimiento.md`).

David: «no me puedo creer que una red social se termine con lo que tenemos». Las listas de busquedas, hashtags y hubs por red salen de `00_OPERATIVO/descubrimiento_gpt.json`; cada escaner las
suma a sus propios pools con `terms(red, "busquedas")`. Para ampliar solo hay que editar ese JSON (o volver a consultar a GPT).
"""
from __future__ import annotations

import json
import os

PATH = os.path.join(os.path.dirname(__file__), "..", "00_OPERATIVO", "descubrimiento_gpt.json")


def terms(network, kind="busquedas", suffix="", skip=()):
    """Catalogo estatico + terminos de reciprocidad (#65) + expansion local no vencida (#63), sin duplicados ni los de `skip`, con `suffix` opcional. Solo lectura."""
    import unicodedata

    def norm(value):
        # El plegado de acentos no se aplica: #año y #ano son busquedas distintas.
        return unicodedata.normalize("NFC", str(value).strip().lstrip("#")).casefold()

    try:
        with open(PATH, encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    entry = data.get(network)
    static = entry.get(kind, []) if isinstance(entry, dict) else []
    if not isinstance(static, list):
        static = []
    try:
        from reciprocity_signals import search_terms
    except ImportError:
        from tools.reciprocity_signals import search_terms
    extra = search_terms(network, kind)
    try:
        from hashtag_expansion import snapshot_terms
    except ImportError:
        from tools.hashtag_expansion import snapshot_terms
    observed = snapshot_terms(network, kind)
    skip_keys = {norm(item) for item in skip}
    out, seen = [], set()
    for item in list(static) + list(extra) + list(observed):
        if not isinstance(item, str):
            continue
        value = item.strip().lstrip("#") if kind == "hashtags" else item.strip()
        key = norm(value)
        if value and key not in seen and key not in skip_keys:
            seen.add(key)
            out.append(value + suffix)
    return out

# PR #48: taxonomía de semillas observadas. No toca cuentas ni promociona hubs.
# El catálogo `descubrimiento_gpt.json` contiene *ideas* de fuentes, no
# evidencia de que una persona sea audiencia real ni haga follow-back.
EVIDENCE_ROLES = {
    "follow_graph": "follow_hub",
    "conversation_post": "conversation_hub",
    "reader_interaction": "audience_hub",
}
NETWORKS = frozenset(("bluesky", "mastodon", "x", "threads", "facebook",
                      "pinterest", "reddit", "tiktok", "instagram"))


def tag_seeds(network, observations):
    """Etiqueta semillas con hechos identificables, deduplicados por origen.

    observations: [{"handle": str, "source": str,
                    "evidence": [{"kind": "conversation_post", "id": str}, ...]}].
    Los IDs han de venir de una lectura verificable del adaptador; no inferimos
    identidad a partir de texto, nombre visible, likes o seguidores agregados.
    Una misma cuenta en dos fuentes conserva ambas procedencias.
    Sin evidencia => `roles=[]`, `status="unverified"`: nunca una audiencia
    ficticia. Función pura; no altera escáneres ni sus planes de ejecución.
    """
    if not isinstance(network, str) or network.strip().casefold() not in NETWORKS:
        raise ValueError("red desconocida/no permitida")
    network = network.strip().casefold()
    if not isinstance(observations, (list, tuple)):
        raise ValueError("observaciones deben ser una secuencia")
    grouped = {}
    for row in observations:
        if not isinstance(row, dict):
            raise ValueError("observacion no estructurada")
        handle = row.get("handle")
        source = row.get("source")
        evidence = row.get("evidence", [])
        if (not isinstance(handle, str) or not handle.strip().lstrip("@")
                or any(ch.isspace() for ch in handle.strip())):
            raise ValueError("semilla sin handle verificable")
        if (not isinstance(source, str) or not source.strip()
                or any(ord(ch) < 32 for ch in source)):
            raise ValueError("semilla sin origen")
        if not isinstance(evidence, (list, tuple)):
            raise ValueError("evidencia no estructurada")
        canonical = handle.strip().lstrip("@").casefold()
        origin = source.strip().casefold()
        key = (network.casefold(), canonical, origin)
        entry = grouped.setdefault(key, {
            "network": network.casefold(), "handle": canonical,
            "source": source.strip(), "roles": [], "evidence": [],
            "status": "unverified",
        })
        known = {(e["kind"], e["id"]) for e in entry["evidence"]}
        for item in evidence:
            if not isinstance(item, dict):
                raise ValueError("evidencia no estructurada")
            kind, identifier = item.get("kind"), item.get("id")
            if (not isinstance(kind, str) or kind not in EVIDENCE_ROLES
                    or not isinstance(identifier, str) or not identifier.strip()
                    or any(ord(ch) < 32 for ch in identifier)):
                raise ValueError("evidencia sin clase o ID verificable")
            proof = (kind, identifier.strip())
            if proof not in known:
                entry["evidence"].append({"kind": kind, "id": proof[1]})
                known.add(proof)
        entry["roles"] = sorted({EVIDENCE_ROLES[e["kind"]] for e in entry["evidence"]})
        entry["status"] = "observed" if entry["roles"] else "unverified"
    return list(grouped.values())
