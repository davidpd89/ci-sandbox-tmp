"""Consultas editoriales de intención lectora, sin APIs ni identidades de terceros.

Amplía el catálogo existente de discovery_terms, sin sustituir la rotación,
los adaptadores de consulta ni el ranking. Las frases son propuestas de búsqueda,
NO observaciones ni prueba de que existan autores o publicaciones concretas.
"""
from __future__ import annotations

import argparse
import json
import unicodedata

NETWORKS = frozenset({
    "x", "threads", "facebook", "pinterest", "reddit", "bluesky",
    "mastodon", "tiktok", "instagram",
})

INTENTS = {
    "lector_pide": (
        "recomendadme fantasía juvenil",
        "busco novelas romantasy en español",
        "qué saga de fantasía me recomendáis",
        "recomendaciones de fantasía épica",
        "libros de fantasía que enganchen",
    ),
    "lector_comparte": (
        "acabo de terminar una novela de fantasía",
        "estoy leyendo romantasy",
        "mi próxima lectura de fantasía",
        "me ha gustado esta saga de fantasía",
    ),
    "resenas": (
        "reseña de romantasy",
        "opinión fantasía juvenil",
        "crítica novela de fantasía",
        "reseñas de libros de dragones",
    ),
    "comunidad": (
        "club de lectura de fantasía",
        "lectura conjunta romantasy",
        "lectores de fantasía en español",
    ),
    "autoria": (
        "escribo fantasía juvenil",
        "autora independiente de fantasía",
        "proceso de escribir una novela fantástica",
    ),
    "subgeneros": (
        "academia mágica novelas",
        "fantasía con dragones libros",
        "fantasía oscura recomendaciones",
        "enemigos a amantes en fantasía",
    ),
}

# Cada adaptador añade únicamente superficies pertinentes; los operadores
# específicos de búsqueda siguen siendo responsabilidad de cada escáner.
ADAPTER_PHRASES = {
    "x": ("busco libros parecidos a romantasy",),
    "threads": ("debate final de saga fantástica",),
    "facebook": (
        "grupos lectura conjunta fantasía",
        "club de lectura romantasy España",
        "páginas reseñas fantasía juvenil",
    ),
    "pinterest": (
        "tableros estética romantasy libros",
        "ilustraciones academia mágica libros",
        "listas lectura fantasía juvenil",
        "ideas para diario de lectura fantasía",
    ),
    "reddit": (
        "recomendación fantasía juvenil en español",
        "opiniones sobre novelas romantasy",
        "recomendación sistema de magia novelas",
    ),
    "bluesky": ("lectoras de fantasía en Bluesky",),
    "mastodon": ("lectores fantasía en fediverso",),
    "tiktok": (
        "booktok romantasy España reseñas",
        "booktok fantasía juvenil recomendaciones",
    ),
    "instagram": (
        "bookstagram español reseñas romantasy",
        "bookstagram fantasía juvenil lectoras",
    ),
}

MAX_SUGGESTIONS_PER_NETWORK = 32


def _key(term: str) -> str:
    return " ".join(unicodedata.normalize("NFC", term).casefold().split())


def queries(network: str) -> list[str]:
    """Frases únicas ordenadas por red, sin IO ni operadores no documentados."""
    if network not in NETWORKS:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for group in INTENTS.values():
        for phrase in group:
            key = _key(phrase)
            if key not in seen:
                seen.add(key)
                result.append(phrase)
    for phrase in ADAPTER_PHRASES[network]:
        key = _key(phrase)
        if key not in seen:
            seen.add(key)
            result.append(phrase)
    return result[:MAX_SUGGESTIONS_PER_NETWORK]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Consultas editoriales para los nueve adaptadores")
    parser.add_argument("--network", choices=sorted(NETWORKS))
    args = parser.parse_args(argv)
    names = (args.network,) if args.network else tuple(sorted(NETWORKS))
    print(json.dumps({net: queries(net) for net in names}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
