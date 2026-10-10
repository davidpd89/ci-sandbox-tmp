"""Adaptadores puros para consumir vocabulario de discovery_terms (#63).

No consulta redes ni ejecuta acciones. La lectura es *en el momento del scan*:
un snapshot renovado no exige reiniciar el proceso. Compatible con los pools
legados y con el loader de #63 una vez integrado por Claude.
"""
from __future__ import annotations

from copy import deepcopy
import unicodedata
from typing import Callable

NETWORK_QUEUE = {
    "x": "WEB", "threads": "WEB", "facebook": "WEB",
    "pinterest": "WEB", "reddit": "WEB", "bluesky": "API",
    "mastodon": "API", "tiktok": "MOBILE", "instagram": "WEB",
}
TAG_NETWORKS = frozenset(NETWORK_QUEUE) - {"reddit"}
Reader = Callable[[str, str], list[str]]


def _read(network: str, kind: str, reader: Reader | None) -> list[str]:
    if network not in NETWORK_QUEUE or kind not in ("hashtags", "busquedas"):
        raise ValueError("red o tipo desconocido")
    if reader is None:
        try:
            from . import discovery_terms
        except ImportError:  # python tools/<script>.py
            import discovery_terms
        reader = discovery_terms.terms
    try:
        result = reader(network, kind)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        return []
    return result if isinstance(result, list) else []


def _clean(term: object, *, tag: bool) -> str:
    if not isinstance(term, str):
        return ""
    value = unicodedata.normalize("NFC", " ".join(term.split()))
    if (not value or len(value) > 120 or
            any(unicodedata.category(ch)[0] == "C" for ch in value)):
        return ""
    if tag:
        value = value.lstrip("#")
        if (not value or len(value) > 48 or
                not value[0].isalpha() or
                not all(ch.isalnum() or ch == "_" for ch in value)):
            return ""
    return value


def _key(value: str) -> str:
    # NFC, no NFKD: #año != #ano; los buscadores pueden distinguirlos.
    return unicodedata.normalize("NFC", " ".join(value.split())).casefold()


def format_term(network: str, kind: str, raw: object) -> str:
    """Devuelve la consulta final, no una URL (la codifica el transporte)."""
    if network not in NETWORK_QUEUE or kind not in ("hashtags", "busquedas"):
        raise ValueError("red o tipo desconocido")
    if kind == "hashtags" and network not in TAG_NETWORKS:
        return ""
    value = _clean(raw, tag=kind == "hashtags")
    if not value:
        return ""
    if kind == "hashtags":
        value = "#" + value
    if network == "x" and "lang:es" not in value.casefold().split():
        value += " lang:es"
    return value


def combine(network: str, kind: str, seeds, *, reader: Reader | None = None):
    """(semillas normalizadas, nuevas normalizadas), sin modificar entradas.

    Deduplica *después* de formar la consulta final. Las semillas se priorizan,
    y términos malformados o repetidos no consumen presupuesto.
    """
    out, fresh, seen = [], [], set()
    for group, values in ((out, seeds), (fresh, _read(network, kind, reader))):
        for raw in values:
            query = format_term(network, kind, raw)
            canonical = _key(query)
            if query and canonical not in seen:
                seen.add(canonical)
                group.append(query)
    return out, fresh


def rotate(pool, n: int, tick: int):
    """Rotación determinista, sin repetidos ni exceder n consultas."""
    if not isinstance(n, int) or n < 0 or not isinstance(tick, int):
        raise ValueError("presupuesto y tick invalidos")
    if not pool or not n:
        return []
    count = min(n, len(pool))
    start = tick % len(pool)
    return [pool[(start + i) % len(pool)] for i in range(count)]


def select(network: str, kind: str, seeds, *, budget: int, tick: int,
           reader: Reader | None = None):
    """Respeta el presupuesto y reserva una plaza para expansión fresca.

    Con presupuesto=1 alterna las cohortes por turno; con >=2 mantiene
    siempre presencia de semillas y de nuevos términos cuando ambos existan.
    """
    old, fresh = combine(network, kind, seeds, reader=reader)
    if not isinstance(budget, int) or budget < 0 or not isinstance(tick, int):
        raise ValueError("presupuesto y tick invalidos")
    if budget == 0:
        return []
    if not old:
        return rotate(fresh, budget, tick)
    if not fresh:
        return rotate(old, budget, tick)
    if budget == 1:
        return rotate(old if tick % 2 == 0 else fresh, 1, tick // 2)
    n_old = min(budget - 1, len(old))
    selected = rotate(old, n_old, tick * max(1, n_old))
    selected += rotate(fresh, min(budget - n_old, len(fresh)),
                       tick * max(1, budget - n_old))
    if len(selected) < budget:
        remaining = [x for x in rotate(old + fresh, len(old) + len(fresh), tick)
                     if _key(x) not in {_key(item) for item in selected}]
        selected += remaining[:budget - len(selected)]
    return selected


def extend_native_config(network: str, config: dict, *,
                         reader: Reader | None = None) -> dict:
    """Conserva el esquema de los tres escáneres por configuración.

    Solo amplía pools; la cobertura/presupuesto/ranking originales siguen
    decidiendo cuántas consultas ejecutar. No escribe la configuración.
    """
    if network not in ("bluesky", "mastodon", "tiktok"):
        raise ValueError("red sin adaptador de config")
    data = deepcopy(config)
    if network in ("bluesky", "mastodon"):
        families = data.setdefault("query_families", [])
        old = [q for f in families for q in f.get("queries", [])]
        _, new_queries = combine(network, "busquedas", old, reader=reader)
        if new_queries:
            families.append({"name": "lexical_expansion", "queries": new_queries})
        if network == "bluesky":
            tags = data.setdefault("tag_queries", [])
            old_tags = [row.get("tag", "") for row in tags]
            _, new_tags = combine(network, "hashtags", old_tags, reader=reader)
            tags.extend({"tag": tag[1:], "query": tag[1:]}
                        for tag in new_tags)
        else:
            tags = data.setdefault("hashtags", [])
            _, new_tags = combine(network, "hashtags", tags, reader=reader)
            tags.extend(tag[1:] for tag in new_tags)
    else:
        for field, kind in (("actor_queries", "busquedas"),
                            ("video_queries", "busquedas")):
            original = data.setdefault(field, [])
            _, fresh = combine(network, kind, original, reader=reader)
            original.extend(fresh)
        original = data.setdefault("video_queries", [])
        _, fresh = combine(network, "hashtags", original, reader=reader)
        original.extend(fresh)
    return data
