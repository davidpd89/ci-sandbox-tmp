"""Comparación humana ciega por pares: sin evaluaciones inventadas ni filtración de claves."""
from __future__ import annotations

import hashlib
import json
import secrets
from collections import Counter
from spanish_voice_quality import NETWORKS

CHOICES = frozenset({"left", "right", "tie", "both_bad"})
CONTENT_FIELDS = ("id", "network", "context", "left", "right")


def _digest(row):
    """Sella texto y red/contexto sin exponer los textos en la clave privada."""
    data = {field: row[field] for field in CONTENT_FIELDS}
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate(pairs):
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("se requiere una lista no vacía")
    ids = set()
    for pair in pairs:
        if not isinstance(pair, dict) or set(pair) != {"id", "network", "context", "before", "after"}:
            raise ValueError("esquema de caso inválido")
        ident, net = pair["id"], pair["network"]
        if not isinstance(ident, str) or not ident.strip() or ident in ids:
            raise ValueError("id de caso vacío o duplicado")
        ids.add(ident)
        if not isinstance(net, str) or net not in NETWORKS:
            raise ValueError("red no admitida")
        if not all(isinstance(pair[k], str) and pair[k].strip()
                   for k in ("context", "before", "after")):
            raise ValueError("contexto o propuestas no válidas")


def pack(pairs, *, seed=None):
    """Semilla criptográfica por defecto; claves aparte del formulario de revisión."""
    _validate(pairs)
    if seed is None:
        seed = secrets.token_hex(32)
    if not isinstance(seed, str) or not seed:
        raise ValueError("seed inválida")
    review, after_side, integrity = [], {}, {}
    for pair in sorted(pairs, key=lambda p: p["id"]):
        flip = bool(hashlib.sha256((seed + "\0" + pair["id"]).encode("utf-8")).digest()[0] & 1)
        row = {
            "id": pair["id"], "network": pair["network"], "context": pair["context"],
            "left": pair["after"] if flip else pair["before"],
            "right": pair["before"] if flip else pair["after"],
            "preference": None,
        }
        review.append(row)
        after_side[pair["id"]] = "left" if flip else "right"
        integrity[pair["id"]] = _digest(row)
    return ({"schema_version": 1, "items": review},
            {"schema_version": 1, "after_side": after_side, "sha256_by_id": integrity})


def score(review, key):
    """Rechazar revisiones incompletas, alteradas o con contexto/red modificados."""
    if (not isinstance(review, dict) or not isinstance(key, dict) or
        review.get("schema_version") != 1 or key.get("schema_version") != 1):
        raise ValueError("versión o esquema inválido")
    items, mapping, digests = (review.get("items"), key.get("after_side"),
                               key.get("sha256_by_id"))
    if (not isinstance(items, list) or not isinstance(mapping, dict) or
        not isinstance(digests, dict) or not items or
        len(items) != len(mapping) or len(items) != len(digests)):
        raise ValueError("pares incompletos")
    counts, by_net, seen = Counter(), {}, set()
    for item in items:
        if not isinstance(item, dict) or set(item) != set(CONTENT_FIELDS) | {"preference"}:
            raise ValueError("esquema de revisión inválido")
        ident, net, choice = item["id"], item["network"], item["preference"]
        if (not isinstance(ident, str) or ident in seen or ident not in mapping or
            ident not in digests or not isinstance(net, str) or net not in NETWORKS or
            any(not isinstance(item[k], str) or not item[k].strip()
                for k in CONTENT_FIELDS[2:]) or
            not isinstance(choice, str) or choice not in CHOICES or
            not isinstance(mapping[ident], str) or mapping[ident] not in ("left", "right")):
            raise ValueError("revisión incompleta o inválida")
        if not isinstance(digests[ident], str) or _digest(item) != digests[ident]:
            raise ValueError("un texto, contexto o red se modificó tras generar la clave")
        seen.add(ident)
        outcome = ("tie" if choice == "tie" else
                   "both_bad" if choice == "both_bad" else
                   "after" if choice == mapping[ident] else "before")
        counts[outcome] += 1
        by_net.setdefault(net, Counter())[outcome] += 1
    if set(mapping) != seen or set(digests) != seen:
        raise ValueError("IDs de revisión/clave no coinciden")

    def result(counter):
        return {name: counter[name] for name in ("before", "after", "tie", "both_bad")}

    return {"n": len(items), "preferences": result(counts),
            "by_network": {net: result(c) for net, c in sorted(by_net.items())},
            "note": "Juicio humano por pares; no acredita mejora sin revisores independientes."}
