"""Cuarentena por alertas externas verificadas: procesador SOLO OFFLINE.

No sondeos de inbox, OAuth ni datos operativos. La autenticidad de la entrada
debe validarla una persona/controlador; --apply es la confirmación explícita.
No registrar texto privado ni identidades de remitentes en disco/log.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import circuit_breaker as breaker

NETWORKS = frozenset(("bluesky", "mastodon", "x", "threads", "facebook",
                      "pinterest", "reddit", "tiktok", "instagram"))
CATEGORIES = frozenset(("moderation_warning", "account_suspended",
                        "account_restricted", "moderator_notice",
                        "modmail_ban", "platform_notice"))
# No interpretar como queja un 'normas' o 'spam' genérico en una mención ajena.
SUBJECT = re.compile(
    r"\b(?:necroposting|necroposte[oa]|publicaciones? antiguas?|"
    r"spam|contenido no deseado|acoso|harassment|abuse|"
    r"automated behavior|comportamiento automatizado|"
    r"viola(?:s|ción|cion)? de normas|violat(?:ion|ed) (?:of )?(?:rules|policy))\b",
    re.IGNORECASE,
)


def classify_event(event):
    """Devuelve categoría sin divulgar texto: ignorada, revisar, o cuarentena."""
    if not isinstance(event, dict):
        return "ignorada"
    network = event.get("network")
    category = event.get("category")
    # JSON puede contener listas/diccionarios en vez de escalares: no dejar
    # que un TypeError interrumpa todo el lote de avisos.
    if not isinstance(network, str) or network not in NETWORKS:
        return "ignorada"
    if not isinstance(category, str) or category not in CATEGORIES:
        return "ignorada"
    source = event.get("source")
    if source not in ("platform", "verified_moderator", "manual"):
        return "ignorada"
    # verified es una afirmación del JSON, no una prueba de autenticidad.
    # Eventos importados nunca disparan el bloqueo hasta revisión explícita;
    # --apply constituye la autorización de escritura, no la verificación.
    if event.get("verified") is not True:
        return "revisar"
    # Ningún campo "verified" importado constituye prueba de autenticidad.
    # Toda propuesta de hold requiere revisión positiva y explícita del aviso.
    if event.get("confirmed_by_human") is not True:
        return "revisar"
    # No inferir que cualquier alerta de plataforma se refiere a nuestra cuenta.
    # La notificación estructurada moderation_warning de Mastodon sí lo hace.
    if source == "platform" and event.get("network") == "mastodon":
        if category != "moderation_warning":
            return "revisar"
    # Una notificación estructurada inequívoca de plataforma no requiere
    # comparar texto; para aviso humano, comprobar el asunto del aviso.
    if category in ("moderation_warning", "account_suspended",
                    "account_restricted", "modmail_ban"):
        return "cuarentena"
    if SUBJECT.search(str(event.get("text") or "")[:2000]):
        return "cuarentena"
    return "revisar"


def process_events(events, *, root, apply=False):
    """Redes en cuarentena. No persiste texto, remitente ni ID privado."""
    if not isinstance(events, list) or len(events) > 1000:
        raise ValueError("entrada exige lista de 0..1000 eventos")
    stats = {"cuarentena": 0, "revisar": 0, "ignoradas": 0, "redes": []}
    selected = set()
    for event in events:
        kind = classify_event(event)
        if kind == "cuarentena":
            selected.add(event["network"])
            stats["cuarentena"] += 1
        elif kind == "revisar":
            stats["revisar"] += 1
        else:
            stats["ignoradas"] += 1
    for network in sorted(selected):
        if apply:
            directory = os.path.join(root, "SISTEMA_DIARIO_" + network.upper())
            breaker.hold_for_review(directory, "external_complaint",
                                    origin="external_complaint_watch")
        stats["redes"].append(network)
    stats["aplicado"] = bool(apply)
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSON local revisado por humano")
    parser.add_argument("--root", default=os.path.join(os.path.dirname(__file__), ".."))
    parser.add_argument("--apply", action="store_true",
                        help="escribe cuarentenas SOLO con autorización humana explícita")
    args = parser.parse_args(argv)
    # No cargar ficheros ilimitados o con claves duplicadas que hagan
    # ambiguo el evento a un revisor; no registrar nunca texto privado.
    max_bytes = 1024 * 1024
    with open(args.input, "rb") as stream:
        raw = stream.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("entrada JSON supera 1 MiB")
    def unique_keys(pairs):
        parsed = {}
        for key, value in pairs:
            if key in parsed:
                raise ValueError("claves JSON repetidas")
            parsed[key] = value
        return parsed
    def invalid_constant(value):
        raise ValueError("constante JSON no válida")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_keys,
                      parse_constant=invalid_constant)
    result = process_events(data, root=args.root, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
