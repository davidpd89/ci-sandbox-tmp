"""Evaluación ciega emparejada offline: sin opiniones humanas inventadas."""
from __future__ import annotations

import hashlib
from collections import Counter
from spanish_voice_quality import NETWORKS

CHOICES = frozenset({"left", "right", "tie", "both_bad"})


def _validate(pairs):
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("se requiere una lista no vacía")
    ids = set()
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != {"id", "network", "context", "before", "after"}:
            raise ValueError("esquema de caso inválido")
        ident = pair["id"]
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError("id de caso vacío o duplicado")
        ids.add(ident)
        if (pair["network"] not in NETWORKS or
            not all(isinstance(pair[k], str) and pair[k].strip()
                    for k in ("context", "before", "after"))):
            raise ValueError("red, contexto o propuestas no válidas")


def pack(pairs, *, seed):
    """Ciego por pares; separar el fichero de revisión de su clave."""
    _validate(pairs)
    if not isinstance(seed, str) or not seed:
        raise ValueError("seed requerida")
    review, key = [], {}
    for pair in sorted(pairs, key=lambda p: p["id"]):
        flip = bool(hashlib.sha256((seed + "\0" + pair["id"]).encode("utf-8")).digest()[0] & 1)
        review.append({
            "id": pair["id"], "network": pair["network"], "context": pair["context"],
            "left": pair["after"] if flip else pair["before"],
            "right": pair["before"] if flip else pair["after"],
            "preference": None,
        })
        key[pair["id"]] = "left" if flip else "right"
    return ({"schema_version": 1, "items": review},
            {"schema_version": 1, "after_side": key})


def score(review, key):
    items = review.get("items") if isinstance(review, dict) else None
    mapping = key.get("after_side") if isinstance(key, dict) else None
    if not isinstance(items, list) or not isinstance(mapping, dict):
        raise ValueError("esquema de revisión o clave inválido")
    if (set(mapping) != {i.get("id") for i in items if isinstance(i, dict)} or
        len(items) != len(mapping)):
        raise ValueError("pares incompletos o duplicados")
    counts, by_net = Counter(), {}
    for item in items:
        ident, net, choice = item["id"], item["network"], item.get("preference")
        if net not in NETWORKS or choice not in CHOICES or mapping[ident] not in ("left", "right"):
            raise ValueError("revisión incompleta o inválida")
        outcome = ("tie" if choice == "tie" else
                   "both_bad" if choice == "both_bad" else
                   "after" if choice == mapping[ident] else "before")
        counts[outcome] += 1
        by_net.setdefault(net, Counter())[outcome] += 1

    def result(c):
        return {k: c[k] for k in ("before", "after", "tie", "both_bad")}

    return {"n": len(items), "preferences": result(counts),
            "by_network": {net: result(c) for net, c in sorted(by_net.items())},
            "note": "Juicio humano por pares; no acredita mejora sin revisores independientes."}
