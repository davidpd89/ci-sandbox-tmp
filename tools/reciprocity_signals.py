"""Detector explicable y de solo lectura de reciprocidad explícita.

Contrato para adaptadores WEB/API/MOBILE: texto observado -> indicios tipados ->
candidato para revisión/ranking, NUNCA una acción social. Sin dependencias de red.
"""
from __future__ import annotations

import datetime as dt
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping

NETWORKS = frozenset(("x", "threads", "facebook", "pinterest", "reddit",
                      "bluesky", "mastodon", "tiktok", "instagram"))
SURFACES = frozenset(("bio", "post", "hashtag", "group", "list"))
POST_MAX_AGE_DAYS = 7

# Cada regex describe una intención expresa, no una coincidencia genérica con "seguir".
# Los límites de palabra evitan "f4foo" y "desfollowback". El orden es estable.
_RULES = {
    "follow_exchange": (
        r"\b(?:sigo de vuelta|sigo a (?:todos|quien(?:es)? me sig(?:a|an|ue|uen))|"
        r"si(?:gueme|guenos) y te sigo|sigueme y te sigo|"
        r"te sigo si me sigues|seguimos a quien nos sigue|"
        r"follow[\s-]?back|follow[\s-]?for[\s-]?follow|follow4follow|"
        r"f4f|sdv|fb100|fb\s?100|devuelvo (?:el )?follow|"
        r"devuelvo (?:los )?seguidores)\b",
    ),
    "comment_exchange": (
        r"\b(?:comentario por comentario|comenta y te comento|"
        r"te comento si me comentas|devuelvo comentarios|"
        r"comment[\s-]?for[\s-]?comment|c4c|"
        r"intercambio de comentarios)\b",
    ),
    "reading_chain": (
        r"\b(?:cadena de lectura|cadena de resenas|"
        r"intercambio de resenas|intercambio de lecturas|"
        r"leemos y nos comentamos|lectura conjunta de autores)\b",
    ),
    "support_group": (
        r"\b(?:grupo de apoyo mutuo (?:para |de )?(?:lectores|autores|escritores)|"
        r"apoyo mutuo (?:entre |de )?(?:escritores|autores|lectores)|"
        r"grupo de interaccion (?:literaria|de escritores|de lectores)|"
        r"nos apoyamos entre (?:escritores|autores)|"
        r"hilo de apoyo (?:lector|literario))\b",
    ),
}
_PATTERNS = {k: tuple(re.compile(p) for p in v) for k, v in _RULES.items()}
# El metacomentario y el rechazo no son una oferta; nunca se usa como prueba.
_META = re.compile(
    r"\b(?:que es|que significa|como funciona|que opinas|"
    r"no hago|no participo|nunca hago|evita|evitad|cuidado con|"
    r"odio|estafa|trampa|no recomiendo|desaconsejo|"
    r"definicion de|hablamos de|debate sobre|contra el|"
    r"ejemplo de|explicar el|explico el|en mi novela|personaje dice|prefiero no|no recomendar)\b"
)
_NICHE = re.compile(
    r"\b(?:libros?|lecturas?|lectores?|escrit(?:or|ora|ores|oras)|"
    r"romantasy|fantasia|novela|resenas?|booktok|bookstagram|"
    r"booksky|booktube|literari[oa]s?|editoriales?)\b"
)

# Búsquedas semilla en lenguaje natural, sin handles reales ni grupos privados.
# Pueden incorporarse a terms(network,"busquedas") sin alterar adaptadores.
QUERIES = {
    "x": ("sigo de vuelta libros", "comentario por comentario escritores"),
    "threads": ("sigo de vuelta lectores", "apoyo mutuo escritores"),
    "facebook": ("grupo apoyo mutuo escritores", "cadena de lectura autores"),
    "pinterest": ("tablero colaborativo libros", "intercambio de reseñas libros"),
    "reddit": ("cadena de lectura escritores", "intercambio de reseñas libros"),
    "bluesky": ("sigo de vuelta libros", "cadena de lectura"),
    "mastodon": ("sigo de vuelta lectores", "apoyo mutuo escritores"),
    "tiktok": ("f4f booktok", "cadena de lectura booktok"),
    "instagram": ("f4f bookstagram", "apoyo mutuo escritores"),
}
HASHTAGS = {
    "x": ("SiguemeYTeSigo", "FollowBack"),
    "threads": ("FollowBack", "ApoyoMutuoEscritores"),
    "facebook": ("ApoyoMutuoEscritores",),
    "pinterest": ("LecturaConjunta",),
    "reddit": ("LecturaConjunta",),
    "bluesky": ("FollowBack",),
    "mastodon": ("FollowBack",),
    "tiktok": ("F4F", "BookTok"),
    "instagram": ("F4F", "Bookstagram"),
}


def fold(value: str) -> str:
    """NFKC + casefold + eliminación de tildes; conserva hashtags y palabras."""
    if not isinstance(value, str):
        return ""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = "".join(c for c in unicodedata.normalize("NFKD", value)
                    if not unicodedata.combining(c))
    return " ".join(value.split())


