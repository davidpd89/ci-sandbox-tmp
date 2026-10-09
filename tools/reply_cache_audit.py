"""R9: auditoría SOLO LECTURA del coste de rotar claves de caché.

No imprime textos, handles, URLs ni respuestas. Nunca modifica archivos.
El informe diferencia claves heredadas de respuestas (sin metadatos
suficientes para migración segura) y duplicación potencial de pendientes.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib

import reply_queue as rq


def _read(path):
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError(f"estado de {path.name} no es un objeto")
    return data


def _recent(entry, now, hours):
    if not isinstance(entry, dict):
        return False
    try:
        seconds = (now - datetime.datetime.fromisoformat(entry.get("ts", ""))).total_seconds()
        return 0 <= seconds < hours * 3600
    except (ValueError, TypeError, OverflowError):
        return False


def audit(folder, *, now=None):
    folder = pathlib.Path(folder)
    now = now or datetime.datetime.now()
    answers = _read(folder / "answers.json")
    pending = _read(folder / "pending.json")
    old_answers = {k: v for k, v in answers.items()
                   if isinstance(k, str) and len(k) == 16
                   and all(ch in "0123456789abcdef" for ch in k.lower())}
    useful_old = sum(
        isinstance(v, dict) and bool(v.get("reply")) and rq._fresh(v, now)
        for v in old_answers.values()
    )
    pending_24h = {k: v for k, v in pending.items() if _recent(v, now, 24)}
    fresh_pending = {
        k: v for k, v in pending.items()
        if isinstance(v, dict) and rq._fresh(v, now)
    }
    new_keys = set()
    by_network = {}
    no_target = 0
    for entry in fresh_pending.values():
        value = str(entry.get("network") or "").casefold()
        network = value if value in {"bluesky", "mastodon", "threads", "x", "facebook", "pinterest", "reddit", "tiktok"} else "otras"
        by_network[network] = by_network.get(network, 0) + 1
        no_target += not bool(rq._remote_target(entry, network))
    for entry in fresh_pending.values():
        new_keys.add(rq.key_for(entry.get("network", ""), entry))
    return {
        "schema": 2,
        "legacy_answers_total": len(old_answers),
        "legacy_answers_fresh_useful_unmigratable": useful_old,
        "legacy_answers_24h_useful_unmigratable": sum(bool(v.get("reply")) and _recent(v, now, 24) for v in old_answers.values() if isinstance(v, dict)),
        "answers_total": len(answers),
        "pending_total": len(pending),
        "pending_fresh": len(fresh_pending),
        "pending_24h": len(pending_24h),
        "pending_24h_possible_duplicates": len(pending_24h) - len({rq.key_for(v.get("network", ""), v) for v in pending_24h.values()}),
        "pending_unique_after_rekey": len(new_keys),
        "pending_possible_duplicates": len(fresh_pending) - len(new_keys),
        "pending_capacity": rq.MAX_PENDING,
        "pending_without_remote_target": no_target,
        "pending_fresh_by_network": dict(sorted(by_network.items())),
        "cache_hit_rate_24h": None,
        "cache_hit_rate_note": "Los snapshots no registran hits ni misses. Tras desplegar, usar contadores agregados cache_hits/cache_misses por red (#117 C1).",
        "notes": "Claves sha1 legadas carecen de texto/autor original; NO migrarlas a ciegas. Solo métricas agregadas.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Auditar caché de respuestas sin modificarla")
    parser.add_argument("--dir", default=str(pathlib.Path(rq.DIR)))
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.dir), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