def classify_text(text: str) -> list[dict]:
    """Señales, con clase, frase exacta normalizada e intención distinguible."""
    value = fold(text)
    if not value or len(value) > 20000:
        return []
    meta = bool(_META.search(value))
    results = []
    for kind, patterns in _PATTERNS.items():
        found = next((m.group(0) for pattern in patterns
                      if (m := pattern.search(value))), None)
        if found:
            results.append({
                "kind": kind, "matched": found,
                "intent": "mention" if meta else "explicit",
                "confidence": 0.0 if meta else
                (0.95 if kind == "follow_exchange" else 0.9),
            })
    return results


def search_terms(network: str, kind: str = "busquedas") -> tuple[str, ...]:
    """Ampliación de descubrimiento por red; lista cerrada y determinista."""
    network = fold(network).strip()
    if network not in NETWORKS:
        return ()
    return (HASHTAGS if kind == "hashtags" else QUERIES).get(network, ()) if kind in ("hashtags", "busquedas") else ()


def assess_candidate(row: Mapping, *, as_of: dt.date,
                     max_post_age_days: int = POST_MAX_AGE_DAYS) -> dict:
    """Evaluación offline: no lee ni muta reservas, no propone acciones."""
    if not isinstance(row, Mapping) or not isinstance(as_of, dt.date) or isinstance(as_of, dt.datetime):
        raise ValueError("fila o fecha inválida")
    if type(max_post_age_days) is not int or max_post_age_days < 0:
        raise ValueError("edad máxima inválida")
    network = fold(row.get("network"))
    surface = fold(row.get("surface"))
    if network not in NETWORKS or surface not in SURFACES:
        return {"status": "rejected", "reason": "unsupported_surface", "signals": []}
    signals = classify_text(row.get("text"))
    explicit = [s for s in signals if s["intent"] == "explicit"]
    if not explicit:
        return {"status": "rejected", "reason": "mention_or_no_signal",
                "signals": signals}
    relevant = row.get("niche_verified") is True or bool(_NICHE.search(fold(row.get("text"))))
    if not relevant:
        return {"status": "review", "reason": "niche_unverified", "signals": signals}
    if surface == "post":
        day = row.get("created_on")
        try:
            created = dt.date.fromisoformat(day) if isinstance(day, str) and len(day) == 10 else None
        except ValueError:
            created = None
        if created is None or created > as_of:
            return {"status": "review", "reason": "post_age_unknown", "signals": signals}
        if (as_of - created).days > max_post_age_days:
            return {"status": "rejected", "reason": "stale_post", "signals": signals}
    return {"status": "eligible", "reason": "explicit_relevant",
            "signals": signals}


def evaluate(rows: list[dict], *, as_of: dt.date) -> dict:
    """Precision/recall supervisadas por red sobre casos etiquetados sintéticos."""
    buckets = defaultdict(lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0})
    for row in rows:
        expected = row.get("expected_eligible")
        if type(expected) is not bool:
            raise ValueError("etiqueta binaria ausente")
        network = row["network"]
        actual = assess_candidate(row, as_of=as_of)["status"] == "eligible"
        buckets[network][("tp" if expected else "fp") if actual
                         else ("fn" if expected else "tn")] += 1
    out = {}
    for network in sorted(buckets):
        b = buckets[network]
        tp, fp, fn = b["tp"], b["fp"], b["fn"]
        out[network] = {**b,
                        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                        "recall": round(tp / (tp + fn), 3) if tp + fn else None}
    return out


def outcome_report(rows: list[dict], *, as_of: dt.date, min_age_days: int = 3) -> dict:
    """Tasas descriptivas (no causales), solo resultados confirmados de cohortes maduras.

    Cada señal cuenta una vez por (red, actor, fuente), sin contar desconocidos
    como fracasos. Métricas: relation_active, comments, visits (bool o None).
    """
    if type(min_age_days) is not int or min_age_days < 0:
        raise ValueError("madurez inválida")
    groups = defaultdict(lambda: {k: [0, 0] for k in
                                  ("relation_active", "comments", "visits")})
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping) or row.get("verified") is not True:
            continue
        network, kind, actor, source = (row.get(k) for k in
                                         ("network", "kind", "actor_id", "source_id"))
        if (network not in NETWORKS or kind not in _RULES or
                not all(isinstance(x, str) and 0 < len(x) <= 256
                        for x in (actor, source))):
            continue
        key = (network, actor, source)
        if key in seen:
            continue
        try:
            day = dt.date.fromisoformat(row["observed_on"])
        except (KeyError, TypeError, ValueError):
            continue
        if not 0 <= (as_of - day).days or (as_of - day).days < min_age_days:
            continue
        seen.add(key)
        for metric in ("relation_active", "comments", "visits"):
            value = row.get(metric)
            if type(value) is bool:
                groups[(network, kind)][metric][0] += int(value)
                groups[(network, kind)][metric][1] += 1
    return {network + "/" + kind: {
        metric: {"confirmed": value[0], "observed": value[1],
                 "rate": round(value[0] / value[1], 3) if value[1] else None}
        for metric, value in metrics.items()}
        for (network, kind), metrics in sorted(groups.items())}
